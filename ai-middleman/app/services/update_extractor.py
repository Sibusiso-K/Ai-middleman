"""
update_extractor.py — Applies a conversational contact update to the database.

Receives a structured update_target dict already extracted by IntentClassifier:
  {"contact_name": "Aaron Acosta" | null, "attribute": "company", "new_value": "Deloitte"}

Steps:
  1. Resolve the target contact: if contact_name is null/self-referential, treat
     the sender as the target (using FRIEND_CONTACT_ID env var, default
     'sam-ndlovu'). Otherwise fuzzy-match the name against contacts.full_name.
  2. Read the old value from the contacts row.
  3. Write the new value directly into the contacts table (keeps Stage 1 keyword
     matching working unchanged — no EAV complexity).
  4. Append a row to contact_change_log with before/after, who said it, and the
     raw source message.
  5. Return a human-readable confirmation string for the reply to Sam.

Exposed: apply_update(db_pool, update_target, changed_by, source_message) -> str
"""

import os
from typing import Optional
from app.log_safe import slog

# Attribute names the LLM can return → actual columns in the contacts table.
_ALLOWED_ATTRIBUTES: dict[str, str] = {
    "company":   "company",
    "title":     "title",
    "email":     "email",
    "phone":     "phone",
    "location":  "location",
    "sector":    "sector",
    "specialty": "specialty",
}

# Words that indicate the sender is talking about themselves rather than naming
# someone else. When contact_name is null or matches these, we target the
# FRIEND_CONTACT_ID contact instead of trying to fuzzy-search the DB.
_SELF_REFERENTIAL = frozenset({"i", "me", "my", "myself", "self", "null", "none", ""})

FRIEND_CONTACT_ID = os.getenv("FRIEND_CONTACT_ID", "sam-ndlovu")


def _is_self_update(contact_name: Optional[str]) -> bool:
    if contact_name is None:
        return True
    return contact_name.lower().strip() in _SELF_REFERENTIAL


async def _resolve_contact(conn, contact_name: Optional[str]) -> Optional[dict]:
    """Return the matching contacts row, or None if not found."""
    if _is_self_update(contact_name):
        row = await conn.fetchrow(
            "SELECT id, full_name FROM contacts WHERE contact_id = $1",
            FRIEND_CONTACT_ID,
        )
        if row:
            slog(f"[Update] self-update → resolved to {row['full_name']!r} ({FRIEND_CONTACT_ID})")
        else:
            slog(f"[Update] self-update requested but FRIEND_CONTACT_ID={FRIEND_CONTACT_ID!r} not found in DB")
        return dict(row) if row else None

    # Fuzzy name match: tokenise the name, require all tokens to appear in
    # full_name (case-insensitive). If multiple rows match, pick the one whose
    # name most closely matches token count (closest to an exact match).
    name = contact_name.strip()
    tokens = [t for t in name.lower().split() if len(t) >= 2]
    if not tokens:
        return None

    # Build a WHERE clause: each token must appear somewhere in lower(full_name).
    conditions = " AND ".join(
        f"LOWER(full_name) LIKE ${ i + 1 }" for i in range(len(tokens))
    )
    params = [f"%{t}%" for t in tokens]
    rows = await conn.fetch(
        f"SELECT id, full_name FROM contacts WHERE {conditions} LIMIT 5",
        *params,
    )
    if not rows:
        slog(f"[Update] no contact found matching name {name!r}")
        return None

    # Prefer the row whose tokenised name length is closest to the query.
    best = min(rows, key=lambda r: abs(len(r["full_name"].split()) - len(tokens)))
    slog(f"[Update] resolved {name!r} → {best['full_name']!r} (id={best['id']})")
    return dict(best)


async def apply_update(
    db_pool,
    update_target: dict,
    changed_by: str = "Sam",
    source_message: str = "",
) -> str:
    """Apply the update and return a confirmation string to send back to Sam.

    Returns an error string (not an exception) if the contact can't be found
    or the attribute isn't in the allowed list — callers relay this to Sam as
    a plain WhatsApp reply.
    """
    contact_name = update_target.get("contact_name")
    raw_attribute = (update_target.get("attribute") or "").lower().strip()
    new_value = (update_target.get("new_value") or "").strip()

    if not new_value:
        return "I couldn't work out the new value from that message — could you rephrase it?"

    column = _ALLOWED_ATTRIBUTES.get(raw_attribute)
    if not column:
        slog(f"[Update] unsupported attribute {raw_attribute!r} — ignoring")
        return f"I'm not sure which field to update ({raw_attribute!r}). I can update: company, title, email, phone, location, sector, or specialty."

    async with db_pool.acquire() as conn:
        contact = await _resolve_contact(conn, contact_name)
        if not contact:
            display = "yourself" if _is_self_update(contact_name) else f"'{contact_name}'"
            return f"I couldn't find a contact for {display} in the network — no update made."

        contact_id = contact["id"]
        full_name = contact["full_name"]

        # Read old value before overwriting.
        old_row = await conn.fetchrow(
            f"SELECT {column} FROM contacts WHERE id = $1", contact_id
        )
        old_value = str(old_row[column]) if old_row and old_row[column] is not None else None

        # Write the update directly into the contacts table.
        await conn.execute(
            f"UPDATE contacts SET {column} = $1, updated_at = NOW() WHERE id = $2",
            new_value, contact_id,
        )

        # Append to audit log.
        await conn.execute(
            """
            INSERT INTO contact_change_log
                (contact_id, attribute_name, old_value, new_value, changed_by, source_message)
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            contact_id, column, old_value, new_value, changed_by, source_message,
        )

    slog(f"[Update] {full_name}: {column} '{old_value}' → '{new_value}' (by {changed_by})")

    is_self = _is_self_update(contact_name)
    if is_self:
        return f"Updated! Your {column} is now {new_value} ✓"
    old_note = f" (was: {old_value})" if old_value else ""
    return f"Got it! Updated {full_name.split()[0]}'s {column} to {new_value}{old_note} ✓"
