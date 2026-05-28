from .basic_text import DustinTextPrefixNode
from .image_atlas import DustinImageAtlasExtractNode, DustinImageAtlasNode
from .marble_multi_image import (
    DustinMarbleBuildMultiImagePromptNode,
    DustinMarbleGenerateMultiImageWorldNode,
)
from .marble_preview import DustinMarblePreviewPanoNode, DustinMarblePreviewThumbnailNode
from .marble_video import DustinMarbleGenerateVideoWorldNode, DustinMarbleUploadVideoNode
from .marble_world import DustinMarbleGenerateWorldNode

NODE_CLASS_MAPPINGS = {
    "DustinTextPrefix": DustinTextPrefixNode,
    "DustinImageAtlas": DustinImageAtlasNode,
    "DustinImageAtlasExtract": DustinImageAtlasExtractNode,
    "DustinMarbleGenerateWorld": DustinMarbleGenerateWorldNode,
    "DustinMarbleBuildMultiImagePrompt": DustinMarbleBuildMultiImagePromptNode,
    "DustinMarbleGenerateMultiImageWorld": DustinMarbleGenerateMultiImageWorldNode,
    "DustinMarbleUploadVideo": DustinMarbleUploadVideoNode,
    "DustinMarbleGenerateVideoWorld": DustinMarbleGenerateVideoWorldNode,
    "DustinMarblePreviewThumbnail": DustinMarblePreviewThumbnailNode,
    "DustinMarblePreviewPano": DustinMarblePreviewPanoNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "DustinTextPrefix": "Dustin Text Prefix",
    "DustinImageAtlas": "Dustin Image Atlas",
    "DustinImageAtlasExtract": "Dustin Image Atlas Extract",
    "DustinMarbleGenerateWorld": "Dustin Marble Generate World",
    "DustinMarbleBuildMultiImagePrompt": "Dustin Marble Build Multi-Image Prompt",
    "DustinMarbleGenerateMultiImageWorld": "Dustin Marble Generate Multi-Image World",
    "DustinMarbleUploadVideo": "Dustin Marble Upload Video",
    "DustinMarbleGenerateVideoWorld": "Dustin Marble Generate Video World",
    "DustinMarblePreviewThumbnail": "Dustin Marble Preview Thumbnail",
    "DustinMarblePreviewPano": "Dustin Marble Preview Panorama",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
