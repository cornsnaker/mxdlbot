"""
Admin commands for bot management.
"""

import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait, UserIsBlocked, InputUserDeactivated
from core.middlewares import admin_only, owner_only
from core.database import db
from config import OWNER_ID, ADMINS


@Client.on_message(filters.command("stats") & filters.private)
@admin_only
async def cmd_stats(client: Client, message: Message):
    """Show bot statistics."""
    status_msg = await message.reply_text("Fetching statistics...")

    stats = await db.get_stats()

    text = f"""**Bot Statistics**

**Users:**
- Total users: {stats['total_users']}
- Active today: {stats['active_today']}
- Banned users: {stats['banned_users']}

**Server:**
- Status: Online
- Pyrogram: Running"""

    await status_msg.edit_text(text)


@Client.on_message(filters.command("broadcast") & filters.private)
@admin_only
async def cmd_broadcast(client: Client, message: Message):
    """
    Broadcast message to all users.

    Usage: /broadcast <message>
    Or reply to a message with /broadcast
    """
    # Get message to broadcast
    if message.reply_to_message:
        broadcast_msg = message.reply_to_message
    elif len(message.command) > 1:
        broadcast_text = message.text.split(None, 1)[1]
        broadcast_msg = None
    else:
        await message.reply_text(
            "**Usage:**\n"
            "/broadcast <message>\n"
            "Or reply to a message with /broadcast"
        )
        return

    # Get all users
    users = await db.get_all_users()
    total = len(users)

    if total == 0:
        await message.reply_text("No users to broadcast to.")
        return

    status_msg = await message.reply_text(
        f"**Broadcasting...**\n\n"
        f"Total users: {total}\n"
        f"Progress: 0/{total}"
    )

    success = 0
    failed = 0
    blocked = 0

    for i, user_id in enumerate(users):
        try:
            if broadcast_msg:
                # Forward or copy the message
                await broadcast_msg.copy(chat_id=user_id)
            else:
                await client.send_message(chat_id=user_id, text=broadcast_text)
            success += 1

        except FloodWait as e:
            await asyncio.sleep(e.value)
            # Retry after flood wait
            try:
                if broadcast_msg:
                    await broadcast_msg.copy(chat_id=user_id)
                else:
                    await client.send_message(chat_id=user_id, text=broadcast_text)
                success += 1
            except Exception:
                failed += 1

        except (UserIsBlocked, InputUserDeactivated):
            blocked += 1
            # Optionally remove blocked/deactivated users
            # await db.delete_user(user_id)

        except Exception:
            failed += 1

        # Update status every 50 users
        if (i + 1) % 50 == 0:
            try:
                await status_msg.edit_text(
                    f"**Broadcasting...**\n\n"
                    f"Total: {total}\n"
                    f"Progress: {i + 1}/{total}\n"
                    f"Success: {success}\n"
                    f"Failed: {failed}\n"
                    f"Blocked: {blocked}"
                )
            except Exception:
                pass

        # Rate limiting
        await asyncio.sleep(0.05)

    # Final status
    await status_msg.edit_text(
        f"**Broadcast Complete**\n\n"
        f"Total: {total}\n"
        f"Success: {success}\n"
        f"Failed: {failed}\n"
        f"Blocked/Deactivated: {blocked}"
    )


@Client.on_message(filters.command("ban") & filters.private)
@admin_only
async def cmd_ban(client: Client, message: Message):
    """
    Ban a user from using the bot.

    Usage: /ban <user_id> [reason]
    """
    if len(message.command) < 2:
        await message.reply_text(
            "**Usage:**\n"
            "/ban <user_id> [reason]\n\n"
            "Example: /ban 123456789 Spam"
        )
        return

    try:
        target_id = int(message.command[1])
    except ValueError:
        await message.reply_text("Invalid user ID. Must be a number.")
        return

    # Check if trying to ban admin or owner
    if target_id == OWNER_ID or target_id in ADMINS:
        await message.reply_text("Cannot ban admins or owner.")
        return

    reason = " ".join(message.command[2:]) if len(message.command) > 2 else "No reason provided"
    admin_id = message.from_user.id

    # Check if already banned
    if await db.is_banned(target_id):
        await message.reply_text(f"User `{target_id}` is already banned.")
        return

    success = await db.ban_user(target_id, reason=reason, banned_by=admin_id)

    if success:
        await message.reply_text(
            f"**User Banned**\n\n"
            f"User ID: `{target_id}`\n"
            f"Reason: {reason}\n"
            f"Banned by: {message.from_user.mention}"
        )

        # Notify the banned user (optional)
        try:
            await client.send_message(
                chat_id=target_id,
                text=f"**You have been banned from using this bot.**\n\nReason: {reason}"
            )
        except Exception:
            pass
    else:
        await message.reply_text("Failed to ban user. They may already be banned.")


