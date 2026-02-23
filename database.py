import aiosqlite
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
DB_PATH = "leads.db"


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                name TEXT,
                service TEXT,
                service_price TEXT,
                object_type TEXT,
                area TEXT,
                timing TEXT,
                price_accepted INTEGER,
                status TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()
        logger.info("✅ DB ready")


async def save_lead(user_id: int, data: dict):
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                INSERT INTO leads 
                (user_id, username, name, service, service_price, object_type, area, timing, price_accepted, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id,
                data.get("username", ""),
                data.get("name", ""),
                data.get("service", ""),
                data.get("service_price", ""),
                data.get("object_type", ""),
                data.get("area", ""),
                data.get("timing", ""),
                1 if data.get("price_accepted") else 0,
                data.get("status", "NEW")
            ))
            await db.commit()
            logger.info(f"✅ Lead saved: {user_id}")
    except Exception as e:
        logger.error(f"❌ Save error: {e}")
