#!/usr/bin/env python3
"""
MX Player Telegram Bot - Main Entry Point

A production-ready Telegram bot for downloading videos from MX Player.

Features:
- Per-user cookie authentication
- Quality selection with dynamic m3u8 parsing
- Real-time download/upload progress
- tgcrypto-accelerated uploads via Pyrogram
- Large file support via Gofile.io
- User settings and custom thumbnails
- Admin commands (broadcast, stats, ban)

Usage:
    python run.py

Environment variables (in .env file):
    API_ID - Telegram API ID from my.telegram.org
    API_HASH - Telegram API Hash from my.telegram.org
    BOT_TOKEN - Bot token from @BotFather
    MONGO_URI - MongoDB connection URI
    OWNER_ID - Owner's Telegram user ID
    ADMINS - Comma-separated admin user IDs (optional)
"""

import asyncio
import sys
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Fix for Python 3.10+ asyncio event loop issue
if sys.version_info >= (3, 10):
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)


async def main():
    """Main entry point for the bot."""
    # Import after event loop setup
    from core.client import app
    from core.database import db
    from services.mx_scraper import mx_scraper

    logger.info("Starting MX Player Bot...")

    try:
        # Connect to MongoDB
        await db.connect()
        logger.info("Database connected")

        # Start the bot
        logger.info("Starting Pyrogram client...")
        await app.start()

        me = await app.get_me()
        logger.info(f"Bot started as @{me.username}")

        # Keep the bot running
        logger.info("Bot is now running. Press Ctrl+C to stop.")
        await asyncio.Event().wait()

    except KeyboardInterrupt:
        logger.info("Shutting down...")

    except Exception as e:
        logger.error(f"Error: {e}")
        raise

    finally:
        # Cleanup
        logger.info("Cleaning up...")

        try:
            await app.stop()
        except Exception:
            pass

        try:
            await mx_scraper.close()
        except Exception:
            pass

        try:
            await db.close()
        except Exception:
            pass

        logger.info("Shutdown complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
