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

load_dotenv(Path(__file__).parent.parent.parent / ".env")


class IntentClassificationError(Exception):
    """Raised when the classifier could not reach a verdict (LLM unreachable/
    timing out after retries). Callers should decide how to fail — never treat
    this the same as a confident 'not a contact request'."""


class IntentClassifier:
    def __init__(self):
        self.api_key = os.getenv("FEATHERLESS_API_KEY") or os.getenv("OPENROUTER_API_KEY")
        self.api_url = os.getenv(
            "FEATHERLESS_API_URL",
            "https://api.featherless.ai/v1/chat/completions"
        )
        self.model = os.getenv(
            "FEATHERLESS_MODEL",
            "NousResearch/Meta-Llama-3.1-8B-Instruct"
        )
        # Featherless can run ~8-10s/call when warming up, so give each attempt
        # generous headroom and retry a few times before giving up.
        self.timeout = float(os.getenv("INTENT_TIMEOUT_SECONDS", "30"))
        self.max_attempts = int(os.getenv("INTENT_MAX_ATTEMPTS", "3"))

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

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": 5,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        last_error = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        self.api_url, headers=headers, json=payload, timeout=self.timeout
                    )
                if response.status_code == 200:
                    answer = response.json()["choices"][0]["message"]["content"].strip().upper()
                    print(f"[Intent] Classified as: {answer} (attempt {attempt})")
                    return answer.startswith("YES")
                # Retry server-side/rate-limit errors; give up on other 4xx.
                last_error = f"HTTP {response.status_code}"
                print(f"[Intent] API error {response.status_code} (attempt {attempt}/{self.max_attempts})")
                if response.status_code < 500 and response.status_code != 429:
                    break
            except (httpx.TimeoutException, httpx.TransportError) as e:
                last_error = f"{type(e).__name__}: {e!r}"
                print(f"[Intent] transient error (attempt {attempt}/{self.max_attempts}): {last_error}")

            if attempt < self.max_attempts:
                await asyncio.sleep(1.5 * attempt)  # linear backoff: 1.5s, 3s, …

        raise IntentClassificationError(
            f"Intent classification failed after {self.max_attempts} attempts: {last_error}"
        )
