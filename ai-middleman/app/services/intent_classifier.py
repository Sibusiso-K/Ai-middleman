"""
intent_classifier.py — Detects whether an incoming WhatsApp message is a
contact request that Alex should act on, and in which language it was
written.

Friends may write to Alex in English or Afrikaans (or a natural
code-switched mix) — see sa_languages.py for why the scope is these two
and not all 11 of South Africa's official languages. classify() does
intent detection, language detection, and an English gloss of the
message in a single LLM call — no extra round trip is added for the
common English case, and the English gloss lets Stage 1's keyword filter
(a plain SQL match against English contact data) work correctly for
Afrikaans messages too.
"""

import asyncio
import httpx
import os
from dotenv import load_dotenv
from pathlib import Path

from app.services.llm_provider import get_chat_configs
from app.services.llm_json import extract_json
from app.services.sa_languages import SA_LANGUAGES
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

    async def classify(self, message: str) -> dict:
        """
        Returns {"is_request": bool, "language": str, "english_query": str}.

        "language" is one of SA_LANGUAGES. "english_query" is an English
        rendering of the message (unchanged if it's already English) —
        callers use it to re-run the keyword filter when the original text
        wouldn't match anything in the (English) contacts table.
        """
        languages_list = " or ".join(SA_LANGUAGES)
        prompt = f"""You are analysing a WhatsApp message sent to Alex, a well-connected business professional in South Africa.

Friends may write to him in {languages_list}, and sometimes code-switch naturally between the two in the same message.

Do all three of the following in one pass:

1. Identify which language the message is written in: {languages_list} only — no other option exists. If it's already in English, is mostly English with just a greeting/aside in Afrikaans, is short/ambiguous, or you are not confident it is genuinely Afrikaans, say "English". Only say "Afrikaans" if you are confident the message is substantially written in Afrikaans.
2. Decide: is this message asking Alex to introduce someone, recommend a contact, refer someone, or connect the sender with a person from Alex's professional network?
3. Give an English rendering of the message. If it's already in English, repeat it unchanged. Translate meaning, not word-for-word — keep any names, companies, and locations exactly as written.

The message may contain typos, missing letters, or autocorrect mistakes (people type fast on WhatsApp) — read past the typos and judge the intended meaning, not the exact spelling. For example "i want sometging is Al consunltinnng" means "I want something in AI consulting" and IS a contact request.

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

Reply with ONLY this exact JSON shape, nothing else — no markdown, no explanation:
{{"language": "English or Afrikaans, nothing else", "is_request": true or false, "english_query": "<English rendering of the message>"}}"""

        last_error = None
        for config in self.configs:
            payload = {
                "model": config["model"],
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 300,
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
                        content = response.json()["choices"][0]["message"]["content"]
                        try:
                            data = extract_json(content)
                            detected_language = data.get("language") or "English"
                            if detected_language not in SA_LANGUAGES:
                                # Defensive fallback: despite the prompt constraining the
                                # options to SA_LANGUAGES, small models occasionally
                                # hallucinate a third value. Never trust an option outside
                                # the supported set — default to English rather than risk
                                # drafting in a language nobody asked for.
                                slog(f"[Intent] model returned unsupported language {detected_language!r} — defaulting to English")
                                detected_language = "English"
                            result = {
                                "is_request": bool(data.get("is_request")),
                                "language": detected_language,
                                "english_query": data.get("english_query") or message,
                            }
                            slog(f"[Intent/{config['name']}] {result['language']}, is_request={result['is_request']} (attempt {attempt})")
                            return result
                        except ValueError as e:
                            # Malformed / non-JSON reply — retry (transient LLM behaviour).
                            last_error = f"unparseable reply: {e}"
                            slog(f"[Intent/{config['name']}] unparseable reply (attempt {attempt}/{self.max_attempts}): {e}")
                    else:
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
