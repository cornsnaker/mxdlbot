import os
from dotenv import load_dotenv

load_dotenv()

# --- TELEGRAM CONFIGURATION ---
API_ID = int(os.getenv("API_ID", "123456"))  # Get from my.telegram.org
API_HASH = os.getenv("API_HASH", "your_api_hash")
BOT_TOKEN = os.getenv("BOT_TOKEN", "your_bot_token")

# --- MONGODB CONFIGURATION ---
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "mxdlbot")

# --- BOT CONFIGURATION ---
# Owner ID - Has full control over the bot
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

# Admin IDs - Can use admin commands
ADMINS = [int(x.strip()) for x in os.getenv("ADMINS", "").split(",") if x.strip()]

# --- PATHS ---
# Path to the N_m3u8DL-RE binary (Make sure this is executable!)
BINARY_PATH = os.getenv("BINARY_PATH", "N_m3u8DL-RE")

# Per-user cookie storage directory
COOKIES_DIR = os.getenv("COOKIES_DIR", "data/cookies")

# Download directory for temporary files
DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR", "data/downloads")

# Thumbnail directory
THUMBNAIL_DIR = os.getenv("THUMBNAIL_DIR", "data/thumbnails")

# --- CREATE REQUIRED DIRECTORIES ---
for directory in [DOWNLOAD_DIR, COOKIES_DIR, THUMBNAIL_DIR]:
    if not os.path.exists(directory):
        os.makedirs(directory)


def get_user_cookies_path(user_id: int) -> str:
    """
    Get the path to a user's cookies file.

    Args:
        user_id: Telegram user ID

    Returns:
        Path to cookies/{user_id}.txt
    """
    return os.path.join(COOKIES_DIR, f"{user_id}.txt")


def user_has_cookies(user_id: int) -> bool:
    """
    Check if a user has uploaded cookies.

    Args:
        user_id: Telegram user ID

    Returns:
        True if cookies file exists
    """
    return os.path.exists(get_user_cookies_path(user_id))
