"""
friend.py — "Sam" (the friend) side of the AI Middleman loop.

The friend dashboard posts here to role-play Sam. Each send:
  1. records a friend_message event on the single Sam<->Alex thread,
  2. relays the text to Alex's real WhatsApp (send FROM our Cloud API number
     650746242 TO Alex 736013348) so it shows up in his 650746242 chat,
  3. runs the intent/matching/draft pipeline, and if it's a contact request,
     pushes Alex a clearly-marked draft with Send/Skip interactive buttons and
     records a draft_suggested event.

The dashboard then polls GET /friend/thread to render the conversation and any
replies Alex sends back (which arrive via the webhook as alex_reply / draft_*).
"""

import os
from fastapi import APIRouter, Request
from dotenv import load_dotenv
from pathlib import Path

from app.services.intent_classifier import IntentClassifier, IntentClassificationError
from app.services.matching_engine import MatchingEngine
from app.services.draft_generator import DraftGenerator
from app.services.conversation_manager import ConversationManager
from app.services.whatsapp_client import WhatsAppClient

load_dotenv(Path(__file__).parent.parent.parent / ".env")

router = APIRouter()

ALEX_NUMBER = os.getenv("ALEX_WHATSAPP_NUMBER", "27736013348")
FRIEND_NAME = os.getenv("FRIEND_SIM_NAME", "Sam")


@router.post("/friend/send")
async def friend_send(request: Request):
    """Send a message as the friend (Sam) into the system."""
    db_pool = request.app.state.db_pool
    body = await request.json()
    text = (body.get("text") or "").strip()
    if not text:
        return {"error": "text is required"}

    manager = ConversationManager(db_pool)
    whatsapp = WhatsAppClient()

    thread = await manager.get_or_create_thread(ALEX_NUMBER)
    thread_id = thread["id"]

    # 1. Record Sam's message on the thread.
    await manager.add_event(thread_id, "friend_message", {"text": text})

    # 2. Relay Sam's message to Alex's real WhatsApp (prefixed so Alex sees who
    #    it's from, since it arrives from our Cloud API number).
    relay = await whatsapp.send_message(to=ALEX_NUMBER, text=f"🧑 {FRIEND_NAME}: {text}")

    # 3. Run the pipeline; if it's a contact request, draft a reply for Alex.
    #    If classification itself fails (LLM unreachable), fail OPEN — treat it
    #    as a request so a genuine ask is never silently dropped. Worst case
    #    Alex gets a draft on a non-request, which he can simply skip.
    classifier = IntentClassifier()
    classify_failed = False
    try:
        is_request = await classifier.is_contact_request(text)
    except IntentClassificationError as e:
        print(f"[Friend] Intent classification unavailable, failing open: {e}")
        is_request = True
        classify_failed = True

    draft_sent = False
    if is_request:
        engine = MatchingEngine(db_pool)
        result = await engine.match(text)
        all_matches = result.get("matches", [])
        viable = [m for m in all_matches if m.get("confidence", 0) >= 0.5]

        generator = DraftGenerator()
        draft = await generator.generate_draft(original_request=text, matches=viable)

        event_id = await manager.add_event(thread_id, "draft_suggested", {
            "original_message": text,
            "draft_reply": draft,
            "matches": all_matches,
        })

        # Push the draft to Alex with Send/Skip buttons, clearly marked so it is
        # distinguishable from Sam's relayed message (same sender number).
        buttons = [
            {"type": "reply", "reply": {"id": f"send_{event_id}", "title": "✅ Send"}},
            {"type": "reply", "reply": {"id": f"skip_{event_id}", "title": "❌ Skip"}},
        ]
        uncertain_note = (
            "⚠️ _(couldn't auto-verify this was a request — sending a draft anyway)_\n\n"
            if classify_failed else ""
        )
        draft_body = (
            f"🤖 *Suggested reply to {FRIEND_NAME}*\n\n"
            f"{uncertain_note}"
            f"_{FRIEND_NAME} asked:_ {text}\n\n"
            f"*Draft:* {draft}\n\n"
            f"Tap Send to use it, or reply EDIT <your text>."
        )
        await whatsapp.send_interactive_buttons(to=ALEX_NUMBER, body_text=draft_body, buttons=buttons)
        draft_sent = True

    return {
        "status": "sent",
        "relayed_to_alex": relay.get("error") is None,
        "draft_suggested": draft_sent,
        "classification_failed": classify_failed,
    }


@router.get("/friend/thread")
async def friend_thread(request: Request):
    """Return the Sam<->Alex conversation events for the friend dashboard."""
    db_pool = request.app.state.db_pool
    manager = ConversationManager(db_pool)
    thread = await manager.get_or_create_thread(ALEX_NUMBER)
    events = await manager.get_recent_events(thread["id"], limit=100)
    return {"thread_id": thread["id"], "events": events}
