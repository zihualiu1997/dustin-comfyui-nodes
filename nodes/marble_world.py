import base64
import io
import json
import os
import time

import requests

API_BASE = "https://api.worldlabs.ai"
DEFAULT_POLL_INTERVAL = 15
DEFAULT_MAX_WAIT = 600

MARBLE_MODELS = [
    "marble-1.1",
    "marble-1.1-plus",
    "marble-1.0",
    "marble-1.0-draft",
]

PROMPT_TYPES = [
    "text",
    "image_url",
    "image_tensor",
]


class MarbleApiError(RuntimeError):
    pass


def _api_headers(api_key: str) -> dict[str, str]:
    key = (api_key or "").strip() or os.environ.get("WLT_API_KEY", "").strip()
    if not key:
        raise MarbleApiError(
            "Missing API key. Set the node api_key input or the WLT_API_KEY environment variable."
        )
    return {"WLT-Api-Key": key, "Content-Type": "application/json"}


def _raise_for_response(response: requests.Response) -> None:
    if response.ok:
        return
    try:
        detail = response.json()
    except ValueError:
        detail = response.text
    raise MarbleApiError(f"HTTP {response.status_code}: {detail}")


def _image_tensor_to_base64(image) -> tuple[str, str]:
    try:
        from PIL import Image
    except ImportError as exc:
        raise MarbleApiError(
            "ComfyUI image upload requires numpy and Pillow (usually bundled with ComfyUI)."
        ) from exc

    if not hasattr(image, "shape") or len(image.shape) != 4:
        raise MarbleApiError("Expected an IMAGE batch tensor with shape [batch, height, width, channels].")

    if int(image.shape[0]) < 1:
        raise MarbleApiError("Image batch is empty.")

    frame = image[0]
    array = (frame.detach().cpu().numpy() * 255.0).clip(0, 255).astype("uint8")
    pil_image = Image.fromarray(array, mode="RGB")
    buffer = io.BytesIO()
    pil_image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return encoded, "png"


def _build_world_prompt(
    prompt_type: str,
    text_prompt: str,
    image_url: str,
    image,
    is_pano: bool,
    disable_recaption: bool,
) -> dict:
    text = (text_prompt or "").strip()
    common = {}
    if disable_recaption:
        common["disable_recaption"] = True

    if prompt_type == "text":
        if not text:
            raise MarbleApiError("text_prompt is required when prompt_type is text.")
        return {"type": "text", "text_prompt": text, **common}

    if prompt_type == "image_url":
        url = (image_url or "").strip()
        if not url:
            raise MarbleApiError("image_url is required when prompt_type is image_url.")
        payload = {
            "type": "image",
            "image_prompt": {"source": "uri", "uri": url},
            **common,
        }
        if text:
            payload["text_prompt"] = text
        if is_pano:
            payload["is_pano"] = True
        return payload

    if prompt_type == "image_tensor":
        if image is None:
            raise MarbleApiError("image is required when prompt_type is image_tensor.")
        data_base64, extension = _image_tensor_to_base64(image)
        payload = {
            "type": "image",
            "image_prompt": {
                "source": "data_base64",
                "data_base64": data_base64,
                "extension": extension,
            },
            **common,
        }
        if text:
            payload["text_prompt"] = text
        if is_pano:
            payload["is_pano"] = True
        return payload

    raise MarbleApiError(f"Unsupported prompt_type: {prompt_type}")


def _start_generation(
    api_key: str,
    world_prompt: dict,
    display_name: str,
    model: str,
    seed: int,
) -> str:
    body: dict = {"world_prompt": world_prompt, "model": model}
    name = (display_name or "").strip()
    if name:
        body["display_name"] = name[:64]
    if seed >= 0:
        body["seed"] = int(seed)

    response = requests.post(
        f"{API_BASE}/marble/v1/worlds:generate",
        headers=_api_headers(api_key),
        json=body,
        timeout=120,
    )
    _raise_for_response(response)
    data = response.json()
    operation_id = data.get("operation_id")
    if not operation_id:
        raise MarbleApiError("Generate response did not include operation_id.")
    return operation_id


