"""
Pyrogram-based uploader with tgcrypto acceleration and professional progress tracking.
"""

import asyncio
import time
from typing import Optional
from pyrogram import Client
from pyrogram.errors import FloodWait


def generate_progress_bar(percent: float, width: int = 12) -> str:
    """
    Generate a professional visual progress bar.

    Args:
        percent: Percentage value (0-100)
        width: Width of the progress bar

    Returns:
        String progress bar like "████████░░░░"
    """
    filled = int(percent / 100 * width)
    empty = width - filled
    return "█" * filled + "░" * empty


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


def format_speed(bytes_per_sec: float) -> str:
    """
    Format speed to human-readable format.

    Args:
        bytes_per_sec: Speed in bytes per second

    Returns:
        Formatted string like "12.5 MB/s"
    """
    if bytes_per_sec < 1024:
        return f"{bytes_per_sec:.0f} B/s"
    elif bytes_per_sec < 1024 * 1024:
        return f"{bytes_per_sec / 1024:.1f} KB/s"
    else:
        return f"{bytes_per_sec / (1024 * 1024):.2f} MB/s"


def format_time(seconds: float) -> str:
    """
    Format seconds to human-readable time.

    Args:
        seconds: Time in seconds

    Returns:
        Formatted string like "2m 30s" or "1h 5m"
    """
    if seconds < 0:
        return "calculating..."

    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        mins = seconds // 60
        secs = seconds % 60
        return f"{mins}m {secs}s"
    else:
        hours = seconds // 3600
        mins = (seconds % 3600) // 60
        return f"{hours}h {mins}m"


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
    Upload video to Telegram with professional progress updates.

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
    update_interval = 2  # Update every 2 seconds
    start_time = time.time()
    last_bytes = 0
    last_speed_time = start_time

    async def progress_callback(current: int, total: int):
        """
        Pyrogram progress callback with speed and ETA calculation.
        """
        nonlocal last_update_time, last_bytes, last_speed_time

        now = time.time()
        if now - last_update_time < update_interval:
            return

        if progress_message and total > 0:
            # Calculate progress
            percent = (current / total) * 100
            progress_bar = generate_progress_bar(percent)

            # Calculate speed (bytes per second)
            time_diff = now - last_speed_time
            if time_diff > 0:
                bytes_diff = current - last_bytes
                speed = bytes_diff / time_diff
            else:
                speed = 0

            # Calculate ETA
            remaining_bytes = total - current
            if speed > 0:
                eta_seconds = remaining_bytes / speed
            else:
                eta_seconds = -1

            # Format sizes
            current_size = format_size(current)
            total_size = format_size(total)
            speed_str = format_speed(speed)
            eta_str = format_time(eta_seconds)

            # Build professional progress message
            text = (
                f"**Uploading**\n\n"
                f"`{progress_bar}` **{percent:.1f}%**\n\n"
                f"**Progress:** {current_size} / {total_size}\n"
                f"**Speed:** {speed_str}\n"
                f"**ETA:** {eta_str}"
            )

            try:
                await progress_message.edit_text(text)
                last_update_time = now
                last_bytes = current
                last_speed_time = now
            except FloodWait as e:
                await asyncio.sleep(e.value)
            except Exception:
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
