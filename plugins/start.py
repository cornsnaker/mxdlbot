"""
Start and help command handlers.
"""

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from core.middlewares import authorized
from core.database import db


WELCOME_MESSAGE = """**Welcome to MX Player Bot**

Send me an MX Player link (Episode or Movie) and I'll download it for you.

**First time?** Use /auth to upload your cookies.txt

**Features:**
- Quality selection (1080p, 720p, etc.)
- All audio languages included
- Real-time progress tracking
- Fast uploads with thumbnail
- Download queue (max 2 concurrent)
- MediaInfo with Telegraph links

**Commands:**
/start - Show this message
/auth - Upload your cookies.txt
/settings - Configure your preferences
/queue - View your download queue
/status - View all active downloads
/canceltask - Cancel a task by ID
/help - Show help information
"""

HELP_MESSAGE = """**How to use this bot:**

**Step 1: Authenticate**
Use /auth to upload your `cookies.txt` file from MX Player.
This is required to download premium content.

**Step 2: Send a link**
Simply send an MX Player episode or movie URL.
Example: `https://www.mxplayer.in/show/...`

**Step 3: Select quality**
Choose your preferred video quality.
All audio languages are automatically included.

**Step 4: Wait for download**
The bot will download and upload the video to you.
Large files (>2GB) are uploaded to Gofile.io.

**Download Queue:**
- Max 2 concurrent downloads per user
- Additional downloads are queued automatically
- Use /queue to view your queue status with task IDs
- Use `/canceltask DL-XXXX` to cancel a specific task
- Use /cancelqueue to cancel all pending downloads

**Settings:**
Use /settings to:
- Change output format (MP4/MKV)
- Choose upload mode (Video/Document)
- Set your Gofile API token
- Upload custom thumbnail

**Need cookies?**
Export cookies from your browser using extensions like:
- "Get cookies.txt LOCALLY" (Chrome/Firefox)
- "EditThisCookie" export as Netscape format

**Issues?**
Make sure your cookies are fresh and not expired.
Re-authenticate with /auth if downloads fail.
"""


@Client.on_message(filters.command("start") & filters.private)
@authorized
async def cmd_start(client: Client, message: Message):
    """Handle /start command."""
    user = message.from_user

    # Add user to database
    is_new = await db.add_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Upload Cookies", callback_data="start_auth"),
            InlineKeyboardButton("Settings", callback_data="open_settings")
        ],
        [
            InlineKeyboardButton("Help", callback_data="show_help")
        ]
    ])

    await message.reply_text(
        WELCOME_MESSAGE,
        reply_markup=keyboard,
        disable_web_page_preview=True
    )


@Client.on_message(filters.command("help") & filters.private)
@authorized
async def cmd_help(client: Client, message: Message):
    """Handle /help command."""
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Upload Cookies", callback_data="start_auth"),
            InlineKeyboardButton("Settings", callback_data="open_settings")
        ]
    ])

    await message.reply_text(
        HELP_MESSAGE,
        reply_markup=keyboard,
        disable_web_page_preview=True
    )


@Client.on_callback_query(filters.regex("^show_help$"))
@authorized
async def callback_show_help(client: Client, callback):
    """Handle show_help callback."""
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Back", callback_data="show_start")
        ]
    ])

    await callback.message.edit_text(
        HELP_MESSAGE,
        reply_markup=keyboard,
        disable_web_page_preview=True
    )
    await callback.answer()


@Client.on_callback_query(filters.regex("^show_start$"))
@authorized
async def callback_show_start(client: Client, callback):
    """Handle show_start callback."""
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Upload Cookies", callback_data="start_auth"),
            InlineKeyboardButton("Settings", callback_data="open_settings")
        ],
        [
            InlineKeyboardButton("Help", callback_data="show_help")
        ]
    ])

    await callback.message.edit_text(
        WELCOME_MESSAGE,
        reply_markup=keyboard,
        disable_web_page_preview=True
    )
    await callback.answer()
