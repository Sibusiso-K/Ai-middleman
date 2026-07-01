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

async def import_contacts():
    print(f"Connecting to database...")
    conn = await asyncpg.connect(DATABASE_URL)

    print(f"Reading {CSV_PATH}...")
    with open(CSV_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"Found {len(rows)} rows. Importing...")

    inserted = 0
    skipped = 0

    for i, row in enumerate(rows):
        try:
            await conn.execute("""
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
            """,
                row["contact_id"],
                row["full_name"],
                row["phone"] or None,
                row["email"] or None,
                row["company"] or None,
                row["title"] or None,
                row["sector"] or None,
                row["specialty"] or None,
                row["location"] or None,
                row["seniority"] or None,
                row["expertise_tags"] or None,
                row["can_help_with"] or None,
                row["looking_for"] or None,
                int(row["relationship_strength"]) if row["relationship_strength"] else None,
                row["how_alex_knows_them"] or None,
                row["is_vip"].strip().upper() == "TRUE",
                date.fromisoformat(row["last_contacted"]) if row["last_contacted"] else None,
                int(row["intros_made"]) if row["intros_made"] else None,
                int(row["deals_closed"]) if row["deals_closed"] else None,
                row["preferred_contact_channel"] or None,
                row["do_not_intro_to"] or None,
                date.fromisoformat(row["last_verified"]) if row["last_verified"] else None,
                row["comment"] or None,
            )
            inserted += 1
        except Exception as e:
            skipped += 1
            if skipped <= 5:
                print(f"  Row {i} error: {e}")

        if (i + 1) % 1000 == 0:
            print(f"  Progress: {i + 1}/{len(rows)}")

    await conn.close()
    print(f"\nDone! Inserted: {inserted}, Skipped: {skipped}")

if __name__ == "__main__":
    asyncio.run(import_contacts())