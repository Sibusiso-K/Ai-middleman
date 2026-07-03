"""
llm_provider.py — Picks which chat-completions provider the LLM-calling
services (intent_classifier, agent, draft_generator) should use.

Groq and Featherless both expose an OpenAI-compatible /v1/chat/completions
endpoint (same request/response shape), so switching providers is just a
matter of pointing at a different URL/key/model — no per-service code changes
needed. Groq is preferred when GROQ_API_KEY is set (much faster inference on
the free tier); otherwise falls back to the existing Featherless config so
nothing breaks for anyone who hasn't added a Groq key yet.
"""

import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent.parent.parent / ".env")


def get_chat_config() -> dict:
    """Returns {"api_key", "api_url", "model"} for whichever provider is active."""
    if os.getenv("GROQ_API_KEY"):
        return {
            "api_key": os.getenv("GROQ_API_KEY"),
            "api_url": os.getenv("GROQ_API_URL", "https://api.groq.com/openai/v1/chat/completions"),
            "model": os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"),
        }
    return {
        "api_key": os.getenv("FEATHERLESS_API_KEY") or os.getenv("OPENROUTER_API_KEY"),
        "api_url": os.getenv("FEATHERLESS_API_URL", "https://api.featherless.ai/v1/chat/completions"),
        "model": os.getenv("FEATHERLESS_MODEL", "NousResearch/Meta-Llama-3.1-8B-Instruct"),
    }


def using_groq() -> bool:
    return bool(os.getenv("GROQ_API_KEY"))
