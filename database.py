import aiosqlite
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
DB_PATH = "clients.db"


async def init_db():
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    messages TEXT DEFAULT '[]',
                    collected_data TEXT DEFAULT '{}',
                    status TEXT DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS leads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    data TEXT,
                    score TEXT,
                    score_reason TEXT,
                    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.commit()
            logger.info("✅ Database initialized")
    except Exception as e:
        logger.error(f"❌ Database init error: {e}")


async def get_conversation(user_id: int):
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT messages, collected_data FROM conversations WHERE user_id = ?",
                (user_id,)
            ) as cursor:
                return await cursor.fetchone()
    except Exception as e:
        logger.error(f"❌ Get conversation error: {e}")
        return None


async def save_conversation(user_id: int, username: str, first_name: str, messages: str, collected_data: str):
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                INSERT INTO conversations (user_id, username, first_name, messages, collected_data, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    messages = excluded.messages,
                    collected_data = excluded.collected_data,
                    updated_at = excluded.updated_at
            """, (user_id, username, first_name, messages, collected_data, datetime.now()))
            await db.commit()
            logger.info(f"✅ Conversation saved for user {user_id}")
    except Exception as e:
        logger.error(f"❌ Save conversation error: {e}")


async def save_lead(user_id: int, data: str, score: str, score_reason: str):
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO leads (user_id, data, score, score_reason) VALUES (?, ?, ?, ?)",
                (user_id, data, score, score_reason)
            )
            await db.execute(
                "UPDATE conversations SET status = 'lead_sent' WHERE user_id = ?",
                (user_id,)
            )
            await db.commit()
            logger.info(f"✅ Lead saved for user {user_id}")
    except Exception as e:
        logger.error(f"❌ Save lead error: {e}")


async def reset_user(user_id: int):
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM conversations WHERE user_id = ?", (user_id,))
            await db.commit()
            logger.info(f"✅ User {user_id} reset")
    except Exception as e:
        logger.error(f"❌ Reset user error: {e}")
