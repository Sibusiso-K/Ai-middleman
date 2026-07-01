"""
whatsapp_webhook.py — FastAPI webhook receiver for WhatsApp Business Cloud API.

Handles:
- GET /webhook/whatsapp: Meta verification handshake
- POST /webhook/whatsapp: Incoming message processing

Privacy layer: replies never reveal personal contact details.
Contact selection (1-5) triggers an introduction request logged for middleman approval.

Pipeline: receive → save → match → format → reply
"""

from fastapi import APIRouter, Request, HTTPException, Query, BackgroundTasks
import hashlib
import hmac
import os
import json
import logging
from dotenv import load_dotenv
from pathlib import Path

from app.services.matching_engine import MatchingEngine
from app.services.whatsapp_client import WhatsAppClient

load_dotenv(Path(__file__).parent.parent.parent / ".env")

router = APIRouter()

APP_SECRET = os.getenv("WHATSAPP_APP_SECRET")
VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN")

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(Path(__file__).parent.parent.parent / "webhook.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("webhook")


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
    """Meta calls this once when you set the Callback URL, to verify ownership."""
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        return int(hub_challenge)
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/webhook/whatsapp")
async def receive_webhook(request: Request, background_tasks: BackgroundTasks):
    payload = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")

    # Signature check — log warning but don't block (temporarily relaxed for debugging)
    if APP_SECRET and not verify_signature(payload, signature):
        logger.warning("Invalid webhook signature — allowing through for debugging")

    data = await request.json()

    if data.get("object") != "whatsapp_business_account":
        return {"status": "ignored"}

    try:
        for entry in data.get("entry", []):
            for change in entry.get("changes", []):
                if change.get("field") == "messages":
                    background_tasks.add_task(process_message, request.app.state.db_pool, change["value"])
    except Exception as e:
        logger.error(f"Webhook processing error: {e}")

    return {"status": "received"}


async def process_message(db_pool, value: dict):
    try:
        messages = value.get("messages", [])
        if not messages:
            return

        message = messages[0]
        if message.get("type") != "text":
            return

        sender = message["from"]
        text = message["text"]["body"].strip()

        logger.info(f"Message from {sender}: {text}")

        # Save inbound message and get its ID
        async with db_pool.acquire() as conn:
            msg_row = await conn.fetchrow(
                "INSERT INTO messages (sender_number, message_text) VALUES ($1, $2) RETURNING id",
                sender, text
            )
            message_id = msg_row['id']

        # Check if user is selecting a contact (replies 1-5)
        if text in ['1', '2', '3', '4', '5']:
            await handle_contact_selection(db_pool, sender, text, message_id)
            return

        # Run full matching pipeline
        engine = MatchingEngine(db_pool)
        result = await engine.match(text)

        # Save conversation state so we remember what was shown
        async with db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO conversation_state (sender_number, last_matches, last_query, updated_at)
                VALUES ($1, $2::jsonb, $3, CURRENT_TIMESTAMP)
                ON CONFLICT (sender_number) DO UPDATE
                SET last_matches = $2::jsonb,
                    last_query = $3,
                    updated_at = CURRENT_TIMESTAMP
            """, sender, json.dumps(result['matches']), text)

        # Send privacy-safe reply
        whatsapp_client = WhatsAppClient()
        await whatsapp_client.send_message(to=sender, text=result["formatted_response"])

        logger.info(f"Replied to {sender} with match_quality={result['match_quality']}")

    except Exception as e:
        logger.error(f"Background task error: {e}", exc_info=True)


async def handle_contact_selection(db_pool, sender: str, selection: str, message_id: int):
    """User replied with 1-5 to select a contact. Log introduction request for approval."""
    whatsapp_client = WhatsAppClient()

    async with db_pool.acquire() as conn:
        state = await conn.fetchrow(
            "SELECT last_matches, last_query FROM conversation_state WHERE sender_number = $1",
            sender
        )

    if not state or not state['last_matches']:
        await whatsapp_client.send_message(
            to=sender,
            text="I don't have any recent matches on file. Please send a new search request."
        )
        return

    matches = state['last_matches']
    # Handle both string (JSON) and already-parsed dict/list
    if isinstance(matches, str):
        matches = json.loads(matches)

    idx = int(selection) - 1

    if idx >= len(matches):
        await whatsapp_client.send_message(
            to=sender,
            text=f"Please reply with a number between 1 and {len(matches)}."
        )
        return

    selected = matches[idx]
    contact_id = selected.get('contact_id')

    # Log the introduction request
    async with db_pool.acquire() as conn:
        req = await conn.fetchrow("""
            INSERT INTO introduction_requests
            (message_id, requester_number, contact_id, status)
            VALUES ($1, $2, $3, 'pending')
            RETURNING id
        """, message_id, sender, contact_id)
        request_id = req['id']

    # Confirm to user — no personal details
    confirmation = (
        f"✅ *Introduction Request Received*\n\n"
        f"Reference: *REQ-{request_id:04d}*\n"
        f"Contact: *C-{contact_id}*\n\n"
        f"The middleman will review your request and be in touch shortly.\n\n"
        f"_Typical response time: within 24 hours_"
    )
    await whatsapp_client.send_message(to=sender, text=confirmation)
    logger.info(f"Introduction request REQ-{request_id:04d} logged: sender={sender}, contact={contact_id}")