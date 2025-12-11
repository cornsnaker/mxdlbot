"""
Middleware decorators for authentication and authorization.
"""

from functools import wraps
from typing import Callable
from pyrogram import Client
from pyrogram.types import Message, CallbackQuery
from config import OWNER_ID, ADMINS
from core.database import db


def authorized(func: Callable) -> Callable:
    """
    Decorator to check if user is authorized (not banned).
    Silently ignores banned users.
    """
    @wraps(func)
    async def wrapper(client: Client, update: Message | CallbackQuery, *args, **kwargs):
        if isinstance(update, CallbackQuery):
            user_id = update.from_user.id
        else:
            user_id = update.from_user.id

        # Check if user is banned
        if await db.is_banned(user_id):
            return  # Silently ignore banned users

        # Update user activity
        await db.add_user(
            user_id=user_id,
            username=update.from_user.username,
            first_name=update.from_user.first_name
        )

        return await func(client, update, *args, **kwargs)

    return wrapper


def admin_only(func: Callable) -> Callable:
    """
    Decorator to restrict command to admins only.
    Shows error message to non-admins.
    """
    @wraps(func)
    async def wrapper(client: Client, message: Message, *args, **kwargs):
        user_id = message.from_user.id

        if user_id != OWNER_ID and user_id not in ADMINS:
            await message.reply_text("⛔ This command is restricted to admins only.")
            return

        return await func(client, message, *args, **kwargs)

    return wrapper


def owner_only(func: Callable) -> Callable:
    """
    Decorator to restrict command to owner only.
    """
    @wraps(func)
    async def wrapper(client: Client, message: Message, *args, **kwargs):
        user_id = message.from_user.id

        if user_id != OWNER_ID:
            await message.reply_text("⛔ This command is restricted to the bot owner only.")
            return

        return await func(client, message, *args, **kwargs)

    return wrapper


async def check_user_exists(user_id: int) -> bool:
    """Check if a user exists in the database."""
    user = await db.get_user(user_id)
    return user is not None
