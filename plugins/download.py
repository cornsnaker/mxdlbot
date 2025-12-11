"""
Download handler for MX Player links with quality selection wizard and queue system.
Supports max 2 concurrent downloads per user with queue management.
"""

import os
import re
import asyncio
from pyrogram import Client, filters
from pyrogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from core.middlewares import authorized
from core.database import db
from config import (
    get_user_cookies_path, user_has_cookies,
    DOWNLOAD_DIR
)
from states import get_state, set_state, clear_state, UserStep
from services.mx_scraper import mx_scraper, VideoMetadata, AudioTrack
from services.downloader import downloader, sanitize_filename, generate_filename, get_video_duration, clean_download_directory
from services.uploader import Uploader
from services.thumbnail import ThumbnailService
from services.queue import download_queue, QueueItem, QueueItemStatus
from utils.progress import DownloadProgress, UploadProgress
from utils.formatters import format_size, format_duration, format_user_mention
from utils.notifications import Toast, build_final_message, build_detailed_caption
from utils.mediainfo import extract_media_info
from services.telegraph import create_telegraph_page


# MX Player URL pattern
MX_PATTERN = re.compile(r'https?://[^\s]*mxplayer\.in[^\s]*')

# Store client reference for queue processing
_client: Client = None


def build_resolution_keyboard(resolutions: list) -> InlineKeyboardMarkup:
    """Build inline keyboard for resolution selection."""
    buttons = []
    row = []

    for res in resolutions:
        btn_text = f"📺 {res['label']}"
        callback_data = f"res:{res['height']}"
        row.append(InlineKeyboardButton(btn_text, callback_data=callback_data))

        if len(row) == 2:
            buttons.append(row)
            row = []

    if row:
        buttons.append(row)

    # Add "Best Quality" option if not present
    has_best = any(r['label'].lower() == 'best' for r in resolutions)
    if not has_best and resolutions:
        buttons.append([
            InlineKeyboardButton("🏆 Best Quality", callback_data="res:best")
        ])

    # Cancel button
    buttons.append([
        InlineKeyboardButton("❌ Cancel", callback_data="dl_cancel")
    ])

    return InlineKeyboardMarkup(buttons)


def build_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Build confirmation keyboard."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⬇️ Start Download", callback_data="dl_start")
        ],
        [
            InlineKeyboardButton("⬅️ Back", callback_data="dl_back"),
            InlineKeyboardButton("❌ Cancel", callback_data="dl_cancel")
        ]
    ])


def format_metadata_caption(metadata: VideoMetadata, step: str = None) -> str:
    """Format metadata as caption."""
    lines = [f"🎬 **{metadata.title}**"]

    if not metadata.is_movie:
        if metadata.season and metadata.episode:
            lines.append(f"📅 Season {metadata.season} | Episode {metadata.episode}")
        if metadata.episode_title:
            lines.append(f"📝 {metadata.episode_title}")

    if metadata.duration:
        lines.append(f"⏱️ Duration: {format_duration(metadata.duration)}")

    if metadata.description and len(metadata.description) < 200:
        lines.append("")
        lines.append(f"_{metadata.description[:150]}..._" if len(metadata.description) > 150 else f"_{metadata.description}_")

    if step:
        lines.append("")
        lines.append(f"**{step}**")

    return "\n".join(lines)


def format_queue_status(user_id: int) -> str:
    """Format queue status message for user with task IDs."""
    status = download_queue.get_user_queue_status(user_id)

    lines = ["📊 **Your Queue Status**", ""]

    if status["active_count"] > 0:
        lines.append(f"🔄 **Active Downloads:** {status['active_count']}/{download_queue.MAX_CONCURRENT_PER_USER}")
        for item in status["active_items"]:
            lines.append(f"  `{item['id']}` - {item['title'][:35]}... ({item['status']})")

    if status["pending_count"] > 0:
        lines.append("")
        lines.append(f"⏳ **Queued:** {status['pending_count']}")
        for item in status["pending_items"]:
            lines.append(f"  `{item['id']}` - #{item['position']}: {item['title'][:35]}...")
        lines.append("")
        lines.append("💡 Cancel with: `/canceltask DL-XXXX`")

    if status["active_count"] == 0 and status["pending_count"] == 0:
        lines.append("No active or queued downloads.")

    return "\n".join(lines)


