"""
Progress tracking and visual progress bar generation.
Enhanced style with hexagon symbols and detailed info.
"""

import time
import asyncio
from typing import Optional, Dict, Any
from pyrogram.types import Message
from pyrogram.errors import FloodWait
from .formatters import format_size, format_speed, format_time


# Hexagon symbols for progress bar
FILLED_HEX = "⬢"
EMPTY_HEX = "⬡"
BAR_WIDTH = 12


def generate_progress_bar(percent: float, width: int = BAR_WIDTH) -> str:
    """
    Generate a visual progress bar using hexagon characters.

    Args:
        percent: Progress percentage (0-100)
        width: Width of the progress bar in characters

    Returns:
        Progress bar string like "〘⬢⬢⬢⬢⬡⬡⬡⬡⬡⬡⬡⬡〙"
    """
    percent = max(0, min(100, percent))  # Clamp to 0-100
    filled = int(percent / 100 * width)
    empty = width - filled
    bar = FILLED_HEX * filled + EMPTY_HEX * empty
    return f"〘{bar}〙"


def format_elapsed_eta(elapsed: float, eta: float) -> str:
    """
    Format elapsed and ETA time like: "4m3s of 6m37s ( 2m34s )"

    Args:
        elapsed: Elapsed seconds
        eta: Remaining seconds

    Returns:
        Formatted string
    """
    total_est = elapsed + eta if eta > 0 else elapsed

    elapsed_str = format_time(elapsed)
    total_str = format_time(total_est) if eta > 0 else "∞"
    eta_str = format_time(eta) if eta > 0 else "calculating..."

    return f"{elapsed_str} of {total_str} ( {eta_str} )"


