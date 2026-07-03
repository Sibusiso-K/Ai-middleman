"""
whatsapp_client.py — WhatsApp Business Cloud API client for sending replies.

Handles sending text messages back to users via the Meta Graph API (v21.0).
Manages authentication via permanent access tokens and SSL verification
(using certifi, with an option to disable for restricted networks).

Exposed: WhatsAppClient class with send_message(to, text) method.
"""

import httpx
import os
import ssl
import certifi
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent.parent.parent / ".env")

# SSL verification: use certifi bundle, or disable if on restricted network
# Set WHATSAPP_VERIFY_SSL=false in .env to disable SSL verification (dev only)
_VERIFY_SSL = os.getenv("WHATSAPP_VERIFY_SSL", "true").lower() != "false"

if _VERIFY_SSL:
    # Use certifi's CA bundle for SSL verification
    os.environ["SSL_CERT_FILE"] = certifi.where()
    _VERIFY = certifi.where()
else:
    print("WARNING: WhatsApp SSL verification is DISABLED (WHATSAPP_VERIFY_SSL=false)")
    _VERIFY = False


class WhatsAppClient:
    def __init__(self):
        self.phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
        self.access_token = os.getenv("WHATSAPP_ACCESS_TOKEN")
        print(f"[DEBUG] Using Phone Number ID: {self.phone_number_id}")
        print(f"[DEBUG] WhatsApp token length: {len(self.access_token) if self.access_token else 0}")
        print(f"[DEBUG] WhatsApp token start: {self.access_token[:30] if self.access_token else 'NONE'}")
        print(f"[DEBUG] WhatsApp token end: {self.access_token[-10:] if self.access_token else 'NONE'}")
        self.api_url = f"https://graph.facebook.com/v21.0/{self.phone_number_id}/messages"

    async def send_message(self, to: str, text: str) -> dict:
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": text}
        }

        async with httpx.AsyncClient(verify=_VERIFY, follow_redirects=True) as client:
            response = await client.post(self.api_url, headers=headers, json=payload, timeout=15.0)

            if response.status_code != 200:
                print(f"WhatsApp send error: {response.status_code} {response.text}")
                return {"error": response.status_code, "body": response.text}

            try:
                return response.json()
            except Exception:
                return {"raw_response": response.text}

    async def download_media(self, media_id: str) -> tuple[bytes, str]:
        """
        Download a voice-note or image attachment from a WhatsApp message.
        Meta's media API is two-step: look up the temporary CDN URL for the
        media_id, then fetch the bytes from that URL (both need the access
        token). Returns (content_bytes, mime_type).
        """
        headers = {"Authorization": f"Bearer {self.access_token}"}
        async with httpx.AsyncClient(verify=_VERIFY, follow_redirects=True) as client:
            meta_resp = await client.get(
                f"https://graph.facebook.com/v21.0/{media_id}", headers=headers, timeout=15.0
            )
            meta_resp.raise_for_status()
            meta = meta_resp.json()

            media_resp = await client.get(meta["url"], headers=headers, timeout=30.0)
            media_resp.raise_for_status()
            return media_resp.content, meta.get("mime_type", "application/octet-stream")

    async def send_interactive_buttons(
        self,
        to: str,
        body_text: str,
        buttons: list[dict],
    ) -> dict:
        """
        Send an interactive button message via the Meta Cloud API.

        Args:
            to: Recipient WhatsApp number
            body_text: Message body (max 1024 chars)
            buttons: List of button dicts, each with:
                {"type": "reply", "reply": {"id": "...", "title": "..."}}
                Max 3 buttons, each title max 20 chars, id max 256 chars.

        Returns:
            API response dict or error dict.
        """
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": body_text},
                "action": {"buttons": buttons}
            }
        }

        async with httpx.AsyncClient(verify=_VERIFY, follow_redirects=True) as client:
            response = await client.post(self.api_url, headers=headers, json=payload, timeout=15.0)

            if response.status_code != 200:
                print(f"WhatsApp interactive send error: {response.status_code} {response.text}")
                return {"error": response.status_code, "body": response.text}

            try:
                return response.json()
            except Exception:
                return {"raw_response": response.text}

    async def send_flow(
        self,
        to: str,
        flow_id: str,
        screen: str,
        cta: str,
        body_text: str,
        initial_data: dict,
    ) -> dict:
        """
        Send a WhatsApp Flow message — a single-button interactive message
        that opens an in-chat form pre-populated with initial_data. Used for
        the Edit-draft flow: the form's TextArea is pre-filled with the draft
        text; the completed edit comes back via the normal webhook as an
        interactive "nfm_reply" message.

        Args:
            to: Recipient WhatsApp number
            flow_id: The published Flow's ID (WHATSAPP_EDIT_FLOW_ID)
            screen: The Flow's screen id to open (e.g. "EDIT_DRAFT")
            cta: Button label, max 20 chars
            body_text: Message body shown above the button
            initial_data: Dict passed into the screen as its starting data
                (must match the Flow's declared `data` schema)
        """
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "interactive",
            "interactive": {
                "type": "flow",
                "body": {"text": body_text},
                "action": {
                    "name": "flow",
                    "parameters": {
                        "flow_message_version": "3",
                        "flow_id": flow_id,
                        "flow_cta": cta,
                        "flow_action": "navigate",
                        "flow_action_payload": {
                            "screen": screen,
                            "data": initial_data,
                        },
                    },
                },
            },
        }

        async with httpx.AsyncClient(verify=_VERIFY, follow_redirects=True) as client:
            response = await client.post(self.api_url, headers=headers, json=payload, timeout=15.0)

            if response.status_code != 200:
                print(f"WhatsApp flow send error: {response.status_code} {response.text}")
                return {"error": response.status_code, "body": response.text}

            try:
                return response.json()
            except Exception:
                return {"raw_response": response.text}
