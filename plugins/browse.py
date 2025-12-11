"""
Show browser plugin for listing and selecting episodes from a series.

Allows users to:
1. Send a show URL to see all seasons/episodes
2. Select a season to view episodes
3. Select individual episodes or batch download
"""

import re
from typing import Dict, List
from pyrogram import Client, filters
from pyrogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from core.middlewares import authorized
from core.database import db
from config import user_has_cookies
from services.mx_scraper import mx_scraper, SeasonInfo, EpisodeInfo
from utils.notifications import Toast
from states import get_state, set_state, clear_state, UserStep


# Store show data temporarily (user_id -> show_data)
show_cache: Dict[int, Dict] = {}


def build_seasons_keyboard(seasons: List[SeasonInfo], page: int = 0) -> InlineKeyboardMarkup:
    """Build keyboard for season selection."""
    buttons = []

    # 4 seasons per page
    page_size = 8
    start = page * page_size
    end = start + page_size

    page_seasons = seasons[start:end]
    row = []

    for season in page_seasons:
        ep_count = len(season.episodes)
        btn_text = f"S{season.season_number} ({ep_count} ep)"
        callback_data = f"season:{season.season_number}"
        row.append(InlineKeyboardButton(btn_text, callback_data=callback_data))

        if len(row) == 2:
            buttons.append(row)
            row = []

    if row:
        buttons.append(row)

    # Navigation row
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"seasons_page:{page - 1}"))
    if end < len(seasons):
        nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"seasons_page:{page + 1}"))

    if nav_row:
        buttons.append(nav_row)

    # Cancel button
    buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="browse_cancel")])

    return InlineKeyboardMarkup(buttons)


def build_episodes_keyboard(
    episodes: List[EpisodeInfo],
    season_num: int,
    page: int = 0,
    selected: set = None
) -> InlineKeyboardMarkup:
    """Build keyboard for episode selection."""
    if selected is None:
        selected = set()

    buttons = []

    # 6 episodes per page
    page_size = 6
    start = page * page_size
    end = start + page_size

    page_episodes = episodes[start:end]

    for ep in page_episodes:
        check = "✓ " if ep.episode_number in selected else ""
        btn_text = f"{check}Ep {ep.episode_number}"
        callback_data = f"ep:{season_num}:{ep.episode_number}"
        buttons.append([InlineKeyboardButton(btn_text, callback_data=callback_data)])

    # Selection helpers
    helper_row = [
        InlineKeyboardButton("Select All", callback_data=f"select_all:{season_num}"),
        InlineKeyboardButton("Clear", callback_data=f"clear_sel:{season_num}")
    ]
    buttons.append(helper_row)

    # Navigation row
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"eps_page:{season_num}:{page - 1}"))

    nav_row.append(InlineKeyboardButton(f"📄 {page + 1}/{(len(episodes) + page_size - 1) // page_size}", callback_data="noop"))

    if end < len(episodes):
        nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"eps_page:{season_num}:{page + 1}"))

    buttons.append(nav_row)

    # Action row
    action_row = [
        InlineKeyboardButton("⬅️ Seasons", callback_data="back_seasons"),
    ]

    if selected:
        action_row.append(InlineKeyboardButton(f"⬇️ Download ({len(selected)})", callback_data=f"dl_selected:{season_num}"))

    buttons.append(action_row)

    # Cancel
    buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="browse_cancel")])

    return InlineKeyboardMarkup(buttons)


@Client.on_message(filters.regex(r'mxplayer\.in/show/[^/]+$') & filters.private)
@authorized
async def handle_show_link(client: Client, message: Message):
    """Handle MX Player show URLs (not specific episodes)."""
    user_id = message.from_user.id
    text = message.text

    # Extract URL
    url_match = re.search(r'https?://[^\s]*mxplayer\.in/show/[^\s/]+', text)
    if not url_match:
        return

    url = url_match.group(0)

    # Check if it's actually a show page (not an episode)
    if not mx_scraper.is_show_url(url):
        return  # Let download.py handle it

    # Check if user has cookies
    if not user_has_cookies(user_id):
        await message.reply_text(
            "**Authentication Required**\n\n"
            "You need to upload your cookies first.\n"
            "Use /auth to get started."
        )
        return

    # Create toast
    toast = Toast(client, message.chat.id)
    await toast.loading("Fetching show information...")

    try:
        # Get show seasons and episodes
        seasons = await mx_scraper.get_show_seasons(url)

        if not seasons:
            await toast.error("Could not fetch show episodes. Try sending a specific episode link instead.")
            return

        # Get show metadata
        metadata = await mx_scraper.get_metadata(url)
        show_title = metadata.title if metadata else "Unknown Show"

        # Cache show data
        show_cache[user_id] = {
            'url': url,
            'title': show_title,
            'seasons': seasons,
            'selected': {},  # season_num -> set of episode numbers
            'current_season': None,
            'current_page': 0
        }

        # Build message
        total_episodes = sum(len(s.episodes) for s in seasons)

        text = f"📺 **{show_title}**\n\n"
        text += f"**Seasons:** {len(seasons)}\n"
        text += f"**Total Episodes:** {total_episodes}\n\n"
        text += "Select a season to browse episodes:"

        keyboard = build_seasons_keyboard(seasons)

        await toast.dismiss()

        if metadata and metadata.image:
            try:
                await client.send_photo(
                    chat_id=message.chat.id,
                    photo=metadata.image,
                    caption=text,
                    reply_markup=keyboard
                )
            except Exception:
                await message.reply_text(text, reply_markup=keyboard)
        else:
            await message.reply_text(text, reply_markup=keyboard)

    except Exception as e:
        await toast.error(f"Error: {str(e)[:100]}")


