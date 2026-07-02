"""
simulate_friend_message.py — Simulate an inbound WhatsApp message from a fake
"friend" number for local testing, without going through the real Meta API.

Usage:
    python scripts/simulate_friend_message.py [sender_number] [message_body]

Examples:
    python scripts/simulate_friend_message.py
    python scripts/simulate_friend_message.py 27700000001 "Yo, looking for a lawyer"
    python scripts/simulate_friend_message.py 27700000002 "Need a corporate attorney in Joburg"

The script POSTs a Meta-format webhook payload to the local webhook endpoint
(http://localhost:8000/webhook/whatsapp) and prints the full response.
"""

import httpx
import json
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
load_dotenv(Path(__file__).parent.parent / ".env")

# ── Config ──────────────────────────────────────────────────────────────────
WEBHOOK_URL = "http://localhost:8000/webhook/whatsapp"
DEFAULT_SENDER = "27700000001"
DEFAULT_MESSAGE = "Yo, looking for a lawyer"

# ── Validate .env phone numbers ─────────────────────────────────────────────
# Alex no longer has a dedicated WhatsApp number in this flow — approvals
# happen in the dashboard, not via a second WhatsApp number. Only the
# business number (registered to the Cloud API webhook) matters here.
BUSINESS_NUMBER = os.getenv("BUSINESS_PHONE_NUMBER", "")

print("=" * 60)
print("ENVIRONMENT CHECK")
print("=" * 60)
print(f"  BUSINESS_PHONE_NUMBER  = {BUSINESS_NUMBER or 'NOT SET'}")

warnings = []
if BUSINESS_NUMBER != "27650746242":
    warnings.append(
        f"BUSINESS_PHONE_NUMBER is '{BUSINESS_NUMBER}', expected '27650746242'"
    )

if warnings:
    print("\n[WARNINGS]:")
    for w in warnings:
        print(f"  - {w}")
else:
    print("  [OK] Phone numbers match expected values")
print()

# ── Parse arguments ─────────────────────────────────────────────────────────
sender = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SENDER
message = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_MESSAGE

# ── Build the EXACT Meta WhatsApp webhook payload ───────────────────────────
# This matches the shape parsed in app/routes/whatsapp_webhook.py:
#   data["object"] == "whatsapp_business_account"
#   entry -> changes -> field == "messages" -> value -> messages[]
#   message["from"], message["type"], message["text"]["body"]
payload = {
    "object": "whatsapp_business_account",
    "entry": [
        {
            "id": "000000000000000",
            "changes": [
                {
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {
                            "display_phone_number": BUSINESS_NUMBER,
                            "phone_number_id": os.getenv(
                                "WHATSAPP_PHONE_NUMBER_ID", ""
                            ),
                        },
                        "contacts": [
                            {
                                "profile": {"name": f"Test Friend {sender}"},
                                "wa_id": sender,
                            }
                        ],
                        "messages": [
                            {
                                "from": sender,
                                "id": "wamid.test" + sender,
                                "timestamp": "1700000000",
                                "text": {"body": message},
                                "type": "text",
                            }
                        ],
                    },
                    "field": "messages",
                }
            ],
        }
    ],
}

print("=" * 60)
print("SENDING SIMULATED WEBHOOK")
print("=" * 60)
print(f"  URL:     {WEBHOOK_URL}")
print(f"  Sender:  {sender}")
print(f"  Message: {message}")
print()
print("  Payload (abridged):")
print(f"    object: {payload['object']}")
print(f"    entry[0].changes[0].field: {payload['entry'][0]['changes'][0]['field']}")
print(
    f"    message.from: {payload['entry'][0]['changes'][0]['value']['messages'][0]['from']}"
)
print(
    f"    message.text.body: {payload['entry'][0]['changes'][0]['value']['messages'][0]['text']['body']}"
)
print()

# ── Send the request ────────────────────────────────────────────────────────
try:
    r = httpx.post(
        WEBHOOK_URL,
        headers={"Content-Type": "application/json"},
        json=payload,
        timeout=120.0,
    )
    print("=" * 60)
    print("RESPONSE")
    print("=" * 60)
    print(f"  HTTP Status: {r.status_code}")
    print(f"  Body:")
    try:
        response_json = r.json()
        print(json.dumps(response_json, indent=4))
    except Exception:
        print(f"  {r.text}")
    print()
    print("=" * 60)
    print("Check the server console for pipeline logs:")
    print("  [Route] From {sender}: ...")
    print("  [Route] Contact request detected from {sender}")
    print("  [Route] Manual mode — draft pending approval in dashboard for {sender}")
    print()
    print("Then check the dashboard's 'Live Threads' page, or run:")
    print("  python scripts/check_db.py")
    print("=" * 60)

except httpx.ConnectError:
    print("\n[ERROR] Could not connect to localhost:8000")
    print("   Is the server running? Start it with:")
    print("   cd ai-middleman && uvicorn app.main:app --reload --port 8000")
    sys.exit(1)
except Exception as e:
    print(f"\n[ERROR] {type(e).__name__}: {e}")
    sys.exit(1)