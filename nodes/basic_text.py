class DustinTextPrefixNode:
    CATEGORY = "Dustin Nodes/Text"
    FUNCTION = "build_text"
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("text",)

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text": ("STRING", {"multiline": True, "default": ""}),
                "prefix": ("STRING", {"multiline": False, "default": ""}),
                "separator": ("STRING", {"multiline": False, "default": " "}),
            }
        }

    def build_text(self, text, prefix, separator):
        if not prefix:
            return (text,)

        return (f"{prefix}{separator}{text}",)