@Client.on_message(filters.command("unban") & filters.private)
@admin_only
async def cmd_unban(client: Client, message: Message):
    """
    Unban a user.

    Usage: /unban <user_id>
    """
    if len(message.command) < 2:
        await message.reply_text(
            "**Usage:**\n"
            "/unban <user_id>\n\n"
            "Example: /unban 123456789"
        )
        return

    try:
        target_id = int(message.command[1])
    except ValueError:
        await message.reply_text("Invalid user ID. Must be a number.")
        return

    # Check if actually banned
    if not await db.is_banned(target_id):
        await message.reply_text(f"User `{target_id}` is not banned.")
        return

    success = await db.unban_user(target_id)

    if success:
        await message.reply_text(f"**User Unbanned**\n\nUser ID: `{target_id}`")

        # Notify the user (optional)
        try:
            await client.send_message(
                chat_id=target_id,
                text="**You have been unbanned.**\n\nYou can now use the bot again."
            )
        except Exception:
            pass
    else:
        await message.reply_text("Failed to unban user.")


@Client.on_message(filters.command("banlist") & filters.private)
@admin_only
async def cmd_banlist(client: Client, message: Message):
    """Show list of banned users."""
    banned = await db.get_banned_users()

    if not banned:
        await message.reply_text("No banned users.")
        return

    lines = ["**Banned Users**\n"]

    for user in banned[:50]:  # Limit to 50
        user_id = user.get('user_id')
        reason = user.get('reason', 'No reason')
        banned_at = user.get('banned_at')
        date_str = banned_at.strftime('%Y-%m-%d') if banned_at else 'Unknown'

        lines.append(f"- `{user_id}` | {reason[:20]} | {date_str}")

    if len(banned) > 50:
        lines.append(f"\n_...and {len(banned) - 50} more_")

    await message.reply_text("\n".join(lines))


@Client.on_message(filters.command("users") & filters.private)
@owner_only
async def cmd_users(client: Client, message: Message):
    """Show recent users (owner only)."""
    users = await db.get_all_users()
    total = len(users)

    text = f"**Total Users:** {total}\n\n"
    text += "Use /stats for detailed statistics."

    await message.reply_text(text)


@Client.on_message(filters.command("addadmin") & filters.private)
@owner_only
async def cmd_addadmin(client: Client, message: Message):
    """
    Add a new admin (owner only).

    Note: This is a runtime-only change. For persistent admin,
    update the ADMINS list in config.py.
    """
    if len(message.command) < 2:
        await message.reply_text(
            "**Usage:**\n"
            "/addadmin <user_id>\n\n"
            "Note: This only works until bot restart.\n"
            "For persistent admins, edit config.py"
        )
        return

    try:
        target_id = int(message.command[1])
    except ValueError:
        await message.reply_text("Invalid user ID.")
        return

    if target_id in ADMINS:
        await message.reply_text("User is already an admin.")
        return

    ADMINS.append(target_id)

    await message.reply_text(
        f"**Admin Added**\n\n"
        f"User `{target_id}` is now an admin.\n"
        f"_This is temporary. Add to config.py for persistence._"
    )


@Client.on_message(filters.command("removeadmin") & filters.private)
@owner_only
async def cmd_removeadmin(client: Client, message: Message):
    """
    Remove an admin (owner only).
    """
    if len(message.command) < 2:
        await message.reply_text(
            "**Usage:**\n"
            "/removeadmin <user_id>"
        )
        return

    try:
        target_id = int(message.command[1])
    except ValueError:
        await message.reply_text("Invalid user ID.")
        return

    if target_id not in ADMINS:
        await message.reply_text("User is not an admin.")
        return

    ADMINS.remove(target_id)

    await message.reply_text(f"**Admin Removed**\n\nUser `{target_id}` is no longer an admin.")


@Client.on_message(filters.command("admins") & filters.private)
@admin_only
async def cmd_admins(client: Client, message: Message):
    """Show list of admins."""
    lines = ["**Bot Admins**\n"]
    lines.append(f"Owner: `{OWNER_ID}`")

    if ADMINS:
        lines.append("\nAdmins:")
        for admin_id in ADMINS:
            lines.append(f"- `{admin_id}`")
    else:
        lines.append("\n_No additional admins_")

    await message.reply_text("\n".join(lines))
