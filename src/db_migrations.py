from __future__ import annotations
import aiosqlite
import logging
from src.db import DB_PATH

log = logging.getLogger(__name__)

async def run_migrations() -> None:
    """
    Run database migrations to ensure all required tables exist.
    This function should be called once at startup.
    """
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            # Create portfolio_addresses table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS portfolio_addresses (
                    user_id INTEGER NOT NULL,
                    address TEXT NOT NULL,
                    label TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, address)
                )
            """)
            
            # Create user_prefs table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_prefs (
                    user_id INTEGER PRIMARY KEY,
                    target_stable_pct REAL,
                    alert_drop_pct REAL,
                    alerts_enabled INTEGER DEFAULT 0
                )
            """)
            
            await db.commit()
            log.info("Database migrations completed successfully")
            
    except Exception as e:
        log.error(f"Error running database migrations: {str(e)}")
        raise
