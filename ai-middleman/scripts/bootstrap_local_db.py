"""Create the local Compose database, apply migrations, and import contacts.

This intentionally works without any Docker Hub account transfer: Compose
creates a new local PostgreSQL volume, then the repository CSV seeds it.
It is safe to re-run because the importer keys records by ``contact_id``.
"""

import asyncio
import sys

from start_all import start_database


async def bootstrap() -> None:
    if not start_database():
        raise SystemExit(1)

    from app import database
    from data.import_contacts import import_contacts

    await database.init_db()
    try:
        await import_contacts()
    finally:
        if database.pool is not None:
            await database.pool.close()


if __name__ == "__main__":
    asyncio.run(bootstrap())
