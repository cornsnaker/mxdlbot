"""
User settings handler with inline buttons.
"""

from pyrogram import Client, filters
from pyrogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from core.middlewares import authorized
from core.database import db
from states import get_state, set_state, clear_state, UserStep


def build_settings_keyboard(settings: dict) -> InlineKeyboardMarkup:
    """Build settings menu keyboard."""
    output_format = settings.get('output_format', 'mp4')
    has_gofile = bool(settings.get('gofile_token'))
    has_thumbnail = bool(settings.get('custom_thumbnail'))

    format_text = f"📦 Format: {output_format.upper()}"
    gofile_text = "🔑 Gofile: " + ("Set" if has_gofile else "Not Set")
    thumb_text = "🖼️ Thumbnail: " + ("Custom" if has_thumbnail else "Default")

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(format_text, callback_data="settings_format")
        ],
        [
            InlineKeyboardButton(gofile_text, callback_data="settings_gofile")
        ],
        [
            InlineKeyboardButton(thumb_text, callback_data="settings_thumbnail")
        ],
        [
            InlineKeyboardButton("❌ Close", callback_data="settings_close")
        ]
    ])


def build_format_keyboard(current: str) -> InlineKeyboardMarkup:
    """Build format selection keyboard."""
    mp4_check = " ✓" if current == "mp4" else ""
    mkv_check = " ✓" if current == "mkv" else ""

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"MP4{mp4_check}", callback_data="set_format:mp4"),
            InlineKeyboardButton(f"MKV{mkv_check}", callback_data="set_format:mkv")
        ],
        [
            InlineKeyboardButton("⬅️ Back", callback_data="settings_back")
        ]
    ])


def build_gofile_keyboard(has_token: bool) -> InlineKeyboardMarkup:
    """Build Gofile settings keyboard."""
    buttons = []

    if has_token:
        buttons.append([
            InlineKeyboardButton("🔄 Update Token", callback_data="gofile_set"),
            InlineKeyboardButton("🗑️ Remove Token", callback_data="gofile_remove")
        ])
    else:
        buttons.append([
            InlineKeyboardButton("➕ Add Token", callback_data="gofile_set")
        ])

    buttons.append([
        InlineKeyboardButton("⬅️ Back", callback_data="settings_back")
    ])

    return InlineKeyboardMarkup(buttons)


def build_thumbnail_keyboard(has_thumbnail: bool) -> InlineKeyboardMarkup:
    """Build thumbnail settings keyboard."""
    buttons = []

    if has_thumbnail:
        buttons.append([
            InlineKeyboardButton("🔄 Update Thumbnail", callback_data="thumb_set"),
            InlineKeyboardButton("🗑️ Remove", callback_data="thumb_remove")
        ])
    else:
        buttons.append([
            InlineKeyboardButton("➕ Set Thumbnail", callback_data="thumb_set")
        ])

    buttons.append([
        InlineKeyboardButton("⬅️ Back", callback_data="settings_back")
    ])

    return InlineKeyboardMarkup(buttons)


@Client.on_message(filters.command("settings") & filters.private)
@authorized
async def cmd_settings(client: Client, message: Message):
    """Handle /settings command."""
    user_id = message.from_user.id
    settings = await db.get_user_settings(user_id)

    text = """**Settings**

Configure your preferences below.

**Output Format:** Video container format
**Gofile Token:** For large file uploads (>2GB)
**Thumbnail:** Custom thumbnail for uploads"""

    keyboard = build_settings_keyboard(settings)
    await message.reply_text(text, reply_markup=keyboard)


@Client.on_callback_query(filters.regex("^open_settings$"))
@authorized
async def callback_open_settings(client: Client, callback: CallbackQuery):
    """Handle open_settings callback from start message."""
    user_id = callback.from_user.id
    settings = await db.get_user_settings(user_id)

    text = """**Settings**

Configure your preferences below.

**Output Format:** Video container format
**Gofile Token:** For large file uploads (>2GB)
**Thumbnail:** Custom thumbnail for uploads"""

    keyboard = build_settings_keyboard(settings)
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@Client.on_callback_query(filters.regex("^settings_format$"))
@authorized
async def callback_format_menu(client: Client, callback: CallbackQuery):
    """Show format selection menu."""
    user_id = callback.from_user.id
    settings = await db.get_user_settings(user_id)
    current = settings.get('output_format', 'mp4')

    text = """**Output Format**

Choose your preferred video format:

**MP4** - Better compatibility, smaller size
**MKV** - Better quality, multiple audio tracks"""

    keyboard = build_format_keyboard(current)
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@Client.on_callback_query(filters.regex(r"^set_format:(.+)$"))
@authorized
async def callback_set_format(client: Client, callback: CallbackQuery):
    """Set output format."""
    user_id = callback.from_user.id
    new_format = callback.matches[0].group(1)

    if new_format not in ['mp4', 'mkv']:
        await callback.answer("Invalid format", show_alert=True)
        return

    await db.set_output_format(user_id, new_format)

    # Show updated menu
    settings = await db.get_user_settings(user_id)
    keyboard = build_format_keyboard(new_format)

    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer(f"Format set to {new_format.upper()}")


