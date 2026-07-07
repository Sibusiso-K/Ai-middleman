"""
contact_lookup.py — Fuzzy contact-name resolution shared by the update
pipeline (update_extractor.py) and the direct named-contact lookup flow
(friend.py's "Do you know Aaron Aguirre?" handling).

Both features need to turn a free-text name Sam typed into a real contacts
row, tolerant of partial names ("Aaron" for "Aaron Aguirre") and typos in
casing/spacing — hence one shared resolver instead of two copies drifting
apart.
"""

from typing import Optional
from app.log_safe import slog


async def resolve_contact_by_name(conn, name: str) -> Optional[dict]:
    """Fuzzy-match a free-text name against contacts.full_name.

    Tokenises the name and requires every token to appear somewhere in
    full_name (case-insensitive substring). If multiple rows match, prefers
    the one whose name's word count is closest to the query's — the closer
    to an exact match. Returns the full contacts row as a dict, or None.
    """
    tokens = [t for t in name.lower().split() if len(t) >= 2]
    if not tokens:
        return None

    conditions = " AND ".join(
        f"LOWER(full_name) LIKE ${i + 1}" for i in range(len(tokens))
    )
    params = [f"%{t}%" for t in tokens]
    rows = await conn.fetch(
        f"""
        SELECT id, contact_id, full_name, phone, email, company, title,
               sector, specialty, location, seniority, is_vip
        FROM contacts
        WHERE {conditions}
        LIMIT 5
        """,
        *params,
    )
    if not rows:
        slog(f"[ContactLookup] no contact found matching name {name!r}")
        return None

    best = min(rows, key=lambda r: abs(len(r["full_name"].split()) - len(tokens)))
    slog(f"[ContactLookup] resolved {name!r} -> {best['full_name']!r} (id={best['id']})")
    return dict(best)
