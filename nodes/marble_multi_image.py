import json

from .marble_api import (
    DEFAULT_MAX_WAIT,
    DEFAULT_POLL_INTERVAL,
    MARBLE_MODELS,
    build_multi_image_prompt,
    build_world_prompt,
    generate_world_from_prompt,
)


class DustinMarbleBuildMultiImagePromptNode:
    CATEGORY = "Dustin Nodes/Marble"
    FUNCTION = "build_prompt"
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("multi_image_json",)

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "api_key": ("STRING", {"default": ""}),
                "images": ("IMAGE",),
                "azimuths": (
                    "STRING",
                    {
                        "default": "0,180",
                        "multiline": False,
                    },
                ),
                "upload_mode": (["media_asset", "data_base64"], {"default": "media_asset"}),
            }
        }

    def build_prompt(self, api_key, images, azimuths, upload_mode):
        entries = build_multi_image_prompt(
            api_key=api_key,
            images=images,
            azimuths=azimuths,
            upload_mode=upload_mode,
        )
        return (json.dumps(entries, ensure_ascii=True),)


class DustinMarbleGenerateMultiImageWorldNode:
    CATEGORY = "Dustin Nodes/Marble"
    FUNCTION = "generate_world"
    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("world_json", "world_id", "marble_url", "asset_urls_json")

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "api_key": ("STRING", {"default": ""}),
                "images": ("IMAGE",),
                "azimuths": ("STRING", {"default": "0,180"}),
                "upload_mode": (["media_asset", "data_base64"], {"default": "media_asset"}),
                "text_prompt": ("STRING", {"multiline": True, "default": ""}),
                "model": (MARBLE_MODELS, {"default": "marble-1.1"}),
                "display_name": ("STRING", {"default": ""}),
                "seed": ("INT", {"default": -1, "min": -1, "max": 4294967295, "step": 1}),
                "reconstruct_images": ("BOOLEAN", {"default": False}),
                "disable_recaption": ("BOOLEAN", {"default": False}),
                "poll_interval_seconds": (
                    "INT",
                    {"default": DEFAULT_POLL_INTERVAL, "min": 5, "max": 120, "step": 1},
                ),
                "max_wait_seconds": (
                    "INT",
                    {"default": DEFAULT_MAX_WAIT, "min": 60, "max": 3600, "step": 30},
                ),
            }
        }

    def generate_world(
        self,
        api_key,
        images,
        azimuths,
        upload_mode,
        text_prompt,
        model,
        display_name,
        seed,
        reconstruct_images,
        disable_recaption,
        poll_interval_seconds,
        max_wait_seconds,
    ):
        entries = build_multi_image_prompt(
            api_key=api_key,
            images=images,
            azimuths=azimuths,
            upload_mode=upload_mode,
        )
        world_prompt = build_world_prompt(
            prompt_type="multi_image_json",
            text_prompt=text_prompt,
            image_url="",
            image=None,
            is_pano=False,
            disable_recaption=disable_recaption,
            multi_image_json="",
            multi_image_entries=entries,
            reconstruct_images=reconstruct_images,
            video_url="",
            video_media_asset_id="",
        )
        return generate_world_from_prompt(
            api_key=api_key,
            world_prompt=world_prompt,
            display_name=display_name,
            model=model,
            seed=seed,
            poll_interval_seconds=poll_interval_seconds,
            max_wait_seconds=max_wait_seconds,
        )