async def process_queue_item(item: QueueItem) -> None:
    """
    Process a single queue item (called by queue worker).

    Args:
        item: The QueueItem to process
    """
    global _client

    if not _client:
        print("[Queue] No client available for processing")
        item.status = QueueItemStatus.FAILED
        item.error = "Bot not ready"
        return

    client = _client
    metadata_dict = item.metadata
    user_id = item.user_id
    chat_id = item.chat_id

    # Create progress message
    progress_msg = await client.send_message(
        chat_id=chat_id,
        text=f"⬇️ **Starting download...**\n\n{metadata_dict['title']}"
    )

    item.progress_message_id = progress_msg.id

    download_progress = DownloadProgress(progress_msg)
    upload_progress = UploadProgress(progress_msg)

    result = None
    thumb_path = None

    try:
        # Generate filename
        filename = sanitize_filename(metadata_dict['title'])
        if not metadata_dict['is_movie'] and metadata_dict.get('season') and metadata_dict.get('episode'):
            filename = f"{filename}_S{metadata_dict['season']:02d}E{metadata_dict['episode']:02d}"

        # Download (clean_download_directory is called inside downloader.download)
        result = await downloader.download(
            m3u8_url=metadata_dict['m3u8_url'],
            filename=filename,
            cookies_path=item.cookies_path,
            resolution=item.resolution if item.resolution != "best" else None,
            output_format=item.output_format,
            progress_callback=download_progress.callback
        )

        if not result.success:
            await progress_msg.edit_text(f"❌ **Download failed**\n\n{result.error or 'Unknown error'}")
            item.status = QueueItemStatus.FAILED
            item.error = result.error
            return

        # Update status to uploading
        item.status = QueueItemStatus.UPLOADING
        await progress_msg.edit_text(f"⬆️ **Preparing upload...**\n\n{metadata_dict['title']}")

        # Get video duration
        duration = await get_video_duration(result.file_path) or metadata_dict.get('duration')

        # Get thumbnail
        thumb_service = ThumbnailService(client)
        thumb_path = await thumb_service.get_thumbnail(
            user_id=user_id,
            custom_file_id=item.custom_thumbnail,
            fallback_url=metadata_dict.get('image'),
            filename=filename
        )

        # Extract media info using pymediainfo
        media_info = extract_media_info(result.file_path)
        audio_count = len(media_info.audio_tracks) if media_info else 0
        subtitle_count = media_info.subtitle_count if media_info else 0
        quality_label = media_info.quality_label if media_info and media_info.height else (f"{item.resolution}p" if item.resolution and item.resolution != "best" else "Best")

        # Generate clean filename with audio info and rename file
        clean_filename = generate_filename(
            title=metadata_dict['title'],
            audio_count=audio_count,
            season=metadata_dict.get('season') if not metadata_dict['is_movie'] else None,
            episode=metadata_dict.get('episode') if not metadata_dict['is_movie'] else None
        )
        new_file_path = os.path.join(DOWNLOAD_DIR, f"{clean_filename}.{item.output_format}")

        # Rename the file if paths are different
        if result.file_path != new_file_path:
            try:
                if os.path.exists(new_file_path):
                    os.remove(new_file_path)
                os.rename(result.file_path, new_file_path)
                result.file_path = new_file_path
            except Exception as e:
                print(f"[Download] Could not rename file: {e}")

        # Create Telegraph page for mediainfo
        mediainfo_link = None
        if media_info and (audio_count > 0 or subtitle_count > 0):
            try:
                mediainfo_link = await create_telegraph_page(
                    title=metadata_dict['title'],
                    media_info=media_info,
                    file_path=result.file_path
                )
            except Exception as e:
                print(f"[Download] Telegraph error: {e}")

        # Build detailed caption
        caption = build_detailed_caption(
            title=metadata_dict['title'],
            show_title=metadata_dict['title'] if not metadata_dict['is_movie'] else None,
            season=metadata_dict.get('season'),
            episode=metadata_dict.get('episode'),
            episode_title=metadata_dict.get('episode_title'),
            quality=quality_label,
            is_movie=metadata_dict['is_movie'],
            user_mention=format_user_mention(user_id, item.user_name),
            audio_count=audio_count,
            subtitle_count=subtitle_count,
            mediainfo_link=mediainfo_link
        )

        # Upload
        uploader = Uploader(client)
        upload_result = await uploader.upload(
            chat_id=chat_id,
            file_path=result.file_path,
            caption=caption,
            thumb_path=thumb_path,
            duration=duration,
            gofile_token=item.gofile_token,
            upload_mode=item.upload_mode,
            progress_callback=upload_progress.callback
        )

        if upload_result.success:
            item.status = QueueItemStatus.COMPLETED
            if upload_result.platform == "gofile":
                final_text = build_detailed_caption(
                    title=metadata_dict['title'],
                    show_title=metadata_dict['title'] if not metadata_dict['is_movie'] else None,
                    season=metadata_dict.get('season'),
                    episode=metadata_dict.get('episode'),
                    episode_title=metadata_dict.get('episode_title'),
                    quality=quality_label,
                    is_movie=metadata_dict['is_movie'],
                    user_mention=format_user_mention(user_id, item.user_name),
                    audio_count=audio_count,
                    subtitle_count=subtitle_count,
                    mediainfo_link=mediainfo_link,
                    gofile_link=upload_result.gofile_link
                )
                await progress_msg.edit_text(final_text, disable_web_page_preview=True)
            else:
                await progress_msg.delete()
        else:
            item.status = QueueItemStatus.FAILED
            item.error = upload_result.error
            await progress_msg.edit_text(f"❌ **Upload failed**\n\n{upload_result.error or 'Unknown error'}")

    except Exception as e:
        item.status = QueueItemStatus.FAILED
        item.error = str(e)
        try:
            await progress_msg.edit_text(f"❌ **Error**\n\n{str(e)[:200]}")
        except Exception:
            pass

    finally:
        # Cleanup
        clear_state(user_id)

        # Remove thumbnail
        if thumb_path and os.path.exists(thumb_path):
            try:
                os.remove(thumb_path)
            except Exception:
                pass

        # Clean up entire download directory
        clean_download_directory()


