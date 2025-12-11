"""
N_m3u8DL-RE downloader service with progress tracking.
"""

import os
import re
import glob
import asyncio
from typing import Optional, Callable, Tuple
from dataclasses import dataclass
from config import BINARY_PATH, DOWNLOAD_DIR


def clean_download_directory():
    """Remove all files from download directory."""
    try:
        for f in glob.glob(os.path.join(DOWNLOAD_DIR, "*")):
            try:
                if os.path.isfile(f):
                    os.remove(f)
                    print(f"[Cleanup] Removed: {f}")
            except Exception as e:
                print(f"[Cleanup] Failed to remove {f}: {e}")
    except Exception as e:
        print(f"[Cleanup] Directory cleanup error: {e}")


@dataclass
class DownloadResult:
    """Download result container."""
    success: bool
    file_path: Optional[str]
    file_size: int
    error: Optional[str] = None


def parse_netscape_cookies(cookies_path: str) -> str:
    """
    Parse Netscape format cookies file to Cookie header string.

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
                if not line or line.startswith('#'):
                    continue
                parts = line.split('\t')
                if len(parts) >= 7:
                    name = parts[5]
                    value = parts[6]
                    cookies.append(f"{name}={value}")
    except Exception as e:
        print(f"[Downloader] Cookie parse error: {e}")
        return ""

    return "; ".join(cookies)


class Downloader:
    """
    N_m3u8DL-RE wrapper for downloading HLS streams.
    """

    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127 Safari/537.36"
    ORIGIN = "https://www.mxplayer.in"
    TIMEOUT = 1800  # 30 minutes

    def __init__(self):
        self.current_process: Optional[asyncio.subprocess.Process] = None

    async def download(
        self,
        m3u8_url: str,
        filename: str,
        cookies_path: Optional[str] = None,
        resolution: Optional[str] = None,
        output_format: str = "mp4",
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> DownloadResult:
        """
        Download video using N_m3u8DL-RE.

        Args:
            m3u8_url: Master m3u8 URL
            filename: Output filename (without extension)
            cookies_path: Path to user's cookies file
            resolution: Resolution to download (e.g., "1080") or None for best
            output_format: Output format ("mp4" or "mkv")
            progress_callback: Async callback function(percent, status_line)

        Returns:
            DownloadResult with success status and file path
        """
        # IMPORTANT: Clean download directory before starting
        clean_download_directory()

        output_path = os.path.join(DOWNLOAD_DIR, filename)

        # Build command
        cmd = self._build_command(
            m3u8_url=m3u8_url,
            output_path=output_path,
            cookies_path=cookies_path,
            resolution=resolution,
            output_format=output_format
        )

        print(f"[Downloader] Command: {' '.join(cmd)}")

        try:
            self.current_process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT
            )

            # Read output with progress tracking
            await self._read_progress(progress_callback)
            await self.current_process.wait()

            # Find the output file - N_m3u8DL-RE may use different naming
            final_path = f"{output_path}.{output_format}"

            # If expected path doesn't exist, search for any video file
            if not os.path.exists(final_path):
                # Look for any file with the output format
                found_files = glob.glob(os.path.join(DOWNLOAD_DIR, f"*.{output_format}"))
                if found_files:
                    # Get the most recently modified file
                    final_path = max(found_files, key=os.path.getmtime)
                    print(f"[Downloader] Found output file: {final_path}")

            if self.current_process.returncode == 0 and os.path.exists(final_path):
                file_size = os.path.getsize(final_path)
                return DownloadResult(
                    success=True,
                    file_path=final_path,
                    file_size=file_size
                )
            else:
                # List what files exist for debugging
                existing = glob.glob(os.path.join(DOWNLOAD_DIR, "*"))
                print(f"[Downloader] Files in download dir: {existing}")
                return DownloadResult(
                    success=False,
                    file_path=None,
                    file_size=0,
                    error="Download failed or file not found"
                )

        except asyncio.TimeoutError:
            await self.cancel()
            return DownloadResult(
                success=False,
                file_path=None,
                file_size=0,
                error="Download timed out"
            )
        except Exception as e:
            return DownloadResult(
                success=False,
                file_path=None,
                file_size=0,
                error=str(e)
            )

    def _build_command(
        self,
        m3u8_url: str,
        output_path: str,
        cookies_path: Optional[str],
        resolution: Optional[str],
        output_format: str
    ) -> list:
        """Build N_m3u8DL-RE command arguments."""
        cmd = [
            BINARY_PATH,
            m3u8_url,
            "--save-dir", DOWNLOAD_DIR,
            "--save-name", os.path.basename(output_path),
            "--thread-count", "16",
            "--download-retry-count", "5",
            "-M", f"format={output_format}:muxer=ffmpeg",
            "-mt",  # Concurrent download
            "--auto-select",
            "--del-after-done"  # Clean up temp files
        ]

        # Add headers
        cmd.extend(["-H", f"User-Agent: {self.USER_AGENT}"])
        cmd.extend(["-H", f"Origin: {self.ORIGIN}"])
        cmd.extend(["-H", f"Referer: {self.ORIGIN}/"])

        # Add cookies if available
        if cookies_path and os.path.exists(cookies_path):
            cookie_header = parse_netscape_cookies(cookies_path)
            if cookie_header:
                cmd.extend(["-H", f"Cookie: {cookie_header}"])

        # Add resolution filter
        if resolution and resolution not in ["best", "Best"]:
            cmd.extend(["-sv", f"res={resolution}*"])

        return cmd

    async def _read_progress(self, callback: Optional[Callable]) -> None:
        """Read process output and extract progress."""
        try:
            async def read_with_timeout():
                while True:
                    line = await self.current_process.stdout.readline()
                    if not line:
                        break

                    line_str = line.decode().strip()
                    if not line_str:
                        continue

                    # Extract progress percentage
                    if "%" in line_str and callback:
                        match = re.search(r'(\d+(?:\.\d+)?)\s*%', line_str)
                        if match:
                            percent = float(match.group(1))
                            await callback(percent, line_str)

            await asyncio.wait_for(read_with_timeout(), timeout=self.TIMEOUT)

        except asyncio.TimeoutError:
            raise

    async def cancel(self) -> None:
        """Cancel the current download."""
        if self.current_process:
            try:
                self.current_process.kill()
                await self.current_process.wait()
            except Exception:
                pass


async def get_video_duration(file_path: str) -> Optional[int]:
    """
    Extract video duration using ffprobe.

    Args:
        file_path: Path to video file

    Returns:
        Duration in seconds or None
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
            return int(float(stdout.decode().strip()))
    except Exception as e:
        print(f"[Downloader] Duration extract error: {e}")

    return None


