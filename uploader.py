"""
Pyrogram-based uploader with tgcrypto acceleration and progress tracking.
"""

import asyncio
import time
from typing import Optional, Callable
from pyrogram import Client
from pyrogram.errors import FloodWait


def generate_progress_bar(percent: float) -> str:
    """
    Generate a visual progress bar.

    Args:
        percent: Percentage value (0-100)

    Returns:
        String progress bar like "[▓▓▓▓▓░░░░░] 45.2%"
    """
    filled = int(percent // 10)
    bar = "▓" * filled + "░" * (10 - filled)
    return f"[{bar}] {percent:.1f}%"


def format_size(size_bytes: int) -> str:
    """
    Format bytes to human-readable size.

    Args:
        size_bytes: Size in bytes

    Returns:
        Formatted string like "128.5 MB"
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


async def upload_with_progress(
    client: Client,
    chat_id: int,
    file_path: str,
    thumb_path: Optional[str] = None,
    duration: Optional[int] = None,
    caption: str = "",
    progress_message=None,
    filename: str = ""
) -> bool:
    """
    Upload video to Telegram with progress updates.

    Uses Pyrogram's native progress callback with tgcrypto acceleration
    (auto-enabled when tgcrypto is installed).

    Args:
        client: Pyrogram Client instance
        chat_id: Telegram chat ID to send to
        file_path: Path to video file
        thumb_path: Path to thumbnail image (optional)
        duration: Video duration in seconds (optional)
        caption: Video caption
        progress_message: Message object to edit for progress updates
        filename: Display filename for progress message

    Returns:
        True on success, False on failure
    """
    last_update_time = 0
    update_interval = 3  # Update every 3 seconds to avoid FloodWait

    async def progress_callback(current: int, total: int):
        """
        Pyrogram progress callback.

        Args:
            current: Bytes uploaded so far
            total: Total file size in bytes
        """
        nonlocal last_update_time

        now = time.time()
        if now - last_update_time < update_interval:
            return

        if progress_message and total > 0:
            percent = (current / total) * 100
            progress_bar = generate_progress_bar(percent)
            current_size = format_size(current)
            total_size = format_size(total)

            text = (
                f"⬆️ **Uploading {filename}**\n"
                f"{progress_bar}\n"
                f"📁 {current_size} / {total_size}"
            )

            try:
                await progress_message.edit_text(text)
                last_update_time = now
            except FloodWait as e:
                # Wait and retry
                await asyncio.sleep(e.value)
            except Exception:
                # Silently ignore other edit errors
                pass

    # Retry logic for FloodWait
    max_retries = 3
    for attempt in range(max_retries):
        try:
            await client.send_video(
                chat_id=chat_id,
                video=file_path,
                thumb=thumb_path,
                duration=duration,
                caption=caption,
                supports_streaming=True,
                progress=progress_callback
            )
            return True

        except FloodWait as e:
            if attempt < max_retries - 1:
                await asyncio.sleep(e.value)
            else:
                raise

        except Exception as e:
            print(f"Upload error: {e}")
            return False

    return False
