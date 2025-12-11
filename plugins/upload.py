"""
Video and document upload handler.

Allows users to upload their own video/document files which will be
re-uploaded with progress tracking and optional Gofile support for large files.
"""

import os
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from core.middlewares import authorized
from core.database import db
from config import DOWNLOAD_DIR
from services.uploader import Uploader
from services.thumbnail import ThumbnailService
from utils.progress import UploadProgress
from utils.formatters import format_size, format_user_mention
from utils.notifications import Toast, build_upload_caption


# Maximum file size to process (4GB)
MAX_FILE_SIZE = 4 * 1024 * 1024 * 1024

# Supported video extensions
VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.avi', '.mov', '.webm', '.flv', '.wmv', '.m4v'}

# Supported document extensions (for re-upload)
DOCUMENT_EXTENSIONS = {'.pdf', '.zip', '.rar', '.7z', '.tar', '.gz'}


@Client.on_message(filters.video & filters.private)
@authorized
async def handle_video_upload(client: Client, message: Message):
    """Handle video file uploads from users."""
    user_id = message.from_user.id
    video = message.video

    # Check file size
    if video.file_size > MAX_FILE_SIZE:
        await message.reply_text(
            f"**File too large**\n\n"
            f"Maximum supported size is 4GB.\n"
            f"Your file: {format_size(video.file_size)}"
        )
        return

    # Get user settings
    settings = await db.get_user_settings(user_id)
    gofile_token = settings.get('gofile_token')
    custom_thumbnail = settings.get('custom_thumbnail')

    # Create toast for status
    toast = Toast(client, message.chat.id)
    await toast.loading("Processing video...")

    try:
        # Download the video
        await toast.show("Downloading video from Telegram...", "download")

        file_name = video.file_name or f"video_{message.id}.mp4"
        download_path = os.path.join(DOWNLOAD_DIR, f"{user_id}_{file_name}")

        await message.download(file_name=download_path)

        if not os.path.exists(download_path):
            await toast.error("Failed to download video.")
            return

        file_size = os.path.getsize(download_path)

        # Create progress message for upload
        progress_msg = await client.send_message(
            chat_id=message.chat.id,
            text=f"**Preparing upload...**\n\n📁 {file_name}\n💾 {format_size(file_size)}"
        )

        await toast.dismiss()

        upload_progress = UploadProgress(progress_msg)

        # Get thumbnail
        thumb_service = ThumbnailService(client)
        thumb_path = None

        if custom_thumbnail:
            thumb_path = await thumb_service.get_thumbnail(
                user_id=user_id,
                custom_file_id=custom_thumbnail,
                filename=f"upload_{message.id}"
            )

        # Build caption
        caption = build_upload_caption(
            title=os.path.splitext(file_name)[0],
            filename=file_name,
            size=format_size(file_size),
            user_mention=format_user_mention(user_id, message.from_user.first_name)
        )

        # Upload
        uploader = Uploader(client)
        result = await uploader.upload(
            chat_id=message.chat.id,
            file_path=download_path,
            caption=caption,
            thumb_path=thumb_path,
            duration=video.duration,
            gofile_token=gofile_token,
            progress_callback=upload_progress.callback
        )

        if result.success:
            if result.platform == "gofile":
                final_caption = build_upload_caption(
                    title=os.path.splitext(file_name)[0],
                    filename=file_name,
                    size=format_size(file_size),
                    user_mention=format_user_mention(user_id, message.from_user.first_name),
                    gofile_link=result.gofile_link
                )
                await progress_msg.edit_text(final_caption, disable_web_page_preview=True)
            else:
                await progress_msg.delete()
        else:
            await progress_msg.edit_text(f"**Upload failed**\n\n{result.error or 'Unknown error'}")

    except Exception as e:
        await toast.error(f"Error: {str(e)[:100]}")

    finally:
        # Cleanup
        if 'download_path' in locals() and os.path.exists(download_path):
            try:
                os.remove(download_path)
            except Exception:
                pass

        if 'thumb_path' in locals() and thumb_path and os.path.exists(thumb_path):
            try:
                os.remove(thumb_path)
            except Exception:
                pass