def _poll_operation(api_key: str, operation_id: str, poll_interval: int, max_wait: int) -> dict:
    deadline = time.monotonic() + max_wait
    headers = _api_headers(api_key)
    url = f"{API_BASE}/marble/v1/operations/{operation_id}"

    while True:
        response = requests.get(url, headers=headers, timeout=60)
        _raise_for_response(response)
        operation = response.json()

        if operation.get("done"):
            error = operation.get("error")
            if error:
                message = error.get("message") if isinstance(error, dict) else str(error)
                raise MarbleApiError(f"World generation failed: {message or error}")
            world = operation.get("response")
            if not isinstance(world, dict):
                raise MarbleApiError("Operation completed but response world payload is missing.")
            return world

        if time.monotonic() >= deadline:
            raise MarbleApiError(
                f"Timed out after {max_wait}s waiting for operation {operation_id}. "
                "Increase max_wait_seconds or poll the operation manually."
            )

        time.sleep(max(1, poll_interval))


def _normalize_world(world: dict) -> dict:
    world_id = world.get("world_id") or world.get("id")
    if world_id and "world_id" not in world:
        world = {**world, "world_id": world_id}
    return world


def _extract_outputs(world: dict) -> tuple[str, str, str, str]:
    world = _normalize_world(world)
    world_id = str(world.get("world_id", ""))
    marble_url = str(world.get("world_marble_url", ""))

    assets = world.get("assets") if isinstance(world.get("assets"), dict) else {}
    splats = assets.get("splats") if isinstance(assets.get("splats"), dict) else {}
    spz_urls = splats.get("spz_urls") if isinstance(splats.get("spz_urls"), dict) else {}
    mesh = assets.get("mesh") if isinstance(assets.get("mesh"), dict) else {}
    imagery = assets.get("imagery") if isinstance(assets.get("imagery"), dict) else {}

    asset_urls = {
        "thumbnail_url": assets.get("thumbnail_url"),
        "caption": assets.get("caption"),
        "pano_url": imagery.get("pano_url"),
        "collider_mesh_url": mesh.get("collider_mesh_url"),
        "spz_100k": spz_urls.get("100k"),
        "spz_500k": spz_urls.get("500k"),
        "spz_full_res": spz_urls.get("full_res"),
    }

    return (
        json.dumps(world, ensure_ascii=True),
        world_id,
        marble_url,
        json.dumps(asset_urls, ensure_ascii=True),
    )


class DustinMarbleGenerateWorldNode:
    CATEGORY = "Dustin Nodes/Marble"
    FUNCTION = "generate_world"
    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("world_json", "world_id", "marble_url", "asset_urls_json")

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "api_key": ("STRING", {"default": ""}),
                "prompt_type": (PROMPT_TYPES, {"default": "text"}),
                "text_prompt": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "A mystical forest with glowing mushrooms",
                    },
                ),
                "model": (MARBLE_MODELS, {"default": "marble-1.1"}),
                "display_name": ("STRING", {"default": ""}),
                "seed": ("INT", {"default": -1, "min": -1, "max": 4294967295, "step": 1}),
                "is_pano": ("BOOLEAN", {"default": False}),
                "disable_recaption": ("BOOLEAN", {"default": False}),
                "poll_interval_seconds": (
                    "INT",
                    {"default": DEFAULT_POLL_INTERVAL, "min": 5, "max": 120, "step": 1},
                ),
                "max_wait_seconds": (
                    "INT",
                    {"default": DEFAULT_MAX_WAIT, "min": 60, "max": 3600, "step": 30},
                ),
            },
            "optional": {
                "image_url": ("STRING", {"default": ""}),
                "image": ("IMAGE",),
            },
        }

    def generate_world(
        self,
        api_key,
        prompt_type,
        text_prompt,
        model,
        display_name,
        seed,
        is_pano,
        disable_recaption,
        poll_interval_seconds,
        max_wait_seconds,
        image_url="",
        image=None,
    ):
        world_prompt = _build_world_prompt(
            prompt_type=prompt_type,
            text_prompt=text_prompt,
            image_url=image_url,
            image=image,
            is_pano=is_pano,
            disable_recaption=disable_recaption,
        )
        operation_id = _start_generation(
            api_key=api_key,
            world_prompt=world_prompt,
            display_name=display_name,
            model=model,
            seed=seed,
        )
        world = _poll_operation(
            api_key=api_key,
            operation_id=operation_id,
            poll_interval=int(poll_interval_seconds),
            max_wait=int(max_wait_seconds),
        )
        return _extract_outputs(world)
