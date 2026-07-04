"""
intent_classifier.py — Detects whether an incoming WhatsApp message is a 
contact request that Alex should act on.

Uses a lightweight LLM call to classify intent before running the full
matching pipeline. Returns True for contact requests, False for everything else.
"""

import asyncio
import httpx
import os
from dotenv import load_dotenv
from pathlib import Path

from app.services.llm_provider import get_chat_configs
from app.log_safe import slog

load_dotenv(Path(__file__).parent.parent.parent / ".env")


class IntentClassificationError(Exception):
    """Raised when the classifier could not reach a verdict (LLM unreachable/
    timing out after retries). Callers should decide how to fail — never treat
    this the same as a confident 'not a contact request'."""


class IntentClassifier:
    def __init__(self):
        # Groq first (fast) when configured, Featherless as a fallback if
        # Groq's free-tier rate limit is exhausted mid-session.
        self.configs = get_chat_configs()
        self.max_attempts = int(os.getenv("INTENT_MAX_ATTEMPTS", "3"))
        # Timeout/backoff are per-provider, not fixed once for the whole
        # instance — otherwise the Featherless fallback silently inherits
        # Groq's short timeout instead of the longer one it actually needs.
        self._timeout_override = os.getenv("INTENT_TIMEOUT_SECONDS")

    def _timeout_for(self, config: dict) -> float:
        # Featherless can run ~8-10s/call when warming up; Groq is much
        # faster but keep headroom for retries either way.
        if self._timeout_override:
            return float(self._timeout_override)
        return 10.0 if config["name"] == "groq" else 30.0

    def _backoff_for(self, config: dict) -> float:
        return 0.5 if config["name"] == "groq" else 1.5

    async def is_contact_request(self, message: str) -> bool:
        """
        Returns True if the message is asking Alex for a contact introduction,
        referral, or business connection. Returns False for everything else.
        """
        prompt = f"""You are analysing a WhatsApp message sent to Alex, a well-connected business professional.

Is this message asking Alex to introduce someone, recommend a contact, refer someone,
or connect the sender with a person from Alex's professional network?

The message may contain typos, missing letters, or autocorrect mistakes (people type
fast on WhatsApp) — read past the typos and judge the intended meaning, not the exact
spelling. For example "i want sometging is Al consunltinnng" means
"I want something in AI consulting" and IS a contact request.

Examples that ARE contact requests:
- "Do you know any good lawyers in London?"
- "Who should I speak to about raising Series A?"
- "Can you connect me with someone in private equity?"
- "I need a CFO for my startup, anyone come to mind?"
- "Hey Alex any contacts in real estate Dubai?"
- "Know anyone who does M&A advisory?"
- "Who's your guy for debt financing?"

Examples that are NOT contact requests:
- "Hey how are you doing?"
- "Are we still on for dinner?"
- "Thanks for yesterday"
- "Call me when you're free"
- "What do you think about the market?"
- "Send"
- "Skip"
- "Edit"
- "Status"

Message: "{message}"

Reply with only YES or NO."""

        last_error = None
        for config in self.configs:
            payload = {
                "model": config["model"],
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 5,
            }
            headers = {
                "Authorization": f"Bearer {config['api_key']}",
                "Content-Type": "application/json",
            }

            for attempt in range(1, self.max_attempts + 1):
                try:
                    async with httpx.AsyncClient() as client:
                        response = await client.post(
                            config["api_url"], headers=headers, json=payload, timeout=self._timeout_for(config)
                        )
                    if response.status_code == 200:
                        answer = response.json()["choices"][0]["message"]["content"].strip().upper()
                        slog(f"[Intent/{config['name']}] Classified as: {answer} (attempt {attempt})")
                        return answer.startswith("YES")
                    # Retry server-side/rate-limit errors; give up on other 4xx.
                    last_error = f"HTTP {response.status_code}"
                    slog(f"[Intent/{config['name']}] API error {response.status_code} (attempt {attempt}/{self.max_attempts})")
                    if response.status_code < 500 and response.status_code != 429:
                        break
                except (httpx.TimeoutException, httpx.TransportError) as e:
                    last_error = f"{type(e).__name__}: {e!r}"
                    slog(f"[Intent/{config['name']}] transient error (attempt {attempt}/{self.max_attempts}): {last_error}")

                if attempt < self.max_attempts:
                    await asyncio.sleep(self._backoff_for(config) * attempt)

        raise IntentClassificationError(
            f"Intent classification failed across all providers: {last_error}"
        )
