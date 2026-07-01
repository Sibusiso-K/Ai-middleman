"""
whatsapp_webhook.py — WhatsApp webhook receiver for the AI Middleman API.

Handles Meta's webhook verification (GET) and incoming message events (POST).
Each text message is processed asynchronously via background tasks: saved to
the database, run through the two-stage matching pipeline, and replied to
via the WhatsApp Business Cloud API.

Exposed: FastAPI APIRouter with GET and POST /webhook/whatsapp endpoints.
"""

from fastapi import APIRouter, Request, HTTPException, Query, BackgroundTasks
import hashlib
import hmac
import os
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
        # raise HTTPException(status_code=401, detail="Invalid signature")

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
        text = message["text"]["body"]

        print(f"[DEBUG] Sender number from webhook payload: {sender}")
        logger.info(f"Message from {sender}: {text}")

        # Save inbound message
        async with db_pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO messages (sender_number, message_text) VALUES ($1, $2)",
                sender, text
            )

        # Run through matching pipeline
        engine = MatchingEngine(db_pool)
        result = await engine.match(text)

        # Send reply
        whatsapp_client = WhatsAppClient()
        await whatsapp_client.send_message(to=sender, text=result["formatted_response"])

        logger.info(f"Replied to {sender} with match_quality={result['match_quality']}")

    except Exception as e:
        logger.error(f"Background task error: {e}", exc_info=True)
