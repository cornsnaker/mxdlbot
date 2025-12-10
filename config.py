import os
from dotenv import load_dotenv

load_dotenv()

# --- CONFIGURATION ---
API_ID = int(os.getenv("API_ID", "123456"))  # Get from my.telegram.org
API_HASH = os.getenv("API_HASH", "your_api_hash")
BOT_TOKEN = os.getenv("BOT_TOKEN", "your_bot_token")

# Path to the N_m3u8DL-RE binary (Make sure this is executable!)
BINARY_PATH = "N_m3u8DL-RE"

# Per-user cookie storage directory
COOKIES_DIR = "cookies"

# Download directory for temporary files
DOWNLOAD_DIR = "downloads"

# Admin IDs (for authorized access if needed)
ADMINS = [123456789]

# Create required directories on startup
for directory in [DOWNLOAD_DIR, COOKIES_DIR]:
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
