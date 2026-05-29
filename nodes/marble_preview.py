import io
import os
import uuid

import requests
import torch

from .marble_api import MarbleApiError, raise_for_response, resolve_asset_url


def _download_image_tensor(url: str):
    try:
        import numpy as np
        from PIL import Image
    except ImportError as exc:
        raise MarbleApiError("Preview requires numpy and Pillow.") from exc

    response = requests.get(url, timeout=120)
    raise_for_response(response)
    pil_image = Image.open(io.BytesIO(response.content)).convert("RGB")
    array = np.array(pil_image).astype("float32") / 255.0
    tensor = torch.from_numpy(array)[None,]
    return tensor, pil_image


def _preview_ui(pil_image) -> dict:
    try:
        import folder_paths
    except ImportError:
        return {"images": []}

    filename = f"marble_preview_{uuid.uuid4().hex}.png"
    full_path = os.path.join(folder_paths.get_temp_directory(), filename)
    pil_image.save(full_path, format="PNG")
    return {"images": [{"filename": filename, "subfolder": "", "type": "temp"}]}


class DustinMarblePreviewThumbnailNode:
    CATEGORY = "Dustin Nodes/Marble"
    FUNCTION = "preview_thumbnail"
    OUTPUT_NODE = True
    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {},
            "optional": {
                "asset_urls_json": ("STRING", {"multiline": True, "default": ""}),
                "image_url": ("STRING", {"default": ""}),
            },
        }

    def preview_thumbnail(self, asset_urls_json="", image_url=""):
        url = resolve_asset_url(asset_urls_json, image_url, "thumbnail_url")
        tensor, pil_image = _download_image_tensor(url)
        return {"ui": _preview_ui(pil_image), "result": (tensor,)}


class DustinMarblePreviewPanoNode:
    CATEGORY = "Dustin Nodes/Marble"
    FUNCTION = "preview_pano"
    OUTPUT_NODE = True
    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {},
            "optional": {
                "asset_urls_json": ("STRING", {"multiline": True, "default": ""}),
                "image_url": ("STRING", {"default": ""}),
            },
        }

    def preview_pano(self, asset_urls_json="", image_url=""):
        url = resolve_asset_url(asset_urls_json, image_url, "pano_url")
        tensor, pil_image = _download_image_tensor(url)
        return {"ui": _preview_ui(pil_image), "result": (tensor,)}
