import os
from dotenv import load_dotenv

load_dotenv()

# --- CONFIGURATION ---
API_ID = int(os.getenv("API_ID", "123456"))  # Get from my.telegram.org
API_HASH = os.getenv("API_HASH", "your_api_hash")
BOT_TOKEN = os.getenv("BOT_TOKEN", "your_bot_token")

# Path to the N_m3u8DL-RE binary (Make sure this is executable!)
BINARY_PATH = "N_m3u8DL-RE" 
COOKIES_FILE = "cookies.txt"  # Put your Netscape cookies here
DOWNLOAD_DIR = "downloads"

# Admin IDs (for authorized access if needed)
ADMINS = [123456789] 

if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)