@Client.on_callback_query(filters.regex(r"^season:(\d+)$"))
@authorized
async def callback_select_season(client: Client, callback: CallbackQuery):
    """Handle season selection."""
    user_id = callback.from_user.id

    if user_id not in show_cache:
        await callback.answer("Session expired. Send the show link again.", show_alert=True)
        return

    season_num = int(callback.matches[0].group(1))
    show_data = show_cache[user_id]

    # Find the season
    season = None
    for s in show_data['seasons']:
        if s.season_number == season_num:
            season = s
            break

    if not season:
        await callback.answer("Season not found.", show_alert=True)
        return

    show_data['current_season'] = season_num
    show_data['current_page'] = 0

    # Get selected episodes for this season
    selected = show_data['selected'].get(season_num, set())

    # Build episodes list
    text = f"📺 **{show_data['title']}**\n"
    text += f"📂 **Season {season_num}**\n\n"
    text += f"Episodes: {len(season.episodes)}\n\n"
    text += "Tap episodes to select, then download:"

    keyboard = build_episodes_keyboard(season.episodes, season_num, 0, selected)

    try:
        await callback.message.edit_caption(caption=text, reply_markup=keyboard)
    except Exception:
        await callback.message.edit_text(text, reply_markup=keyboard)

    await callback.answer()


@Client.on_callback_query(filters.regex(r"^ep:(\d+):(\d+)$"))
@authorized
async def callback_toggle_episode(client: Client, callback: CallbackQuery):
    """Toggle episode selection."""
    user_id = callback.from_user.id

    if user_id not in show_cache:
        await callback.answer("Session expired.", show_alert=True)
        return

    season_num = int(callback.matches[0].group(1))
    ep_num = int(callback.matches[0].group(2))

    show_data = show_cache[user_id]

    # Initialize selected set for this season
    if season_num not in show_data['selected']:
        show_data['selected'][season_num] = set()

    # Toggle selection
    selected = show_data['selected'][season_num]
    if ep_num in selected:
        selected.remove(ep_num)
    else:
        selected.add(ep_num)

    # Find season
    season = None
    for s in show_data['seasons']:
        if s.season_number == season_num:
            season = s
            break

    if not season:
        await callback.answer("Error", show_alert=True)
        return

    # Rebuild keyboard
    page = show_data.get('current_page', 0)
    keyboard = build_episodes_keyboard(season.episodes, season_num, page, selected)

    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer(f"Episode {ep_num} {'selected' if ep_num in selected else 'deselected'}")


@Client.on_callback_query(filters.regex(r"^select_all:(\d+)$"))
@authorized
async def callback_select_all(client: Client, callback: CallbackQuery):
    """Select all episodes in current season."""
    user_id = callback.from_user.id

    if user_id not in show_cache:
        await callback.answer("Session expired.", show_alert=True)
        return

    season_num = int(callback.matches[0].group(1))
    show_data = show_cache[user_id]

    # Find season
    season = None
    for s in show_data['seasons']:
        if s.season_number == season_num:
            season = s
            break

    if not season:
        return

    # Select all
    show_data['selected'][season_num] = {ep.episode_number for ep in season.episodes}

    page = show_data.get('current_page', 0)
    keyboard = build_episodes_keyboard(season.episodes, season_num, page, show_data['selected'][season_num])

    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer(f"Selected all {len(season.episodes)} episodes")


@Client.on_callback_query(filters.regex(r"^clear_sel:(\d+)$"))
@authorized
async def callback_clear_selection(client: Client, callback: CallbackQuery):
    """Clear episode selection."""
    user_id = callback.from_user.id

    if user_id not in show_cache:
        await callback.answer("Session expired.", show_alert=True)
        return

    season_num = int(callback.matches[0].group(1))
    show_data = show_cache[user_id]

    show_data['selected'][season_num] = set()

    # Find season
    season = None
    for s in show_data['seasons']:
        if s.season_number == season_num:
            season = s
            break

    if not season:
        return

    page = show_data.get('current_page', 0)
    keyboard = build_episodes_keyboard(season.episodes, season_num, page, set())

    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer("Selection cleared")


