"""Test: Spin up fresh DB and run all migrations, then verify schema matches expectations."""
import asyncio, asyncpg, os, sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

# Use a separate test database
TEST_DB = "aimiddleman_test"

async def main():
    # Connect to default postgres database to create/drop test DB
    admin_conn = await asyncpg.connect(
        host="localhost",
        user="postgres",
        password=os.getenv("DB_PASSWORD"),
        database="postgres"
    )

    # Drop and recreate test database
    await admin_conn.execute(f"DROP DATABASE IF EXISTS {TEST_DB}")
    await admin_conn.execute(f"CREATE DATABASE {TEST_DB}")
    await admin_conn.close()
    print(f"[OK] Created fresh test database: {TEST_DB}")

    # Connect to test DB
    test_conn = await asyncpg.connect(
        host="localhost",
        user="postgres",
        password=os.getenv("DB_PASSWORD"),
        database=TEST_DB
    )

    # Run all migration files in order
    migrations_dir = Path(__file__).parent.parent / "migrations"
    migration_files = sorted(migrations_dir.glob("*.sql"))
    print(f"\nFound {len(migration_files)} migration files:")
    for mf in migration_files:
        print(f"  - {mf.name}")

    for migration_path in migration_files:
        print(f"\n[RUN] {migration_path.name}")
        sql = migration_path.read_text(encoding="utf-8")
        await test_conn.execute(sql)
        print(f"  [OK] Executed successfully")

    # Verify all expected tables exist
    print("\n" + "=" * 60)
    print("VERIFYING SCHEMA")
    print("=" * 60)

    expected_tables = [
        "contacts", "messages", "match_history", "conversation_state",
        "introduction_requests", "threads", "thread_events",
    ]

    tables = await test_conn.fetch("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'public' ORDER BY table_name
    """)
    actual_tables = [t['table_name'] for t in tables]

    print(f"\nExpected tables: {expected_tables}")
    print(f"Actual tables:   {actual_tables}")

    all_ok = True
    for expected in expected_tables:
        if expected in actual_tables:
            print(f"  [OK] {expected} exists")
        else:
            print(f"  [MISSING] {expected} NOT FOUND")
            all_ok = False

    # Check threads has UNIQUE constraint on sender_number (the new
    # multi-turn model's equivalent of the old conversation_state constraint)
    constraints = await test_conn.fetch("""
        SELECT conname, contype
        FROM pg_constraint
        WHERE conrelid = 'threads'::regclass
    """)
    print(f"\nthreads constraints: {[(c['conname'], c['contype']) for c in constraints]}")

    has_unique = any(c['contype'] in ('u', b'u') for c in constraints)
    if has_unique:
        print("  [OK] UNIQUE constraint on sender_number exists")
    else:
        print("  [MISSING] No UNIQUE constraint on sender_number")
        all_ok = False

    # Check column counts match live DB
    expected_columns = {
        "contacts": 26,
        "messages": 5,
        "match_history": 8,
        "conversation_state": 5,
        "introduction_requests": 9,
        "threads": 5,
        "thread_events": 5,
    }

    for table_name, expected_count in expected_columns.items():
        cols = await test_conn.fetch("""
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = $1
        """, table_name)
        actual_count = len(cols)
        if actual_count == expected_count:
            print(f"  [OK] {table_name}: {actual_count} columns (expected {expected_count})")
        else:
            print(f"  [MISMATCH] {table_name}: {actual_count} columns (expected {expected_count})")
            all_ok = False

    # Cleanup
    await test_conn.close()
    admin_conn = await asyncpg.connect(
        host="localhost",
        user="postgres",
        password=os.getenv("DB_PASSWORD"),
        database="postgres"
    )
    await admin_conn.execute(f"DROP DATABASE IF EXISTS {TEST_DB}")
    await admin_conn.close()
    print(f"\n[OK] Dropped test database: {TEST_DB}")

    if all_ok:
        print("\n[PASS] ALL CHECKS PASSED - migrations produce correct schema")
    else:
        print("\n[FAIL] SOME CHECKS FAILED - see above")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())