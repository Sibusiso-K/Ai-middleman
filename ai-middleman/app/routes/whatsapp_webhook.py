"""
whatsapp_webhook.py — Webhook handler for AI Middleman (Phase 2).

Number-role model (authoritative):
  - 27650746242 = our Cloud API number (phone_number_id / webhook / token).
    The friend dashboard drives this number to play "Sam" (sends FROM it).
  - 27736013348 = Alex's real consumer WhatsApp (web.whatsapp.com).

Therefore the ONLY inbound webhook traffic we care about is ALEX texting our
Cloud API number (736013348 -> 650746242). Sam's messages do NOT arrive here —
they are injected by the friend dashboard via POST /friend/send.

What Alex can send (all handled here):
  - Interactive button reply on a pending draft  -> Send / Skip
  - Text command with a pending draft:  SEND / EDIT <text> / SKIP
  - Any other free-text                          -> treated as Alex's own reply
                                                    to Sam (logged as alex_reply)

"Delivering to Sam" is virtual: Sam is the friend dashboard, which polls the
thread's events. So resolving a draft or forwarding Alex's reply just means
recording the appropriate thread_event — no outbound WhatsApp is sent to Sam.

LOOP PREVENTION: messages sent FROM our own Cloud API number are ignored.
"""

from fastapi import APIRouter, Request, HTTPException, Query
import hashlib
import hmac
import json
import os
from dotenv import load_dotenv
from pathlib import Path

from app.services.conversation_manager import ConversationManager
from app.services.pipeline_events import emit
from app.log_safe import slog

load_dotenv(Path(__file__).parent.parent.parent / ".env")

router = APIRouter()

APP_SECRET = os.getenv("WHATSAPP_APP_SECRET")
VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN")
BUSINESS_NUMBER = os.getenv("BUSINESS_PHONE_NUMBER", "27650746242")
ALEX_NUMBER = os.getenv("ALEX_WHATSAPP_NUMBER", "27736013348")

ALEX_COMMANDS = {"SEND", "SKIP", "STATUS"}


def is_alex_command(text: str) -> bool:
    text_upper = text.strip().upper()
    return (
        text_upper in ALEX_COMMANDS
        or text_upper.startswith("EDIT ")
        or text_upper.startswith("EDIT:")
    )


