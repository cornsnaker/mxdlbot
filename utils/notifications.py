"""
Toast-style notification system for status updates.
"""

import asyncio
from typing import Optional
from pyrogram import Client
from pyrogram.types import Message
from pyrogram.errors import FloodWait


class Toast:
    """
    Toast-style notification system.

    Provides temporary status messages that auto-delete
    or transform into final results.
    """

    # Toast types with icons
    ICONS = {
        "info": "ℹ️",
        "success": "✅",
        "warning": "⚠️",
        "error": "❌",
        "loading": "⏳",
        "download": "⬇️",
        "upload": "⬆️",
        "search": "🔍",
        "done": "✨"
    }

    def __init__(self, client: Client, chat_id: int):
        """
        Initialize toast system.

        Args:
            client: Pyrogram client
            chat_id: Chat ID to send toasts to
        """
        self.client = client
        self.chat_id = chat_id
        self.current_message: Optional[Message] = None

    async def show(
        self,
        text: str,
        toast_type: str = "info",
        auto_delete: float = 0
    ) -> Message:
        """
        Show a toast notification.

        Args:
            text: Toast message text
            toast_type: Type of toast (info, success, warning, error, loading, etc.)
            auto_delete: Auto-delete after N seconds (0 = no auto-delete)

        Returns:
            The sent message
        """
        icon = self.ICONS.get(toast_type, "")
        full_text = f"{icon} {text}" if icon else text

        try:
            if self.current_message:
                # Update existing toast
                self.current_message = await self.current_message.edit_text(full_text)
            else:
                # Send new toast
                self.current_message = await self.client.send_message(
                    self.chat_id,
                    full_text
                )

            # Schedule auto-delete if requested
            if auto_delete > 0:
                asyncio.create_task(self._auto_delete(auto_delete))

            return self.current_message

        except FloodWait as e:
            await asyncio.sleep(e.value)
            return await self.show(text, toast_type, auto_delete)
        except Exception:
            # If edit fails, send new message
            self.current_message = await self.client.send_message(
                self.chat_id,
                full_text
            )
            return self.current_message

    async def _auto_delete(self, delay: float) -> None:
        """Auto-delete the current toast after delay."""
        await asyncio.sleep(delay)
        await self.dismiss()

    async def dismiss(self) -> None:
        """Dismiss (delete) the current toast."""
        if self.current_message:
            try:
                await self.current_message.delete()
            except Exception:
                pass
            self.current_message = None

    async def success(self, text: str, auto_delete: float = 3) -> Message:
        """Show success toast."""
        return await self.show(text, "success", auto_delete)

    async def error(self, text: str, auto_delete: float = 0) -> Message:
        """Show error toast (no auto-delete by default)."""
        return await self.show(text, "error", auto_delete)

    async def loading(self, text: str) -> Message:
        """Show loading toast."""
        return await self.show(text, "loading")

    async def info(self, text: str, auto_delete: float = 5) -> Message:
        """Show info toast."""
        return await self.show(text, "info", auto_delete)

    # Specialized toasts for common operations
    async def fetching_metadata(self) -> Message:
        """Show 'fetching metadata' toast."""
        return await self.show("Fetching video metadata...", "search")

    async def download_started(self, title: str) -> Message:
        """Show download started toast."""
        return await self.show(f"Starting download: **{title}**", "download")

    async def upload_started(self) -> Message:
        """Show upload started toast."""
        return await self.show("Preparing upload...", "upload")

    async def processing(self, text: str = "Processing...") -> Message:
        """Show processing toast."""
        return await self.show(text, "loading")


def build_final_message(
    title: str,
    duration: Optional[str] = None,
    size: Optional[str] = None,
    quality: Optional[str] = None,
    user_mention: Optional[str] = None,
    gofile_link: Optional[str] = None
) -> str:
    """
    Build the final success message after upload.

    Args:
        title: Video title
        duration: Formatted duration
        size: Formatted file size
        quality: Video quality
        user_mention: Markdown user mention
        gofile_link: Gofile download link (if uploaded there)

    Returns:
        Formatted message string
    """
    lines = ["✅ **Download Complete**", ""]

    lines.append(f"**Title:** {title}")

    if duration:
        lines.append(f"**Duration:** {duration}")

    if size:
        lines.append(f"**Size:** {size}")

    if quality:
        lines.append(f"**Quality:** {quality}")

    if gofile_link:
        lines.append("")
        lines.append(f"📁 **Download Link:** [Gofile]({gofile_link})")
        lines.append("_(File was too large for Telegram)_")

    if user_mention:
        lines.append("")
        lines.append(f"**Requested by:** {user_mention}")

    return "\n".join(lines)
