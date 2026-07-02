# app/database.py
"""Database utilities for AI Middleman.

Provides an asyncpg connection pool, reads DATABASE_URL from .env, and runs
migrations on startup.
"""
import os
from pathlib import Path
import asyncpg
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DATABASE_URL = os.getenv("DATABASE_URL")

pool: asyncpg.pool.Pool | None = None

async def init_db() -> None:
    """Create connection pool and execute all migrations in filename order."""
    global pool
    if pool is None:
        pool = await asyncpg.create_pool(DATABASE_URL)
        async with pool.acquire() as conn:
            migrations_dir = BASE_DIR / "migrations"
            migration_files = sorted(migrations_dir.glob("*.sql"))
            for migration_path in migration_files:
                print(f"[DB] Running migration: {migration_path.name}")
                sql = migration_path.read_text(encoding="utf-8")
                await conn.execute(sql)

async def get_db() -> asyncpg.pool.Pool:
    """Return the asyncpg pool (must be initialized first)."""
    if pool is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return pool
