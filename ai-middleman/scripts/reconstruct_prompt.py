"""Reconstruct the exact LLM prompt from a stored draft_suggested thread event."""
import asyncio, asyncpg, os, json, io, sys
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent.parent / ".env")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

async def main():
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))

    sender = sys.argv[1] if len(sys.argv) > 1 else "27700000002"

    # Get the latest draft_suggested event for this sender's thread
    row = await conn.fetchrow("""
        SELECT e.payload
        FROM thread_events e
        JOIN threads t ON t.id = e.thread_id
        WHERE t.sender_number = $1 AND e.event_type = 'draft_suggested'
        ORDER BY e.created_at DESC LIMIT 1
    """, sender)

    if not row:
        print(f"No draft_suggested event found for {sender}")
        return

    payload = json.loads(row['payload']) if isinstance(row['payload'], str) else row['payload']
    matches = payload.get('matches', [])
    query = payload.get('original_message', '')
    draft = payload.get('draft_reply', '')

    print("=" * 70)
    print("RECONSTRUCTED DRAFT GENERATION PROMPT")
    print("=" * 70)

    # Reconstruct the exact prompt (same logic as draft_generator.py)
    contact_summary = ""
    for i, m in enumerate(matches[:3], 1):
        contact_summary += (
            f"{i}. {m.get('name', 'Unknown')} - "
            f"{m.get('title', '')} at {m.get('company', '')}, "
            f"{m.get('location', '')}. "
            f"Why relevant: {m.get('reasoning', '')}\n"
        )

    prompt = f"""You are drafting a WhatsApp reply for Alex, a well-connected business professional.

Alex's communication style:
- Warm, direct, and personal - like texting a close friend or colleague
- Short and punchy - maximum 3-4 sentences total
- Mentions the contact's name, role, and why they are perfect for this situation
- Offers to make the introduction personally
- Never uses bullet points, numbered lists, or formal language
- Uses occasional emoji naturally (handshake, ok, flex) but not more than one or two
- Speaks as if he personally knows and vouches for every contact he mentions
- Gets straight to the point - no long preambles
- Never reveals phone numbers or email addresses

Original request:
"{query}"

Best matching contacts from Alex's network:
{contact_summary}

Write Alex's WhatsApp reply now. 2-4 sentences maximum.
Do NOT use bullet points or lists.
Do NOT start with Hi or Hello - jump straight in.
Do NOT include any contact phone numbers or emails.
Sound genuine, personal, and confident."""

    print(prompt)

    print("\n" + "=" * 70)
    print("STORED DRAFT (LLM RESPONSE)")
    print("=" * 70)
    print(f"\n{draft}")

    print("\n" + "=" * 70)
    print(f"ALL {len(matches)} MATCHES (FULL)")
    print("=" * 70)
    for i, m in enumerate(matches, 1):
        print(f"\n{i}. {m.get('name')} - {m.get('title')} at {m.get('company')}")
        print(f"   Location: {m.get('location')}")
        print(f"   Confidence: {m.get('confidence')}")
        print(f"   Reasoning: {m.get('reasoning')}")

    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
