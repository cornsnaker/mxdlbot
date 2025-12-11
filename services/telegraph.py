"""
Telegraph service for uploading MediaInfo.
"""

import aiohttp
from typing import Optional
from utils.mediainfo import MediaInfo


async def create_telegraph_page(title: str, media_info: MediaInfo, file_path: str) -> Optional[str]:
    """
    Create a Telegraph page with MediaInfo details.

    Args:
        title: Video title
        media_info: MediaInfo object with video details
        file_path: Path to video file for raw mediainfo

    Returns:
        Telegraph page URL or None on failure
    """
    try:
        # Get raw mediainfo text
        raw_mediainfo = await get_raw_mediainfo(file_path)

        # Build HTML content
        content = build_mediainfo_html(title, media_info, raw_mediainfo)

        # Create Telegraph page
        async with aiohttp.ClientSession() as session:
            # Create account (anonymous)
            create_account_url = "https://api.telegra.ph/createAccount"
            account_data = {
                "short_name": "MXBot",
                "author_name": "MX Player Bot"
            }

            async with session.post(create_account_url, data=account_data) as resp:
                if resp.status != 200:
                    return None
                result = await resp.json()
                if not result.get("ok"):
                    return None
                access_token = result["result"]["access_token"]

            # Create page using form data (Telegraph API requires this)
            create_page_url = "https://api.telegra.ph/createPage"
            page_data = {
                "access_token": access_token,
                "title": f"MediaInfo - {title[:50]}",
                "author_name": "MX Player Bot",
                "content": content,
                "return_content": "false"
            }

            async with session.post(create_page_url, data=page_data) as resp:
                if resp.status != 200:
                    print(f"[Telegraph] Page creation failed: status {resp.status}")
                    return None
                result = await resp.json()
                print(f"[Telegraph] Page result: {result}")
                if result.get("ok"):
                    return result["result"]["url"]
                else:
                    print(f"[Telegraph] Error: {result.get('error')}")

        return None

    except Exception as e:
        print(f"[Telegraph] Error creating page: {e}")
        return None


async def get_raw_mediainfo(file_path: str) -> str:
    """
    Get raw mediainfo text output.

    Args:
        file_path: Path to video file

    Returns:
        Raw mediainfo text
    """
    try:
        import asyncio

        process = await asyncio.create_subprocess_exec(
            "mediainfo", file_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await process.communicate()

        if process.returncode == 0:
            return stdout.decode('utf-8', errors='ignore')
    except FileNotFoundError:
        # mediainfo CLI not installed, use pymediainfo
        try:
            from pymediainfo import MediaInfo as PyMediaInfo
            media_info = PyMediaInfo.parse(file_path, output="text")
            return media_info if media_info else "MediaInfo not available"
        except Exception:
            pass
    except Exception as e:
        print(f"[Telegraph] MediaInfo error: {e}")

    return "MediaInfo not available"


def build_mediainfo_html(title: str, media_info: MediaInfo, raw_mediainfo: str) -> str:
    """
    Build HTML content for Telegraph page.

    Args:
        title: Video title
        media_info: Parsed MediaInfo object
        raw_mediainfo: Raw mediainfo text output

    Returns:
        JSON-encoded HTML content for Telegraph API
    """
    import json

    content = []

    # Title
    content.append({"tag": "h3", "children": [title]})

    # Summary section
    content.append({"tag": "h4", "children": ["Summary"]})

    summary_lines = []

    if media_info:
        if media_info.container:
            summary_lines.append(f"Container: {media_info.container}")
        if media_info.duration:
            mins, secs = divmod(media_info.duration, 60)
            hours, mins = divmod(mins, 60)
            if hours > 0:
                summary_lines.append(f"Duration: {hours}h {mins}m {secs}s")
            else:
                summary_lines.append(f"Duration: {mins}m {secs}s")
        if media_info.file_size:
            size_mb = media_info.file_size / (1024 * 1024)
            if size_mb > 1024:
                summary_lines.append(f"File Size: {size_mb/1024:.2f} GB")
            else:
                summary_lines.append(f"File Size: {size_mb:.2f} MB")

    if summary_lines:
        content.append({"tag": "p", "children": ["\n".join(summary_lines)]})

    # Video section
    if media_info and media_info.width and media_info.height:
        content.append({"tag": "h4", "children": ["Video"]})
        video_info = [
            f"Resolution: {media_info.width}x{media_info.height} ({media_info.quality_label})",
        ]
        if media_info.video_codec:
            video_info.append(f"Codec: {media_info.video_codec}")
        if media_info.frame_rate:
            video_info.append(f"Frame Rate: {media_info.frame_rate} fps")
        content.append({"tag": "p", "children": ["\n".join(video_info)]})

    # Audio section
    if media_info and media_info.audio_tracks:
        content.append({"tag": "h4", "children": [f"Audio ({len(media_info.audio_tracks)} tracks)"]})
        audio_lines = []
        for i, track in enumerate(media_info.audio_tracks, 1):
            audio_lines.append(f"{i}. {track.language} - {track.codec} ({track.channels}ch)")
        content.append({"tag": "p", "children": ["\n".join(audio_lines)]})

    # Subtitles section
    if media_info and media_info.subtitles:
        content.append({"tag": "h4", "children": [f"Subtitles ({len(media_info.subtitles)} tracks)"]})
        sub_lines = []
        for i, sub in enumerate(media_info.subtitles, 1):
            sub_lines.append(f"{i}. {sub.language} ({sub.format})")
        content.append({"tag": "p", "children": ["\n".join(sub_lines)]})

    # Raw MediaInfo
    content.append({"tag": "h4", "children": ["Raw MediaInfo"]})
    content.append({"tag": "pre", "children": [raw_mediainfo[:4000]]})  # Limit length

    return json.dumps(content)
