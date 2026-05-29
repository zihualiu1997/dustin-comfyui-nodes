import base64
import io
import json
import os
import time
from pathlib import Path

import requests

API_BASE = "https://api.worldlabs.ai"
DEFAULT_POLL_INTERVAL = 15
DEFAULT_MAX_WAIT = 600
DEFAULT_REQUEST_RETRIES = 5
_RETRY_BACKOFF_SECONDS = 2.0

_TRANSIENT_REQUEST_ERRORS = (
    requests.exceptions.ConnectionError,
    requests.exceptions.Timeout,
    requests.exceptions.ChunkedEncodingError,
)

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
    "multi_image_json",
    "video_url",
    "video_file",
]

DEFAULT_TEXT_PROMPT = "A mystical forest with glowing mushrooms"


class MarbleApiError(RuntimeError):
    pass


def api_headers(api_key: str) -> dict[str, str]:
    key = (api_key or "").strip() or os.environ.get("WLT_API_KEY", "").strip()
    if not key:
        raise MarbleApiError(
            "Missing API key. Set the node api_key input or the WLT_API_KEY environment variable."
        )
    return {"WLT-Api-Key": key, "Content-Type": "application/json"}


def raise_for_response(response: requests.Response) -> None:
    if response.ok:
        return
    try:
        detail = response.json()
    except ValueError:
        detail = response.text
    raise MarbleApiError(f"HTTP {response.status_code}: {detail}")


def request_with_retry(
    method: str,
    url: str,
    *,
    retries: int = DEFAULT_REQUEST_RETRIES,
    backoff_seconds: float = _RETRY_BACKOFF_SECONDS,
    **kwargs,
) -> requests.Response:
    """Retry transient network failures (connection reset, timeouts, etc.)."""
    last_exc: Exception | None = None
    attempts = max(1, int(retries))

    for attempt in range(attempts):
        try:
            return requests.request(method, url, **kwargs)
        except _TRANSIENT_REQUEST_ERRORS as exc:
            last_exc = exc
            if attempt + 1 >= attempts:
                break
            time.sleep(backoff_seconds * (attempt + 1))

    raise MarbleApiError(
        f"Network error talking to Marble API after {attempts} attempts: {last_exc}. "
        "Check internet/VPN/proxy or retry later. "
        "If generation was already submitted, check status on the World Labs platform."
    ) from last_exc


def image_tensor_to_bytes(image, index: int = 0) -> tuple[bytes, str]:
    try:
        from PIL import Image
    except ImportError as exc:
        raise MarbleApiError(
            "ComfyUI image handling requires Pillow (usually bundled with ComfyUI)."
        ) from exc

    if not hasattr(image, "shape") or len(image.shape) != 4:
        raise MarbleApiError("Expected an IMAGE batch tensor with shape [batch, height, width, channels].")

    batch_size = int(image.shape[0])
    if batch_size <= 0:
        raise MarbleApiError("Image batch is empty.")
    if index < 0 or index >= batch_size:
        raise MarbleApiError(f"Image batch index {index} is out of range (batch size {batch_size}).")

    frame = image[index]
    array = (frame.detach().cpu().numpy() * 255.0).clip(0, 255).astype("uint8")
    pil_image = Image.fromarray(array, mode="RGB")
    buffer = io.BytesIO()
    pil_image.save(buffer, format="PNG")
    return buffer.getvalue(), "png"


def image_tensor_to_base64(image, index: int = 0) -> tuple[str, str]:
    raw, extension = image_tensor_to_bytes(image, index=index)
    return base64.b64encode(raw).decode("ascii"), extension


def parse_azimuths(azimuths: str, expected_count: int) -> list[float]:
    parts = [part.strip() for part in (azimuths or "").split(",") if part.strip()]
    if len(parts) != expected_count:
        raise MarbleApiError(
            f"Expected {expected_count} azimuth values but got {len(parts)}. "
            "Use a comma-separated list like 0,90,180,270."
        )
    values = []
    for part in parts:
        try:
            values.append(float(part))
        except ValueError as exc:
            raise MarbleApiError(f"Invalid azimuth value: {part}") from exc
    return values


