"""
MX Player Engine - Async scraping, m3u8 parsing, and download execution.
"""

import os
import re
import json
import asyncio
import aiohttp
from typing import Optional, Dict, List, Any, Callable, Tuple
from urllib.parse import urljoin
from config import BINARY_PATH, DOWNLOAD_DIR, get_user_cookies_path

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127 Safari/537.36"
ORIGIN = "https://www.mxplayer.in"

# Download timeout in seconds (30 minutes)
DOWNLOAD_TIMEOUT = 1800


async def fetch_html(url: str) -> Optional[str]:
    """
    Fetch HTML content from a URL.

    Args:
        url: URL to fetch

    Returns:
        HTML string or None on failure
    """
    headers = {"User-Agent": USER_AGENT, "Origin": ORIGIN}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            if resp.status != 200:
                return None
            return await resp.text()


async def get_metadata(url: str) -> Optional[Dict[str, Any]]:
    """
    Scrapes Title, Description, Season, Episode, Image, and M3U8 URL.

    Args:
        url: MX Player content URL

    Returns:
        Dictionary with metadata or None on failure
    """
    html = await fetch_html(url)
    if not html:
        return None

    # Regex for JSON-LD
    data = {}
    pattern = r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>'
    matches = re.finditer(pattern, html, re.DOTALL)

    for m in matches:
        try:
            json_data = json.loads(m.group(1))
            if isinstance(json_data, dict):
                json_data = [json_data]
            for item in json_data:
                if item.get('@type') in ['Episode', 'Movie']:
                    data = item
                    break
        except:
            continue

    # Extract details
    meta = {
        "title": "Unknown Title",
        "description": "No description available.",
        "image": None,
        "season": None,
        "episode": None,
        "episode_title": None,
        "is_movie": True,
        "m3u8": None
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
        if isinstance(imgs, list):
            meta['image'] = imgs[0]
        elif isinstance(imgs, str):
            meta['image'] = imgs

    # Fallback m3u8 search (needed for download)
    meta['m3u8'] = find_m3u8_in_text(html)
    return meta


def find_m3u8_in_text(text: str) -> Optional[str]:
    """
    Extract m3u8 URL from HTML text.

    Args:
        text: HTML content

    Returns:
        M3U8 URL or None
    """
    # Standard URL format
    m = re.search(r'(https?://[^"\']+?\.m3u8[^"\']*)', text)
    if m:
        return m.group(1)
    # Escaped URL format
    m = re.search(r'(https?:\\\\/\\\\/[^"]+?\.m3u8[^"]*)', text)
    if m:
        return m.group(1).replace("\\/", "/").replace("\\\\/", "/")
    return None


async def parse_master_m3u8(m3u8_url: str) -> Tuple[List[Dict], List[Dict]]:
    """
    Fetch master m3u8 playlist and parse video resolutions and audio tracks.

    Args:
        m3u8_url: URL to master m3u8 playlist

    Returns:
        Tuple of (resolutions_list, audio_tracks_list)
        resolutions: [{"resolution": "1080p", "height": 1080, "bandwidth": 5000000, "uri": "..."}, ...]
        audio_tracks: [{"name": "Hindi", "language": "hi", "group_id": "...", "uri": "..."}, ...]
    """
    resolutions = []
    audio_tracks = []

    try:
        headers = {"User-Agent": USER_AGENT, "Origin": ORIGIN}
        async with aiohttp.ClientSession() as session:
            async with session.get(m3u8_url, headers=headers) as resp:
                if resp.status != 200:
                    return resolutions, audio_tracks
                content = await resp.text()

        base_url = m3u8_url.rsplit('/', 1)[0] + '/'
        lines = content.strip().split('\n')

        i = 0
        while i < len(lines):
            line = lines[i].strip()

            # Parse audio tracks: #EXT-X-MEDIA:TYPE=AUDIO
            if line.startswith('#EXT-X-MEDIA:') and 'TYPE=AUDIO' in line:
                track = _parse_audio_media_line(line)
                if track:
                    # Make URI absolute if relative
                    if track.get('uri') and not track['uri'].startswith('http'):
                        track['uri'] = urljoin(base_url, track['uri'])
                    audio_tracks.append(track)

            # Parse video resolutions: #EXT-X-STREAM-INF
            elif line.startswith('#EXT-X-STREAM-INF:'):
                variant = _parse_stream_inf_line(line)
                if variant and i + 1 < len(lines):
                    uri = lines[i + 1].strip()
                    if not uri.startswith('http'):
                        uri = urljoin(base_url, uri)
                    variant['uri'] = uri
                    resolutions.append(variant)
                    i += 1  # Skip next line (URI)

            i += 1

        # Sort resolutions by bandwidth (highest first)
        resolutions.sort(key=lambda x: x.get('bandwidth', 0), reverse=True)

        # Remove duplicate resolutions (keep highest bandwidth)
        seen_heights = set()
        unique_resolutions = []
        for res in resolutions:
            height = res.get('height')
            if height and height not in seen_heights:
                seen_heights.add(height)
                unique_resolutions.append(res)
        resolutions = unique_resolutions

    except Exception as e:
        print(f"Error parsing m3u8: {e}")

    return resolutions, audio_tracks


def _parse_stream_inf_line(line: str) -> Optional[Dict]:
    """
    Parse #EXT-X-STREAM-INF line for video resolution info.

    Args:
        line: The STREAM-INF line

    Returns:
        Dict with resolution info or None
    """
    result = {}

    # Extract BANDWIDTH
    bw_match = re.search(r'BANDWIDTH=(\d+)', line)
    if bw_match:
        result['bandwidth'] = int(bw_match.group(1))

    # Extract RESOLUTION (e.g., 1920x1080)
    res_match = re.search(r'RESOLUTION=(\d+)x(\d+)', line)
    if res_match:
        width = int(res_match.group(1))
        height = int(res_match.group(2))
        result['width'] = width
        result['height'] = height
        result['resolution'] = f"{height}p"

    if result.get('height'):
        return result
    return None


def _parse_audio_media_line(line: str) -> Optional[Dict]:
    """
    Parse #EXT-X-MEDIA:TYPE=AUDIO line for audio track info.

    Args:
        line: The MEDIA line

    Returns:
        Dict with audio track info or None
    """
    result = {}

    # Extract NAME
    name_match = re.search(r'NAME="([^"]+)"', line)
    if name_match:
        result['name'] = name_match.group(1)

    # Extract LANGUAGE
    lang_match = re.search(r'LANGUAGE="([^"]+)"', line)
    if lang_match:
        result['language'] = lang_match.group(1)

    # Extract GROUP-ID
    group_match = re.search(r'GROUP-ID="([^"]+)"', line)
    if group_match:
        result['group_id'] = group_match.group(1)

    # Extract URI
    uri_match = re.search(r'URI="([^"]+)"', line)
    if uri_match:
        result['uri'] = uri_match.group(1)

    if result.get('name') or result.get('language'):
        return result
    return None


def parse_netscape_cookies_to_header(cookies_path: str) -> str:
    """
    Parse Netscape format cookies file and convert to Cookie header string.

    Args:
        cookies_path: Path to cookies.txt file

    Returns:
        Cookie header string like "name1=value1; name2=value2"
    """
    cookies = []
    try:
        with open(cookies_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                # Skip empty lines and comments
                if not line or line.startswith('#'):
                    continue
                # Netscape format: domain, flag, path, secure, expiry, name, value
                parts = line.split('\t')
                if len(parts) >= 7:
                    name = parts[5]
                    value = parts[6]
                    cookies.append(f"{name}={value}")
    except Exception as e:
        print(f"Error parsing cookies: {e}")
        return ""

    return "; ".join(cookies)


async def download_thumbnail(image_url: str, save_path: str) -> bool:
    """
    Download thumbnail image from URL.

    Args:
        image_url: URL of the image
        save_path: Local path to save the image

    Returns:
        True on success, False on failure
    """
    try:
        headers = {"User-Agent": USER_AGENT}
        async with aiohttp.ClientSession() as session:
            async with session.get(image_url, headers=headers) as resp:
                if resp.status != 200:
                    return False
                content = await resp.read()
                with open(save_path, 'wb') as f:
                    f.write(content)
                return True
    except Exception as e:
        print(f"Error downloading thumbnail: {e}")
        return False


async def get_video_duration(file_path: str) -> Optional[int]:
    """
    Extract video duration using ffprobe.

    Args:
        file_path: Path to video file

    Returns:
        Duration in seconds (int) or None on failure
    """
    try:
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            file_path
        ]
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await process.communicate()
        if process.returncode == 0:
            duration_str = stdout.decode().strip()
            return int(float(duration_str))
    except Exception as e:
        print(f"Error getting video duration: {e}")
    return None


async def run_download(
    m3u8_url: str,
    filename: str,
    user_id: int,
    resolution: Optional[str] = None,
    audio_track: Optional[str] = None,
    progress_callback: Optional[Callable] = None
) -> Tuple[str, bool]:
    """
    Run N_m3u8DL-RE asynchronously with quality/audio selection and progress tracking.

    Args:
        m3u8_url: Master m3u8 URL
        filename: Output filename (without extension)
        user_id: Telegram user ID for cookie lookup
        resolution: Selected resolution height (e.g., "1080") or None for best
        audio_track: Selected audio language code (e.g., "hi") or None for default
        progress_callback: Async callback function(percent, raw_line)

    Returns:
        Tuple of (output_file_path, success_boolean)
    """
    output_path = os.path.join(DOWNLOAD_DIR, filename)

    # Build command arguments
    cmd = [
        BINARY_PATH,
        m3u8_url,
        "--save-dir", DOWNLOAD_DIR,
        "--save-name", filename,
        "--thread-count", "16",
        "--download-retry-count", "5",
        "-M", "format=mp4"
    ]

    # Add custom headers
    cmd.extend(["-H", f"User-Agent: {USER_AGENT}"])
    cmd.extend(["-H", f"Origin: {ORIGIN}"])
    cmd.extend(["-H", f"Referer: {ORIGIN}/"])

    # Add per-user cookies via header (N_m3u8DL-RE uses -H for cookies)
    cookies_path = get_user_cookies_path(user_id)
    if os.path.exists(cookies_path):
        cookie_header = parse_netscape_cookies_to_header(cookies_path)
        if cookie_header:
            cmd.extend(["-H", f"Cookie: {cookie_header}"])

    # Add resolution selection if specified and not "best"
    if resolution and resolution not in ["best", "Best"]:
        # Format: --select-video "res=1080*" for 1080p
        cmd.extend(["--select-video", f"res={resolution}*"])

    # Add audio selection if specified and not "default"
    if audio_track and audio_track not in ["default", "Default"]:
        # Try by name first, fallback to language
        cmd.extend(["--select-audio", f"name={audio_track}"])

    # Log the command for debugging
    print(f"[DEBUG] Running command: {' '.join(cmd)}")

    # Run subprocess with timeout
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT
        )

        # Read output for progress with timeout
        async def read_progress():
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                line_str = line.decode().strip()

                # Log output for debugging
                if line_str:
                    print(f"[N_m3u8DL-RE] {line_str}")

                # Parse progress percentage from N_m3u8DL-RE output
                if "%" in line_str and progress_callback:
                    try:
                        # Extract percentage number before %
                        percent_match = re.search(r'(\d+(?:\.\d+)?)\s*%', line_str)
                        if percent_match:
                            percent = float(percent_match.group(1))
                            await progress_callback(percent, line_str)
                    except:
                        pass

        # Apply timeout to the download process
        await asyncio.wait_for(read_progress(), timeout=DOWNLOAD_TIMEOUT)
        await process.wait()

        print(f"[DEBUG] Process exit code: {process.returncode}")

        final_path = f"{output_path}.mp4"
        exists = os.path.exists(final_path)
        print(f"[DEBUG] Output file exists: {exists}, path: {final_path}")

        return final_path, process.returncode == 0 and exists

    except asyncio.TimeoutError:
        # Kill process on timeout
        try:
            process.kill()
            await process.wait()
        except:
            pass
        return f"{output_path}.mp4", False

    except Exception as e:
        print(f"Download error: {e}")
        return f"{output_path}.mp4", False


def sanitize_filename(name: str) -> str:
    """
    Sanitize a string for use as a filename.

    Args:
        name: Original filename

    Returns:
        Sanitized filename with only alphanumeric and underscores
    """
    return re.sub(r'[^a-zA-Z0-9]', '_', name)
