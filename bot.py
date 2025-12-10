"""
MX Player Telegram Bot - Pyrogram-based with tgcrypto acceleration.

Features:
- Per-user cookie authentication (/auth command)
- FSM-based interactive quality/audio selection wizard
- Dynamic m3u8 parsing for resolutions and audio tracks
- Real-time download/upload progress tracking
- tgcrypto-accelerated uploads via Pyrogram
"""

import asyncio
import os
import re
import logging
import time
import aiofiles
from typing import Dict, Optional

# Fix for Python 3.10+ asyncio event loop issue with Pyrogram
import sys
if sys.version_info >= (3, 10):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

from pyrogram import Client, filters
from pyrogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from pyrogram.errors import FloodWait

from config import (
    API_ID,
    API_HASH,
    BOT_TOKEN,
    DOWNLOAD_DIR,
    get_user_cookies_path,
    user_has_cookies
)
from states import (
    UserStep,
    UserState,
    get_state,
    set_state,
    clear_state
)
import mx_engine
from uploader import upload_with_progress, generate_progress_bar

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Pyrogram Client
app = Client(
    name="mxdlbot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# --- QUEUE SYSTEM ---
# Per-user queues for fair distribution
user_queues: Dict[int, asyncio.Queue] = {}
# Global flag for worker
worker_running = False


def get_user_queue(user_id: int) -> asyncio.Queue:
    """Get or create a queue for a user."""
    if user_id not in user_queues:
        user_queues[user_id] = asyncio.Queue()
    return user_queues[user_id]


# --- COOKIE VALIDATION ---
def validate_netscape_cookies(content: str) -> bool:
    """
    Validate that content is in Netscape cookie format.

    Netscape format: domain, flag, path, secure, expiry, name, value
    Lines starting with # are comments
    Lines must have tab-separated values
    """
    lines = content.strip().split('\n')
    valid_lines = 0

    for line in lines:
        line = line.strip()
        # Skip empty lines and comments
        if not line or line.startswith('#'):
            continue
        # Check for tab-separated values (at least 6 tabs for 7 fields)
        parts = line.split('\t')
        if len(parts) >= 7:
            valid_lines += 1

    # Must have at least one valid cookie line
    return valid_lines > 0


# --- KEYBOARD BUILDERS ---
def build_resolution_keyboard(resolutions: list) -> InlineKeyboardMarkup:
    """Build inline keyboard for resolution selection (Step 1)."""
    buttons = []
    row = []

    for res in resolutions:
        height = res.get('height', 0)
        label = f"📺 {height}p"
        callback = f"res:{height}"
        row.append(InlineKeyboardButton(text=label, callback_data=callback))

        # 2 buttons per row
        if len(row) == 2:
            buttons.append(row)
            row = []

    if row:
        buttons.append(row)

    # Cancel button
    buttons.append([InlineKeyboardButton(text="❌ Cancel", callback_data="cancel")])

    return InlineKeyboardMarkup(buttons)


def build_audio_keyboard(audio_tracks: list) -> InlineKeyboardMarkup:
    """Build inline keyboard for audio selection (Step 2)."""
    buttons = []
    row = []

    for idx, track in enumerate(audio_tracks):
        name = track.get('name', track.get('language', f'Track {idx+1}'))
        label = f"🔊 {name}"
        # Use index to identify track reliably
        callback = f"audio:{idx}"
        row.append(InlineKeyboardButton(text=label, callback_data=callback))

        # 2 buttons per row
        if len(row) == 2:
            buttons.append(row)
            row = []

    if row:
        buttons.append(row)

    # Back and Cancel buttons
    buttons.append([
        InlineKeyboardButton(text="⬅️ Back", callback_data="back"),
        InlineKeyboardButton(text="❌ Cancel", callback_data="cancel")
    ])

    return InlineKeyboardMarkup(buttons)


def build_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Build inline keyboard for confirmation (Step 3)."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(text="⬇️ Start Download", callback_data="start")],
        [
            InlineKeyboardButton(text="⬅️ Back", callback_data="back"),
            InlineKeyboardButton(text="❌ Cancel", callback_data="cancel")
        ]
    ])


# --- CAPTION BUILDERS ---
def build_step1_caption(metadata: dict) -> str:
    """Build caption for Step 1 (quality selection)."""
    caption = f"🎬 **{metadata['title']}**\n"
    if not metadata['is_movie']:
        caption += f"📅 Season: {metadata['season']} | Episode: {metadata['episode']}\n"
        if metadata.get('episode_title'):
            caption += f"📝 {metadata['episode_title']}\n"
    caption += "\n**Step 1/2:** Select video quality"
    return caption


