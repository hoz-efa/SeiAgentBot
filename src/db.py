from __future__ import annotations
import aiosqlite
from typing import List, Tuple

DB_PATH = "sei_bot.db"

async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS watches (
                user_id INTEGER NOT NULL,
                address TEXT NOT NULL,
                last_tx_hash TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, address)
            )
            """
        )
        await db.commit()

async def add_watch(user_id: int, address: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO watches (user_id, address) VALUES (?, ?)",
            (user_id, address),
        )
        await db.commit()

async def remove_watch(user_id: int, address: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "DELETE FROM watches WHERE user_id = ? AND address = ?",
            (user_id, address),
        )
        await db.commit()
        return cur.rowcount

async def list_watches(user_id: int) -> List[str]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT address FROM watches WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        )
        return [row[0] for row in await cur.fetchall()]

async def get_all_watches() -> List[Tuple[int, str, str | None]]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT user_id, address, last_tx_hash FROM watches")
        return await cur.fetchall()

async def set_last_tx_hash(user_id: int, address: str, tx_hash: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE watches SET last_tx_hash = ? WHERE user_id = ? AND address = ?",
            (tx_hash, user_id, address),
        )
        await db.commit()
