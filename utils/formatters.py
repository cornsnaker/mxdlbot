"""
Formatting utilities for sizes, times, and durations.
"""


def format_size(size_bytes: int) -> str:
    """
    Format bytes to human-readable size.

    Args:
        size_bytes: Size in bytes

    Returns:
        Formatted string like "1.25 GB"
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.2f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def format_speed(bytes_per_sec: float) -> str:
    """
    Format speed to human-readable format.

    Args:
        bytes_per_sec: Speed in bytes per second

    Returns:
        Formatted string like "12.5 MB/s"
    """
    if bytes_per_sec < 1024:
        return f"{bytes_per_sec:.0f} B/s"
    elif bytes_per_sec < 1024 * 1024:
        return f"{bytes_per_sec / 1024:.1f} KB/s"
    else:
        return f"{bytes_per_sec / (1024 * 1024):.2f} MB/s"


def format_time(seconds: float) -> str:
    """
    Format seconds to human-readable time.

    Args:
        seconds: Time in seconds

    Returns:
        Formatted string like "2m 30s" or "1h 5m"
    """
    if seconds < 0:
        return "calculating..."

    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        mins = seconds // 60
        secs = seconds % 60
        return f"{mins}m {secs}s"
    else:
        hours = seconds // 3600
        mins = (seconds % 3600) // 60
        return f"{hours}h {mins}m"


def format_duration(seconds: int) -> str:
    """
    Format video duration.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted string like "1:30:45" or "25:30"
    """
    if seconds is None:
        return "Unknown"

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes}:{secs:02d}"


def truncate(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Truncate text to max length with suffix.

    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add when truncated

    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def format_user_mention(user_id: int, first_name: str) -> str:
    """
    Format user mention for Telegram.

    Args:
        user_id: Telegram user ID
        first_name: User's first name

    Returns:
        Markdown mention format
    """
    # Handle None or non-string first_name
    if first_name is None:
        first_name = "User"
    elif isinstance(first_name, list):
        first_name = first_name[0] if first_name else "User"
    first_name = str(first_name)

    # Escape special characters in name
    safe_name = first_name.replace('[', '').replace(']', '')
    return f"[{safe_name}](tg://user?id={user_id})"