def sanitize_filename(name: str) -> str:
    """
    Sanitize string for use as filename.
    Keeps the title readable while removing only truly problematic characters.
    Also handles URL-encoded names from m3u8 metadata.
    """
    from urllib.parse import unquote

    # First, decode any URL-encoded characters (like %20 for space)
    name = unquote(name)

    # Remove common URL artifacts and m3u8 metadata patterns
    # Pattern: "language - en-IN value - " or similar
    name = re.sub(r'^language\s*[-_]\s*\w+[-_]\w*\s*value\s*[-_]\s*', '', name, flags=re.IGNORECASE)
    name = re.sub(r'^_?language[-_]\w+[-_]value[-_]', '', name, flags=re.IGNORECASE)

    # Remove characters not allowed in filenames
    # Keep: letters, numbers, spaces, hyphens, underscores, dots, colons (for titles like "Movie: Subtitle")
    name = re.sub(r'[<>"/\\|?*]', '', name)

    # Replace colon with a dash or keep it based on context
    # "Movie: Subtitle" -> "Movie - Subtitle"
    name = re.sub(r'\s*:\s*', ' - ', name)

    # Remove any other special characters but keep basic punctuation
    name = re.sub(r'[^\w\s\-\.\(\)]', '', name)

    # Remove leading/trailing underscores and dashes
    name = name.strip('_- ')

    # Normalize whitespace and underscores to spaces
    name = re.sub(r'[_\s]+', ' ', name).strip()

    return name[:200]  # Limit length


def generate_filename(title: str, audio_count: int = 0, season: int = None, episode: int = None) -> str:
    """
    Generate a clean filename with audio info.

    Args:
        title: Video title
        audio_count: Number of audio tracks
        season: Season number (for episodes)
        episode: Episode number (for episodes)

    Returns:
        Clean filename like "Movie Name (Dual)" or "Show Name S01E05 (Tri-Audio)"
    """
    # Sanitize the title
    clean_title = sanitize_filename(title)

    # Add season/episode info for TV shows
    if season is not None and episode is not None:
        clean_title = f"{clean_title} S{season:02d}E{episode:02d}"

    # Add audio info
    if audio_count >= 2:
        if audio_count == 2:
            audio_tag = "(Dual)"
        elif audio_count == 3:
            audio_tag = "(Tri-Audio)"
        elif audio_count == 4:
            audio_tag = "(Quad-Audio)"
        else:
            audio_tag = f"({audio_count}-Audio)"
        clean_title = f"{clean_title} {audio_tag}"

    return clean_title


# Global downloader instance
downloader = Downloader()
