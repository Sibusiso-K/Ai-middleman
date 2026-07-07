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
import re
from dotenv import load_dotenv
from pathlib import Path

from app.services.llm_provider import get_chat_configs
from app.services.llm_json import extract_json
from app.services.sa_languages import SA_LANGUAGES
from app.log_safe import slog

load_dotenv(Path(__file__).parent.parent.parent / ".env")

# Deterministic backstop, not just a prompt instruction: seen live, the model
# sometimes force-fit genuine isiZulu into the "Afrikaans" bucket, since both
# just read as "not English" to it — e.g. "Ngifuna ummuntu kwiEnergy sector"
# (real isiZulu) came back drafted in Afrikaans. These are common isiZulu/
# Nguni words and noun-class prefixes that never appear in Afrikaans; if any
# show up, the message is NOT Afrikaans regardless of what the model said,
# so fall back to English rather than draft in the wrong language.
_NGUNI_MARKERS_RE = re.compile(
    r"\b(ngifuna|ngicela|ngidinga|sawubona|yebo|ngiyabonga|unjani|kanjani|"
    r"umuntu|abantu|umsebenzi|ngiyakuthanda|nginesiqiniseko)\b"
    r"|\b(kwi|ngi|ngu|izi|ubu|uku)[a-z]{2,}",
    re.IGNORECASE,
)


def _looks_nguni_not_afrikaans(text: str) -> bool:
    return bool(_NGUNI_MARKERS_RE.search(text))


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

Do ALL FIVE of the following in one pass:

1. Identify which language the message is written in: {languages_list} only — no other option exists. If it's already in English, is mostly English with just a greeting/aside in Afrikaans, is short/ambiguous, or you are not confident it is genuinely Afrikaans, say "English". Only say "Afrikaans" if you are confident the message is substantially written in Afrikaans.
2. Decide: is this message asking Alex to introduce someone, recommend a contact, refer someone, or connect the sender with a person from Alex's professional network? (is_request)
3. Decide: is this message sharing NEW factual information that should update a contact record — e.g. a new employer, new job title, new phone, new email, a promotion, or a location change? (is_update). This is DIFFERENT from a request: "I heard Aaron works at Deloitte now" is an update, NOT a request. "I moved to Yoco" is an update about the sender themselves.
4. If is_request is true, decide whether the message is asking about ONE SPECIFIC NAMED PERSON Alex might know (not a role/skill/sector search). "Do you know Aaron Aguirre?" and "Do you have Sarah Chen's details?" name a specific individual — extract that name into named_contact. "Do you know any good lawyers?" and "Anyone senior at JPMorgan?" do NOT name a specific individual (they describe a role/company/sector) — named_contact is null for these, even though they ARE still is_request=true.
5. Give an English rendering of the message. If it's already in English, repeat it unchanged. Translate meaning, not word-for-word — keep any names, companies, and locations exactly as written.

The message may contain typos, missing letters, or autocorrect mistakes (people type fast on WhatsApp) — read past the typos and judge the intended meaning, not the exact spelling. For example "i want sometging is Al consunltinnng" means "I want something in AI consulting" and IS a contact request.

is_request examples (TRUE), named_contact null (role/sector/company search, not one specific person):
- "Do you know any good lawyers in London?"
- "Who should I speak to about raising Series A?"
- "Can you connect me with someone in private equity?"
- "I need a CFO for my startup, anyone come to mind?"
- "Hey Alex any contacts in real estate Dubai?"
- "Do you know anyone from JPMorgan in a senior position?"
- "Who's your guy for debt financing?"

is_request examples (TRUE), named_contact SET (asking about one specific named individual):
- "Do you know Aaron Aguirre? Do you have his details?" → named_contact: "Aaron Aguirre"
- "Do you have Sarah Chen's number?" → named_contact: "Sarah Chen"
- "Is David Cohen still someone you know?" → named_contact: "David Cohen"

is_update examples (TRUE, is_request must be false):
- "Aaron Acosta works at Deloitte now" → contact_name: "Aaron Acosta", attribute: "company", new_value: "Deloitte"
- "Sarah left McKinsey, she's at BCG now" → contact_name: "Sarah", attribute: "company", new_value: "BCG"
- "Thabo got promoted to Managing Director" → contact_name: "Thabo", attribute: "title", new_value: "Managing Director"
- "I moved to Yoco, not Takealot anymore" → contact_name: null (sender updating themselves), attribute: "company", new_value: "Yoco"
- "My email changed to sam@yoco.com" → contact_name: null, attribute: "email", new_value: "sam@yoco.com"
- "My new number is 082 555 1234" → contact_name: null, attribute: "phone", new_value: "082 555 1234"

Attribute name must be one of: company, title, email, phone, location, sector, specialty.

Neither (is_request=false, is_update=false):
- "Hey how are you doing?"
- "Are we still on for dinner?"
- "Thanks for yesterday"
- "Call me when you're free"
- "What do you think about the market?"
- "Send" / "Skip" / "Edit" / "Status"

Message: "{message}"

Reply with ONLY this exact JSON shape, nothing else — no markdown, no explanation:
{{"language": "English or Afrikaans, nothing else", "is_request": true or false, "is_update": true or false, "named_contact": "<full name or null>", "english_query": "<English rendering of the message>"}}

If no specific person is named for a request, set named_contact to null."""

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
                            elif detected_language == "Afrikaans" and _looks_nguni_not_afrikaans(message):
                                # Seen live: the model force-fits genuine isiZulu into
                                # "Afrikaans" since both just read as "not English" to it.
                                # This deterministic word/prefix check overrides that —
                                # never draft in Afrikaans for a message that's actually
                                # isiZulu (or another Nguni language we don't support).
                                slog(f"[Intent] model said Afrikaans but text looks Nguni, not Afrikaans — defaulting to English: {message[:60]!r}")
                                detected_language = "English"
                            is_update = bool(data.get("is_update"))
                            named_contact = data.get("named_contact") or None
                            if isinstance(named_contact, str) and not named_contact.strip():
                                named_contact = None
                            result = {
                                "is_request": bool(data.get("is_request")),
                                "is_update": is_update,
                                "named_contact": named_contact,
                                "language": detected_language,
                                "english_query": data.get("english_query") or message,
                            }
                            slog(f"[Intent/{config['name']}] {result['language']}, is_request={result['is_request']}, is_update={result['is_update']}, named_contact={named_contact!r} (attempt {attempt})")
                            return result
                        except ValueError as e:
                            # Malformed / non-JSON reply — retry (transient LLM behaviour).
                            last_error = f"unparseable reply: {e}"
                            slog(f"[Intent/{config['name']}] unparseable reply (attempt {attempt}/{self.max_attempts}): {e}")
                    elif response.status_code == 429 and config is not self.configs[-1]:
                        # Rate-limited and a fallback provider exists — skip this
                        # hot provider's remaining retries and try the next one.
                        last_error = "HTTP 429"
                        slog(f"[Intent/{config['name']}] rate-limited (429) — switching to next provider")
                        break
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