@Client.on_callback_query(filters.regex("^settings_gofile$"))
@authorized
async def callback_gofile_menu(client: Client, callback: CallbackQuery):
    """Show Gofile settings menu."""
    user_id = callback.from_user.id
    token = await db.get_gofile_token(user_id)

    text = """**Gofile API Token**

Files larger than 2GB are uploaded to Gofile.io.

You can use your own API token for:
- Persistent download links
- File management
- Custom folder organization

Get your token at: https://gofile.io/myProfile"""

    keyboard = build_gofile_keyboard(bool(token))
    await callback.message.edit_text(text, reply_markup=keyboard, disable_web_page_preview=True)
    await callback.answer()


@Client.on_callback_query(filters.regex("^gofile_set$"))
@authorized
async def callback_gofile_set(client: Client, callback: CallbackQuery):
    """Prompt user to send Gofile token."""
    user_id = callback.from_user.id

    # Set state to waiting for token
    set_state(user_id, step=UserStep.WAITING_COOKIES)  # Reuse waiting state

    text = """**Enter Gofile Token**

Send your Gofile API token now.

Get your token from: https://gofile.io/myProfile

Send /cancel to abort."""

    # Store that we're waiting for gofile token, not cookies
    state = get_state(user_id)
    state.metadata = {'waiting_for': 'gofile_token'}

    await callback.message.edit_text(text, disable_web_page_preview=True)
    await callback.answer()


@Client.on_callback_query(filters.regex("^gofile_remove$"))
@authorized
async def callback_gofile_remove(client: Client, callback: CallbackQuery):
    """Remove Gofile token."""
    user_id = callback.from_user.id
    await db.set_gofile_token(user_id, None)

    # Go back to gofile menu
    keyboard = build_gofile_keyboard(False)
    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer("Token removed")


@Client.on_callback_query(filters.regex("^settings_thumbnail$"))
@authorized
async def callback_thumbnail_menu(client: Client, callback: CallbackQuery):
    """Show thumbnail settings menu."""
    user_id = callback.from_user.id
    thumb = await db.get_custom_thumbnail(user_id)

    text = """**Custom Thumbnail**

Set a custom thumbnail that will be used for all your video uploads.

The thumbnail should be:
- A square or landscape image
- Under 200KB in size
- JPG or PNG format"""

    keyboard = build_thumbnail_keyboard(bool(thumb))
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@Client.on_callback_query(filters.regex("^thumb_set$"))
@authorized
async def callback_thumb_set(client: Client, callback: CallbackQuery):
    """Prompt user to send thumbnail."""
    user_id = callback.from_user.id

    # Set state to waiting
    set_state(user_id, step=UserStep.WAITING_COOKIES)  # Reuse waiting state
    state = get_state(user_id)
    state.metadata = {'waiting_for': 'thumbnail'}

    text = """**Send Thumbnail**

Send an image to use as your custom thumbnail.

Requirements:
- Square or landscape orientation
- Under 200KB
- JPG or PNG format

Send /cancel to abort."""

    await callback.message.edit_text(text)
    await callback.answer()


@Client.on_callback_query(filters.regex("^thumb_remove$"))
@authorized
async def callback_thumb_remove(client: Client, callback: CallbackQuery):
    """Remove custom thumbnail."""
    user_id = callback.from_user.id
    await db.clear_custom_thumbnail(user_id)

    # Go back to thumbnail menu
    keyboard = build_thumbnail_keyboard(False)
    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer("Thumbnail removed")


@Client.on_callback_query(filters.regex("^settings_back$"))
@authorized
async def callback_settings_back(client: Client, callback: CallbackQuery):
    """Go back to main settings menu."""
    user_id = callback.from_user.id
    settings = await db.get_user_settings(user_id)

    text = """**Settings**

Configure your preferences below.

**Output Format:** Video container format
**Gofile Token:** For large file uploads (>2GB)
**Thumbnail:** Custom thumbnail for uploads"""

    keyboard = build_settings_keyboard(settings)
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@Client.on_callback_query(filters.regex("^settings_close$"))
@authorized
async def callback_settings_close(client: Client, callback: CallbackQuery):
    """Close settings menu."""
    await callback.message.delete()
    await callback.answer()


@Client.on_message(filters.text & filters.private)
@authorized
async def handle_settings_input(client: Client, message: Message):
    """Handle text input for settings (Gofile token)."""
    user_id = message.from_user.id
    state = get_state(user_id)

    if state.step != UserStep.WAITING_COOKIES:
        return

    if not state.metadata or 'waiting_for' not in state.metadata:
        return

    waiting_for = state.metadata.get('waiting_for')

    if waiting_for == 'gofile_token':
        token = message.text.strip()

        if len(token) < 10:
            await message.reply_text("Invalid token. Please try again or send /cancel.")
            return

        await db.set_gofile_token(user_id, token)
        clear_state(user_id)

        await message.reply_text(
            "**Gofile token saved!**\n\n"
            "Your large files will now be uploaded to your Gofile account."
        )


@Client.on_message(filters.photo & filters.private)
@authorized
async def handle_thumbnail_upload(client: Client, message: Message):
    """Handle thumbnail photo upload."""
    user_id = message.from_user.id
    state = get_state(user_id)

    if state.step != UserStep.WAITING_COOKIES:
        return

    if not state.metadata or state.metadata.get('waiting_for') != 'thumbnail':
        return

    # Get the largest photo size
    photo = message.photo
    file_id = photo.file_id

    # Save to database
    await db.set_custom_thumbnail(user_id, file_id)
    clear_state(user_id)

    await message.reply_text(
        "**Thumbnail saved!**\n\n"
        "This thumbnail will be used for all your video uploads."
    )
