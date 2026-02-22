import aiosqlite
from datetime import datetime

DB_PATH = "clients.db"

async def init_db():
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

async def get_conversation(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT messages, collected_data FROM conversations WHERE user_id = ?",
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return row if row else None

async def save_conversation(user_id: int, username: str, first_name: str, messages: str, collected_data: str):
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

async def save_lead(user_id: int, data: str, score: str, score_reason: str):
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
