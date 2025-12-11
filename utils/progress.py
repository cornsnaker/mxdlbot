"""
Progress tracking and visual progress bar generation.
"""

import time
import asyncio
from typing import Optional, Callable
from pyrogram.types import Message
from pyrogram.errors import FloodWait
from .formatters import format_size, format_speed, format_time


def generate_progress_bar(percent: float, width: int = 12) -> str:
    """
    Generate a visual progress bar using block characters.

    Args:
        percent: Progress percentage (0-100)
        width: Width of the progress bar in characters

    Returns:
        Progress bar string like "████████░░░░"
    """
    percent = max(0, min(100, percent))  # Clamp to 0-100
    filled = int(percent / 100 * width)
    empty = width - filled
    return "█" * filled + "░" * empty


class ProgressTracker:
    """
    Unified progress tracker for downloads and uploads.

    Features:
    - Visual progress bar
    - Speed calculation
    - ETA estimation
    - Rate-limited message updates
    """

    def __init__(
        self,
        message: Message,
        operation: str = "Processing",
        update_interval: float = 2.0
    ):
        """
        Initialize progress tracker.

        Args:
            message: Telegram message to update
            operation: Operation name (e.g., "Downloading", "Uploading")
            update_interval: Minimum seconds between message updates
        """
        self.message = message
        self.operation = operation
        self.update_interval = update_interval

        self.start_time = time.time()
        self.last_update_time = 0
        self.last_bytes = 0
        self.last_speed_time = self.start_time

    async def update(
        self,
        current: int,
        total: int,
        status: str = ""
    ) -> None:
        """
        Update progress display.

        Args:
            current: Current bytes/units processed
            total: Total bytes/units
            status: Additional status text
        """
        now = time.time()

        # Rate limit updates
        if now - self.last_update_time < self.update_interval:
            return

        if total <= 0:
            return

        # Calculate metrics
        percent = (current / total) * 100
        elapsed = now - self.start_time

        # Calculate speed
        time_diff = now - self.last_speed_time
        if time_diff > 0:
            bytes_diff = current - self.last_bytes
            speed = bytes_diff / time_diff
        else:
            speed = 0

        # Calculate ETA
        remaining = total - current
        eta = remaining / speed if speed > 0 else -1

        # Generate progress bar
        bar = generate_progress_bar(percent)

        # Build message
        text = self._build_message(
            percent=percent,
            bar=bar,
            current=current,
            total=total,
            speed=speed,
            elapsed=elapsed,
            eta=eta,
            status=status
        )

        # Update message
        try:
            await self.message.edit_text(text)
            self.last_update_time = now
            self.last_bytes = current
            self.last_speed_time = now
        except FloodWait as e:
            await asyncio.sleep(e.value)
        except Exception:
            pass

    def _build_message(
        self,
        percent: float,
        bar: str,
        current: int,
        total: int,
        speed: float,
        elapsed: float,
        eta: float,
        status: str
    ) -> str:
        """Build the progress message."""
        lines = [
            f"**{self.operation}**",
            "",
            f"`{bar}` **{percent:.1f}%**",
            "",
            f"**Progress:** {format_size(current)} / {format_size(total)}",
            f"**Speed:** {format_speed(speed)}",
            f"**Elapsed:** {format_time(elapsed)}",
            f"**ETA:** {format_time(eta)}",
        ]

        if status:
            lines.append(f"**Status:** `{status[:50]}`")

        return "\n".join(lines)

    async def complete(self, final_message: str = None) -> None:
        """
        Mark progress as complete.

        Args:
            final_message: Optional final message to show
        """
        if final_message:
            try:
                await self.message.edit_text(final_message)
            except Exception:
                pass

    async def error(self, error_message: str) -> None:
        """
        Show error state.

        Args:
            error_message: Error description
        """
        try:
            await self.message.edit_text(f"❌ **Error**\n\n{error_message}")
        except Exception:
            pass


class DownloadProgress(ProgressTracker):
    """Progress tracker specialized for downloads."""

    def __init__(self, message: Message):
        super().__init__(message, operation="Downloading", update_interval=3.0)

    async def callback(self, percent: float, status_line: str) -> None:
        """
        Callback for download progress.

        Args:
            percent: Download percentage
            status_line: Raw status line from downloader
        """
        # Estimate bytes from percentage (we don't have actual bytes)
        current = int(percent)
        total = 100

        await self.update(current, total, status_line)


class UploadProgress(ProgressTracker):
    """Progress tracker specialized for uploads."""

    def __init__(self, message: Message):
        super().__init__(message, operation="Uploading", update_interval=2.0)

    async def callback(self, current: int, total: int) -> None:
        """
        Callback for upload progress (Pyrogram format).

        Args:
            current: Bytes uploaded
            total: Total bytes
        """
        await self.update(current, total)