def build_step2_caption(metadata: dict) -> str:
    """Build caption for Step 2 (audio selection)."""
    caption = f"🎬 **{metadata['title']}**\n"
    if not metadata['is_movie']:
        caption += f"📅 Season: {metadata['season']} | Episode: {metadata['episode']}\n"
    caption += "\n**Step 2/2:** Select audio language"
    return caption


def build_confirmation_caption(metadata: dict, resolution: str, audio: str) -> str:
    """Build caption for confirmation step."""
    caption = f"🎬 **{metadata['title']}**\n\n"
    caption += "✅ **Ready to download**\n"
    caption += f"📺 Quality: {resolution}p\n"
    caption += f"🔊 Audio: {audio}\n\n"
    caption += "Tap Start to begin downloading."
    return caption


# --- HANDLERS ---

@app.on_message(filters.command("start"))
async def cmd_start(client: Client, message: Message):
    """Handle /start command."""
    user_id = message.from_user.id

    # Clear any existing state
    clear_state(user_id)

    welcome_text = (
        "👋 **Welcome to MX Player Bot**\n\n"
        "Send me an MX Player link (Episode or Movie).\n\n"
        "**First time?** Use /auth to upload your cookies.txt\n\n"
        "**Features:**\n"
        "• Quality selection (1080p, 720p, etc.)\n"
        "• Audio language selection\n"
        "• Real-time progress tracking\n"
        "• Fast uploads with thumbnail"
    )

    await message.reply_text(welcome_text)


@app.on_message(filters.command("auth"))
async def cmd_auth(client: Client, message: Message):
    """Handle /auth command - initiate cookie upload flow."""
    user_id = message.from_user.id

    # Set state to waiting for cookies
    set_state(user_id, step=UserStep.WAITING_COOKIES)

    await message.reply_text(
        "📤 Send your `cookies.txt` file (Netscape format)\n\n"
        "**How to export:**\n"
        "1. Install 'Get cookies.txt' browser extension\n"
        "2. Visit mxplayer.in and log in\n"
        "3. Click extension and export cookies\n"
        "4. Send the file here"
    )


@app.on_message(filters.document & filters.private)
async def handle_document(client: Client, message: Message):
    """Handle document uploads (for cookie files)."""
    user_id = message.from_user.id
    state = get_state(user_id)

    # Only process if waiting for cookies
    if state.step != UserStep.WAITING_COOKIES:
        return

    document = message.document

    # Validate file extension
    if not document.file_name or not document.file_name.endswith('.txt'):
        await message.reply_text("❌ Please send a `.txt` file.")
        return

    # Validate file size (max 100KB)
    if document.file_size > 100 * 1024:
        await message.reply_text("❌ File too large. Maximum 100KB allowed.")
        return

    # Download and validate content
    try:
        file_path = await message.download()

        async with aiofiles.open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = await f.read()

        # Remove temp download
        os.remove(file_path)

        # Validate Netscape format
        if not validate_netscape_cookies(content):
            await message.reply_text(
                "❌ Invalid cookie format. Export as Netscape format from browser."
            )
            clear_state(user_id)
            return

        # Save to user's cookies file
        cookies_path = get_user_cookies_path(user_id)
        async with aiofiles.open(cookies_path, 'w', encoding='utf-8') as f:
            await f.write(content)

        # Reset state
        clear_state(user_id)

        await message.reply_text(
            "✅ Cookies saved! You can now download from MX Player.\n\n"
            "Send me an MX Player link to get started."
        )

    except Exception as e:
        logger.error(f"Error saving cookies for user {user_id}: {e}")
        await message.reply_text("❌ Failed to save cookies. Please try again.")
        clear_state(user_id)


