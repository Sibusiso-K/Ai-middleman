"""Dump live Postgres schema for comparison with migration files."""
import asyncio, asyncpg, os, json
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent.parent / ".env")

async def dump():
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))

    tables = await conn.fetch("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        ORDER BY table_name
    """)

    output_lines = []

    for t in tables:
        table_name = t['table_name']
        output_lines.append(f"\n=== TABLE: {table_name} ===")

        cols = await conn.fetch("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = $1
            ORDER BY ordinal_position
        """, table_name)

        for c in cols:
            default = c['column_default'] or ''
            nullable = 'NULL' if c['is_nullable'] == 'YES' else 'NOT NULL'
            output_lines.append(
                f"  {c['column_name']:30s} {c['data_type']:20s} {nullable:10s} {default}"
            )

    await conn.close()

    output = "\n".join(output_lines)
    print(output)

    with open(Path(__file__).parent.parent / "live_schema.txt", "w", encoding="utf-8") as f:
        f.write(output)

    print("\n\nWritten to live_schema.txt")

if __name__ == "__main__":
    asyncio.run(dump())