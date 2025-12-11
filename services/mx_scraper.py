"""
MX Player scraper service with multiple extraction fallbacks.
"""

import re
import json
import aiohttp
from typing import Optional, Dict, Any, List, Tuple
from urllib.parse import urljoin
from dataclasses import dataclass


@dataclass
class VideoMetadata:
    """Video metadata container."""
    title: str
    description: str
    image: Optional[str]
    season: Optional[int]
    episode: Optional[int]
    episode_title: Optional[str]
    is_movie: bool
    m3u8_url: Optional[str]
    duration: Optional[int] = None
    show_id: Optional[str] = None
    content_id: Optional[str] = None
    genres: Optional[List[str]] = None
    release_year: Optional[int] = None
    rating: Optional[str] = None


@dataclass
class Resolution:
    """Video resolution info."""
    height: int
    width: int
    bandwidth: int
    uri: str
    label: str  # e.g., "1080p"


@dataclass
class AudioTrack:
    """Audio track info."""
    name: str
    language: str
    group_id: str
    uri: Optional[str] = None
    is_default: bool = False


@dataclass
class EpisodeInfo:
    """Episode info for show browser."""
    title: str
    episode_number: int
    season_number: int
    url: str
    thumbnail: Optional[str] = None
    duration: Optional[int] = None
    description: Optional[str] = None


@dataclass
class SeasonInfo:
    """Season info for show browser."""
    season_number: int
    title: str
    episodes: List[EpisodeInfo]