def upload_media_asset(
    api_key: str,
    file_bytes: bytes,
    file_name: str,
    kind: str,
    extension: str,
) -> str:
    response = request_with_retry(
        "POST",
        f"{API_BASE}/marble/v1/media-assets:prepare_upload",
        headers=api_headers(api_key),
        json={
            "file_name": file_name,
            "kind": kind,
            "extension": extension.lstrip("."),
        },
        timeout=120,
    )
    raise_for_response(response)
    payload = response.json()
    media_asset = payload.get("media_asset") or {}
    upload_info = payload.get("upload_info") or {}
    media_asset_id = media_asset.get("id")
    upload_url = upload_info.get("upload_url")
    if not media_asset_id or not upload_url:
        raise MarbleApiError("prepare_upload response is missing media_asset.id or upload_url.")

    upload_headers = dict(upload_info.get("required_headers") or {})
    upload_method = (upload_info.get("upload_method") or "PUT").upper()
    upload_response = request_with_retry(
        upload_method,
        upload_url,
        headers=upload_headers,
        data=file_bytes,
        timeout=300,
    )
    raise_for_response(upload_response)
    return str(media_asset_id)


def upload_file_path(api_key: str, file_path: str, kind: str) -> str:
    path = Path(file_path.strip().strip('"'))
    if not path.is_file():
        raise MarbleApiError(f"File not found: {path}")
    extension = path.suffix.lstrip(".").lower()
    if not extension:
        raise MarbleApiError(f"Could not determine file extension for: {path}")
    return upload_media_asset(
        api_key=api_key,
        file_bytes=path.read_bytes(),
        file_name=path.name,
        kind=kind,
        extension=extension,
    )


def build_multi_image_prompt(
    api_key: str,
    images,
    azimuths: str,
    upload_mode: str,
) -> list[dict]:
    if images is None:
        raise MarbleApiError("images batch is required for multi-image generation.")

    batch_size = int(images.shape[0])
    azimuth_values = parse_azimuths(azimuths, batch_size)
    entries = []

    for index, azimuth in enumerate(azimuth_values):
        if upload_mode == "media_asset":
            raw, extension = image_tensor_to_bytes(images, index=index)
            media_asset_id = upload_media_asset(
                api_key=api_key,
                file_bytes=raw,
                file_name=f"frame_{index}.{extension}",
                kind="image",
                extension=extension,
            )
            content = {"source": "media_asset", "media_asset_id": media_asset_id}
        elif upload_mode == "data_base64":
            data_base64, extension = image_tensor_to_base64(images, index=index)
            content = {
                "source": "data_base64",
                "data_base64": data_base64,
                "extension": extension,
            }
        else:
            raise MarbleApiError(f"Unsupported upload_mode: {upload_mode}")

        entries.append({"azimuth": azimuth, "content": content})

    return entries


def resolve_prompt_type(
    prompt_type: str,
    text_prompt: str,
    image_url: str,
    image,
    multi_image_json: str,
    video_url: str,
    video_path: str,
    media_asset_id: str,
) -> tuple[str, str]:
    """Pick a concrete prompt_type when the widget is still on text but inputs say otherwise."""
    text = (text_prompt or "").strip()
    if prompt_type != "text" or text:
        return prompt_type, text

    if image is not None:
        return "image_tensor", text
    if (image_url or "").strip():
        return "image_url", text
    if (multi_image_json or "").strip():
        return "multi_image_json", text
    if (video_url or "").strip():
        return "video_url", text
    if (video_path or "").strip() or (media_asset_id or "").strip():
        return "video_file", text

    return "text", DEFAULT_TEXT_PROMPT


