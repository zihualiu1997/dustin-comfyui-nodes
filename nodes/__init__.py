from .basic_text import DustinTextPrefixNode
from .image_atlas import DustinImageAtlasExtractNode, DustinImageAtlasNode

NODE_CLASS_MAPPINGS = {
    "DustinTextPrefix": DustinTextPrefixNode,
    "DustinImageAtlas": DustinImageAtlasNode,
    "DustinImageAtlasExtract": DustinImageAtlasExtractNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "DustinTextPrefix": "Dustin Text Prefix",
    "DustinImageAtlas": "Dustin Image Atlas",
    "DustinImageAtlasExtract": "Dustin Image Atlas Extract",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