@app.on_message(filters.regex(r'mxplayer\.in') & filters.private)
async def process_link(client: Client, message: Message):
    """Handle MX Player links."""
    user_id = message.from_user.id
    state = get_state(user_id)

    # Skip if user is in another flow
    if state.step not in [UserStep.IDLE, UserStep.SELECT_QUALITY]:
        return

    # Check for cookies first
    if not user_has_cookies(user_id):
        await message.reply_text(
            "❌ Authentication required. Use /auth to upload your cookies.txt first."
        )
        return

    # Extract URL from message
    url_match = re.search(r'https?://[^\s]+mxplayer\.in[^\s]*', message.text)
    if not url_match:
        await message.reply_text(
            "❌ Invalid MX Player link. Please send a valid episode or movie URL."
        )
        return

    url = url_match.group(0)

    # Show fetching status
    status_msg = await message.reply_text("🔍 **Fetching metadata...**")

    try:
        # Fetch metadata
        metadata = await mx_engine.get_metadata(url)

        if not metadata:
            await status_msg.edit_text(
                "❌ Could not fetch video info. The link may be expired or invalid."
            )
            return

        if not metadata.get('m3u8'):
            await status_msg.edit_text(
                "❌ Video stream not found. Content may be DRM protected or unavailable."
            )
            return

        # Parse m3u8 for resolutions and audio tracks
        resolutions, audio_tracks = await mx_engine.parse_master_m3u8(metadata['m3u8'])

        # Store state
        set_state(
            user_id,
            step=UserStep.SELECT_QUALITY,
            url=url,
            metadata=metadata,
            resolutions=resolutions,
            audio_tracks=audio_tracks
        )

        # Determine the flow based on available options
        skip_quality = len(resolutions) <= 1
        skip_audio = len(audio_tracks) <= 1

        if skip_quality and skip_audio:
            # Go directly to confirmation with defaults
            default_res = resolutions[0]['height'] if resolutions else "best"
            default_audio_name = audio_tracks[0].get('name', audio_tracks[0].get('language', 'Default')) if audio_tracks else "Default"

            set_state(
                user_id,
                step=UserStep.CONFIRMATION,
                selected_resolution=str(default_res),
                selected_audio=default_audio_name
            )

            caption = build_confirmation_caption(
                metadata,
                default_res if default_res != "best" else "Best",
                default_audio_name
            )
            keyboard = build_confirmation_keyboard()

        elif skip_quality:
            # Skip to audio selection
            default_res = resolutions[0]['height'] if resolutions else "best"
            set_state(
                user_id,
                step=UserStep.SELECT_AUDIO,
                selected_resolution=str(default_res)
            )

            caption = build_step2_caption(metadata)
            keyboard = build_audio_keyboard(audio_tracks)

        else:
            # Show quality selection (Step 1)
            caption = build_step1_caption(metadata)
            keyboard = build_resolution_keyboard(resolutions)

        # Delete status message and show selection UI
        await status_msg.delete()

        if metadata.get('image'):
            sent_msg = await message.reply_photo(
                photo=metadata['image'],
                caption=caption,
                reply_markup=keyboard
            )
        else:
            sent_msg = await message.reply_text(
                caption,
                reply_markup=keyboard
            )

        # Store message ID for editing
        set_state(user_id, message_id=sent_msg.id)

    except Exception as e:
        logger.error(f"Error processing link for user {user_id}: {e}")
        await status_msg.edit_text(f"⚠️ Error: {str(e)}")


@app.on_callback_query(filters.regex(r'^res:'))
async def callback_resolution(client: Client, callback: CallbackQuery):
    """Handle resolution selection callback."""
    user_id = callback.from_user.id
    state = get_state(user_id)

    # Validate state
    if state.step != UserStep.SELECT_QUALITY:
        await callback.answer("❌ Session expired. Please send the link again.")
        return

    # Extract resolution
    resolution = callback.data.split(':')[1]

    # Store selection
    set_state(user_id, selected_resolution=resolution)

    # Check if we need audio selection
    audio_tracks = state.audio_tracks or []

    if len(audio_tracks) <= 1:
        # Skip to confirmation
        default_audio_name = audio_tracks[0].get('name', audio_tracks[0].get('language', 'Default')) if audio_tracks else "Default"

        set_state(
            user_id,
            step=UserStep.CONFIRMATION,
            selected_audio=default_audio_name
        )

        caption = build_confirmation_caption(
            state.metadata,
            resolution,
            default_audio_name
        )
        keyboard = build_confirmation_keyboard()
    else:
        # Move to audio selection
        set_state(user_id, step=UserStep.SELECT_AUDIO)

        caption = build_step2_caption(state.metadata)
        keyboard = build_audio_keyboard(audio_tracks)

    # Edit message
    try:
        await callback.message.edit_caption(
            caption=caption,
            reply_markup=keyboard
        )
    except Exception:
        try:
            await callback.message.edit_text(
                text=caption,
                reply_markup=keyboard
            )
        except Exception as e:
            logger.error(f"Error editing message: {e}")

    await callback.answer()