def build_world_prompt(
    prompt_type: str,
    text_prompt: str,
    image_url: str,
    image,
    is_pano: bool,
    disable_recaption: bool,
    multi_image_json: str,
    multi_image_entries: list[dict] | None,
    reconstruct_images: bool,
    video_url: str,
    video_media_asset_id: str,
) -> dict:
    text = (text_prompt or "").strip()
    common: dict = {}
    if disable_recaption:
        common["disable_recaption"] = True

    if prompt_type == "text":
        if not text:
            raise MarbleApiError(
                "text_prompt is empty. Enter a prompt, connect an image/video input "
                "(prompt_type will auto-switch), or change prompt_type explicitly."
            )
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
        data_base64, extension = image_tensor_to_base64(image)
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

    if prompt_type == "multi_image_json":
        if multi_image_entries is not None:
            entries = multi_image_entries
        else:
            raw = (multi_image_json or "").strip()
            if not raw:
                raise MarbleApiError(
                    "multi_image_json is required when prompt_type is multi_image_json."
                )
            try:
                entries = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise MarbleApiError("multi_image_json is not valid JSON.") from exc
        if not isinstance(entries, list) or not entries:
            raise MarbleApiError("multi_image_json must be a non-empty JSON array.")
        payload = {
            "type": "multi-image",
            "multi_image_prompt": entries,
            **common,
        }
        if text:
            payload["text_prompt"] = text
        if reconstruct_images:
            payload["reconstruct_images"] = True
        return payload

    if prompt_type == "video_url":
        url = (video_url or "").strip()
        if not url:
            raise MarbleApiError("video_url is required when prompt_type is video_url.")
        payload = {
            "type": "video",
            "video_prompt": {"source": "uri", "uri": url},
            **common,
        }
        if text:
            payload["text_prompt"] = text
        return payload

    if prompt_type == "video_file":
        asset_id = (video_media_asset_id or "").strip()
        if not asset_id:
            raise MarbleApiError(
                "video_media_asset_id is required when prompt_type is video_file. "
                "Connect Dustin Marble Upload Video or set the ID manually."
            )
        payload = {
            "type": "video",
            "video_prompt": {"source": "media_asset", "media_asset_id": asset_id},
            **common,
        }
        if text:
            payload["text_prompt"] = text
        return payload

    raise MarbleApiError(f"Unsupported prompt_type: {prompt_type}")


