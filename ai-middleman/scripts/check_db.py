"""Quick database state check for the AI Middleman pipeline."""
import asyncio, asyncpg, os, json
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent.parent / ".env")

async def check():
    try:
        conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    except Exception as e:
        print(f"DB connection failed: {e}")
        return

    msg = await conn.fetchrow("SELECT * FROM messages ORDER BY id DESC LIMIT 1")
    print("=== LATEST MESSAGE ===")
    print(json.dumps(dict(msg) if msg else {}, default=str, indent=2))

    threads = await conn.fetch("""
        SELECT id, sender_number, autonomy_mode, updated_at
        FROM threads ORDER BY updated_at DESC LIMIT 5
    """)
    print("\n=== RECENT THREADS ===")
    for t in threads:
        print(json.dumps(dict(t), default=str, indent=2))

    events = await conn.fetch("""
        SELECT thread_id, event_type, payload, created_at
        FROM thread_events ORDER BY id DESC LIMIT 10
    """)
    print("\n=== RECENT THREAD EVENTS ===")
    for e in events:
        print(json.dumps(dict(e), default=str, indent=2))

    await conn.close()

if __name__ == "__main__":
    asyncio.run(check())