@app.on_callback_query(filters.regex(r'^audio:'))
async def callback_audio(client: Client, callback: CallbackQuery):
    """Handle audio selection callback."""
    user_id = callback.from_user.id
    state = get_state(user_id)

    # Validate state
    if state.step != UserStep.SELECT_AUDIO:
        await callback.answer("❌ Session expired. Please send the link again.")
        return

    # Extract audio track index
    audio_idx = int(callback.data.split(':')[1])
    audio_tracks = state.audio_tracks or []

    # Get the selected track info
    if audio_idx < len(audio_tracks):
        selected_track = audio_tracks[audio_idx]
        audio_name = selected_track.get('name', selected_track.get('language', 'Default'))
    else:
        audio_name = "Default"
        selected_track = {}

    # Store selection and move to confirmation
    # Store the track name for N_m3u8DL-RE --select-audio
    set_state(
        user_id,
        step=UserStep.CONFIRMATION,
        selected_audio=audio_name
    )

    caption = build_confirmation_caption(
        state.metadata,
        state.selected_resolution,
        audio_name
    )
    keyboard = build_confirmation_keyboard()

    # Edit message
    try:
        await callback.message.edit_caption(
            caption=caption,
            reply_markup=keyboard
        )
    except Exception:
        try:
            await callback.message.edit_text(
                text=caption,
                reply_markup=keyboard
            )
        except Exception as e:
            logger.error(f"Error editing message: {e}")

    await callback.answer()


@app.on_callback_query(filters.regex(r'^back$'))
async def callback_back(client: Client, callback: CallbackQuery):
    """Handle back button callback."""
    user_id = callback.from_user.id
    state = get_state(user_id)

    if state.step == UserStep.SELECT_AUDIO:
        # Go back to quality selection
        set_state(user_id, step=UserStep.SELECT_QUALITY)

        caption = build_step1_caption(state.metadata)
        keyboard = build_resolution_keyboard(state.resolutions or [])

    elif state.step == UserStep.CONFIRMATION:
        # Go back to audio selection (or quality if no audio tracks)
        audio_tracks = state.audio_tracks or []

        if len(audio_tracks) <= 1:
            # Go back to quality selection
            set_state(user_id, step=UserStep.SELECT_QUALITY)
            caption = build_step1_caption(state.metadata)
            keyboard = build_resolution_keyboard(state.resolutions or [])
        else:
            # Go back to audio selection
            set_state(user_id, step=UserStep.SELECT_AUDIO)
            caption = build_step2_caption(state.metadata)
            keyboard = build_audio_keyboard(audio_tracks)
    else:
        await callback.answer("❌ Session expired.")
        return

    # Edit message
    try:
        await callback.message.edit_caption(
            caption=caption,
            reply_markup=keyboard
        )
    except Exception:
        try:
            await callback.message.edit_text(
                text=caption,
                reply_markup=keyboard
            )
        except Exception as e:
            logger.error(f"Error editing message: {e}")

    await callback.answer()


@app.on_callback_query(filters.regex(r'^cancel$'))
async def callback_cancel(client: Client, callback: CallbackQuery):
    """Handle cancel button callback."""
    user_id = callback.from_user.id

    # Clear state
    clear_state(user_id)

    # Update message
    try:
        await callback.message.edit_caption(
            caption="❌ **Cancelled**\n\nSend another link when ready.",
            reply_markup=None
        )
    except Exception:
        try:
            await callback.message.edit_text(
                text="❌ **Cancelled**\n\nSend another link when ready.",
                reply_markup=None
            )
        except Exception:
            pass

    await callback.answer("Cancelled")


@app.on_callback_query(filters.regex(r'^start$'))
async def callback_start_download(client: Client, callback: CallbackQuery):
    """Handle start download button callback."""
    user_id = callback.from_user.id
    state = get_state(user_id)

    # Validate state
    if state.step != UserStep.CONFIRMATION:
        await callback.answer("❌ Session expired. Please send the link again.")
        return

    chat_id = callback.message.chat.id

    # Remove buttons
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    # Get queue position
    queue = get_user_queue(user_id)
    position = queue.qsize()

    if position > 0:
        await callback.message.reply_text(
            f"⏳ Added to queue. Position: {position}"
        )

    # Add to queue
    await queue.put({
        "url": state.url,
        "metadata": state.metadata,
        "resolution": state.selected_resolution,
        "audio": state.selected_audio,
        "chat_id": chat_id,
        "user_id": user_id
    })

    # Clear state
    clear_state(user_id)

    await callback.answer("✅ Added to queue!")