class ProgressTracker:
    """
    Unified progress tracker for downloads and uploads.

    Features:
    - Visual hexagon progress bar
    - Speed calculation
    - ETA estimation
    - Rate-limited message updates
    - Enhanced display format
    """

    def __init__(
        self,
        message: Message,
        task_id: str = "",
        title: str = "",
        user_name: str = "",
        user_id: int = 0,
        operation: str = "Processing",
        update_interval: float = 2.0
    ):
        """
        Initialize progress tracker.

        Args:
            message: Telegram message to update
            task_id: Task ID like "DL-A3X9"
            title: Video/file title
            user_name: User's display name
            user_id: User's Telegram ID
            operation: Operation name (e.g., "Download", "Upload")
            update_interval: Minimum seconds between message updates
        """
        self.message = message
        self.task_id = task_id
        self.title = title
        self.user_name = user_name
        self.user_id = user_id
        self.operation = operation
        self.update_interval = update_interval

        self.start_time = time.time()
        self.last_update_time = 0
        self.last_bytes = 0
        self.last_speed_time = self.start_time

        # For accurate total tracking
        self.total_bytes = 0
        self.current_bytes = 0

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

        # Store for reference
        self.current_bytes = current
        self.total_bytes = total

        # Calculate metrics
        percent = (current / total) * 100
        elapsed = now - self.start_time

        # Calculate speed (smoothed)
        time_diff = now - self.last_speed_time
        if time_diff > 0.5:
            bytes_diff = current - self.last_bytes
            speed = bytes_diff / time_diff
            self.last_bytes = current
            self.last_speed_time = now
        else:
            speed = 0

        # Calculate ETA
        remaining = total - current
        eta = remaining / speed if speed > 0 else -1

        # Build message
        text = self._build_enhanced_message(
            percent=percent,
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
        except FloodWait as e:
            await asyncio.sleep(e.value)
        except Exception:
            pass

    def _build_enhanced_message(
        self,
        percent: float,
        current: int,
        total: int,
        speed: float,
        elapsed: float,
        eta: float,
        status: str
    ) -> str:
        """Build the enhanced progress message with hexagon bar."""
        bar = generate_progress_bar(percent)
        time_str = format_elapsed_eta(elapsed, eta)

        # Truncate title if too long
        display_title = self.title[:45] + "..." if len(self.title) > 45 else self.title

        lines = [
            f"**{display_title}**",
            "",
            f"╭{bar} **{percent:.2f}%**",
            f"┊**Processed** » {format_size(current)} of {format_size(total)}",
            f"┊**Status** » {self.operation}",
            f"┊**Speed** » {format_speed(speed)}",
            f"┊**Time** » {time_str}",
            f"┊**Engine** » Pyro + N_m3u8DL-RE",
        ]

        if self.task_id:
            lines.append(f"╰**Stop** » `/canceltask {self.task_id}`")
        else:
            lines.append("╰━━━━━━━━━━━━━━━━")

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

    def __init__(
        self,
        message: Message,
        task_id: str = "",
        title: str = "",
        user_name: str = "",
        user_id: int = 0
    ):
        super().__init__(
            message,
            task_id=task_id,
            title=title,
            user_name=user_name,
            user_id=user_id,
            operation="Download",
            update_interval=3.0
        )
        # For download, we estimate total from percentage
        self._estimated_total = 0
        self._last_percent = 0

    async def callback(self, percent: float, status_line: str) -> None:
        """
        Callback for download progress.

        Args:
            percent: Download percentage
            status_line: Raw status line from downloader
        """
        # Parse size from status line if available
        # Example: "12.5% 125MB/1GB"
        current = int(percent * 10)  # Scale for smoother updates
        total = 1000

        # Try to parse actual bytes from status line
        import re
        size_match = re.search(r'(\d+(?:\.\d+)?)\s*(KB|MB|GB)\s*/\s*(\d+(?:\.\d+)?)\s*(KB|MB|GB)', status_line)
        if size_match:
            current_val = float(size_match.group(1))
            current_unit = size_match.group(2)
            total_val = float(size_match.group(3))
            total_unit = size_match.group(4)

            # Convert to bytes
            multipliers = {'KB': 1024, 'MB': 1024**2, 'GB': 1024**3}
            current = int(current_val * multipliers.get(current_unit, 1))
            total = int(total_val * multipliers.get(total_unit, 1))

        await self.update(current, total, status_line)


class UploadProgress(ProgressTracker):
    """Progress tracker specialized for uploads."""

    def __init__(
        self,
        message: Message,
        task_id: str = "",
        title: str = "",
        user_name: str = "",
        user_id: int = 0
    ):
        super().__init__(
            message,
            task_id=task_id,
            title=title,
            user_name=user_name,
            user_id=user_id,
            operation="Upload",
            update_interval=2.0
        )

    async def callback(self, current: int, total: int) -> None:
        """
        Callback for upload progress (Pyrogram format).

        Args:
            current: Bytes uploaded
            total: Total bytes
        """
        await self.update(current, total)


class StatusPageManager:
    """
    Manages a single status page showing all active downloads.
    Uses pagination to avoid Telegram message length limits.
    """

    MAX_ITEMS_PER_PAGE = 5
    MAX_MESSAGE_LENGTH = 4000

    def __init__(self):
        self.active_tasks: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def register_task(
        self,
        task_id: str,
        title: str,
        user_name: str,
        user_id: int,
        status: str = "Queued"
    ) -> None:
        """Register a new task."""
        async with self._lock:
            self.active_tasks[task_id] = {
                "title": title,
                "user_name": user_name,
                "user_id": user_id,
                "status": status,
                "percent": 0,
                "current": 0,
                "total": 0,
                "speed": 0,
                "elapsed": 0,
                "eta": 0,
                "start_time": time.time()
            }

    async def update_task(
        self,
        task_id: str,
        percent: float = None,
        current: int = None,
        total: int = None,
        speed: float = None,
        status: str = None,
        elapsed: float = None,
        eta: float = None
    ) -> None:
        """Update task progress."""
        async with self._lock:
            if task_id not in self.active_tasks:
                return

            task = self.active_tasks[task_id]
            if percent is not None:
                task["percent"] = percent
            if current is not None:
                task["current"] = current
            if total is not None:
                task["total"] = total
            if speed is not None:
                task["speed"] = speed
            if status is not None:
                task["status"] = status
            if elapsed is not None:
                task["elapsed"] = elapsed
            if eta is not None:
                task["eta"] = eta

    async def remove_task(self, task_id: str) -> None:
        """Remove a completed/cancelled task."""
        async with self._lock:
            if task_id in self.active_tasks:
                del self.active_tasks[task_id]

    def format_status_page(self, page: int = 1) -> tuple[str, int]:
        """
        Format status page for display.

        Args:
            page: Page number (1-based)

        Returns:
            Tuple of (formatted_text, total_pages)
        """
        tasks = list(self.active_tasks.items())
        total_pages = max(1, (len(tasks) + self.MAX_ITEMS_PER_PAGE - 1) // self.MAX_ITEMS_PER_PAGE)
        page = max(1, min(page, total_pages))

        start_idx = (page - 1) * self.MAX_ITEMS_PER_PAGE
        end_idx = start_idx + self.MAX_ITEMS_PER_PAGE
        page_tasks = tasks[start_idx:end_idx]

        if not page_tasks:
            return "📊 **No Active Downloads**\n\nAll queues are empty.", 1

        lines = []

        for i, (task_id, task) in enumerate(page_tasks, start=start_idx + 1):
            bar = generate_progress_bar(task["percent"])
            time_str = format_elapsed_eta(task["elapsed"], task["eta"])

            # Truncate title
            title = task["title"][:40] + "..." if len(task["title"]) > 40 else task["title"]

            task_block = [
                f"**{i}. {title}**",
                "",
                f"{task['user_name']}  ({task['user_id']})",
                f"╭{bar} **{task['percent']:.2f}%**",
                f"┊**Processed** » {format_size(task['current'])} of {format_size(task['total'])}",
                f"┊**Status** » {task['status']}",
                f"┊**Speed** » {format_speed(task['speed'])}",
                f"┊**Time** » {time_str}",
                f"╰**Stop** » `/canceltask {task_id}`",
                ""
            ]
            lines.extend(task_block)

        # Add separator
        lines.append("▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬✘▬")

        # Add page info if multiple pages
        if total_pages > 1:
            lines.append(f"\n📄 Page {page}/{total_pages} | Use `/status {page+1}` for next")

        return "\n".join(lines), total_pages

    def get_task_count(self) -> int:
        """Get number of active tasks."""
        return len(self.active_tasks)


# Global status page manager
status_manager = StatusPageManager()
