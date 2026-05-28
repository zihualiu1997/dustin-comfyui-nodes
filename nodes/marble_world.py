from .marble_api import (
    DEFAULT_MAX_WAIT,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_TEXT_PROMPT,
    MARBLE_MODELS,
    PROMPT_TYPES,
    build_world_prompt,
    generate_world_from_prompt,
    resolve_prompt_type,
    upload_file_path,
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
                        "default": DEFAULT_TEXT_PROMPT,
                    },
                ),
                "model": (MARBLE_MODELS, {"default": "marble-1.1"}),
                "display_name": ("STRING", {"default": ""}),
                "seed": ("INT", {"default": -1, "min": -1, "max": 4294967295, "step": 1}),
                "is_pano": ("BOOLEAN", {"default": False}),
                "disable_recaption": ("BOOLEAN", {"default": False}),
                "reconstruct_images": ("BOOLEAN", {"default": False}),
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
                "multi_image_json": ("STRING", {"multiline": True, "default": ""}),
                "video_url": ("STRING", {"default": ""}),
                "video_path": ("STRING", {"default": ""}),
                "media_asset_id": ("STRING", {"default": ""}),
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
        reconstruct_images,
        poll_interval_seconds,
        max_wait_seconds,
        image_url="",
        image=None,
        multi_image_json="",
        video_url="",
        video_path="",
        media_asset_id="",
    ):
        prompt_type, text_prompt = resolve_prompt_type(
            prompt_type=prompt_type,
            text_prompt=text_prompt,
            image_url=image_url,
            image=image,
            multi_image_json=multi_image_json,
            video_url=video_url,
            video_path=video_path,
            media_asset_id=media_asset_id,
        )

        video_asset_id = (media_asset_id or "").strip()
        if prompt_type == "video_file" and not video_asset_id:
            video_asset_id = upload_file_path(api_key=api_key, file_path=video_path, kind="video")

        world_prompt = build_world_prompt(
            prompt_type=prompt_type,
            text_prompt=text_prompt,
            image_url=image_url,
            image=image,
            is_pano=is_pano,
            disable_recaption=disable_recaption,
            multi_image_json=multi_image_json,
            multi_image_entries=None,
            reconstruct_images=reconstruct_images,
            video_url=video_url,
            video_media_asset_id=video_asset_id,
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