# Initialize queue with download handler
download_queue.set_download_handler(process_queue_item)


@Client.on_message(filters.text & filters.private & ~filters.command(["start", "help", "auth", "settings", "cancel", "broadcast", "stats", "ban", "unban", "banlist", "users", "addadmin", "removeadmin", "admins", "queue"]))
@authorized
async def handle_link(client: Client, message: Message):
    """Handle MX Player link messages."""
    global _client
    _client = client

    user_id = message.from_user.id
    text = message.text

    # Check if it's an MX Player link
    match = MX_PATTERN.search(text)
    if not match:
        return

    url = match.group(0)

    # Check if user has cookies
    if not user_has_cookies(user_id):
        await message.reply_text(
            "**Authentication Required**\n\n"
            "You need to upload your cookies first.\n"
            "Use /auth to get started."
        )
        return

    # Check if user is already selecting quality
    state = get_state(user_id)
    if state.step not in [UserStep.IDLE, UserStep.WAITING_COOKIES]:
        await message.reply_text(
            "**Already processing**\n\n"
            "Please wait for the current operation to complete or use /cancel."
        )
        return

    # Create toast for status updates
    toast = Toast(client, message.chat.id)
    await toast.fetching_metadata()

    try:
        # Fetch metadata
        metadata = await mx_scraper.get_metadata(url)

        if not metadata:
            await toast.error("Could not fetch video metadata. Check the link.")
            return

        if not metadata.m3u8_url:
            await toast.error("Video stream not found. Content may be DRM protected.")
            return

        # Parse resolutions and audio tracks from m3u8
        resolutions = await mx_scraper.parse_master_m3u8(metadata.m3u8_url)
        audio_tracks = await mx_scraper.parse_audio_tracks(metadata.m3u8_url)

        # Store state with audio info
        set_state(
            user_id,
            step=UserStep.SELECT_QUALITY,
            url=url,
            metadata={
                'title': metadata.title,
                'description': metadata.description,
                'image': metadata.image,
                'season': metadata.season,
                'episode': metadata.episode,
                'episode_title': metadata.episode_title,
                'is_movie': metadata.is_movie,
                'm3u8_url': metadata.m3u8_url,
                'duration': metadata.duration,
                'genres': metadata.genres,
                'release_year': metadata.release_year,
                'rating': metadata.rating,
                'audio_tracks': [{'name': t.name, 'language': t.language} for t in audio_tracks]
            },
            resolutions=[{'height': r.height, 'label': r.label, 'bandwidth': r.bandwidth} for r in resolutions]
        )

        # Build caption and keyboard
        caption = format_metadata_caption(metadata, step="Step 1: Select video quality")

        if resolutions:
            keyboard = build_resolution_keyboard(
                [{'height': r.height, 'label': r.label} for r in resolutions]
            )
        else:
            # No resolutions found, go directly to confirmation
            set_state(user_id, step=UserStep.CONFIRMATION, selected_resolution="best")
            caption = format_metadata_caption(metadata, step="Ready to download (Best Quality)")
            keyboard = build_confirmation_keyboard()

        # Send selection message with thumbnail
        if metadata.image:
            try:
                selection_msg = await client.send_photo(
                    chat_id=message.chat.id,
                    photo=metadata.image,
                    caption=caption,
                    reply_markup=keyboard
                )
            except Exception:
                selection_msg = await message.reply_text(caption, reply_markup=keyboard)
        else:
            selection_msg = await message.reply_text(caption, reply_markup=keyboard)

        # Store message ID for editing
        set_state(user_id, message_id=selection_msg.id)

        # Dismiss the loading toast
        await toast.dismiss()

    except Exception as e:
        await toast.error(f"Error: {str(e)[:100]}")
        clear_state(user_id)


