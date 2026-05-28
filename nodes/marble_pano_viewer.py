import os
import uuid

import torch

from .marble_api import MarbleApiError
from .marble_preview import _download_image_tensor, _resolve_url


def _tensor_from_pil(pil_image):
    import numpy as np

    array = np.array(pil_image).astype("float32") / 255.0
    return torch.from_numpy(array)[None,]


def _pil_from_tensor(image):
    try:
        from PIL import Image
    except ImportError as exc:
        raise MarbleApiError("IMAGE input requires Pillow.") from exc

    if image is None:
        raise MarbleApiError("image tensor is required when no URL input is provided.")

    if not hasattr(image, "shape") or len(image.shape) != 4:
        raise MarbleApiError("Expected an IMAGE batch tensor with shape [batch, height, width, channels].")

    if int(image.shape[0]) < 1:
        raise MarbleApiError("Image batch is empty.")

    frame = image[0]
    array = (frame.detach().cpu().numpy() * 255.0).clip(0, 255).astype("uint8")
    return Image.fromarray(array, mode="RGB")


def _resize_for_preview(pil_image, max_preview_width: int):
    width, height = pil_image.size
    if max_preview_width > 0 and width > max_preview_width:
        scale = max_preview_width / float(width)
        new_size = (max_preview_width, max(1, int(height * scale)))
        pil_image = pil_image.resize(new_size)
    return pil_image


def _load_panorama_image(asset_urls_json: str, image_url: str, image, max_preview_width: int):
    if image is not None:
        pil_image = _pil_from_tensor(image)
    else:
        url = _resolve_url(asset_urls_json, image_url, "pano_url")
        _, pil_image = _download_image_tensor(url)

    pil_image = _resize_for_preview(pil_image, int(max_preview_width))
    width, height = pil_image.size
    if width < 2 or height < 1:
        raise MarbleApiError(f"Invalid panorama dimensions: {width}x{height}")

    aspect = width / float(height)
    if aspect < 1.5 or aspect > 2.5:
        # Equirectangular panos are typically 2:1; warn in metadata only.
        pass

    return pil_image


def _pano_viewer_ui(pil_image) -> dict:
    """Temp file reference for the iframe viewer (not ComfyUI's flat image preview)."""
    try:
        import folder_paths
    except ImportError:
        return {"dustin_pano_360": []}

    filename = f"marble_pano360_{uuid.uuid4().hex}.png"
    full_path = os.path.join(folder_paths.get_temp_directory(), filename)
    pil_image.save(full_path, format="PNG")
    return {"dustin_pano_360": [{"filename": filename, "subfolder": "", "type": "temp"}]}


class DustinMarblePano360ViewerNode:
    CATEGORY = "Dustin Nodes/Marble"
    FUNCTION = "view_pano"
    OUTPUT_NODE = False
    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "max_preview_width": (
                    "INT",
                    {"default": 4096, "min": 512, "max": 16384, "step": 256},
                ),
            },
            "optional": {
                "asset_urls_json": ("STRING", {"multiline": True, "default": ""}),
                "image_url": ("STRING", {"default": ""}),
                "image": ("IMAGE",),
            },
        }

    def view_pano(
        self,
        max_preview_width,
        asset_urls_json="",
        image_url="",
        image=None,
    ):
        has_url = bool((image_url or "").strip()) or bool((asset_urls_json or "").strip())
        if image is None and not has_url:
            raise MarbleApiError(
                "Provide at least one input: asset_urls_json, image_url, or image."
            )

        pil_image = _load_panorama_image(
            asset_urls_json=asset_urls_json,
            image_url=image_url,
            image=image,
            max_preview_width=max_preview_width,
        )
        tensor = _tensor_from_pil(pil_image)
        return {"ui": _pano_viewer_ui(pil_image), "result": (tensor,)}