def verify_signature(payload: bytes, signature: str) -> bool:
    if not signature or not APP_SECRET:
        return False
    expected = "sha256=" + hmac.new(
        APP_SECRET.encode(), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.get("/webhook/whatsapp")
async def verify_webhook(
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge"),
):
    """Meta verification handshake."""
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        return int(hub_challenge)
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/webhook/whatsapp")
async def receive_webhook(request: Request):
    payload = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")

    if APP_SECRET and not verify_signature(payload, signature):
        print("[WARNING] Invalid webhook signature — allowing through for debugging")

    # Parse defensively: a malformed body must not 500 (that makes Meta
    # retry-storm). Decode leniently — real Meta payloads are valid UTF-8.
    try:
        data = json.loads(payload.decode("utf-8", errors="replace"))
    except (ValueError, AttributeError) as e:
        print(f"[Webhook] Could not parse body as JSON: {e}")
        return {"status": "ignored"}

    if not isinstance(data, dict) or data.get("object") != "whatsapp_business_account":
        return {"status": "ignored"}

    try:
        for entry in data.get("entry", []):
            for change in entry.get("changes", []):
                if change.get("field") == "messages":
                    await route_message(request.app.state.db_pool, change["value"])
    except Exception as e:
        print(f"[ERROR] Webhook processing error: {e}")

    return {"status": "received"}


async def route_message(db_pool, value: dict):
    """Route an inbound message. In Phase 2 all inbound traffic is Alex acting
    on his real WhatsApp; the thread is the single Sam<->Alex conversation,
    keyed by Alex's number."""
    messages = value.get("messages", [])
    if not messages:
        return

    message = messages[0]
    sender = message.get("from")
    msg_type = message.get("type")

    # Loop prevention: ignore anything from our own Cloud API number.
    if sender == BUSINESS_NUMBER:
        print("[Route] Ignoring self-message from Cloud API number")
        return

    manager = ConversationManager(db_pool)
    thread = await manager.get_or_create_thread(ALEX_NUMBER)
    thread_id = thread["id"]

    # Interactive button reply (Send / Skip tap on a draft).
    if msg_type == "interactive":
        interactive = message.get("interactive", {})
        if interactive.get("type") == "button_reply":
            reply_id = interactive.get("button_reply", {}).get("id", "")
            print(f"[Route] Button reply from {sender}: {reply_id}")
            await handle_button_reply(manager, thread_id, reply_id)
        return

    # Resolve the message to plain text regardless of how it arrived — typed,
    # voice note, or image — so everything downstream (commands, alex_reply)
    # works identically either way.
    text = None
    if msg_type == "text":
        text = message["text"]["body"].strip()
    elif msg_type in ("audio", "image"):
        text = await _transcribe_media(message, msg_type)
        if text is None:
            return  # transcription unavailable/failed — already logged
    else:
        return

    print(f"[Route] From Alex ({sender}): {text[:80]}")

    pending = await manager.get_latest_pending_draft(thread_id)

    # Alex commands only apply when there is a draft awaiting his decision.
    if pending and is_alex_command(text):
        await handle_alex_command(manager, thread_id, text, pending)
        return

    # Otherwise this is Alex chatting back to Sam in his own words.
    await manager.add_event(thread_id, "alex_reply", {"text": text})
    slog(f"[chat] Alex -> Sam: {text}")


async def _transcribe_media(message: dict, msg_type: str) -> str | None:
    """Download and transcribe/describe a voice note or image from Alex.
    Returns the resulting text, or None if transcription isn't available."""
    from app.services.whatsapp_client import WhatsAppClient
    from app.services.groq_media import transcribe_audio, describe_image, MediaTranscriptionError

    media_id = message.get(msg_type, {}).get("id")
    if not media_id:
        return None

    try:
        content, mime_type = await WhatsAppClient().download_media(media_id)
        if msg_type == "audio":
            text = await transcribe_audio(content)
            print(f"[Media] Transcribed voice note: {text[:100]}")
            return f"🎙️ {text}"
        else:
            text = await describe_image(content, mime_type)
            print(f"[Media] Described image: {text[:100]}")
            return f"🖼️ {text}"
    except MediaTranscriptionError as e:
        slog(f"[Media] Could not process {msg_type} from Alex: {e}")
        return None


async def handle_alex_command(manager, thread_id, text, pending):
    """Resolve a pending draft from a typed command. Delivering to Sam is
    virtual — we just record the resolution event for the friend dashboard."""
    text_upper = text.strip().upper()

    if text_upper == "SEND":
        draft = pending.get("draft_reply", "")
        await manager.mark_draft_handled(thread_id, "sent", draft)
        slog(f"[chat] Alex -> Sam (sent draft): {draft}")
        emit("resolved", f"✅ Alex approved the draft: \"{draft}\"")

    elif text_upper.startswith("EDIT ") or text_upper.startswith("EDIT:"):
        custom = text[5:].strip()
        if custom:
            await manager.mark_draft_handled(thread_id, "edited", custom)
            slog(f"[chat] Alex -> Sam (edited): {custom}")
            emit("resolved", f"✏️ Alex edited the draft: \"{custom}\"")

    elif text_upper == "SKIP":
        await manager.mark_draft_handled(thread_id, "skipped", "")
        print("[Alex] SKIP — request dropped, nothing delivered to Sam")
        emit("resolved", "❌ Alex skipped the draft — nothing sent to Sam")


async def handle_button_reply(manager, thread_id, reply_id: str):
    """Handle a Send/Edit/Skip button tap. Button id format:
    send_<eventid> / edit_<eventid> / skip_<eventid>."""
    pending = await manager.get_latest_pending_draft(thread_id)
    if not pending:
        print("[Button] No pending draft to act on")
        return

    if reply_id.startswith("send_"):
        draft = pending.get("draft_reply", "")
        await manager.mark_draft_handled(thread_id, "sent", draft)
        slog(f"[chat] Alex -> Sam (sent draft): {draft}")
        emit("resolved", f"✅ Alex tapped Send: \"{draft}\"")
    elif reply_id.startswith("edit_"):
        # WhatsApp gives bots no way to pre-fill a user's compose box —
        # interactive buttons can only trigger a fixed reply payload, not
        # inject text into the input field. The closest real equivalent:
        # send the raw draft as its own plain message so Alex can
        # long-press -> Copy -> paste it into his reply, edit it, and send
        # it back as "EDIT <his version>" to resolve the draft.
        from app.services.whatsapp_client import WhatsAppClient
        draft = pending.get("draft_reply", "")
        await WhatsAppClient().send_message(
            to=ALEX_NUMBER,
            text=(
                f"{draft}\n\n"
                "— Long-press the text above to copy it, then paste it into your reply, "
                "tweak it, and send it back as:\nEDIT <your version>"
            ),
        )
        slog("[chat] Alex tapped Edit — sent him a copyable draft")
        emit("checking", "✏️ Alex tapped Edit — sent him a copyable draft to adjust")
    elif reply_id.startswith("skip_"):
        await manager.mark_draft_handled(thread_id, "skipped", "")
        slog("[chat] Alex skipped the draft (nothing sent to Sam)")
        emit("resolved", "❌ Alex tapped Skip — nothing sent to Sam")
    else:
        print(f"[Button] Unknown button id: {reply_id}")
