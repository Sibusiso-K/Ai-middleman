# data/import_contacts.py
# Reads contacts.csv and inserts all rows into the PostgreSQL contacts table

import asyncio
import csv
import os
from datetime import date
from pathlib import Path
from dotenv import load_dotenv
import asyncpg

load_dotenv(Path(__file__).parent.parent / ".env")

DATABASE_URL = os.getenv("DATABASE_URL")

# Try both locations for the CSV
CSV_PATH = Path(__file__).parent / "contacts.csv"
if not CSV_PATH.exists():
    CSV_PATH = Path(__file__).parent.parent / "contacts.csv"

INSERT_CONTACT = """
    INSERT INTO contacts (
        contact_id, full_name, phone, email, company, title,
        sector, specialty, location, seniority, expertise_tags,
        can_help_with, looking_for, relationship_strength,
        how_alex_knows_them, is_vip, last_contacted, intros_made,
        deals_closed, preferred_contact_channel, do_not_intro_to,
        last_verified, comment
    ) VALUES (
        $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21,$22,$23
    ) ON CONFLICT (contact_id) DO NOTHING
"""
BATCH_SIZE = 1_000


def _record(row: dict[str, str]) -> tuple[object, ...]:
    return (
        row["contact_id"], row["full_name"], row["phone"] or None,
        row["email"] or None, row["company"] or None, row["title"] or None,
        row["sector"] or None, row["specialty"] or None, row["location"] or None,
        row["seniority"] or None, row["expertise_tags"] or None,
        row["can_help_with"] or None, row["looking_for"] or None,
        int(row["relationship_strength"]) if row["relationship_strength"] else None,
        row["how_alex_knows_them"] or None,
        row["is_vip"].strip().upper() == "TRUE",
        date.fromisoformat(row["last_contacted"]) if row["last_contacted"] else None,
        int(row["intros_made"]) if row["intros_made"] else None,
        int(row["deals_closed"]) if row["deals_closed"] else None,
        row["preferred_contact_channel"] or None, row["do_not_intro_to"] or None,
        date.fromisoformat(row["last_verified"]) if row["last_verified"] else None,
        row["comment"] or None,
    )


async def import_contacts() -> None:
    """Batch-import contacts; malformed rows fail loudly instead of disappearing."""
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not configured")

    print("Connecting to database...")
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        starting_count = await conn.fetchval("SELECT COUNT(*) FROM contacts")
        print(f"Reading {CSV_PATH}...")
        processed = 0
        batch: list[tuple[object, ...]] = []
        with open(CSV_PATH, encoding="utf-8", newline="") as file:
            reader = csv.DictReader(file)
            required = {"contact_id", "full_name", "relationship_strength", "is_vip"}
            missing = required - set(reader.fieldnames or [])
            if missing:
                raise ValueError(f"CSV is missing required columns: {', '.join(sorted(missing))}")

            print("Importing in batches (safe to re-run; existing contact IDs are skipped)...")
            for row in reader:
                batch.append(_record(row))
                if len(batch) == BATCH_SIZE:
                    await conn.executemany(INSERT_CONTACT, batch)
                    processed += len(batch)
                    print(f"  Progress: {processed} rows")
                    batch.clear()

            if batch:
                await conn.executemany(INSERT_CONTACT, batch)
                processed += len(batch)

        ending_count = await conn.fetchval("SELECT COUNT(*) FROM contacts")
        inserted = ending_count - starting_count
        print(f"\nDone! Inserted: {inserted}, Already present: {processed - inserted}, Errors: 0")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(import_contacts())