def start_generation(
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

    response = request_with_retry(
        "POST",
        f"{API_BASE}/marble/v1/worlds:generate",
        headers=api_headers(api_key),
        json=body,
        timeout=180,
    )
    raise_for_response(response)
    data = response.json()
    operation_id = data.get("operation_id")
    if not operation_id:
        raise MarbleApiError("Generate response did not include operation_id.")
    return operation_id


def poll_operation(api_key: str, operation_id: str, poll_interval: int, max_wait: int) -> dict:
    deadline = time.monotonic() + max_wait
    headers = api_headers(api_key)
    url = f"{API_BASE}/marble/v1/operations/{operation_id}"
    last_metadata: dict | None = None

    while True:
        response = request_with_retry("GET", url, headers=headers, timeout=90)
        raise_for_response(response)
        operation = response.json()
        metadata = operation.get("metadata")
        if isinstance(metadata, dict):
            last_metadata = metadata

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
            world_id = (last_metadata or {}).get("world_id", "")
            extra = f" Last known world_id: {world_id}." if world_id else ""
            raise MarbleApiError(
                f"Timed out after {max_wait}s waiting for operation {operation_id}.{extra} "
                "Increase max_wait_seconds or check the job on the World Labs platform."
            )

        time.sleep(max(1, poll_interval))


def normalize_world(world: dict) -> dict:
    world_id = world.get("world_id") or world.get("id")
    if world_id and "world_id" not in world:
        world = {**world, "world_id": world_id}
    return world


_PANO_URL_CANDIDATE_KEYS = ("pano_url", "rgb_pano_url", "pano_rgb_url", "equirectangular_url")


def _is_http_url(value) -> bool:
    return isinstance(value, str) and value.strip().lower().startswith(("http://", "https://"))


def _first_url(mapping: dict | None, *keys: str) -> str | None:
    if not isinstance(mapping, dict):
        return None
    for key in keys:
        value = mapping.get(key)
        if _is_http_url(value):
            return str(value).strip()
    return None


def find_pano_url(data: dict) -> str | None:
    """Resolve panorama URL from flat asset_urls_json or nested world_json."""
    if not isinstance(data, dict):
        return None

    url = _first_url(data, *_PANO_URL_CANDIDATE_KEYS)
    if url:
        return url

    assets = data.get("assets")
    if not isinstance(assets, dict):
        return None

    imagery = assets.get("imagery")
    url = _first_url(imagery if isinstance(imagery, dict) else None, *_PANO_URL_CANDIDATE_KEYS)
    if url:
        return url

    return _first_url(assets, *_PANO_URL_CANDIDATE_KEYS)


def find_thumbnail_url(data: dict) -> str | None:
    if not isinstance(data, dict):
        return None

    url = _first_url(data, "thumbnail_url")
    if url:
        return url

    assets = data.get("assets")
    if isinstance(assets, dict):
        return _first_url(assets, "thumbnail_url")
    return None


def parse_json_object(raw: str, *, label: str = "JSON") -> dict:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise MarbleApiError(f"{label} is not valid JSON.") from exc

    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError as exc:
            raise MarbleApiError(f"{label} is not valid JSON.") from exc

    if not isinstance(data, dict):
        raise MarbleApiError(f"{label} must be a JSON object.")
    return data


def resolve_asset_url(asset_urls_json: str, image_url: str, key: str) -> str:
    direct = (image_url or "").strip()
    if direct:
        return direct

    raw = (asset_urls_json or "").strip()
    if not raw:
        raise MarbleApiError(
            f"Provide image_url or asset_urls_json / world_json containing '{key}'."
        )

    data = parse_json_object(raw, label="asset_urls_json")

    if key == "pano_url":
        url = find_pano_url(data)
    elif key == "thumbnail_url":
        url = find_thumbnail_url(data)
    else:
        url = _first_url(data, key)
        if not url and isinstance(data.get("assets"), dict):
            url = _first_url(data["assets"], key)

    if not url:
        hint = ""
        if key == "pano_url" and isinstance(data.get("assets"), dict):
            hint = " Connect asset_urls_json from Generate World, or pass full world_json."
        raise MarbleApiError(f"asset_urls_json does not contain '{key}'.{hint}")
    return url


def extract_asset_urls(world: dict) -> dict:
    assets = world.get("assets") if isinstance(world.get("assets"), dict) else {}
    splats = assets.get("splats") if isinstance(assets.get("splats"), dict) else {}
    spz_urls = splats.get("spz_urls") if isinstance(splats.get("spz_urls"), dict) else {}
    mesh = assets.get("mesh") if isinstance(assets.get("mesh"), dict) else {}
    return {
        "thumbnail_url": find_thumbnail_url(world),
        "caption": assets.get("caption"),
        "pano_url": find_pano_url(world),
        "collider_mesh_url": mesh.get("collider_mesh_url"),
        "spz_100k": spz_urls.get("100k"),
        "spz_500k": spz_urls.get("500k"),
        "spz_full_res": spz_urls.get("full_res"),
    }


def extract_outputs(world: dict) -> tuple[str, str, str, str]:
    world = normalize_world(world)
    world_id = str(world.get("world_id", ""))
    marble_url = str(world.get("world_marble_url", ""))
    asset_urls = extract_asset_urls(world)
    return (
        json.dumps(world, ensure_ascii=True),
        world_id,
        marble_url,
        json.dumps(asset_urls, ensure_ascii=True),
    )


def generate_world_from_prompt(
    api_key: str,
    world_prompt: dict,
    display_name: str,
    model: str,
    seed: int,
    poll_interval_seconds: int,
    max_wait_seconds: int,
) -> tuple[str, str, str, str]:
    operation_id = start_generation(
        api_key=api_key,
        world_prompt=world_prompt,
        display_name=display_name,
        model=model,
        seed=seed,
    )
    world = poll_operation(
        api_key=api_key,
        operation_id=operation_id,
        poll_interval=int(poll_interval_seconds),
        max_wait=int(max_wait_seconds),
    )
    return extract_outputs(world)