@Client.on_callback_query(filters.regex(r"^eps_page:(\d+):(\d+)$"))
@authorized
async def callback_episodes_page(client: Client, callback: CallbackQuery):
    """Navigate episode pages."""
    user_id = callback.from_user.id

    if user_id not in show_cache:
        await callback.answer("Session expired.", show_alert=True)
        return

    season_num = int(callback.matches[0].group(1))
    page = int(callback.matches[0].group(2))

    show_data = show_cache[user_id]
    show_data['current_page'] = page

    # Find season
    season = None
    for s in show_data['seasons']:
        if s.season_number == season_num:
            season = s
            break

    if not season:
        return

    selected = show_data['selected'].get(season_num, set())
    keyboard = build_episodes_keyboard(season.episodes, season_num, page, selected)

    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer()


@Client.on_callback_query(filters.regex(r"^seasons_page:(\d+)$"))
@authorized
async def callback_seasons_page(client: Client, callback: CallbackQuery):
    """Navigate season pages."""
    user_id = callback.from_user.id

    if user_id not in show_cache:
        await callback.answer("Session expired.", show_alert=True)
        return

    page = int(callback.matches[0].group(1))
    show_data = show_cache[user_id]

    keyboard = build_seasons_keyboard(show_data['seasons'], page)
    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer()


@Client.on_callback_query(filters.regex(r"^back_seasons$"))
@authorized
async def callback_back_to_seasons(client: Client, callback: CallbackQuery):
    """Go back to season selection."""
    user_id = callback.from_user.id

    if user_id not in show_cache:
        await callback.answer("Session expired.", show_alert=True)
        return

    show_data = show_cache[user_id]

    # Count total selected
    total_selected = sum(len(eps) for eps in show_data['selected'].values())

    text = f"📺 **{show_data['title']}**\n\n"
    text += f"**Seasons:** {len(show_data['seasons'])}\n"

    if total_selected > 0:
        text += f"**Selected:** {total_selected} episodes\n"

    text += "\nSelect a season to browse episodes:"

    keyboard = build_seasons_keyboard(show_data['seasons'])

    try:
        await callback.message.edit_caption(caption=text, reply_markup=keyboard)
    except Exception:
        await callback.message.edit_text(text, reply_markup=keyboard)

    await callback.answer()


@Client.on_callback_query(filters.regex(r"^dl_selected:(\d+)$"))
@authorized
async def callback_download_selected(client: Client, callback: CallbackQuery):
    """Start downloading selected episodes."""
    user_id = callback.from_user.id

    if user_id not in show_cache:
        await callback.answer("Session expired.", show_alert=True)
        return

    season_num = int(callback.matches[0].group(1))
    show_data = show_cache[user_id]

    selected = show_data['selected'].get(season_num, set())

    if not selected:
        await callback.answer("No episodes selected.", show_alert=True)
        return

    # Find season and get episode URLs
    season = None
    for s in show_data['seasons']:
        if s.season_number == season_num:
            season = s
            break

    if not season:
        await callback.answer("Error", show_alert=True)
        return

    # Get episodes to download
    episodes_to_download = [ep for ep in season.episodes if ep.episode_number in selected]
    episodes_to_download.sort(key=lambda x: x.episode_number)

    await callback.answer(f"Starting download of {len(episodes_to_download)} episodes...")

    # Delete the browse message
    try:
        await callback.message.delete()
    except Exception:
        pass

    # Send info message
    info_msg = await client.send_message(
        chat_id=callback.message.chat.id,
        text=f"**Batch Download Started**\n\n"
             f"📺 {show_data['title']}\n"
             f"📂 Season {season_num}\n"
             f"📋 Episodes: {len(episodes_to_download)}\n\n"
             f"Episodes will be downloaded one by one. Please wait..."
    )

    # Clean up cache
    del show_cache[user_id]

    # Queue each episode for download by sending links
    # The download.py handler will process each one
    for i, ep in enumerate(episodes_to_download, 1):
        await client.send_message(
            chat_id=callback.message.chat.id,
            text=f"⬇️ **Queued ({i}/{len(episodes_to_download)}):** Episode {ep.episode_number}\n{ep.url}"
        )

        # Small delay between messages to avoid flood
        if i < len(episodes_to_download):
            import asyncio
            await asyncio.sleep(0.5)


@Client.on_callback_query(filters.regex(r"^browse_cancel$"))
@authorized
async def callback_browse_cancel(client: Client, callback: CallbackQuery):
    """Cancel show browsing."""
    user_id = callback.from_user.id

    # Clean up cache
    if user_id in show_cache:
        del show_cache[user_id]

    try:
        await callback.message.delete()
    except Exception:
        await callback.message.edit_text("❌ Cancelled")

    await callback.answer("Cancelled")


@Client.on_callback_query(filters.regex(r"^noop$"))
@authorized
async def callback_noop(client: Client, callback: CallbackQuery):
    """No-op callback for page indicator."""
    await callback.answer()
