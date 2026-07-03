"""
draft_generator.py — Generates WhatsApp reply drafts in Alex's personal voice.

Takes the original request and matched contacts, returns a natural friendly
reply that sounds like Alex wrote it — not a formal AI system response.
Temperature is set higher (0.7) to allow natural variation in language.
"""

import asyncio
import httpx
import os
from typing import List, Dict, Any
from dotenv import load_dotenv
from pathlib import Path

from app.services.llm_provider import get_chat_config, using_groq

load_dotenv(Path(__file__).parent.parent.parent / ".env")


class DraftGenerator:
    def __init__(self):
        config = get_chat_config()
        self.api_key = config["api_key"]
        self.api_url = config["api_url"]
        self.model = config["model"]
        default_timeout = "10" if using_groq() else "30"
        self.timeout = float(os.getenv("DRAFT_TIMEOUT_SECONDS", default_timeout))
        self.max_attempts = int(os.getenv("DRAFT_MAX_ATTEMPTS", "3"))

    async def generate_draft(
        self,
        original_request: str,
        matches: List[Dict[str, Any]]
    ) -> str:
        """
        Generate a natural WhatsApp reply in Alex's voice.
        Suggests the top matched contacts without revealing phone/email details.
        """
        if not matches:
            return "Hey! Nothing great in my network for this one — let me ask around and get back to you 🤔"

        # Build contact context for the prompt
        contact_summary = ""
        for i, m in enumerate(matches[:3], 1):
            contact_summary += (
                f"{i}. {m.get('name', 'Unknown')} — "
                f"{m.get('title', '')} at {m.get('company', '')}, "
                f"{m.get('location', '')}. "
                f"Why relevant: {m.get('reasoning', '')}\n"
            )

        prompt = f"""You are drafting a WhatsApp reply for Alex, a well-connected business professional.

Alex's communication style:
- Warm, direct, and personal — like texting a close friend or colleague
- Short and punchy — maximum 3-4 sentences total
- Mentions the contact's name, role, and why they are perfect for this situation
- Offers to make the introduction personally
- Never uses bullet points, numbered lists, or formal language
- Uses occasional emoji naturally (🤝 👌 💪) but not more than one or two
- Speaks as if he personally knows and vouches for every contact he mentions
- Gets straight to the point — no long preambles
- Never reveals phone numbers or email addresses

Original request:
"{original_request}"

Best matching contacts from Alex's network:
{contact_summary}

Write Alex's WhatsApp reply now. 2-4 sentences maximum.
Do NOT use bullet points or lists.
Do NOT start with Hi or Hello — jump straight in.
Do NOT include any contact phone numbers or emails.
Sound genuine, personal, and confident."""

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        json_payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "max_tokens": 200,
        }

        for attempt in range(1, self.max_attempts + 1):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        self.api_url, headers=headers, json=json_payload, timeout=self.timeout
                    )
                if response.status_code == 200:
                    draft = response.json()["choices"][0]["message"]["content"].strip()
                    from app.log_safe import slog
                    slog(f"[Draft] Generated (attempt {attempt}): {draft[:100]}...")
                    return draft
                # Retry rate-limits / server errors; give up on other 4xx.
                print(f"[Draft] API error {response.status_code} (attempt {attempt}/{self.max_attempts})")
                if response.status_code < 500 and response.status_code != 429:
                    break
            except (httpx.TimeoutException, httpx.TransportError) as e:
                print(f"[Draft] transient error (attempt {attempt}/{self.max_attempts}): {type(e).__name__}: {e!r}")

            if attempt < self.max_attempts:
                await asyncio.sleep(2 * attempt)  # linear backoff: 2s, 4s, …

        # All attempts failed — return a graceful, natural fallback so Alex still
        # gets something to send rather than an error.
        print("[Draft] all attempts failed — returning fallback line")
        return "Hey! I've got some great people in mind for this — let me get back to you shortly 🤝"