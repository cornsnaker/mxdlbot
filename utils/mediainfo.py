"""
Media info extraction using pymediainfo.
Extracts audio tracks, video quality, subtitles count for detailed captions.
"""

import os
from typing import Optional, List, Dict, Any
from dataclasses import dataclass


@dataclass
class AudioTrackInfo:
    """Audio track information."""
    language: str
    codec: str
    channels: int
    bitrate: Optional[int] = None


@dataclass
class SubtitleInfo:
    """Subtitle track information."""
    language: str
    format: str


@dataclass
class MediaInfo:
    """Complete media information."""
    # Video
    video_codec: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    video_bitrate: Optional[int] = None
    duration: Optional[int] = None  # in seconds
    frame_rate: Optional[float] = None

    # Audio
    audio_tracks: List[AudioTrackInfo] = None

    # Subtitles
    subtitles: List[SubtitleInfo] = None

    # General
    file_size: Optional[int] = None
    container: Optional[str] = None

    def __post_init__(self):
        if self.audio_tracks is None:
            self.audio_tracks = []
        if self.subtitles is None:
            self.subtitles = []

    @property
    def quality_label(self) -> str:
        """Get quality label based on resolution."""
        if not self.height:
            return "Unknown"

        if self.height >= 2160:
            return "2160p"
        elif self.height >= 1440:
            return "1440p"
        elif self.height >= 1080:
            return "1080p"
        elif self.height >= 720:
            return "720p"
        elif self.height >= 480:
            return "480p"
        elif self.height >= 360:
            return "360p"
        else:
            return f"{self.height}p"

    @property
    def audio_type_label(self) -> str:
        """Get audio type label (Dual-Audio, Tri-Audio, etc.)."""
        count = len(self.audio_tracks)
        if count == 0:
            return ""
        elif count == 1:
            return ""
        elif count == 2:
            return "Dual-Audio"
        elif count == 3:
            return "Tri-Audio"
        elif count == 4:
            return "Quad-Audio"
        else:
            return f"{count}-Audio"

    @property
    def audio_languages(self) -> List[str]:
        """Get list of audio language names."""
        languages = []
        for track in self.audio_tracks:
            if track.language and track.language.lower() not in ['und', 'undefined', '']:
                languages.append(track.language)
        return languages

    @property
    def subtitle_count(self) -> int:
        """Get subtitle track count."""
        return len(self.subtitles)


def extract_media_info(file_path: str) -> Optional[MediaInfo]:
    """
    Extract media information from a video file using pymediainfo.

    Args:
        file_path: Path to the video file

    Returns:
        MediaInfo object with all extracted information, or None if failed
    """
    if not os.path.exists(file_path):
        return None

    try:
        from pymediainfo import MediaInfo as PyMediaInfo

        media_info = PyMediaInfo.parse(file_path)

        result = MediaInfo()
        audio_tracks = []
        subtitles = []

        for track in media_info.tracks:
            if track.track_type == "General":
                result.file_size = track.file_size
                result.container = track.format
                if track.duration:
                    result.duration = int(float(track.duration) / 1000)  # ms to seconds

            elif track.track_type == "Video":
                result.video_codec = track.codec_id or track.format
                result.width = track.width
                result.height = track.height
                result.video_bitrate = track.bit_rate
                result.frame_rate = track.frame_rate
                if not result.duration and track.duration:
                    result.duration = int(float(track.duration) / 1000)

            elif track.track_type == "Audio":
                language = track.language or track.title or "Unknown"
                # Capitalize language name
                if language.lower() in ['hin', 'hindi']:
                    language = "Hindi"
                elif language.lower() in ['eng', 'english']:
                    language = "English"
                elif language.lower() in ['tam', 'tamil']:
                    language = "Tamil"
                elif language.lower() in ['tel', 'telugu']:
                    language = "Telugu"
                elif language.lower() in ['jpn', 'japanese', 'ja']:
                    language = "Japanese"
                elif language.lower() in ['kor', 'korean', 'ko']:
                    language = "Korean"
                elif language.lower() in ['mal', 'malayalam']:
                    language = "Malayalam"
                elif language.lower() in ['kan', 'kannada']:
                    language = "Kannada"
                elif language.lower() in ['ben', 'bengali']:
                    language = "Bengali"
                elif language.lower() in ['mar', 'marathi']:
                    language = "Marathi"
                elif language.lower() in ['und', 'undefined']:
                    language = "Unknown"
                else:
                    language = language.capitalize()

                audio_tracks.append(AudioTrackInfo(
                    language=language,
                    codec=track.codec_id or track.format or "Unknown",
                    channels=track.channel_s or 2,
                    bitrate=track.bit_rate
                ))

            elif track.track_type == "Text":
                language = track.language or track.title or "Unknown"
                if language.lower() in ['und', 'undefined']:
                    language = "Unknown"
                else:
                    language = language.capitalize()

                subtitles.append(SubtitleInfo(
                    language=language,
                    format=track.format or "SRT"
                ))

        result.audio_tracks = audio_tracks
        result.subtitles = subtitles

        return result

    except ImportError:
        print("[MediaInfo] pymediainfo not installed, using fallback")
        return _fallback_media_info(file_path)
    except Exception as e:
        print(f"[MediaInfo] Error extracting info: {e}")
        return _fallback_media_info(file_path)


def _fallback_media_info(file_path: str) -> MediaInfo:
    """
    Fallback when pymediainfo is not available.
    Returns basic info from file.
    """
    result = MediaInfo()

    if os.path.exists(file_path):
        result.file_size = os.path.getsize(file_path)

        # Try to detect container from extension
        ext = os.path.splitext(file_path)[1].lower()
        if ext in ['.mp4', '.mkv', '.avi', '.mov', '.webm']:
            result.container = ext[1:].upper()

    return result


def get_type_label(audio_count: int, subtitle_count: int) -> str:
    """
    Generate the type label like (Tri-Audio) (Multi-Subs)[3]

    Args:
        audio_count: Number of audio tracks
        subtitle_count: Number of subtitle tracks

    Returns:
        Formatted type label string
    """
    parts = []

    # Audio part
    if audio_count >= 2:
        if audio_count == 2:
            parts.append("(Dual-Audio)")
        elif audio_count == 3:
            parts.append("(Tri-Audio)")
        elif audio_count == 4:
            parts.append("(Quad-Audio)")
        else:
            parts.append(f"({audio_count}-Audio)")

    # Subtitle part
    if subtitle_count > 0:
        if subtitle_count == 1:
            parts.append("(Subs)")
        else:
            parts.append(f"(Multi-Subs)[{subtitle_count}]")

    return " ".join(parts)
