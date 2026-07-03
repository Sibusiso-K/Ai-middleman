"""
groq_media.py — Voice-note transcription and image understanding via Groq.

Both WhatsApp voice notes and images (from Alex's real phone or Sam's
dashboard/web upload) get converted to plain text here, then fed into the
exact same intent/matching/draft pipeline as a normal typed message — so a
voice note asking "know a lawyer in Durban?" triggers a suggestion exactly
like typing it would.

Requires GROQ_API_KEY. Raises MediaTranscriptionError if it's missing or the
API call fails — callers should surface that clearly rather than silently
dropping a voice note/image.
"""

import base64
import os
import httpx
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent.parent.parent / ".env")

GROQ_BASE = "https://api.groq.com/openai/v1"


class MediaTranscriptionError(Exception):
    """Raised when a voice note/image could not be transcribed or described."""


def _require_key() -> str:
    key = os.getenv("GROQ_API_KEY")
    if not key:
        raise MediaTranscriptionError(
            "GROQ_API_KEY is not set — voice/image transcription needs a free "
            "key from https://console.groq.com/keys, added to .env."
        )
    return key


async def transcribe_audio(audio_bytes: bytes, filename: str = "voice.ogg") -> str:
    """Transcribe a voice note to text using Groq's hosted Whisper."""
    api_key = _require_key()
    model = os.getenv("GROQ_WHISPER_MODEL", "whisper-large-v3-turbo")

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{GROQ_BASE}/audio/transcriptions",
            headers={"Authorization": f"Bearer {api_key}"},
            files={"file": (filename, audio_bytes)},
            data={"model": model, "response_format": "text"},
            timeout=60.0,
        )
    if response.status_code != 200:
        raise MediaTranscriptionError(f"Groq transcription failed: {response.status_code} {response.text[:300]}")
    return response.text.strip()


async def describe_image(image_bytes: bytes, mime_type: str = "image/jpeg") -> str:
    """
    Describe an image (and read any text in it) using a Groq vision model.
    Returns a short plain-English description suitable for feeding into the
    same text pipeline as a typed message — e.g. a business-card photo becomes
    something like "A business card for Jane Doe, Partner at XYZ Legal,
    jane@xyz.com, +27 82 555 1234."
    """
    api_key = _require_key()
    model = os.getenv("GROQ_VISION_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")

    b64 = base64.b64encode(image_bytes).decode("ascii")
    data_url = f"data:{mime_type};base64,{b64}"

    prompt = (
        "Describe this image in 1-3 sentences, in plain English. If it contains "
        "any text (e.g. a business card, screenshot, or job posting), transcribe "
        "that text exactly. Be factual and concise — this will be treated as if "
        "the sender had typed it as a WhatsApp message."
    )

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{GROQ_BASE}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }],
                "max_tokens": 300,
                "temperature": 0.2,
            },
            timeout=45.0,
        )
    if response.status_code != 200:
        raise MediaTranscriptionError(f"Groq vision failed: {response.status_code} {response.text[:300]}")
    return response.json()["choices"][0]["message"]["content"].strip()
