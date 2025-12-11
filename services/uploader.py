"""
Uploader service with Telegram and Gofile.io support.
"""

import os
import time
import asyncio
import aiohttp
from typing import Optional, Callable
from dataclasses import dataclass
from pyrogram import Client
from pyrogram.errors import FloodWait


# Telegram file size limit (2GB)
TELEGRAM_SIZE_LIMIT = 2 * 1024 * 1024 * 1024


@dataclass
class UploadResult:
    """Upload result container."""
    success: bool
    platform: str  # "telegram" or "gofile"
    file_id: Optional[str] = None  # Telegram file_id
    gofile_link: Optional[str] = None  # Gofile download link
    error: Optional[str] = None


class GofileUploader:
    """Gofile.io upload handler."""

    BASE_URL = "https://api.gofile.io"

    async def get_best_server(self) -> Optional[str]:
        """Get the best available Gofile server."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.BASE_URL}/servers") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("status") == "ok":
                            servers = data.get("data", {}).get("servers", [])
                            if servers:
                                return servers[0].get("name")
        except Exception as e:
            print(f"[Gofile] Server fetch error: {e}")
        return None

    async def upload(
        self,
        file_path: str,
        token: Optional[str] = None,
        progress_callback: Optional[Callable[[float], None]] = None
    ) -> UploadResult:
        """
        Upload file to Gofile.io.

        Args:
            file_path: Path to file
            token: User's Gofile API token (optional)
            progress_callback: Callback for upload progress

        Returns:
            UploadResult with success status and download link
        """
        server = await self.get_best_server()
        if not server:
            return UploadResult(
                success=False,
                platform="gofile",
                error="Could not get Gofile server"
            )

        upload_url = f"https://{server}.gofile.io/contents/uploadfile"

        try:
            file_size = os.path.getsize(file_path)
            uploaded = 0
            start_time = time.time()

            # Create form data with file
            data = aiohttp.FormData()

            # Add token if provided
            if token:
                data.add_field('token', token)

            # Add file with progress tracking
            async def file_sender():
                nonlocal uploaded
                with open(file_path, 'rb') as f:
                    chunk_size = 1024 * 1024  # 1MB chunks
                    while True:
                        chunk = f.read(chunk_size)
                        if not chunk:
                            break
                        uploaded += len(chunk)
                        if progress_callback:
                            percent = (uploaded / file_size) * 100
                            await progress_callback(percent)
                        yield chunk

            data.add_field(
                'file',
                file_sender(),
                filename=os.path.basename(file_path),
                content_type='application/octet-stream'
            )

            async with aiohttp.ClientSession() as session:
                async with session.post(upload_url, data=data) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        if result.get("status") == "ok":
                            download_page = result["data"].get("downloadPage")
                            return UploadResult(
                                success=True,
                                platform="gofile",
                                gofile_link=download_page
                            )

            return UploadResult(
                success=False,
                platform="gofile",
                error="Upload failed"
            )

        except Exception as e:
            return UploadResult(
                success=False,
                platform="gofile",
                error=str(e)
            )


class TelegramUploader:
    """Telegram upload handler with progress tracking."""

    def __init__(self, client: Client):
        self.client = client

    async def upload_video(
        self,
        chat_id: int,
        file_path: str,
        caption: str = "",
        thumb_path: Optional[str] = None,
        duration: Optional[int] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> UploadResult:
        """
        Upload video to Telegram.

        Args:
            chat_id: Telegram chat ID
            file_path: Path to video file
            caption: Video caption
            thumb_path: Path to thumbnail
            duration: Video duration in seconds
            progress_callback: Callback(current, total) for progress

        Returns:
            UploadResult with success status
        """
        max_retries = 3

        for attempt in range(max_retries):
            try:
                message = await self.client.send_video(
                    chat_id=chat_id,
                    video=file_path,
                    caption=caption,
                    thumb=thumb_path,
                    duration=duration,
                    supports_streaming=True,
                    progress=progress_callback
                )

                return UploadResult(
                    success=True,
                    platform="telegram",
                    file_id=message.video.file_id if message.video else None
                )

            except FloodWait as e:
                if attempt < max_retries - 1:
                    await asyncio.sleep(e.value)
                else:
                    return UploadResult(
                        success=False,
                        platform="telegram",
                        error=f"FloodWait: {e.value}s"
                    )

            except Exception as e:
                return UploadResult(
                    success=False,
                    platform="telegram",
                    error=str(e)
                )

        return UploadResult(
            success=False,
            platform="telegram",
            error="Max retries exceeded"
        )

    async def upload_document(
        self,
        chat_id: int,
        file_path: str,
        caption: str = "",
        thumb_path: Optional[str] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> UploadResult:
        """
        Upload file as document to Telegram.

        Args:
            chat_id: Telegram chat ID
            file_path: Path to file
            caption: Document caption
            thumb_path: Path to thumbnail
            progress_callback: Callback(current, total) for progress

        Returns:
            UploadResult with success status
        """
        max_retries = 3

        for attempt in range(max_retries):
            try:
                message = await self.client.send_document(
                    chat_id=chat_id,
                    document=file_path,
                    caption=caption,
                    thumb=thumb_path,
                    progress=progress_callback
                )

                return UploadResult(
                    success=True,
                    platform="telegram",
                    file_id=message.document.file_id if message.document else None
                )

            except FloodWait as e:
                if attempt < max_retries - 1:
                    await asyncio.sleep(e.value)
                else:
                    return UploadResult(
                        success=False,
                        platform="telegram",
                        error=f"FloodWait: {e.value}s"
                    )

            except Exception as e:
                return UploadResult(
                    success=False,
                    platform="telegram",
                    error=str(e)
                )

        return UploadResult(
            success=False,
            platform="telegram",
            error="Max retries exceeded"
        )


class Uploader:
    """
    Unified uploader with automatic Gofile fallback for large files.
    """

    def __init__(self, client: Client):
        self.telegram = TelegramUploader(client)
        self.gofile = GofileUploader()

    async def upload(
        self,
        chat_id: int,
        file_path: str,
        caption: str = "",
        thumb_path: Optional[str] = None,
        duration: Optional[int] = None,
        gofile_token: Optional[str] = None,
        upload_mode: str = "video",
        progress_callback: Optional[Callable] = None,
        force_gofile: bool = False
    ) -> UploadResult:
        """
        Upload file with automatic platform selection.

        Files over 2GB are automatically uploaded to Gofile.

        Args:
            chat_id: Telegram chat ID
            file_path: Path to file
            caption: Video caption
            thumb_path: Thumbnail path
            duration: Video duration
            gofile_token: User's Gofile API token
            upload_mode: "video" or "document"
            progress_callback: Progress callback
            force_gofile: Force Gofile upload regardless of size

        Returns:
            UploadResult with platform and links
        """
        file_size = os.path.getsize(file_path)

        # Check if file is too large for Telegram or forced to Gofile
        if file_size > TELEGRAM_SIZE_LIMIT or force_gofile:
            return await self.gofile.upload(
                file_path=file_path,
                token=gofile_token,
                progress_callback=progress_callback
            )

        # Upload to Telegram based on upload_mode
        if upload_mode == "document":
            return await self.telegram.upload_document(
                chat_id=chat_id,
                file_path=file_path,
                caption=caption,
                thumb_path=thumb_path,
                progress_callback=progress_callback
            )
        else:
            return await self.telegram.upload_video(
                chat_id=chat_id,
                file_path=file_path,
                caption=caption,
                thumb_path=thumb_path,
                duration=duration,
                progress_callback=progress_callback
            )
