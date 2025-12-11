"""
Authentication handler for cookie upload.
"""

import os
import aiofiles
from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery
from core.middlewares import authorized
from config import get_user_cookies_path, user_has_cookies, COOKIES_DIR
from states import get_state, set_state, clear_state, UserStep


# Max cookie file size (100KB)
MAX_COOKIE_SIZE = 100 * 1024


def validate_netscape_cookies(content: str) -> bool:
    """
    Validate that content is in Netscape cookie format.

    Args:
        content: Cookie file content

    Returns:
        True if valid Netscape format
    """
    valid_lines = 0
    lines = content.strip().split('\n')

    for line in lines:
        line = line.strip()
        # Skip comments and empty lines
        if not line or line.startswith('#'):
            continue

        # Netscape format: domain, flag, path, secure, expiry, name, value
        parts = line.split('\t')
        if len(parts) >= 6:
            valid_lines += 1

    return valid_lines > 0


@Client.on_message(filters.command("auth") & filters.private)
@authorized
async def cmd_auth(client: Client, message: Message):
    """Handle /auth command."""
    user_id = message.from_user.id

    # Set state to waiting for cookies
    set_state(user_id, step=UserStep.WAITING_COOKIES)

    # Check if user already has cookies
    has_cookies = user_has_cookies(user_id)

    if has_cookies:
        text = """**Re-authenticate**

You already have cookies saved. Uploading a new file will replace them.

Send your `cookies.txt` file (Netscape format).

**How to get cookies:**
1. Install "Get cookies.txt LOCALLY" extension
2. Visit MX Player and log in
3. Export cookies for mxplayer.in domain
4. Send the file here

Send /cancel to abort."""
    else:
        text = """**Authentication Required**

To download from MX Player, you need to upload your `cookies.txt` file.

**How to get cookies:**
1. Install "Get cookies.txt LOCALLY" browser extension
2. Visit mxplayer.in and log in
3. Export cookies for the site (Netscape format)
4. Send the exported file here

Send /cancel to abort."""

    await message.reply_text(text, disable_web_page_preview=True)


@Client.on_message(filters.command("cancel") & filters.private)
@authorized
async def cmd_cancel(client: Client, message: Message):
    """Handle /cancel command to abort authentication."""
    user_id = message.from_user.id
    state = get_state(user_id)

    if state.step == UserStep.WAITING_COOKIES:
        clear_state(user_id)
        await message.reply_text("Authentication cancelled.")
    elif state.step in [UserStep.SELECT_QUALITY, UserStep.SELECT_AUDIO, UserStep.CONFIRMATION]:
        clear_state(user_id)
        await message.reply_text("Download cancelled.")
    else:
        await message.reply_text("Nothing to cancel.")


@Client.on_message(filters.document & filters.private)
@authorized
async def handle_document(client: Client, message: Message):
    """Handle document upload for cookies."""
    user_id = message.from_user.id
    state = get_state(user_id)

    # Only process if user is in WAITING_COOKIES state
    if state.step != UserStep.WAITING_COOKIES:
        return

    document = message.document

    # Validate file extension
    if not document.file_name or not document.file_name.endswith('.txt'):
        await message.reply_text(
            "**Invalid file format**\n\n"
            "Please send a `.txt` file."
        )
        return

    # Validate file size
    if document.file_size > MAX_COOKIE_SIZE:
        await message.reply_text(
            f"**File too large**\n\n"
            f"Maximum file size is 100KB. Your file is {document.file_size / 1024:.1f}KB."
        )
        return

    # Download and validate
    status_msg = await message.reply_text("Validating cookies...")

    try:
        # Download to temp path first
        temp_path = os.path.join(COOKIES_DIR, f"{user_id}_temp.txt")
        await message.download(file_name=temp_path)

        # Read and validate content
        async with aiofiles.open(temp_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = await f.read()

        if not validate_netscape_cookies(content):
            os.remove(temp_path)
            await status_msg.edit_text(
                "**Invalid cookie format**\n\n"
                "The file doesn't appear to be in Netscape cookie format.\n"
                "Make sure you export cookies using 'Get cookies.txt LOCALLY' "
                "or similar extension."
            )
            return

        # Move to final path
        final_path = get_user_cookies_path(user_id)
        if os.path.exists(final_path):
            os.remove(final_path)
        os.rename(temp_path, final_path)

        # Clear state
        clear_state(user_id)

        await status_msg.edit_text(
            "**Cookies saved successfully!**\n\n"
            "You can now send MX Player links to download videos.\n\n"
            "Just paste a link like:\n"
            "`https://www.mxplayer.in/show/...`"
        )

    except Exception as e:
        # Cleanup temp file
        temp_path = os.path.join(COOKIES_DIR, f"{user_id}_temp.txt")
        if os.path.exists(temp_path):
            os.remove(temp_path)

        await status_msg.edit_text(
            f"**Error saving cookies**\n\n"
            f"Please try again. Error: {str(e)[:100]}"
        )


@Client.on_callback_query(filters.regex("^start_auth$"))
@authorized
async def callback_start_auth(client: Client, callback: CallbackQuery):
    """Handle start_auth callback from start message."""
    user_id = callback.from_user.id

    # Set state to waiting for cookies
    set_state(user_id, step=UserStep.WAITING_COOKIES)

    has_cookies = user_has_cookies(user_id)

    if has_cookies:
        text = """**Re-authenticate**

You already have cookies saved. Uploading a new file will replace them.

Send your `cookies.txt` file (Netscape format).

Send /cancel to abort."""
    else:
        text = """**Authentication Required**

Send your `cookies.txt` file to authenticate.

**How to get cookies:**
1. Install "Get cookies.txt LOCALLY" extension
2. Visit mxplayer.in and log in
3. Export cookies (Netscape format)
4. Send the file here

Send /cancel to abort."""

    await callback.message.edit_text(text, disable_web_page_preview=True)
    await callback.answer()
