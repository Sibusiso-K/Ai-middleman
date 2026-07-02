"""Debug script: Show exact LLM prompt and response for a given query."""
import asyncio, json, sys, io
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from app.services.draft_generator import DraftGenerator
from app.services.matching_engine import MatchingEngine
from app.database import init_db, get_db

async def main():
    query = sys.argv[1] if len(sys.argv) > 1 else "Need a corporate attorney in Joburg for an M&A deal"

    await init_db()
    db = await get_db()

    # Step 1: Matching
    print("=" * 70)
    print("STEP 1: MATCHING")
    print("=" * 70)
    matcher = MatchingEngine(db)
    result = await matcher.match(query)
    matches = result.get("matches", [])
    print(f"Found {len(matches)} matches:")
    for i, m in enumerate(matches, 1):
        print(f"  {i}. {m.get('name')} - {m.get('title')} at {m.get('company')} "
              f"[confidence: {m.get('confidence')}]")
        print(f"     Reasoning: {m.get('reasoning', 'N/A')[:120]}...")

    # Step 2: Draft generation - capture raw prompt and response
    print("\n" + "=" * 70)
    print("STEP 2: DRAFT GENERATION - RAW PROMPT")
    print("=" * 70)

    generator = DraftGenerator()

    # Reconstruct the exact prompt (same logic as draft_generator.py lines 42-75)
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
    print("STEP 3: DRAFT GENERATION - RAW LLM RESPONSE")
    print("=" * 70)

    draft = await generator.generate_draft(query, matches)
    print(f"\nDRAFT: {draft}")

    await db.close()

if __name__ == "__main__":
    asyncio.run(main())