class MXScraper:
    """
    MX Player content scraper with fallback extraction methods.

    Extraction order:
    1. JSON-LD structured data
    2. Meta tags fallback
    3. Regex patterns fallback
    """

    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127 Safari/537.36"
    ORIGIN = "https://www.mxplayer.in"

    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                headers={"User-Agent": self.USER_AGENT, "Origin": self.ORIGIN}
            )
        return self.session

    async def close(self):
        """Close the session."""
        if self.session and not self.session.closed:
            await self.session.close()

    async def fetch_html(self, url: str) -> Optional[str]:
        """Fetch HTML content from URL."""
        try:
            session = await self._get_session()
            async with session.get(url) as resp:
                if resp.status != 200:
                    return None
                return await resp.text()
        except Exception as e:
            print(f"[MXScraper] Fetch error: {e}")
            return None

    async def get_metadata(self, url: str) -> Optional[VideoMetadata]:
        """
        Extract video metadata using multiple fallback methods.

        Args:
            url: MX Player content URL

        Returns:
            VideoMetadata object or None on failure
        """
        html = await self.fetch_html(url)
        if not html:
            return None

        # Try extraction methods in order
        metadata = self._extract_json_ld(html)

        if not metadata:
            metadata = self._extract_meta_tags(html)

        if not metadata:
            metadata = self._extract_regex_fallback(html)

        if metadata:
            # Always try to find m3u8 URL
            metadata.m3u8_url = self._find_m3u8(html)

        return metadata

    def _extract_json_ld(self, html: str) -> Optional[VideoMetadata]:
        """Extract metadata from JSON-LD structured data."""
        pattern = r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>'
        matches = re.finditer(pattern, html, re.DOTALL)

        for match in matches:
            try:
                json_data = json.loads(match.group(1))
                if isinstance(json_data, dict):
                    json_data = [json_data]

                for item in json_data:
                    if item.get('@type') in ['Episode', 'Movie', 'VideoObject']:
                        return self._parse_json_ld_item(item)
            except json.JSONDecodeError:
                continue

        return None

    def _parse_json_ld_item(self, item: Dict) -> VideoMetadata:
        """Parse JSON-LD item into VideoMetadata."""
        is_movie = item.get('@type') != 'Episode'

        if is_movie:
            title = item.get('name', 'Unknown Title')
            season = None
            episode = None
            episode_title = None
        else:
            part_of_series = item.get('partOfSeries', {})
            title = part_of_series.get('name', item.get('name', 'Unknown Series'))
            part_of_season = item.get('partOfSeason', {})
            season = part_of_season.get('seasonNumber')
            episode = item.get('episodeNumber')
            episode_title = item.get('name')

        # Ensure title is a string
        if isinstance(title, list):
            title = title[0] if title else 'Unknown Title'
        title = str(title) if title else 'Unknown Title'

        # Get image
        image = None
        imgs = item.get('image')
        if isinstance(imgs, list) and imgs:
            image = imgs[0]
        elif isinstance(imgs, str):
            image = imgs

        # Get duration (ISO 8601 format like PT30M)
        duration = self._parse_duration(item.get('duration'))

        # Get description - ensure it's a string
        description = item.get('description', 'No description available.')
        if isinstance(description, list):
            description = description[0] if description else 'No description available.'
        description = str(description) if description else 'No description available.'

        # Ensure episode_title is a string
        if isinstance(episode_title, list):
            episode_title = episode_title[0] if episode_title else None
        if episode_title:
            episode_title = str(episode_title)

        return VideoMetadata(
            title=title,
            description=description,
            image=image,
            season=season,
            episode=episode,
            episode_title=episode_title,
            is_movie=is_movie,
            m3u8_url=None,
            duration=duration
        )

    def _extract_meta_tags(self, html: str) -> Optional[VideoMetadata]:
        """Fallback: Extract metadata from meta tags."""
        title = self._get_meta_content(html, 'og:title') or self._get_meta_content(html, 'title')
        description = self._get_meta_content(html, 'og:description') or self._get_meta_content(html, 'description')
        image = self._get_meta_content(html, 'og:image')

        if not title:
            return None

        # Try to detect if it's an episode
        season, episode = self._parse_season_episode(title)

        return VideoMetadata(
            title=title,
            description=description or 'No description available.',
            image=image,
            season=season,
            episode=episode,
            episode_title=None,
            is_movie=season is None,
            m3u8_url=None
        )

    def _extract_regex_fallback(self, html: str) -> Optional[VideoMetadata]:
        """Fallback: Extract basic info using regex patterns."""
        # Try to find title in <title> tag
        title_match = re.search(r'<title>([^<]+)</title>', html)
        title = title_match.group(1).strip() if title_match else "Unknown Title"

        # Clean up title
        title = re.sub(r'\s*\|\s*MX Player.*$', '', title)
        title = re.sub(r'\s*-\s*Watch Online.*$', '', title)

        return VideoMetadata(
            title=title,
            description='No description available.',
            image=None,
            season=None,
            episode=None,
            episode_title=None,
            is_movie=True,
            m3u8_url=None
        )

    def _get_meta_content(self, html: str, name: str) -> Optional[str]:
        """Extract content from meta tag."""
        patterns = [
            rf'<meta[^>]*property="{name}"[^>]*content="([^"]*)"',
            rf'<meta[^>]*name="{name}"[^>]*content="([^"]*)"',
            rf'<meta[^>]*content="([^"]*)"[^>]*property="{name}"',
            rf'<meta[^>]*content="([^"]*)"[^>]*name="{name}"',
        ]

        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                return match.group(1)
        return None

    def _parse_season_episode(self, title: str) -> Tuple[Optional[int], Optional[int]]:
        """Parse season and episode from title string."""
        patterns = [
            r'[Ss](\d+)[Ee](\d+)',
            r'[Ss]eason\s*(\d+)\s*[Ee]pisode\s*(\d+)',
            r'S(\d+)\s*E(\d+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, title)
            if match:
                return int(match.group(1)), int(match.group(2))

        return None, None

    def _parse_duration(self, duration_str: Optional[str]) -> Optional[int]:
        """Parse ISO 8601 duration to seconds."""
        if not duration_str:
            return None

        # PT30M, PT1H30M, PT45S, etc.
        match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration_str)
        if match:
            hours = int(match.group(1) or 0)
            minutes = int(match.group(2) or 0)
            seconds = int(match.group(3) or 0)
            return hours * 3600 + minutes * 60 + seconds

        return None

    def _find_m3u8(self, html: str) -> Optional[str]:
        """Find m3u8 URL in HTML."""
        # Pattern 1: Standard URL
        match = re.search(r'(https?://[^"\']+?\.m3u8[^"\']*)', html)
        if match:
            return match.group(1)

        # Pattern 2: Escaped URL
        match = re.search(r'(https?:\\\\/\\\\/[^"]+?\.m3u8[^"]*)', html)
        if match:
            return match.group(1).replace("\\/", "/").replace("\\\\/", "/")

        # Pattern 3: In JSON data
        match = re.search(r'"(?:url|src|file|stream)":\s*"([^"]+\.m3u8[^"]*)"', html)
        if match:
            url = match.group(1).replace("\\/", "/")
            return url

        return None

    async def parse_master_m3u8(self, m3u8_url: str) -> List[Resolution]:
        """
        Parse master m3u8 playlist for available resolutions.

        Args:
            m3u8_url: URL to master m3u8 playlist

        Returns:
            List of Resolution objects sorted by bandwidth (highest first)
        """
        resolutions = []

        try:
            session = await self._get_session()
            async with session.get(m3u8_url) as resp:
                if resp.status != 200:
                    return resolutions
                content = await resp.text()

            base_url = m3u8_url.rsplit('/', 1)[0] + '/'
            lines = content.strip().split('\n')

            i = 0
            while i < len(lines):
                line = lines[i].strip()

                if line.startswith('#EXT-X-STREAM-INF:'):
                    resolution = self._parse_stream_inf(line)
                    if resolution and i + 1 < len(lines):
                        uri = lines[i + 1].strip()
                        if not uri.startswith('http'):
                            uri = urljoin(base_url, uri)
                        resolution.uri = uri
                        resolutions.append(resolution)
                        i += 1

                i += 1

            # Sort by bandwidth (highest first) and remove duplicates
            resolutions.sort(key=lambda x: x.bandwidth, reverse=True)

            seen_heights = set()
            unique = []
            for res in resolutions:
                if res.height not in seen_heights:
                    seen_heights.add(res.height)
                    unique.append(res)

            return unique

        except Exception as e:
            print(f"[MXScraper] M3U8 parse error: {e}")
            return []

    async def parse_audio_tracks(self, m3u8_url: str) -> List[AudioTrack]:
        """
        Parse master m3u8 playlist for available audio tracks.

        Args:
            m3u8_url: URL to master m3u8 playlist

        Returns:
            List of AudioTrack objects
        """
        audio_tracks = []

        try:
            session = await self._get_session()
            async with session.get(m3u8_url) as resp:
                if resp.status != 200:
                    return audio_tracks
                content = await resp.text()

            base_url = m3u8_url.rsplit('/', 1)[0] + '/'

            # Parse #EXT-X-MEDIA:TYPE=AUDIO lines
            pattern = r'#EXT-X-MEDIA:TYPE=AUDIO[^\n]+'
            matches = re.findall(pattern, content)

            for match in matches:
                track = self._parse_audio_media(match, base_url)
                if track:
                    audio_tracks.append(track)

            # Remove duplicates by language
            seen_langs = set()
            unique = []
            for track in audio_tracks:
                if track.language not in seen_langs:
                    seen_langs.add(track.language)
                    unique.append(track)

            return unique

        except Exception as e:
            print(f"[MXScraper] Audio track parse error: {e}")
            return []

    def _parse_audio_media(self, line: str, base_url: str) -> Optional[AudioTrack]:
        """Parse #EXT-X-MEDIA:TYPE=AUDIO line."""
        name_match = re.search(r'NAME="([^"]*)"', line)
        lang_match = re.search(r'LANGUAGE="([^"]*)"', line)
        group_match = re.search(r'GROUP-ID="([^"]*)"', line)
        uri_match = re.search(r'URI="([^"]*)"', line)
        default_match = re.search(r'DEFAULT=(YES|NO)', line)

        if name_match and lang_match:
            uri = None
            if uri_match:
                uri = uri_match.group(1)
                if not uri.startswith('http'):
                    uri = urljoin(base_url, uri)

            return AudioTrack(
                name=name_match.group(1),
                language=lang_match.group(1),
                group_id=group_match.group(1) if group_match else "",
                uri=uri,
                is_default=default_match.group(1) == "YES" if default_match else False
            )

        return None

    def _parse_stream_inf(self, line: str) -> Optional[Resolution]:
        """Parse #EXT-X-STREAM-INF line."""
        bandwidth = 0
        width = 0
        height = 0

        bw_match = re.search(r'BANDWIDTH=(\d+)', line)
        if bw_match:
            bandwidth = int(bw_match.group(1))

        res_match = re.search(r'RESOLUTION=(\d+)x(\d+)', line)
        if res_match:
            width = int(res_match.group(1))
            height = int(res_match.group(2))

        if height:
            return Resolution(
                height=height,
                width=width,
                bandwidth=bandwidth,
                uri="",
                label=f"{height}p"
            )

        return None

    async def get_show_seasons(self, show_url: str) -> List[SeasonInfo]:
        """
        Get all seasons and episodes for a show.

        Args:
            show_url: MX Player show URL

        Returns:
            List of SeasonInfo objects with episodes
        """
        html = await self.fetch_html(show_url)
        if not html:
            return []

        seasons = []

        try:
            # Extract show ID from URL
            show_id_match = re.search(r'/show/([^/]+)', show_url)
            if not show_id_match:
                return []

            show_id = show_id_match.group(1)

            # Try to find season/episode data in JSON
            # Look for __NEXT_DATA__ or similar embedded JSON
            next_data_match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
            if next_data_match:
                try:
                    data = json.loads(next_data_match.group(1))
                    seasons = self._parse_next_data_episodes(data, show_url)
                    if seasons:
                        return seasons
                except json.JSONDecodeError:
                    pass

            # Fallback: Parse episode links from HTML
            seasons = self._parse_html_episodes(html, show_url)

        except Exception as e:
            print(f"[MXScraper] Show seasons error: {e}")

        return seasons

    def _parse_next_data_episodes(self, data: Dict, base_url: str) -> List[SeasonInfo]:
        """Parse episodes from __NEXT_DATA__ JSON."""
        seasons = []

        try:
            # Navigate to episodes data (structure varies)
            props = data.get('props', {}).get('pageProps', {})

            # Try different possible paths
            episodes_data = (
                props.get('episodes') or
                props.get('seasonEpisodes') or
                props.get('show', {}).get('episodes') or
                []
            )

            if not episodes_data:
                return []

            # Group by season
            season_map = {}
            for ep in episodes_data:
                season_num = ep.get('seasonNumber', 1)
                if season_num not in season_map:
                    season_map[season_num] = []

                episode = EpisodeInfo(
                    title=ep.get('title', ep.get('name', f"Episode {ep.get('episodeNumber', 0)}")),
                    episode_number=ep.get('episodeNumber', 0),
                    season_number=season_num,
                    url=self._build_episode_url(base_url, ep),
                    thumbnail=ep.get('image', ep.get('thumbnail')),
                    duration=self._parse_duration(ep.get('duration')),
                    description=ep.get('description')
                )
                season_map[season_num].append(episode)

            # Convert to SeasonInfo list
            for season_num in sorted(season_map.keys()):
                episodes = sorted(season_map[season_num], key=lambda x: x.episode_number)
                seasons.append(SeasonInfo(
                    season_number=season_num,
                    title=f"Season {season_num}",
                    episodes=episodes
                ))

        except Exception as e:
            print(f"[MXScraper] NEXT_DATA parse error: {e}")

        return seasons

    def _parse_html_episodes(self, html: str, base_url: str) -> List[SeasonInfo]:
        """Parse episodes from HTML links (fallback method)."""
        seasons = []

        try:
            # Find episode links
            episode_pattern = r'href="([^"]*(?:episode|watch)[^"]*)"[^>]*>([^<]*)</a>'
            matches = re.findall(episode_pattern, html, re.IGNORECASE)

            if not matches:
                # Try alternative pattern
                episode_pattern = r'href="(/show/[^"]+/season-\d+/[^"]+)"'
                matches = [(m, "") for m in re.findall(episode_pattern, html)]

            # Parse and group
            season_map = {}
            for url, title in matches:
                if not url.startswith('http'):
                    url = urljoin(self.ORIGIN, url)

                # Extract season and episode numbers
                se_match = re.search(r'season-(\d+).*?(?:episode-|ep-?)(\d+)', url, re.IGNORECASE)
                if se_match:
                    season_num = int(se_match.group(1))
                    ep_num = int(se_match.group(2))

                    if season_num not in season_map:
                        season_map[season_num] = []

                    episode = EpisodeInfo(
                        title=title.strip() if title else f"Episode {ep_num}",
                        episode_number=ep_num,
                        season_number=season_num,
                        url=url
                    )
                    season_map[season_num].append(episode)

            # Convert to SeasonInfo list
            for season_num in sorted(season_map.keys()):
                episodes = sorted(season_map[season_num], key=lambda x: x.episode_number)
                # Remove duplicates
                seen = set()
                unique_eps = []
                for ep in episodes:
                    if ep.episode_number not in seen:
                        seen.add(ep.episode_number)
                        unique_eps.append(ep)

                seasons.append(SeasonInfo(
                    season_number=season_num,
                    title=f"Season {season_num}",
                    episodes=unique_eps
                ))

        except Exception as e:
            print(f"[MXScraper] HTML episodes parse error: {e}")

        return seasons

    def _build_episode_url(self, base_url: str, episode_data: Dict) -> str:
        """Build episode URL from episode data."""
        if 'url' in episode_data:
            url = episode_data['url']
            if not url.startswith('http'):
                return urljoin(self.ORIGIN, url)
            return url

        # Try to build from slug/id
        slug = episode_data.get('slug') or episode_data.get('id', '')
        if slug:
            return f"{self.ORIGIN}/show/{slug}"

        return base_url

    def is_show_url(self, url: str) -> bool:
        """Check if URL is a show page (not specific episode)."""
        # Show URLs typically don't have episode number
        if re.search(r'/episode-\d+', url, re.IGNORECASE):
            return False
        if re.search(r'/ep-\d+', url, re.IGNORECASE):
            return False
        if '/show/' in url and not re.search(r'season-\d+', url):
            return True
        return False


# Global scraper instance
mx_scraper = MXScraper()
