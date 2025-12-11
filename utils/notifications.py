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


def build_detailed_caption(
    title: str,
    show_title: Optional[str] = None,
    season: Optional[int] = None,
    episode: Optional[int] = None,
    episode_title: Optional[str] = None,
    duration: Optional[str] = None,
    size: Optional[str] = None,
    quality: Optional[str] = None,
    audio_languages: Optional[list] = None,
    description: Optional[str] = None,
    genres: Optional[list] = None,
    release_year: Optional[int] = None,
    rating: Optional[str] = None,
    is_movie: bool = False,
    user_mention: Optional[str] = None,
    gofile_link: Optional[str] = None,
    audio_count: int = 0,
    subtitle_count: int = 0,
    channel_tag: Optional[str] = None,
    mediainfo_link: Optional[str] = None
) -> str:
    """
    Build detailed caption with all video information.

    New format:
    ◉ Title: Show Name
    ◉ Episode: 10
    ◉ Type: (Tri-Audio) (Multi-Subs)[3]
    🌟: [1080p]
    🔗 @CHANNEL

    Args:
        title: Video/Episode title
        show_title: Show title (for episodes)
        season: Season number
        episode: Episode number
        episode_title: Episode title
        duration: Formatted duration
        size: Formatted file size
        quality: Video quality (e.g., "1080p")
        audio_languages: List of audio language names
        description: Video description
        genres: List of genres
        release_year: Release year
        rating: Content rating
        is_movie: True if movie, False if episode
        user_mention: Markdown user mention
        gofile_link: Gofile download link (if uploaded there)
        audio_count: Number of audio tracks
        subtitle_count: Number of subtitle tracks
        channel_tag: Channel tag to display (e.g., "@THECIDANIME")
        mediainfo_link: Telegraph link with detailed mediainfo

    Returns:
        Formatted caption string
    """
    lines = []

    # Title
    display_title = show_title or title
    lines.append(f"◉ Title: {display_title}")

    # Episode info
    if not is_movie and episode is not None:
        lines.append(f"◉ Episode: {episode}")

    # Type label (audio and subtitles) with mediainfo link
    type_parts = []
    if audio_count >= 2:
        if audio_count == 2:
            type_parts.append("(Dual-Audio)")
        elif audio_count == 3:
            type_parts.append("(Tri-Audio)")
        elif audio_count == 4:
            type_parts.append("(Quad-Audio)")
        else:
            type_parts.append(f"({audio_count}-Audio)")

    if subtitle_count > 0:
        if subtitle_count == 1:
            type_parts.append("(Subs)")
        else:
            type_parts.append(f"(Multi-Subs)[{subtitle_count}]")

    if type_parts:
        type_text = ' '.join(type_parts)
        if mediainfo_link:
            lines.append(f"◉ Type: [{type_text}]({mediainfo_link})")
        else:
            lines.append(f"◉ Type: {type_text}")

    # Quality
    if quality:
        lines.append(f"🌟: [{quality}]")

    # Channel tag or user mention
    if channel_tag:
        lines.append(f"🔗 {channel_tag}")
    elif user_mention:
        lines.append(f"🔗 {user_mention}")

    # Gofile link if applicable
    if gofile_link:
        lines.append("")
        lines.append(f"📁 Download: {gofile_link}")

    return "\n".join(lines)


def build_detailed_caption_full(
    title: str,
    show_title: Optional[str] = None,
    season: Optional[int] = None,
    episode: Optional[int] = None,
    episode_title: Optional[str] = None,
    duration: Optional[str] = None,
    size: Optional[str] = None,
    quality: Optional[str] = None,
    audio_languages: Optional[list] = None,
    description: Optional[str] = None,
    genres: Optional[list] = None,
    release_year: Optional[int] = None,
    rating: Optional[str] = None,
    is_movie: bool = False,
    user_mention: Optional[str] = None,
    gofile_link: Optional[str] = None
) -> str:
    """
    Build detailed caption with all video information (full format).

    Args:
        title: Video/Episode title
        show_title: Show title (for episodes)
        season: Season number
        episode: Episode number
        episode_title: Episode title
        duration: Formatted duration
        size: Formatted file size
        quality: Video quality
        audio_languages: List of audio language names
        description: Video description
        genres: List of genres
        release_year: Release year
        rating: Content rating
        is_movie: True if movie, False if episode
        user_mention: Markdown user mention
        gofile_link: Gofile download link (if uploaded there)

    Returns:
        Formatted caption string
    """
    lines = []

    # Title section
    if is_movie:
        lines.append(f"🎬 **{title}**")
    else:
        if show_title:
            lines.append(f"📺 **{show_title}**")
        if season is not None and episode is not None:
            lines.append(f"📍 Season {season} | Episode {episode}")
        if episode_title and episode_title != title:
            lines.append(f"📝 _{episode_title}_")

    lines.append("")

    # Video info section
    lines.append("**Video Info:**")

    if quality:
        lines.append(f"├ Quality: `{quality}`")

    if duration:
        lines.append(f"├ Duration: `{duration}`")

    if size:
        lines.append(f"├ Size: `{size}`")

    if audio_languages:
        audio_str = ", ".join(audio_languages[:5])
        if len(audio_languages) > 5:
            audio_str += f" +{len(audio_languages) - 5} more"
        lines.append(f"└ Audio: `{audio_str}`")

    # Additional info
    if genres or release_year or rating:
        lines.append("")
        lines.append("**Details:**")

        if release_year:
            lines.append(f"├ Year: `{release_year}`")

        if genres:
            lines.append(f"├ Genre: `{', '.join(genres[:3])}`")

        if rating:
            lines.append(f"└ Rating: `{rating}`")

    # Description (truncated)
    if description:
        lines.append("")
        desc = description[:200] + "..." if len(description) > 200 else description
        lines.append(f"_{desc}_")

    # Gofile link if applicable
    if gofile_link:
        lines.append("")
        lines.append(f"📁 **Download:** [Gofile Link]({gofile_link})")
        lines.append("_(File exceeded Telegram's 2GB limit)_")

    # Requested by
    if user_mention:
        lines.append("")
        lines.append(f"👤 {user_mention}")

    return "\n".join(lines)


def build_upload_caption(
    title: str,
    filename: str,
    size: Optional[str] = None,
    user_mention: Optional[str] = None,
    gofile_link: Optional[str] = None
) -> str:
    """
    Build caption for user-uploaded files.

    Args:
        title: File title/name
        filename: Original filename
        size: Formatted file size
        user_mention: User mention
        gofile_link: Gofile link if uploaded there

    Returns:
        Formatted caption
    """
    lines = [f"📁 **{title}**", ""]

    lines.append(f"**Filename:** `{filename}`")

    if size:
        lines.append(f"**Size:** `{size}`")

    if gofile_link:
        lines.append("")
        lines.append(f"🔗 **Download:** [Gofile Link]({gofile_link})")

    if user_mention:
        lines.append("")
        lines.append(f"👤 Uploaded by: {user_mention}")

    return "\n".join(lines)