@Client.on_message(filters.document & filters.private)
@authorized
async def handle_document_upload(client: Client, message: Message):
    """Handle document file uploads from users."""
    user_id = message.from_user.id
    document = message.document

    # Skip cookie files (handled by auth.py)
    if document.file_name and document.file_name.endswith('.txt'):
        # Let auth.py handle .txt files
        return

    # Get file extension
    file_name = document.file_name or f"document_{message.id}"
    _, ext = os.path.splitext(file_name.lower())

    # Check if it's a video file sent as document
    is_video = ext in VIDEO_EXTENSIONS

    # Check file size
    if document.file_size > MAX_FILE_SIZE:
        await message.reply_text(
            f"**File too large**\n\n"
            f"Maximum supported size is 4GB.\n"
            f"Your file: {format_size(document.file_size)}"
        )
        return

    # Get user settings
    settings = await db.get_user_settings(user_id)
    gofile_token = settings.get('gofile_token')
    custom_thumbnail = settings.get('custom_thumbnail')

    # Create toast for status
    toast = Toast(client, message.chat.id)
    await toast.loading("Processing file...")

    try:
        # Download the document
        await toast.show("Downloading file from Telegram...", "download")

        download_path = os.path.join(DOWNLOAD_DIR, f"{user_id}_{file_name}")
        await message.download(file_name=download_path)

        if not os.path.exists(download_path):
            await toast.error("Failed to download file.")
            return

        file_size = os.path.getsize(download_path)

        # Create progress message
        progress_msg = await client.send_message(
            chat_id=message.chat.id,
            text=f"**Preparing upload...**\n\n📁 {file_name}\n💾 {format_size(file_size)}"
        )

        await toast.dismiss()

        upload_progress = UploadProgress(progress_msg)

        # Get thumbnail for videos
        thumb_path = None
        duration = None

        if is_video:
            thumb_service = ThumbnailService(client)
            if custom_thumbnail:
                thumb_path = await thumb_service.get_thumbnail(
                    user_id=user_id,
                    custom_file_id=custom_thumbnail,
                    filename=f"upload_{message.id}"
                )

            # Try to get duration
            from services.downloader import get_video_duration
            duration = await get_video_duration(download_path)

        # Build caption
        caption = build_upload_caption(
            title=os.path.splitext(file_name)[0],
            filename=file_name,
            size=format_size(file_size),
            user_mention=format_user_mention(user_id, message.from_user.first_name)
        )

        # Upload
        uploader = Uploader(client)

        if is_video:
            result = await uploader.upload(
                chat_id=message.chat.id,
                file_path=download_path,
                caption=caption,
                thumb_path=thumb_path,
                duration=duration,
                gofile_token=gofile_token,
                progress_callback=upload_progress.callback
            )
        else:
            # For non-video documents, upload to Gofile if large or re-send as document
            if file_size > 2 * 1024 * 1024 * 1024:  # > 2GB
                result = await uploader.gofile.upload(
                    file_path=download_path,
                    token=gofile_token,
                    progress_callback=lambda p: asyncio.create_task(upload_progress.callback(int(p * file_size / 100), file_size))
                )
            else:
                # Re-send as document
                try:
                    await client.send_document(
                        chat_id=message.chat.id,
                        document=download_path,
                        caption=caption,
                        progress=upload_progress.callback
                    )
                    result = type('Result', (), {'success': True, 'platform': 'telegram'})()
                except Exception as e:
                    result = type('Result', (), {'success': False, 'error': str(e)})()

        if result.success:
            if hasattr(result, 'platform') and result.platform == "gofile":
                final_caption = build_upload_caption(
                    title=os.path.splitext(file_name)[0],
                    filename=file_name,
                    size=format_size(file_size),
                    user_mention=format_user_mention(user_id, message.from_user.first_name),
                    gofile_link=result.gofile_link if hasattr(result, 'gofile_link') else None
                )
                await progress_msg.edit_text(final_caption, disable_web_page_preview=True)
            else:
                await progress_msg.delete()
        else:
            error_msg = result.error if hasattr(result, 'error') else 'Unknown error'
            await progress_msg.edit_text(f"**Upload failed**\n\n{error_msg}")

    except Exception as e:
        await toast.error(f"Error: {str(e)[:100]}")

    finally:
        # Cleanup
        if 'download_path' in locals() and os.path.exists(download_path):
            try:
                os.remove(download_path)
            except Exception:
                pass

        if 'thumb_path' in locals() and thumb_path and os.path.exists(thumb_path):
            try:
                os.remove(thumb_path)
            except Exception:
                pass
