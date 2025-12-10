"""
State management for MX Player Bot using dictionary-based FSM.
Replaces aiogram FSM with custom implementation for Pyrogram compatibility.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional, List, Any


class UserStep(Enum):
    """Enum defining the possible states in the user flow."""
    IDLE = "idle"
    WAITING_COOKIES = "waiting_cookies"
    SELECT_QUALITY = "select_quality"
    SELECT_AUDIO = "select_audio"
    CONFIRMATION = "confirmation"
    DOWNLOADING = "downloading"
    UPLOADING = "uploading"


@dataclass
class UserState:
    """
    Dataclass storing all session data for a user.

    Attributes:
        step: Current state in the flow
        url: MX Player URL being processed
        metadata: Scraped metadata (title, season, episode, image, m3u8_url)
        resolutions: Parsed video resolutions from m3u8
        audio_tracks: Parsed audio tracks from m3u8
        selected_resolution: User's chosen resolution
        selected_audio: User's chosen audio track
        message_id: ID of the selection message for editing
    """
    step: UserStep = UserStep.IDLE
    url: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    resolutions: Optional[List[Dict[str, Any]]] = None
    audio_tracks: Optional[List[Dict[str, Any]]] = None
    selected_resolution: Optional[str] = None
    selected_audio: Optional[str] = None
    message_id: Optional[int] = None


# Global state storage
user_states: Dict[int, UserState] = {}


def get_state(user_id: int) -> UserState:
    """
    Get user state, creating a new IDLE state if none exists.

    Args:
        user_id: Telegram user ID

    Returns:
        UserState for the user
    """
    if user_id not in user_states:
        user_states[user_id] = UserState()
    return user_states[user_id]


def set_state(user_id: int, **kwargs) -> UserState:
    """
    Update specific fields of a user's state.

    Args:
        user_id: Telegram user ID
        **kwargs: Fields to update (step, url, metadata, etc.)

    Returns:
        Updated UserState
    """
    state = get_state(user_id)
    for key, value in kwargs.items():
        if hasattr(state, key):
            setattr(state, key, value)
    return state


def clear_state(user_id: int) -> None:
    """
    Reset user to IDLE state, clearing all data.

    Args:
        user_id: Telegram user ID
    """
    user_states[user_id] = UserState()
