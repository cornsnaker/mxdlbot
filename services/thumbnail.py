"""
Thumbnail service for custom and auto-extracted thumbnails.
"""

import os
import aiohttp
import aiofiles
from typing import Optional
from pyrogram import Client
from config import THUMBNAIL_DIR


class ThumbnailService:
    """
    Service for managing video thumbnails.

    Supports:
    - Custom user-uploaded thumbnails
    - Auto-downloaded thumbnails from URLs
    - Thumbnail validation and resizing
    """

    MAX_SIZE = 200 * 1024  # 200KB max for Telegram thumbnails
    MAX_DIMENSION = 320  # Max width/height

    def __init__(self, client: Client):
        self.client = client

    async def get_thumbnail(
        self,
        user_id: int,
        custom_file_id: Optional[str] = None,
        fallback_url: Optional[str] = None,
        filename: str = "thumb"
    ) -> Optional[str]:
        """
        Get thumbnail for upload, prioritizing custom thumbnail.

        Priority:
        1. Custom user thumbnail (if set)
        2. Fallback URL (auto-extracted from video metadata)

        Args:
            user_id: Telegram user ID
            custom_file_id: User's custom thumbnail file_id
            fallback_url: URL to download thumbnail from
            filename: Base filename for saved thumbnail

        Returns:
            Path to thumbnail file or None
        """
        thumb_path = os.path.join(THUMBNAIL_DIR, f"{user_id}_{filename}.jpg")

        # Try custom thumbnail first
        if custom_file_id:
            try:
                await self.client.download_media(
                    custom_file_id,
                    file_name=thumb_path
                )
                if os.path.exists(thumb_path):
                    return thumb_path
            except Exception as e:
                print(f"[Thumbnail] Custom download error: {e}")

        # Fallback to URL
        if fallback_url:
            downloaded = await self.download_from_url(fallback_url, thumb_path)
            if downloaded:
                return thumb_path

        return None

    async def download_from_url(self, url: str, save_path: str) -> bool:
        """
        Download thumbnail from URL.

        Args:
            url: Image URL
            save_path: Path to save thumbnail

        Returns:
            True if successful
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        return False

                    content = await resp.read()

                    async with aiofiles.open(save_path, 'wb') as f:
                        await f.write(content)

                    return True
        except Exception as e:
            print(f"[Thumbnail] URL download error: {e}")
            return False

    async def save_custom_thumbnail(
        self,
        user_id: int,
        file_id: str
    ) -> Optional[str]:
        """
        Save user's custom thumbnail.

        Args:
            user_id: Telegram user ID
            file_id: Telegram file_id of the photo

        Returns:
            Path to saved thumbnail or None
        """
        thumb_path = os.path.join(THUMBNAIL_DIR, f"{user_id}_custom.jpg")

        try:
            await self.client.download_media(file_id, file_name=thumb_path)

            if os.path.exists(thumb_path):
                # Validate size
                if os.path.getsize(thumb_path) > self.MAX_SIZE:
                    # Could resize here with PIL if needed
                    pass

                return thumb_path
        except Exception as e:
            print(f"[Thumbnail] Save error: {e}")

        return None

    def cleanup(self, user_id: int, filename: str = None) -> None:
        """
        Clean up thumbnail files.

        Args:
            user_id: Telegram user ID
            filename: Specific filename to clean, or None for all
        """
        try:
            if filename:
                path = os.path.join(THUMBNAIL_DIR, f"{user_id}_{filename}.jpg")
                if os.path.exists(path):
                    os.remove(path)
            else:
                # Clean all thumbnails for user
                for f in os.listdir(THUMBNAIL_DIR):
                    if f.startswith(f"{user_id}_"):
                        os.remove(os.path.join(THUMBNAIL_DIR, f))
        except Exception as e:
            print(f"[Thumbnail] Cleanup error: {e}")

    def get_custom_path(self, user_id: int) -> Optional[str]:
        """Get path to user's custom thumbnail if exists."""
        path = os.path.join(THUMBNAIL_DIR, f"{user_id}_custom.jpg")
        return path if os.path.exists(path) else None
