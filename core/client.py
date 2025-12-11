"""
Pyrogram client setup with plugin system.
"""

import asyncio
import sys

# Fix for Python 3.10+ asyncio event loop issue with Pyrogram
if sys.version_info >= (3, 10):
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

from pyrogram import Client
from config import API_ID, API_HASH, BOT_TOKEN

# Initialize Pyrogram Client with plugins
app = Client(
    name="mxdlbot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    plugins=dict(root="plugins")
)
