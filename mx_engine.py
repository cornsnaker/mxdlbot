import os
import re
import json
import asyncio
import aiohttp
from urllib.parse import urljoin
from config import BINARY_PATH, COOKIES_FILE, DOWNLOAD_DIR

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127 Safari/537.36"
ORIGIN = "https://www.mxplayer.in"

async def fetch_html(url):
    headers = {"User-Agent": USER_AGENT, "Origin": ORIGIN}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            if resp.status != 200: return None
            return await resp.text()

async def get_metadata(url):
    """Scrapes Title, Description, Season, Episode, and Image."""
    html = await fetch_html(url)
    if not html: return None

    # Regex for JSON-LD
    data = {}
    pattern = r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>'
    matches = re.finditer(pattern, html, re.DOTALL)
    
    for m in matches:
        try:
            json_data = json.loads(m.group(1))
            if isinstance(json_data, dict): json_data = [json_data]
            for item in json_data:
                if item.get('@type') in ['Episode', 'Movie']:
                    data = item
                    break
        except: continue
    
    # Extract details
    meta = {
        "title": "Unknown Title",
        "description": "No description available.",
        "image": None,
        "season": None,
        "episode": None,
        "is_movie": True
    }

    if data:
        if data.get('@type') == 'Episode':
            meta['is_movie'] = False
            meta['episode'] = data.get('episodeNumber')
            part_of_season = data.get('partOfSeason', {})
            meta['season'] = part_of_season.get('seasonNumber')
            part_of_series = data.get('partOfSeries', {})
            meta['title'] = part_of_series.get('name', 'Unknown Series')
            meta['episode_title'] = data.get('name')
        else:
            meta['title'] = data.get('name')
        
        # Get Image
        imgs = data.get('image')
        if isinstance(imgs, list): meta['image'] = imgs[0]
        elif isinstance(imgs, str): meta['image'] = imgs

    # Fallback m3u8 search (needed for download)
    meta['m3u8'] = find_m3u8_in_text(html)
    return meta

def find_m3u8_in_text(text):
    # Regex logic from original script
    m = re.search(r'(https?://[^"\']+?\.m3u8[^"\']*)', text)
    if m: return m.group(1)
    m = re.search(r'(https?:\\\\/\\\\/[^"]+?\.m3u8[^"]*)', text)
    if m: return m.group(1).replace("\\/", "/").replace("\\\\/", "/")
    return None

async def run_download(m3u8_url, filename, progress_callback=None):
    """Runs N_m3u8DL-RE asynchronously and parses progress."""
    output_path = os.path.join(DOWNLOAD_DIR, filename)
    
    # Command arguments
    cmd = [
        BINARY_PATH,
        m3u8_url,
        "--save-dir", DOWNLOAD_DIR,
        "--save-name", filename,
        "--header", f"Cookie: {open(COOKIES_FILE).read() if os.path.exists(COOKIES_FILE) else ''}",
        "--header", f"User-Agent: {USER_AGENT}",
        "--thread-count", "16",
        "--download-retry-count", "5",
        "-M", "format=mp4"
    ]

    # Run subprocess
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    # Read output for progress
    while True:
        line = await process.stdout.readline()
        if not line: break
        line_str = line.decode().strip()
        
        # Parse logic: Look for "Progress: 45%" pattern from N_m3u8DL-RE
        # Note: Actual output varies by version, usually contains %
        if "%" in line_str and progress_callback:
            # Simple extractor for the % number
            try:
                percent = line_str.split('%')[0].split()[-1]
                await progress_callback(float(percent), line_str)
            except: pass

    await process.wait()
    return f"{output_path}.mp4", process.returncode == 0