# --- WORKER ---
async def worker():
    """
    Background worker that processes download queues round-robin.
    Ensures fair distribution across users.
    """
    global worker_running
    worker_running = True
    logger.info("🚀 Worker started...")

    while worker_running:
        # Process one task from each user queue (round-robin)
        processed_any = False

        for user_id in list(user_queues.keys()):
            queue = user_queues[user_id]
            if queue.empty():
                continue

            processed_any = True
            task = await queue.get()

            chat_id = task["chat_id"]
            metadata = task["metadata"]
            resolution = task["resolution"]
            audio = task["audio"]

            # Generate filename
            if metadata['is_movie']:
                clean_name = metadata['title']
            else:
                clean_name = f"{metadata['title']}_S{metadata['season']}E{metadata['episode']}"
            clean_name = mx_engine.sanitize_filename(clean_name)

            # Progress message
            prog_msg = await app.send_message(
                chat_id,
                f"⬇️ **Downloading {metadata['title']}**\n"
                f"{generate_progress_bar(0)}\n"
                "`Starting download...`"
            )

            try:
                # Progress callback
                last_edit_time = 0

                async def download_progress(percent: float, raw_line: str):
                    nonlocal last_edit_time
                    now = time.time()

                    # Update every 5 seconds
                    if now - last_edit_time > 5:
                        try:
                            await prog_msg.edit_text(
                                f"⬇️ **Downloading {metadata['title']}**\n"
                                f"{generate_progress_bar(percent)}\n"
                                f"`{raw_line[:50]}...`" if len(raw_line) > 50 else f"`{raw_line}`"
                            )
                            last_edit_time = now
                        except FloodWait as e:
                            await asyncio.sleep(e.value)
                        except Exception:
                            pass

                # Execute download
                file_path, success = await mx_engine.run_download(
                    m3u8_url=metadata['m3u8'],
                    filename=clean_name,
                    user_id=user_id,
                    resolution=resolution,
                    audio_track=audio,
                    progress_callback=download_progress
                )

                if success and os.path.exists(file_path):
                    await prog_msg.edit_text("⬆️ **Preparing upload...**")

                    # Download thumbnail
                    thumb_path = None
                    if metadata.get('image'):
                        thumb_path = os.path.join(DOWNLOAD_DIR, f"{clean_name}_thumb.jpg")
                        await mx_engine.download_thumbnail(metadata['image'], thumb_path)
                        if not os.path.exists(thumb_path):
                            thumb_path = None

                    # Get video duration
                    duration = await mx_engine.get_video_duration(file_path)

                    # Upload with progress
                    caption = f"✅ **{metadata['title']}**"
                    if not metadata['is_movie']:
                        caption += f"\n📅 S{metadata['season']}E{metadata['episode']}"

                    upload_success = await upload_with_progress(
                        client=app,
                        chat_id=chat_id,
                        file_path=file_path,
                        thumb_path=thumb_path,
                        duration=duration,
                        caption=caption,
                        progress_message=prog_msg,
                        filename=os.path.basename(file_path)
                    )

                    # Cleanup
                    try:
                        os.remove(file_path)
                        if thumb_path and os.path.exists(thumb_path):
                            os.remove(thumb_path)
                    except Exception as e:
                        logger.error(f"Cleanup error: {e}")

                    if upload_success:
                        await prog_msg.delete()
                    else:
                        await prog_msg.edit_text("❌ Upload failed. Please try again.")

                else:
                    await prog_msg.edit_text(
                        "❌ Download failed. (DRM, network error, or timeout)"
                    )

            except Exception as e:
                logger.error(f"Worker task error: {e}")
                await app.send_message(chat_id, f"⚠️ Task failed: {str(e)}")

            finally:
                queue.task_done()

        # If no tasks processed, sleep briefly
        if not processed_any:
            await asyncio.sleep(1)


# --- MAIN ---
async def main():
    """Main entry point."""
    # Start worker in background
    asyncio.create_task(worker())

    # Start bot
    await app.start()
    logger.info("Bot started successfully!")

    # Keep running
    await asyncio.Event().wait()


if __name__ == "__main__":
    app.run(main())
