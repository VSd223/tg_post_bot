import aiosqlite
import json
from typing import List, Optional, Dict, Any
from config import config

class Database:
    def __init__(self, db_path: str = config.DB_PATH):
        self.db_path = db_path

    async def init(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS channels (
                    channel_id INTEGER PRIMARY KEY,
                    user_id INTEGER,
                    title TEXT,
                    username TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS posts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    channel_id INTEGER,
                    message_id INTEGER DEFAULT NULL,
                    content_type TEXT,
                    raw_text TEXT,
                    file_id TEXT,
                    entities_json TEXT,
                    buttons_json TEXT,
                    publish_at TIMESTAMP DEFAULT NULL,
                    delete_at TIMESTAMP DEFAULT NULL,
                    status TEXT DEFAULT 'published',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.commit()

    async def add_user(self, user_id: int, username: Optional[str]):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
                (user_id, username)
            )
            await db.commit()

    async def add_channel(self, channel_id: int, user_id: int, title: str, username: Optional[str]):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO channels (channel_id, user_id, title, username) VALUES (?, ?, ?, ?)",
                (channel_id, user_id, title, username)
            )
            await db.commit()

    async def get_user_channels(self, user_id: int) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM channels WHERE user_id = ?", (user_id,))
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_channel(self, channel_id: int) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM channels WHERE channel_id = ?", (channel_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def delete_channel(self, channel_id: int, user_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM channels WHERE channel_id = ? AND user_id = ?", (channel_id, user_id))
            await db.commit()

    async def save_published_post(self, user_id: int, channel_id: int, message_id: int,
                                 content_type: str, raw_text: str, file_id: Optional[str],
                                 entities_json: str, buttons_json: str,
                                 delete_at: Optional[str] = None) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                INSERT INTO posts (user_id, channel_id, message_id, content_type, raw_text, file_id, entities_json, buttons_json, delete_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'published')
            """, (user_id, channel_id, message_id, content_type, raw_text, file_id, entities_json, buttons_json, delete_at))
            await db.commit()
            return cursor.lastrowid

    async def save_scheduled_post(self, user_id: int, channel_id: int,
                                 content_type: str, raw_text: str, file_id: Optional[str],
                                 entities_json: str, buttons_json: str,
                                 publish_at: str, delete_at: Optional[str] = None) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                INSERT INTO posts (user_id, channel_id, content_type, raw_text, file_id, entities_json, buttons_json, publish_at, delete_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'scheduled')
            """, (user_id, channel_id, content_type, raw_text, file_id, entities_json, buttons_json, publish_at, delete_at))
            await db.commit()
            return cursor.lastrowid

    async def get_due_scheduled_posts(self, now_str: str) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT * FROM posts 
                WHERE status = 'scheduled' AND publish_at <= ?
            """, (now_str,))
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def mark_post_published(self, post_id: int, message_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE posts 
                SET status = 'published', message_id = ?
                WHERE id = ?
            """, (message_id, post_id))
            await db.commit()

    async def get_due_delete_posts(self, now_str: str) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT * FROM posts 
                WHERE status = 'published' AND delete_at IS NOT NULL AND delete_at <= ?
            """, (now_str,))
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def mark_post_deleted(self, post_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE posts SET status = 'deleted' WHERE id = ?", (post_id,))
            await db.commit()

    async def get_user_scheduled_posts(self, user_id: int) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT p.*, c.title as channel_title 
                FROM posts p
                JOIN channels c ON p.channel_id = c.channel_id
                WHERE p.user_id = ? AND p.status = 'scheduled'
                ORDER BY p.publish_at ASC
            """, (user_id,))
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def cancel_scheduled_post(self, post_id: int, user_id: int) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "DELETE FROM posts WHERE id = ? AND user_id = ? AND status = 'scheduled'",
                (post_id, user_id)
            )
            await db.commit()
            return cursor.rowcount > 0

    async def get_recent_posts(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                SELECT p.*, c.title as channel_title 
                FROM posts p
                JOIN channels c ON p.channel_id = c.channel_id
                WHERE p.user_id = ? AND p.status = 'published'
                ORDER BY p.id DESC LIMIT ?
            """, (user_id, limit))
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_post_by_id(self, post_id: int) -> Optional[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM posts WHERE id = ?", (post_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def update_post_data(self, post_id: int, raw_text: str, entities_json: str, buttons_json: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE posts 
                SET raw_text = ?, entities_json = ?, buttons_json = ?
                WHERE id = ?
            """, (raw_text, entities_json, buttons_json, post_id))
            await db.commit()

db = Database()