@Client.on_callback_query(filters.regex(r"^res:(.+)$"))
@authorized
async def callback_resolution(client: Client, callback: CallbackQuery):
    """Handle resolution selection callback."""
    user_id = callback.from_user.id
    state = get_state(user_id)

    if state.step != UserStep.SELECT_QUALITY:
        await callback.answer("Session expired. Send the link again.", show_alert=True)
        return

    resolution = callback.matches[0].group(1)

    # Store selection and move to confirmation
    set_state(user_id, step=UserStep.CONFIRMATION, selected_resolution=resolution)

    # Get metadata for caption
    metadata_dict = state.metadata
    metadata = VideoMetadata(
        title=metadata_dict['title'],
        description=metadata_dict['description'],
        image=metadata_dict['image'],
        season=metadata_dict['season'],
        episode=metadata_dict['episode'],
        episode_title=metadata_dict['episode_title'],
        is_movie=metadata_dict['is_movie'],
        m3u8_url=metadata_dict['m3u8_url'],
        duration=metadata_dict['duration']
    )

    # Format quality label
    quality_label = f"{resolution}p" if resolution != "best" else "Best Quality"

    # Show queue status in confirmation
    queue_status = download_queue.get_user_queue_status(user_id)
    queue_info = ""
    if queue_status["active_count"] > 0:
        queue_info = f"\n📊 Queue: {queue_status['active_count']} active, {queue_status['pending_count']} pending"

    caption = format_metadata_caption(metadata)
    caption += f"\n\n✅ **Ready to download**\n📺 Quality: {quality_label}\n🔊 Audio: All languages{queue_info}\n\nTap Start to begin."

    keyboard = build_confirmation_keyboard()

    try:
        await callback.message.edit_caption(caption=caption, reply_markup=keyboard)
    except Exception:
        await callback.message.edit_text(caption, reply_markup=keyboard)

    await callback.answer()


@Client.on_callback_query(filters.regex("^dl_back$"))
@authorized
async def callback_back(client: Client, callback: CallbackQuery):
    """Handle back button in download wizard."""
    user_id = callback.from_user.id
    state = get_state(user_id)

    if state.step == UserStep.CONFIRMATION:
        # Go back to quality selection
        set_state(user_id, step=UserStep.SELECT_QUALITY)

        metadata_dict = state.metadata
        metadata = VideoMetadata(
            title=metadata_dict['title'],
            description=metadata_dict['description'],
            image=metadata_dict['image'],
            season=metadata_dict['season'],
            episode=metadata_dict['episode'],
            episode_title=metadata_dict['episode_title'],
            is_movie=metadata_dict['is_movie'],
            m3u8_url=metadata_dict['m3u8_url'],
            duration=metadata_dict['duration']
        )

        caption = format_metadata_caption(metadata, step="Step 1: Select video quality")
        keyboard = build_resolution_keyboard(state.resolutions or [])

        try:
            await callback.message.edit_caption(caption=caption, reply_markup=keyboard)
        except Exception:
            await callback.message.edit_text(caption, reply_markup=keyboard)

    await callback.answer()


@Client.on_callback_query(filters.regex("^dl_cancel$"))
@authorized
async def callback_cancel(client: Client, callback: CallbackQuery):
    """Handle cancel button in download wizard."""
    user_id = callback.from_user.id

    clear_state(user_id)

    try:
        await callback.message.delete()
    except Exception:
        await callback.message.edit_text("❌ Cancelled")

    await callback.answer("Cancelled")


