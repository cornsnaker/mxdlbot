"""
MongoDB async database module for user management and settings.
"""

import os
from datetime import datetime
from typing import Optional, Dict, Any, List
from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGO_URI, DATABASE_NAME


class Database:
    """
    Async MongoDB database handler for user data, settings, and admin functions.
    """

    def __init__(self):
        self.client: Optional[AsyncIOMotorClient] = None
        self.db = None

    async def connect(self):
        """Initialize MongoDB connection."""
        self.client = AsyncIOMotorClient(MONGO_URI)
        self.db = self.client[DATABASE_NAME]

        # Create indexes for performance
        await self.db.users.create_index("user_id", unique=True)
        await self.db.banned.create_index("user_id", unique=True)
        print("[Database] Connected to MongoDB")

    async def close(self):
        """Close MongoDB connection."""
        if self.client:
            self.client.close()
            print("[Database] Connection closed")

    # ==================== USER MANAGEMENT ====================

    async def add_user(self, user_id: int, username: str = None, first_name: str = None) -> bool:
        """
        Add a new user or update existing user info.

        Args:
            user_id: Telegram user ID
            username: Telegram username
            first_name: User's first name

        Returns:
            True if new user, False if existing
        """
        user = await self.db.users.find_one({"user_id": user_id})

        if user:
            # Update existing user
            await self.db.users.update_one(
                {"user_id": user_id},
                {"$set": {
                    "username": username,
                    "first_name": first_name,
                    "last_active": datetime.utcnow()
                }}
            )
            return False
        else:
            # Create new user with default settings
            await self.db.users.insert_one({
                "user_id": user_id,
                "username": username,
                "first_name": first_name,
                "joined_date": datetime.utcnow(),
                "last_active": datetime.utcnow(),
                "settings": {
                    "output_format": "mp4",  # mp4 or mkv
                    "upload_mode": "video",  # video or document
                    "gofile_token": None,
                    "custom_thumbnail": None
                }
            })
            return True

    async def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user data by user ID."""
        return await self.db.users.find_one({"user_id": user_id})

    async def get_all_users(self) -> List[int]:
        """Get all user IDs for broadcast."""
        cursor = self.db.users.find({}, {"user_id": 1})
        users = await cursor.to_list(length=None)
        return [u["user_id"] for u in users]

    async def get_user_count(self) -> int:
        """Get total user count."""
        return await self.db.users.count_documents({})

    async def delete_user(self, user_id: int) -> bool:
        """Delete a user from database."""
        result = await self.db.users.delete_one({"user_id": user_id})
        return result.deleted_count > 0

    # ==================== USER SETTINGS ====================

    async def get_user_settings(self, user_id: int) -> Dict[str, Any]:
        """
        Get user settings with defaults.

        Returns:
            Settings dict with output_format, upload_mode, gofile_token, custom_thumbnail
        """
        user = await self.get_user(user_id)
        if user and "settings" in user:
            settings = user["settings"]
            # Ensure upload_mode has a default for existing users
            if "upload_mode" not in settings:
                settings["upload_mode"] = "video"
            return settings
        return {
            "output_format": "mp4",
            "upload_mode": "video",
            "gofile_token": None,
            "custom_thumbnail": None
        }

    async def set_output_format(self, user_id: int, format: str) -> bool:
        """
        Set user's preferred output format.

        Args:
            user_id: Telegram user ID
            format: 'mp4' or 'mkv'
        """
        if format not in ["mp4", "mkv"]:
            return False

        result = await self.db.users.update_one(
            {"user_id": user_id},
            {"$set": {"settings.output_format": format}}
        )
        return result.modified_count > 0

    async def set_upload_mode(self, user_id: int, mode: str) -> bool:
        """
        Set user's preferred upload mode.

        Args:
            user_id: Telegram user ID
            mode: 'video' or 'document'
        """
        if mode not in ["video", "document"]:
            return False

        result = await self.db.users.update_one(
            {"user_id": user_id},
            {"$set": {"settings.upload_mode": mode}}
        )
        return result.modified_count > 0

    async def get_upload_mode(self, user_id: int) -> str:
        """Get user's upload mode (video or document)."""
        settings = await self.get_user_settings(user_id)
        return settings.get("upload_mode", "video")

    async def set_gofile_token(self, user_id: int, token: str) -> bool:
        """Set user's Gofile API token."""
        result = await self.db.users.update_one(
            {"user_id": user_id},
            {"$set": {"settings.gofile_token": token}}
        )
        return result.modified_count > 0

    async def get_gofile_token(self, user_id: int) -> Optional[str]:
        """Get user's Gofile API token."""
        settings = await self.get_user_settings(user_id)
        return settings.get("gofile_token")

    async def set_custom_thumbnail(self, user_id: int, file_id: str) -> bool:
        """
        Set user's custom thumbnail file ID.

        Args:
            user_id: Telegram user ID
            file_id: Telegram file_id of the thumbnail photo
        """
        result = await self.db.users.update_one(
            {"user_id": user_id},
            {"$set": {"settings.custom_thumbnail": file_id}}
        )
        return result.modified_count > 0

    async def get_custom_thumbnail(self, user_id: int) -> Optional[str]:
        """Get user's custom thumbnail file ID."""
        settings = await self.get_user_settings(user_id)
        return settings.get("custom_thumbnail")

    async def clear_custom_thumbnail(self, user_id: int) -> bool:
        """Clear user's custom thumbnail."""
        result = await self.db.users.update_one(
            {"user_id": user_id},
            {"$set": {"settings.custom_thumbnail": None}}
        )
        return result.modified_count > 0

    # ==================== BAN MANAGEMENT ====================

    async def ban_user(self, user_id: int, reason: str = None, banned_by: int = None) -> bool:
        """
        Ban a user permanently.

        Args:
            user_id: User to ban
            reason: Ban reason
            banned_by: Admin who issued the ban
        """
        try:
            await self.db.banned.insert_one({
                "user_id": user_id,
                "reason": reason,
                "banned_by": banned_by,
                "banned_at": datetime.utcnow()
            })
            return True
        except Exception:
            return False

    async def unban_user(self, user_id: int) -> bool:
        """Unban a user."""
        result = await self.db.banned.delete_one({"user_id": user_id})
        return result.deleted_count > 0

    async def is_banned(self, user_id: int) -> bool:
        """Check if user is banned."""
        ban = await self.db.banned.find_one({"user_id": user_id})
        return ban is not None

    async def get_banned_users(self) -> List[Dict[str, Any]]:
        """Get list of all banned users."""
        cursor = self.db.banned.find({})
        return await cursor.to_list(length=None)

    # ==================== STATISTICS ====================

    async def get_stats(self) -> Dict[str, Any]:
        """
        Get bot statistics.

        Returns:
            Dict with total_users, banned_users, active_today
        """
        total_users = await self.db.users.count_documents({})
        banned_users = await self.db.banned.count_documents({})

        # Users active in last 24 hours
        from datetime import timedelta
        yesterday = datetime.utcnow() - timedelta(days=1)
        active_today = await self.db.users.count_documents({
            "last_active": {"$gte": yesterday}
        })

        return {
            "total_users": total_users,
            "banned_users": banned_users,
            "active_today": active_today
        }


# Global database instance
db = Database()
