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

from app.services.llm_provider import get_chat_configs
from app.log_safe import slog

load_dotenv(Path(__file__).parent.parent.parent / ".env")

_WRAPPING_QUOTE_PAIRS = [('"', '"'), ("'", "'"), ("“", "”"), ("‘", "’")]


def _strip_wrapping_quotes(text: str) -> str:
    """Small models routinely wrap the message they were asked to 'write' in a
    single layer of quote marks, as if captioning it. Strip one such layer
    (straight or curly) if the whole draft is wrapped in a matching pair."""
    stripped = text.strip()
    for open_q, close_q in _WRAPPING_QUOTE_PAIRS:
        if len(stripped) >= 2 and stripped.startswith(open_q) and stripped.endswith(close_q):
            return stripped[1:-1].strip()
    return stripped


class DraftGenerator:
    def __init__(self):
        # Groq first (fast) when configured, Featherless as a fallback if
        # Groq's free-tier rate limit is exhausted mid-session.
        self.configs = get_chat_configs()
        self.max_attempts = int(os.getenv("DRAFT_MAX_ATTEMPTS", "3"))
        # Timeout/backoff are per-provider, not fixed once for the whole
        # instance — otherwise the Featherless fallback silently inherits
        # Groq's short timeout instead of the longer one it actually needs.
        self._timeout_override = os.getenv("DRAFT_TIMEOUT_SECONDS")

    def _timeout_for(self, config: dict) -> float:
        if self._timeout_override:
            return float(self._timeout_override)
        return 10.0 if config["name"] == "groq" else 30.0

    def _backoff_for(self, config: dict) -> float:
        return 1.0 if config["name"] == "groq" else 2.0

    async def generate_draft(
        self,
        original_request: str,
        matches: List[Dict[str, Any]],
        conversation_history: str = "",
        is_first_message: bool = True,
        language: str = "English",
    ) -> str:
        """
        Generate a natural WhatsApp reply in Alex's voice.
        Suggests the top matched contacts without revealing phone/email details.

        conversation_history (oldest to newest, one line per turn) and
        is_first_message let the model continue an ongoing thread naturally
        instead of opening every single reply with a fresh greeting.

        language is English or Afrikaans — whichever IntentClassifier.classify
        detected Sam wrote in (see sa_languages.py for why the scope is these
        two, not all 11 of South Africa's official languages) — the reply is
        written in that same language, not translated to English, so the
        conversation reads naturally on Sam's side.
        """
        if not matches:
            # Static fallback, deliberately English-only: translating it
            # without a native speaker to verify it would risk shipping wrong
            # or awkward phrasing. The one path that does need to work in
            # Sam's language — a real match — is generated fresh by the model
            # above, in the requested language.
            return "Nothing great in my network for this one — let me ask around and get back to you 🤔"

        # Build contact context for the prompt
        contact_summary = ""
        for i, m in enumerate(matches[:3], 1):
            contact_summary += (
                f"{i}. {m.get('name', 'Unknown')} — "
                f"{m.get('title', '')} at {m.get('company', '')}, "
                f"{m.get('location', '')}. "
                f"Why relevant: {m.get('reasoning', '')}\n"
            )

        history_block = (
            f"\nConversation so far (oldest to newest):\n{conversation_history}\n"
            if conversation_history else ""
        )
        opener_rule = (
            "This is the first message in the conversation, so a brief natural "
            "opener (e.g. \"Hey\") is fine."
            if is_first_message else
            "This is an ONGOING conversation — you've already been chatting with "
            "Sam. Do NOT open with \"Hey\", \"Hi\", or any greeting again; reply "
            "the way a real person continues a text thread, picking up naturally "
            "from what Sam just said."
        )
        language_rule = (
            "Sam wrote in English, so reply in English."
            if language == "English" else
            f"Sam wrote in {language}. Write Alex's reply in {language} too — "
            f"do NOT reply in English or translate it back. South Africans "
            f"naturally code-switch, so it's fine to keep contact names, "
            f"company names, and job titles in their original English form "
            f"even inside a {language} sentence."
        )
        n_options = min(len(matches), 3)
        options_rule = (
            "There's one strong match. Suggest that person by name and offer to "
            "introduce them."
            if n_options == 1 else
            f"There are {n_options} good options. Mention all {n_options} by name "
            f"with a few words each on why they fit, then ask Sam who they'd like "
            f"to be connected with (or if they want more than one). Keep it "
            f"natural and conversational — this is a text, not a list. Do NOT "
            f"share any phone numbers or emails yet; that only happens once Sam "
            f"picks and Alex approves."
        )

        prompt = f"""You are drafting a WhatsApp reply for Alex, a well-connected business professional.

Alex's communication style:
- Warm, direct, and personal — like texting a close friend or colleague
- Short and punchy — a few sentences, even when suggesting 2-3 people
- Names the contact(s) and why they fit this situation
- Offers to make the introduction personally
- Never uses bullet points, numbered lists, or formal language
- Uses occasional emoji naturally (🤝 👌 💪) but not more than one or two
- Speaks as if he personally knows and vouches for every contact he mentions
- Gets straight to the point — no long preambles
- Never reveals phone numbers or email addresses
{history_block}
Sam's latest message:
"{original_request}"

How many people to suggest: {options_rule}

Best matching contacts from Alex's network:
{contact_summary}

{opener_rule}

{language_rule}

Write Alex's WhatsApp reply now. 2-4 sentences maximum.
Do NOT use bullet points or lists.
Do NOT include any contact phone numbers or emails.
Do NOT wrap your reply in quotation marks — output only the raw message text,
with no leading or trailing quote characters of any kind.
Sound genuine, personal, and confident."""

        for config in self.configs:
            headers = {
                "Authorization": f"Bearer {config['api_key']}",
                "Content-Type": "application/json",
            }
            json_payload = {
                "model": config["model"],
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
                "max_tokens": 200,
            }

            for attempt in range(1, self.max_attempts + 1):
                try:
                    async with httpx.AsyncClient() as client:
                        response = await client.post(
                            config["api_url"], headers=headers, json=json_payload, timeout=self._timeout_for(config)
                        )
                    if response.status_code == 200:
                        draft = response.json()["choices"][0]["message"]["content"].strip()
                        draft = _strip_wrapping_quotes(draft)
                        slog(f"[Draft/{config['name']}] Generated (attempt {attempt}): {draft[:100]}...")
                        return draft
                    # Retry rate-limits / server errors; give up on other 4xx.
                    slog(f"[Draft/{config['name']}] API error {response.status_code} (attempt {attempt}/{self.max_attempts})")
                    if response.status_code < 500 and response.status_code != 429:
                        break
                except (httpx.TimeoutException, httpx.TransportError) as e:
                    slog(f"[Draft/{config['name']}] transient error (attempt {attempt}/{self.max_attempts}): {type(e).__name__}: {e!r}")

                if attempt < self.max_attempts:
                    await asyncio.sleep(self._backoff_for(config) * attempt)

        # All providers exhausted — return a graceful, natural fallback so Alex
        # still gets something to send rather than an error.
        slog("[Draft] all providers exhausted — returning fallback line")
        return "Hey! I've got some great people in mind for this — let me get back to you shortly 🤝"