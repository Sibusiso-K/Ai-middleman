"""
update_extractor.py — Extracts and applies conversational contact updates.

Two public functions:

extract_update_target(message) -> dict
    Focused LLM call that extracts {contact_name, attribute, new_value} from a
    message already known to be an update (is_update=True from IntentClassifier).
    Keeping extraction separate lets the intent classifier stay lean (flag only)
    and lets this prompt be tightly scoped to field extraction.

apply_update(db_pool, update_target, changed_by, source_message) -> str
    Applies the extracted update_target dict to the database:
    1. Resolve the target contact by name (or FRIEND_CONTACT_ID if self-update).
    2. Read the old value.
    3. Write the new value into contacts.
    4. Append a row to contact_change_log with before/after, who said it, and the
       raw source message.
    5. Return a human-readable confirmation string.
"""

import httpx
import os
from typing import Optional
from dotenv import load_dotenv
from pathlib import Path

from app.log_safe import slog
from app.services.contact_lookup import resolve_contact_by_name
from app.services.llm_provider import get_chat_configs
from app.services.llm_json import extract_json

load_dotenv(Path(__file__).parent.parent.parent / ".env")

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

    return await resolve_contact_by_name(conn, contact_name.strip())


async def extract_update_target(message: str) -> dict:
    """Extract {contact_name, attribute, new_value} from an update message.

    Called after IntentClassifier flags is_update=True. Focused single-purpose
    prompt — better accuracy than the 5-in-1 intent prompt for this subtask.
    Returns a dict with the three keys; values may be None/empty if extraction
    fails, which apply_update handles gracefully.
    """
    prompt = f"""Extract the contact-record update from this WhatsApp message.

The message shares new factual information about a contact in someone's professional network.

Extract:
- contact_name: the full name of the person being updated. If the sender is updating their OWN information ("I moved to Yoco", "my email changed"), set to null.
- attribute: what is changing. Must be exactly one of: company, title, email, phone, location, sector, specialty.
- new_value: the new value, exactly as stated (no paraphrasing).

Examples:
- "Aaron Acosta works at Deloitte now" → {{"contact_name": "Aaron Acosta", "attribute": "company", "new_value": "Deloitte"}}
- "Kara Davis left Andreessen Horowitz, she is at Bain Capital now" → {{"contact_name": "Kara Davis", "attribute": "company", "new_value": "Bain Capital"}}
- "Thabo got promoted to Managing Director" → {{"contact_name": "Thabo", "attribute": "title", "new_value": "Managing Director"}}
- "I moved to Yoco, not Takealot anymore" → {{"contact_name": null, "attribute": "company", "new_value": "Yoco"}}
- "Sarah's new number is 082 555 1234" → {{"contact_name": "Sarah", "attribute": "phone", "new_value": "082 555 1234"}}
- "My email is now sam@newcompany.com" → {{"contact_name": null, "attribute": "email", "new_value": "sam@newcompany.com"}}

Message: "{message}"

Reply with ONLY this JSON, no markdown, no explanation:
{{"contact_name": "<full name or null>", "attribute": "<company|title|email|phone|location|sector|specialty>", "new_value": "<new value>"}}"""

    configs = get_chat_configs()
    for config in configs:
        headers = {
            "Authorization": f"Bearer {config['api_key']}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": config["model"],
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": 120,
        }
        timeout = 10.0 if config["name"] == "groq" else 30.0
        for attempt in range(1, 4):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        config["api_url"], headers=headers, json=payload, timeout=timeout
                    )
                if response.status_code == 200:
                    content = response.json()["choices"][0]["message"]["content"]
                    data = extract_json(content)
                    contact_name = data.get("contact_name") or None
                    if isinstance(contact_name, str) and not contact_name.strip():
                        contact_name = None
                    result = {
                        "contact_name": contact_name,
                        "attribute": (data.get("attribute") or "").lower().strip(),
                        "new_value": (data.get("new_value") or "").strip(),
                    }
                    slog(f"[UpdateExtract/{config['name']}] {result} (attempt {attempt})")
                    return result
                elif response.status_code == 429 and config is not configs[-1]:
                    slog(f"[UpdateExtract/{config['name']}] rate-limited — switching provider")
                    break
                elif response.status_code < 500:
                    slog(f"[UpdateExtract/{config['name']}] HTTP {response.status_code} — giving up")
                    break
            except Exception as e:
                slog(f"[UpdateExtract/{config['name']}] error (attempt {attempt}): {e}")

    slog("[UpdateExtract] all providers failed — returning empty target")
    return {"contact_name": None, "attribute": "", "new_value": ""}


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
