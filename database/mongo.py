"""
database/mongo.py
-----------------
MongoDB connection manager and collection accessor.
Handles connection pooling, indexes, and provides typed access to all collections.

Collections:
  - users        : Authorized users and their metadata
  - banned_users : Permanently banned user IDs
  - history      : Per-user transcript history
  - stats        : Aggregated global statistics
  - analytics    : Daily breakdown analytics
  - settings     : Bot-wide settings (future use)
"""

import logging
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from config import Config

logger = logging.getLogger(__name__)


class Database:
    """Async MongoDB wrapper with typed collection helpers."""

    def __init__(self):
        self._client: AsyncIOMotorClient | None = None
        self._db: AsyncIOMotorDatabase | None = None

    async def connect(self):
        """Establish MongoDB connection and ensure indexes."""
        self._client = AsyncIOMotorClient(
            Config.MONGO_URI,
            serverSelectionTimeoutMS=10_000,
        )
        self._db = self._client[Config.DB_NAME]

        # Verify connection
        await self._client.admin.command("ping")
        logger.info(f"Connected to MongoDB database: {Config.DB_NAME}")

        await self._create_indexes()

    async def _create_indexes(self):
        """Create all required MongoDB indexes for performance."""
        # users collection
        await self._db.users.create_index("user_id", unique=True)
        await self._db.users.create_index("username")

        # banned_users collection
        await self._db.banned_users.create_index("user_id", unique=True)

        # history collection
        await self._db.history.create_index("user_id")
        await self._db.history.create_index("created_at")
        await self._db.history.create_index([("user_id", 1), ("created_at", -1)])

        # analytics collection
        await self._db.analytics.create_index("date", unique=True)

        logger.debug("MongoDB indexes ensured.")

    async def close(self):
        """Close the MongoDB connection."""
        if self._client:
            self._client.close()
            logger.info("MongoDB connection closed.")

    # ─── User Management ──────────────────────────────────────────────────────

    async def add_user(self, user_id: int, name: str, username: str | None) -> bool:
        """Add or update a user. Returns True if newly added."""
        existing = await self._db.users.find_one({"user_id": user_id})
        if existing:
            await self._db.users.update_one(
                {"user_id": user_id},
                {"$set": {"name": name, "username": username, "last_seen": datetime.now(timezone.utc)}},
            )
            return False

        await self._db.users.insert_one({
            "user_id": user_id,
            "name": name,
            "username": username,
            "authorized": False,
            "joined_at": datetime.now(timezone.utc),
            "last_seen": datetime.now(timezone.utc),
            "transcripts_count": 0,
        })
        return True

    async def is_authorized(self, user_id: int) -> bool:
        """Check if a user is authorized to use the bot."""
        if user_id == Config.OWNER_ID:
            return True
        user = await self._db.users.find_one({"user_id": user_id, "authorized": True})
        return user is not None

    async def is_banned(self, user_id: int) -> bool:
        """Check if a user is banned."""
        doc = await self._db.banned_users.find_one({"user_id": user_id})
        return doc is not None

    async def authorize_user(self, user_id: int) -> bool:
        """Grant access to a user. Returns False if user not found."""
        result = await self._db.users.update_one(
            {"user_id": user_id},
            {"$set": {"authorized": True, "authorized_at": datetime.now(timezone.utc)}},
        )
        return result.matched_count > 0

    async def deny_user(self, user_id: int) -> bool:
        """Revoke access from a user."""
        result = await self._db.users.update_one(
            {"user_id": user_id},
            {"$set": {"authorized": False}},
        )
        return result.matched_count > 0

    async def ban_user(self, user_id: int, name: str = "Unknown") -> bool:
        """Ban a user. Also removes from authorized."""
        try:
            await self._db.banned_users.insert_one({
                "user_id": user_id,
                "banned_at": datetime.now(timezone.utc),
                "name": name,
            })
            await self._db.users.update_one(
                {"user_id": user_id},
                {"$set": {"authorized": False}},
            )
            return True
        except Exception:
            return False  # Already banned (duplicate key)

    async def unban_user(self, user_id: int) -> bool:
        """Remove ban from a user."""
        result = await self._db.banned_users.delete_one({"user_id": user_id})
        return result.deleted_count > 0

    async def get_all_users(self) -> list[dict]:
        """Return all registered users."""
        return await self._db.users.find({}).to_list(None)

    async def get_authorized_users(self) -> list[dict]:
        """Return all authorized users."""
        return await self._db.users.find({"authorized": True}).to_list(None)

    async def get_banned_users(self) -> list[dict]:
        """Return all banned users."""
        return await self._db.banned_users.find({}).to_list(None)

    async def get_user(self, user_id: int) -> dict | None:
        """Get a single user document."""
        return await self._db.users.find_one({"user_id": user_id})

    # ─── History ──────────────────────────────────────────────────────────────

    async def add_history(self, user_id: int, entry: dict):
        """Add a transcript history entry for a user."""
        entry.update({
            "user_id": user_id,
            "created_at": datetime.now(timezone.utc),
        })
        await self._db.history.insert_one(entry)
        # Increment user transcript count
        await self._db.users.update_one(
            {"user_id": user_id},
            {"$inc": {"transcripts_count": 1}},
        )

    async def get_user_history(self, user_id: int, limit: int = 20) -> list[dict]:
        """Get a user's transcript history, newest first."""
        return await self._db.history.find(
            {"user_id": user_id},
            sort=[("created_at", -1)],
        ).limit(limit).to_list(None)

    # ─── Statistics ───────────────────────────────────────────────────────────

    async def increment_stat(self, key: str, amount: float = 1):
        """Atomically increment a global stat counter."""
        await self._db.stats.update_one(
            {"_id": "global"},
            {"$inc": {key: amount}},
            upsert=True,
        )

    async def get_global_stats(self) -> dict:
        """Retrieve all global statistics."""
        doc = await self._db.stats.find_one({"_id": "global"}) or {}
        return doc

    async def record_daily_analytics(self, is_video: bool, duration_secs: float):
        """Update today's analytics record."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        inc = {
            "transcripts": 1,
            "duration_secs": duration_secs,
            "videos" if is_video else "audios": 1,
        }
        await self._db.analytics.update_one(
            {"date": today},
            {"$inc": inc, "$addToSet": {}},
            upsert=True,
        )

    async def get_today_analytics(self) -> dict:
        """Get today's analytics."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return await self._db.analytics.find_one({"date": today}) or {}

    async def count_users_today(self) -> int:
        """Count users who interacted today."""
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        return await self._db.users.count_documents({"last_seen": {"$gte": today_start}})

    @property
    def db(self) -> AsyncIOMotorDatabase:
        """Raw database access for advanced queries."""
        return self._db
  
