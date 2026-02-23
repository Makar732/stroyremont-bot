import aiosqlite
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
DB_PATH = "clients.db"


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                name TEXT,
                phone TEXT,
                work TEXT,
                object_type TEXT,
                area TEXT,
                address TEXT,
                timing TEXT,
                budget TEXT,
                status TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()
        logger.info("✅ DB ready")


async def save_lead(user_id: int, data: dict):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO leads (user_id, username, name, phone, work, object_type, area, address, timing, budget, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            data.get("username", ""),
            data.get("name", ""),
            data.get("phone", ""),
            data.get("work", ""),
            data.get("object_type", ""),
            data.get("area", ""),
            data.get("address", ""),
            data.get("timing", ""),
            data.get("budget", ""),
            data.get("status", "NEW")
        ))
        await db.commit()
        logger.info(f"✅ Lead saved: {user_id}")