@Client.on_callback_query(filters.regex("^dl_start$"))
@authorized
async def callback_start_download(client: Client, callback: CallbackQuery):
    """Handle start download button - adds to queue."""
    global _client
    _client = client

    user_id = callback.from_user.id
    state = get_state(user_id)

    if state.step != UserStep.CONFIRMATION:
        await callback.answer("Session expired. Send the link again.", show_alert=True)
        return

    # Check if user is at the queue limit
    queue_status = download_queue.get_user_queue_status(user_id)
    total_user_downloads = queue_status["active_count"] + queue_status["pending_count"]

    if total_user_downloads >= download_queue.MAX_CONCURRENT_PER_USER * 2:
        await callback.answer(
            f"You have {total_user_downloads} downloads queued. Please wait for some to complete.",
            show_alert=True
        )
        return

    # Get user settings
    settings = await db.get_user_settings(user_id)
    output_format = settings.get('output_format', 'mp4')
    upload_mode = settings.get('upload_mode', 'video')
    gofile_token = settings.get('gofile_token')
    custom_thumbnail = settings.get('custom_thumbnail')

    metadata_dict = state.metadata
    resolution = state.selected_resolution
    cookies_path = get_user_cookies_path(user_id)

    # Clear the selection state
    clear_state(user_id)

    # Delete the selection message
    try:
        await callback.message.delete()
    except Exception:
        pass

    # Add to queue
    item, position = await download_queue.add(
        user_id=user_id,
        chat_id=callback.message.chat.id,
        metadata=metadata_dict,
        resolution=resolution,
        cookies_path=cookies_path,
        output_format=output_format,
        upload_mode=upload_mode,
        gofile_token=gofile_token,
        custom_thumbnail=custom_thumbnail,
        user_name=callback.from_user.first_name or ""
    )

    # Notify user
    if queue_status["active_count"] < download_queue.MAX_CONCURRENT_PER_USER:
        await callback.answer(f"Download starting... (Task: {item.id})")
    else:
        await callback.answer(f"Added to queue. Task: {item.id}")
        # Send queue position message with task ID
        await client.send_message(
            chat_id=callback.message.chat.id,
            text=f"⏳ **Added to queue**\n\n"
                 f"**Task ID:** `{item.id}`\n"
                 f"**Title:** {metadata_dict['title'][:50]}...\n"
                 f"**Position:** #{position}\n"
                 f"**Active downloads:** {queue_status['active_count']}/{download_queue.MAX_CONCURRENT_PER_USER}\n\n"
                 f"Your download will start when a slot becomes available.\n"
                 f"Cancel with: `/canceltask {item.id}`"
        )

    # Ensure queue worker is running
    await download_queue.start_worker()


@Client.on_message(filters.command("queue") & filters.private)
@authorized
async def cmd_queue(client: Client, message: Message):
    """Show user's queue status."""
    user_id = message.from_user.id
    status_text = format_queue_status(user_id)

    # Add global stats for info
    global_stats = download_queue.get_global_stats()
    status_text += f"\n\n📈 **Global:** {global_stats['active_downloads']} active, {global_stats['pending_downloads']} pending"

    await message.reply_text(status_text)


@Client.on_message(filters.command("cancelqueue") & filters.private)
@authorized
async def cmd_cancel_queue(client: Client, message: Message):
    """Cancel all pending downloads in user's queue."""
    user_id = message.from_user.id

    cancelled = await download_queue.cancel_user_downloads(user_id)

    if cancelled > 0:
        await message.reply_text(f"✅ Cancelled {cancelled} pending download(s).")
    else:
        await message.reply_text("No pending downloads to cancel.")


@Client.on_message(filters.command("canceltask") & filters.private)
@authorized
async def cmd_cancel_task(client: Client, message: Message):
    """Cancel a specific task by ID."""
    user_id = message.from_user.id

    # Parse task ID from command
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply_text(
            "**Usage:** `/canceltask DL-XXXX`\n\n"
            "Use /queue to see your task IDs."
        )
        return

    task_id = parts[1].strip().upper()

    # Validate task ID format
    if not task_id.startswith("DL-") or len(task_id) != 7:
        await message.reply_text(
            f"**Invalid task ID:** `{task_id}`\n\n"
            "Task IDs look like: `DL-A3X9`\n"
            "Use /queue to see your task IDs."
        )
        return

    # Try to cancel the task
    success, result_message = await download_queue.cancel(task_id, user_id)

    if success:
        await message.reply_text(f"✅ **Task Cancelled**\n\n{result_message}")
    else:
        await message.reply_text(f"❌ **Cannot Cancel**\n\n{result_message}")
