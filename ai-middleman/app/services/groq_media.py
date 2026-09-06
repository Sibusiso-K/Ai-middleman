"""
groq_media.py — Voice-note transcription and image understanding via Groq.

Both WhatsApp voice notes and images (from Alex's real phone or Sam's
dashboard/web upload) get converted to plain text here, then fed into the
exact same intent/matching/draft pipeline as a normal typed message — so a
voice note asking "know a lawyer in Durban?" triggers a suggestion exactly
like typing it would. That shared pipeline (IntentClassifier.classify) is
what detects language and replies in kind, so voice/image messages get the
same language handling as a typed message — English and Afrikaans, per
sa_languages.py — with no extra code needed here.

Requires GROQ_API_KEY. Raises MediaTranscriptionError if it's missing or the
API call fails — callers should surface that clearly rather than silently
dropping a voice note/image.
"""

import base64
import httpx
from dotenv import load_dotenv
from pathlib import Path
from app.services.llm_provider import (
    configured_key,
    groq_model,
    setting,
    chat_payload,
    completion_text,
)

load_dotenv(Path(__file__).parent.parent.parent / ".env")

GROQ_BASE = "https://api.groq.com/openai/v1"


class MediaTranscriptionError(Exception):
    """Raised when a voice note/image could not be transcribed or described."""


async def _post(url: str, **kwargs) -> httpx.Response:
    try:
        async with httpx.AsyncClient() as client:
            return await client.post(url, **kwargs)
    except httpx.HTTPError as exc:
        raise MediaTranscriptionError(
            "Media service could not be reached; please retry or type the message."
        ) from exc


def _require_key() -> str:
    key = configured_key("GROQ_API_KEY")
    if not key:
        raise MediaTranscriptionError(
            "GROQ_API_KEY is not set — voice/image transcription needs a free "
            "key from https://console.groq.com/keys, added to .env."
        )
    return key


async def transcribe_audio(audio_bytes: bytes, filename: str = "voice.ogg") -> str:
    """Transcribe a voice note to text using Groq's hosted Whisper.

    No `language` parameter is passed, so Whisper auto-detects it and
    transcribes in that language (not English) — a voice note in isiZulu
    comes back as isiZulu text, which then flows into IntentClassifier.
    Whisper's accuracy varies a lot across South Africa's 11 official
    languages: strong for English/Afrikaans, workable for isiZulu/isiXhosa/
    Sesotho, and meaningfully weaker for isiNdebele, Xitsonga, Tshivenda,
    siSwati, and Sepedi/Setswana — a training-data limitation of every open
    transcription model, not something fixable in this code."""
    api_key = _require_key()
    model = setting("GROQ_WHISPER_MODEL", "whisper-large-v3-turbo")

    response = await _post(
        f"{GROQ_BASE}/audio/transcriptions",
        headers={"Authorization": f"Bearer {api_key}"},
        files={"file": (filename, audio_bytes)},
        data={"model": model, "response_format": "text"},
        timeout=60.0,
    )
    if response.status_code != 200:
        raise MediaTranscriptionError(
            f"Groq transcription failed (HTTP {response.status_code}); please retry or type the message."
        )
    if not response.text.strip():
        raise MediaTranscriptionError(
            "Groq returned an empty transcription; please retry or type the message."
        )
    return response.text.strip()


async def describe_image(image_bytes: bytes, mime_type: str = "image/jpeg") -> str:
    """
    Describe an image (and read any text in it) using a Groq vision model.
    Returns a short description suitable for feeding into the same text
    pipeline as a typed message — e.g. a business-card photo becomes
    something like "A business card for Jane Doe, Partner at XYZ Legal,
    jane@xyz.com, +27 82 555 1234."

    Does not force the description into English: if the image contains text
    in one of South Africa's other official languages (a business card note
    in isiZulu, for instance), it's transcribed verbatim in its own
    language, not translated — IntentClassifier.classify detects the
    language downstream the same way it would for a typed message.
    """
    api_key = _require_key()
    model = groq_model(vision=True)

    b64 = base64.b64encode(image_bytes).decode("ascii")
    data_url = f"data:{mime_type};base64,{b64}"

    prompt = (
        "Describe this image in 1-3 sentences. If it contains any text (e.g. a "
        "business card, screenshot, or job posting), transcribe that text "
        "exactly as written, in whatever language it's actually in — do NOT "
        "translate it into English. Be factual and concise — this will be "
        "treated as if the sender had typed it as a WhatsApp message."
    )

    response = await _post(
        f"{GROQ_BASE}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=chat_payload(
            {"name": "groq", "model": model},
            [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
            max_tokens=500,
            temperature=0.2,
        ),
        timeout=45.0,
    )
    if response.status_code != 200:
        raise MediaTranscriptionError(
            f"Groq vision failed (HTTP {response.status_code}); please retry or type the message."
        )
    try:
        return completion_text(response)
    except ValueError as exc:
        raise MediaTranscriptionError(
            "Groq returned no usable image description; please retry or type the message."
        ) from exc
