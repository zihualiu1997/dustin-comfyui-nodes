import json


def _validate_image_batch(images):
    if not hasattr(images, "shape"):
        raise ValueError("Expected an IMAGE batch tensor.")

    if len(images.shape) != 4:
        raise ValueError("Expected images with shape [batch, height, width, channels].")

    batch_size = int(images.shape[0])
    if batch_size <= 0:
        raise ValueError("Image batch is empty.")

    return batch_size


def _build_layout(images, max_width, max_height, padding):
    batch_size = _validate_image_batch(images)
    placements = []
    current_x = 0
    current_y = 0
    row_height = 0
    atlas_width = 0
    atlas_height = 0

    for index in range(batch_size):
        image = images[index]
        height = int(image.shape[0])
        width = int(image.shape[1])

        if height != width:
            raise ValueError(f"Image at batch index {index} is not square: {width}x{height}.")

        if width > max_width or height > max_height:
            raise ValueError(
                f"Image at batch index {index} is larger than the atlas limit: "
                f"{width}x{height} vs {max_width}x{max_height}."
            )

        needs_wrap = current_x > 0 and (current_x + width) > max_width
        if needs_wrap:
            current_y += row_height + padding
            current_x = 0
            row_height = 0

        if current_y + height > max_height:
            raise ValueError(
                f"Images do not fit inside the atlas limit {max_width}x{max_height}. "
                f"Stopped while placing batch index {index}."
            )

        placements.append(
            {
                "index": index,
                "x": current_x,
                "y": current_y,
                "width": width,
                "height": height,
            }
        )

        atlas_width = max(atlas_width, current_x + width)
        atlas_height = max(atlas_height, current_y + height)
        current_x += width + padding
        row_height = max(row_height, height)

    return placements, atlas_width, atlas_height


class DustinImageAtlasNode:
    CATEGORY = "Dustin Nodes/Image"
    FUNCTION = "build_atlas"
    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("atlas_image", "atlas_metadata")

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE",),
                "max_width": ("INT", {"default": 1024, "min": 1, "max": 16384, "step": 1}),
                "max_height": ("INT", {"default": 1024, "min": 1, "max": 16384, "step": 1}),
                "padding": ("INT", {"default": 0, "min": 0, "max": 512, "step": 1}),
            }
        }

    def build_atlas(self, images, max_width, max_height, padding):
        placements, atlas_width, atlas_height = _build_layout(images, max_width, max_height, padding)
        channels = int(images.shape[3])
        atlas = images.new_zeros((1, atlas_height, atlas_width, channels))

        for item in placements:
            index = item["index"]
            x = item["x"]
            y = item["y"]
            width = item["width"]
            height = item["height"]
            atlas[0, y : y + height, x : x + width, :] = images[index, :height, :width, :]

        metadata = {
            "atlas_width": atlas_width,
            "atlas_height": atlas_height,
            "max_width": int(max_width),
            "max_height": int(max_height),
            "padding": int(padding),
            "image_count": len(placements),
            "items": placements,
        }
        return (atlas, json.dumps(metadata, ensure_ascii=True))


class DustinImageAtlasExtractNode:
    CATEGORY = "Dustin Nodes/Image"
    FUNCTION = "extract_image"
    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "atlas_image": ("IMAGE",),
                "atlas_metadata": ("STRING", {"multiline": True, "default": ""}),
                "index": ("INT", {"default": 0, "min": 0, "max": 1000000, "step": 1}),
            }
        }

    def extract_image(self, atlas_image, atlas_metadata, index):
        _validate_image_batch(atlas_image)

        if int(atlas_image.shape[0]) != 1:
            raise ValueError("Atlas extractor expects a single atlas image, not an image batch.")

        try:
            metadata = json.loads(atlas_metadata)
        except json.JSONDecodeError as exc:
            raise ValueError("Atlas metadata is not valid JSON.") from exc

        items = metadata.get("items")
        if not isinstance(items, list):
            raise ValueError("Atlas metadata is missing the 'items' list.")

        target = None
        for item in items:
            if int(item.get("index", -1)) == int(index):
                target = item
                break

        if target is None:
            raise ValueError(f"Could not find atlas item with index {index}.")

        x = int(target["x"])
        y = int(target["y"])
        width = int(target["width"])
        height = int(target["height"])
        return (atlas_image[:, y : y + height, x : x + width, :],)
