from .marble_api import (
    DEFAULT_MAX_WAIT,
    DEFAULT_POLL_INTERVAL,
    MARBLE_MODELS,
    build_world_prompt,
    generate_world_from_prompt,
    upload_file_path,
)


class DustinMarbleUploadVideoNode:
    CATEGORY = "Dustin Nodes/Marble"
    FUNCTION = "upload_video"
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("media_asset_id",)

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "api_key": ("STRING", {"default": ""}),
                "video_path": ("STRING", {"default": ""}),
            }
        }

    def upload_video(self, api_key, video_path):
        media_asset_id = upload_file_path(api_key=api_key, file_path=video_path, kind="video")
        return (media_asset_id,)


class DustinMarbleGenerateVideoWorldNode:
    CATEGORY = "Dustin Nodes/Marble"
    FUNCTION = "generate_world"
    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("world_json", "world_id", "marble_url", "asset_urls_json")

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "api_key": ("STRING", {"default": ""}),
                "video_mode": (["video_url", "video_file"], {"default": "video_url"}),
                "text_prompt": ("STRING", {"multiline": True, "default": ""}),
                "model": (MARBLE_MODELS, {"default": "marble-1.1"}),
                "display_name": ("STRING", {"default": ""}),
                "seed": ("INT", {"default": -1, "min": -1, "max": 4294967295, "step": 1}),
                "disable_recaption": ("BOOLEAN", {"default": False}),
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
                "video_url": ("STRING", {"default": ""}),
                "media_asset_id": ("STRING", {"default": ""}),
                "video_path": ("STRING", {"default": ""}),
            },
        }

    def generate_world(
        self,
        api_key,
        video_mode,
        text_prompt,
        model,
        display_name,
        seed,
        disable_recaption,
        poll_interval_seconds,
        max_wait_seconds,
        video_url="",
        media_asset_id="",
        video_path="",
    ):
        asset_id = (media_asset_id or "").strip()
        if video_mode == "video_file" and not asset_id:
            asset_id = upload_file_path(api_key=api_key, file_path=video_path, kind="video")

        world_prompt = build_world_prompt(
            prompt_type=video_mode,
            text_prompt=text_prompt,
            image_url="",
            image=None,
            is_pano=False,
            disable_recaption=disable_recaption,
            multi_image_json="",
            multi_image_entries=None,
            reconstruct_images=False,
            video_url=video_url,
            video_media_asset_id=asset_id,
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
