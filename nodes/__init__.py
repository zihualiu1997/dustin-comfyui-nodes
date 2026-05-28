from .basic_text import DustinTextPrefixNode
from .image_atlas import DustinImageAtlasExtractNode, DustinImageAtlasNode
from .marble_world import DustinMarbleGenerateWorldNode

NODE_CLASS_MAPPINGS = {
    "DustinTextPrefix": DustinTextPrefixNode,
    "DustinImageAtlas": DustinImageAtlasNode,
    "DustinImageAtlasExtract": DustinImageAtlasExtractNode,
    "DustinMarbleGenerateWorld": DustinMarbleGenerateWorldNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "DustinTextPrefix": "Dustin Text Prefix",
    "DustinImageAtlas": "Dustin Image Atlas",
    "DustinImageAtlasExtract": "Dustin Image Atlas Extract",
    "DustinMarbleGenerateWorld": "Dustin Marble Generate World",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
