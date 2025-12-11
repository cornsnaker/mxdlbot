"""
Download queue service with per-user limits and queue management.
Provides fair queuing with max 2 concurrent downloads per user.
"""

import asyncio
import random
import string
from dataclasses import dataclass, field
from typing import Dict, Optional, Callable, Any, List, Tuple
from datetime import datetime
from enum import Enum


class QueueItemStatus(Enum):
    """Status of a queue item."""
    PENDING = "pending"
    DOWNLOADING = "downloading"
    UPLOADING = "uploading"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class QueueItem:
    """A single download queue item."""
    id: str
    user_id: int
    chat_id: int
    metadata: Dict[str, Any]
    resolution: str
    cookies_path: str
    output_format: str
    upload_mode: str
    gofile_token: Optional[str]
    custom_thumbnail: Optional[str]
    user_name: str
    status: QueueItemStatus = QueueItemStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    error: Optional[str] = None
    progress_message_id: Optional[int] = None


class DownloadQueue:
    """
    Download queue manager with per-user limits.

    Features:
    - Max 2 concurrent downloads per user
    - Global queue for fair distribution
    - Queue position tracking
    - Cancellation support
    """

    MAX_CONCURRENT_PER_USER = 2
    MAX_GLOBAL_CONCURRENT = 5  # Total concurrent downloads across all users

    def __init__(self):
        # Global queue of pending items
        self.pending_queue: List[QueueItem] = []

        # Currently active downloads by user_id
        self.active_downloads: Dict[int, List[QueueItem]] = {}

        # All items by ID for quick lookup
        self.items: Dict[str, QueueItem] = {}

        # Counter for generating unique IDs
        self._id_counter = 0

        # Lock for thread-safe operations
        self._lock = asyncio.Lock()

        # Worker task
        self._worker_task: Optional[asyncio.Task] = None

        # Download handler callback
        self._download_handler: Optional[Callable] = None

    def set_download_handler(self, handler: Callable) -> None:
        """
        Set the download handler function.

        Args:
            handler: Async function that processes a QueueItem
        """
        self._download_handler = handler

    async def start_worker(self) -> None:
        """Start the queue worker."""
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._worker_loop())
            print("[Queue] Worker started")

    async def stop_worker(self) -> None:
        """Stop the queue worker."""
        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            print("[Queue] Worker stopped")

    async def _worker_loop(self) -> None:
        """Main worker loop that processes the queue."""
        while True:
            try:
                # Check for items to process
                item = await self._get_next_item()

                if item and self._download_handler:
                    # Process the item
                    asyncio.create_task(self._process_item(item))
                else:
                    # No items to process, wait a bit
                    await asyncio.sleep(1)

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[Queue] Worker error: {e}")
                await asyncio.sleep(5)

    async def _get_next_item(self) -> Optional[QueueItem]:
        """Get the next item to process, respecting limits."""
        async with self._lock:
            # Count total active downloads
            total_active = sum(len(items) for items in self.active_downloads.values())

            if total_active >= self.MAX_GLOBAL_CONCURRENT:
                return None

            # Find next eligible item
            for item in self.pending_queue:
                user_active = len(self.active_downloads.get(item.user_id, []))

                if user_active < self.MAX_CONCURRENT_PER_USER:
                    # Remove from pending queue
                    self.pending_queue.remove(item)

                    # Add to active downloads
                    if item.user_id not in self.active_downloads:
                        self.active_downloads[item.user_id] = []
                    self.active_downloads[item.user_id].append(item)

                    # Update status
                    item.status = QueueItemStatus.DOWNLOADING
                    item.started_at = datetime.utcnow()

                    return item

            return None

    async def _process_item(self, item: QueueItem) -> None:
        """Process a single queue item."""
        try:
            if self._download_handler:
                await self._download_handler(item)
        except Exception as e:
            print(f"[Queue] Process error for {item.id}: {e}")
            item.status = QueueItemStatus.FAILED
            item.error = str(e)
        finally:
            await self._complete_item(item)

    async def _complete_item(self, item: QueueItem) -> None:
        """Mark an item as complete and remove from active."""
        async with self._lock:
            # Remove from active downloads
            if item.user_id in self.active_downloads:
                if item in self.active_downloads[item.user_id]:
                    self.active_downloads[item.user_id].remove(item)
                if not self.active_downloads[item.user_id]:
                    del self.active_downloads[item.user_id]

    async def add(
        self,
        user_id: int,
        chat_id: int,
        metadata: Dict[str, Any],
        resolution: str,
        cookies_path: str,
        output_format: str = "mp4",
        upload_mode: str = "video",
        gofile_token: Optional[str] = None,
        custom_thumbnail: Optional[str] = None,
        user_name: str = ""
    ) -> tuple[QueueItem, int]:
        """
        Add a download to the queue.

        Args:
            user_id: Telegram user ID
            chat_id: Chat ID for sending messages
            metadata: Video metadata dict
            resolution: Selected resolution
            cookies_path: Path to user's cookies file
            output_format: mp4 or mkv
            upload_mode: video or document
            gofile_token: User's Gofile API token
            custom_thumbnail: Custom thumbnail file ID
            user_name: User's display name

        Returns:
            Tuple of (QueueItem, queue_position)
        """
        async with self._lock:
            self._id_counter += 1
            # Generate short, user-friendly task ID (e.g., "DL-A3X9")
            random_suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
            item_id = f"DL-{random_suffix}"

            # Ensure uniqueness
            while item_id in self.items:
                random_suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
                item_id = f"DL-{random_suffix}"

            item = QueueItem(
                id=item_id,
                user_id=user_id,
                chat_id=chat_id,
                metadata=metadata,
                resolution=resolution,
                cookies_path=cookies_path,
                output_format=output_format,
                upload_mode=upload_mode,
                gofile_token=gofile_token,
                custom_thumbnail=custom_thumbnail,
                user_name=user_name
            )

            self.items[item_id] = item
            self.pending_queue.append(item)

            # Calculate position
            position = self._get_position_for_user(user_id)

            return item, position

    def _get_position_for_user(self, user_id: int) -> int:
        """Get queue position for a user (1-based)."""
        position = 0
        for item in self.pending_queue:
            if item.user_id == user_id:
                position += 1
        return position

    async def cancel(self, item_id: str, user_id: int = None) -> Tuple[bool, str]:
        """
        Cancel a queued download by task ID.

        Args:
            item_id: The queue item ID (e.g., "DL-A3X9")
            user_id: Optional user ID for ownership verification

        Returns:
            Tuple of (success, message)
        """
        async with self._lock:
            # Normalize task ID (case-insensitive)
            item_id = item_id.upper()

            if item_id not in self.items:
                return False, "Task not found"

            item = self.items[item_id]

            # Verify ownership if user_id provided
            if user_id is not None and item.user_id != user_id:
                return False, "You can only cancel your own tasks"

            # Check status
            if item.status == QueueItemStatus.CANCELLED:
                return False, "Task already cancelled"

            if item.status in [QueueItemStatus.DOWNLOADING, QueueItemStatus.UPLOADING]:
                return False, "Task already in progress (cannot cancel)"

            if item.status in [QueueItemStatus.COMPLETED, QueueItemStatus.FAILED]:
                return False, "Task already finished"

            # Can only cancel pending items
            if item.status != QueueItemStatus.PENDING:
                return False, f"Cannot cancel task in '{item.status.value}' state"

            # Remove from pending queue
            if item in self.pending_queue:
                self.pending_queue.remove(item)

            item.status = QueueItemStatus.CANCELLED
            title = item.metadata.get("title", "Unknown")[:30]
            return True, f"Cancelled: {title}..."

    def get_item(self, item_id: str) -> Optional[QueueItem]:
        """Get a queue item by ID."""
        return self.items.get(item_id.upper())

    async def cancel_user_downloads(self, user_id: int) -> int:
        """
        Cancel all pending downloads for a user.

        Args:
            user_id: Telegram user ID

        Returns:
            Number of cancelled items
        """
        async with self._lock:
            cancelled = 0
            items_to_remove = []

            for item in self.pending_queue:
                if item.user_id == user_id:
                    items_to_remove.append(item)
                    item.status = QueueItemStatus.CANCELLED
                    cancelled += 1

            for item in items_to_remove:
                self.pending_queue.remove(item)

            return cancelled

    def get_user_queue_status(self, user_id: int) -> Dict[str, Any]:
        """
        Get queue status for a user.

        Returns:
            Dict with active_count, pending_count, total_count, items
        """
        active = self.active_downloads.get(user_id, [])
        pending = [item for item in self.pending_queue if item.user_id == user_id]

        return {
            "active_count": len(active),
            "pending_count": len(pending),
            "total_count": len(active) + len(pending),
            "can_add_more": len(active) + len(pending) < self.MAX_CONCURRENT_PER_USER * 2,  # Allow some buffer
            "active_items": [
                {
                    "id": item.id,
                    "title": item.metadata.get("title", "Unknown"),
                    "status": item.status.value
                }
                for item in active
            ],
            "pending_items": [
                {
                    "id": item.id,
                    "title": item.metadata.get("title", "Unknown"),
                    "position": i + 1
                }
                for i, item in enumerate(pending)
            ]
        }

    def get_global_stats(self) -> Dict[str, Any]:
        """Get global queue statistics."""
        total_active = sum(len(items) for items in self.active_downloads.values())
        total_pending = len(self.pending_queue)

        return {
            "active_downloads": total_active,
            "pending_downloads": total_pending,
            "total_queued": total_active + total_pending,
            "active_users": len(self.active_downloads)
        }

    def is_user_at_limit(self, user_id: int) -> bool:
        """Check if user has reached their concurrent download limit."""
        active = len(self.active_downloads.get(user_id, []))
        return active >= self.MAX_CONCURRENT_PER_USER

    def get_user_active_count(self, user_id: int) -> int:
        """Get number of active downloads for a user."""
        return len(self.active_downloads.get(user_id, []))

    def get_user_pending_count(self, user_id: int) -> int:
        """Get number of pending downloads for a user."""
        return len([item for item in self.pending_queue if item.user_id == user_id])


# Global queue instance
download_queue = DownloadQueue()
