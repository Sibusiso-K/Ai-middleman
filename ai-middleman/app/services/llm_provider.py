"""Provider credentials and model-specific chat contracts.

Defaults checked 2026-09-06. Support is not account entitlement: run
scripts/check_llm.py with configured keys. See MODEL-MIGRATION.md.
"""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env")
logger = logging.getLogger(__name__)
GROQ_CHAT_MODEL = "openai/gpt-oss-20b"
GROQ_VISION_MODEL = "qwen/qwen3.6-27b"


def setting(name: str, default: str = "") -> str:
    """Blank .env entries should not override working defaults."""
    return os.getenv(name, "").strip() or default


def configured_key(name: str) -> str:
    value = setting(name)
    if value.lower().startswith("your_") or value.lower() in {"changeme", "replace_me"}:
        return ""
    return value


def groq_model(*, vision: bool = False) -> str:
    name = "GROQ_VISION_MODEL" if vision else "GROQ_MODEL"
    model = setting(name, GROQ_VISION_MODEL if vision else GROQ_CHAT_MODEL)
    replacements = {
        "llama-3.1-8b-instant": GROQ_CHAT_MODEL,
        "llama-3.3-70b-versatile": "openai/gpt-oss-120b",
        "qwen/qwen3-32b": "openai/gpt-oss-120b",
        "meta-llama/llama-4-scout-17b-16e-instruct": GROQ_VISION_MODEL,
        "meta-llama/llama-4-maverick-17b-128e-instruct": GROQ_VISION_MODEL,
    }
    if model in replacements:
        replacement = replacements[model]
        logger.warning(
            "%s uses retired model %s; migrating to %s", name, model, replacement
        )
        model = replacement
    return model


def get_chat_configs(include_huggingface: bool = True) -> list[dict]:
    """Only configured providers, in order; never borrow another vendor's key.

    HF stays out of ranking pending re-evaluation of multi-candidate output.
    No configuration means no requests, not a request with Bearer None.
    """
    providers = [
        ("groq", "GROQ", "https://api.groq.com/openai/v1/chat/completions", None),
        (
            "featherless",
            "FEATHERLESS",
            "https://api.featherless.ai/v1/chat/completions",
            "meta-llama/Llama-3.1-8B-Instruct",
        ),
        (
            "openrouter",
            "OPENROUTER",
            "https://openrouter.ai/api/v1/chat/completions",
            "meta-llama/llama-3.1-8b-instruct",
        ),
    ]
    if include_huggingface:
        providers.append(
            (
                "huggingface",
                "HUGGINGFACE",
                "https://router.huggingface.co/v1/chat/completions",
                "meta-llama/Llama-3.1-8B-Instruct:nscale",
            )
        )
    configs = []
    for name, prefix, url, default in providers:
        key = configured_key(f"{prefix}_API_KEY")
        if not key:
            continue
        model = groq_model() if name == "groq" else setting(f"{prefix}_MODEL", default)
        if name == "featherless" and model == "NousResearch/Meta-Llama-3.1-8B-Instruct":
            logger.warning("Replacing old Featherless model alias with %s", default)
            model = default
        configs.append(
            {
                "name": name,
                "api_key": key,
                "api_url": setting(f"{prefix}_API_URL", url),
                "model": model,
            }
        )
    return configs


def get_chat_config() -> dict:
    configs = get_chat_configs()
    if not configs:
        raise ValueError("No LLM provider configured; set a provider API key in .env")
    return configs[0]


def using_groq() -> bool:
    return bool(configured_key("GROQ_API_KEY"))


def chat_payload(
    config: dict,
    messages: list,
    *,
    max_tokens: int,
    temperature: float,
    json_object: bool = False,
) -> dict:
    """Budget for reasoning + final text; never display reasoning as a draft.

    Hiding reasoning does not disable it. The old 160-300 token budgets could
    run out before the final answer. Provider-specific fields stay on Groq.
    """
    payload = {
        "model": config["model"],
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if config["name"] == "groq":
        payload["max_completion_tokens"] = payload.pop("max_tokens")
        if config["model"] in {"openai/gpt-oss-20b", "openai/gpt-oss-120b"}:
            payload.update(reasoning_effort="low", include_reasoning=False)
            payload["max_completion_tokens"] = max(2048, max_tokens + 1024)
        elif config["model"] in {"qwen/qwen3.6-27b", "qwen/qwen3.8-27b"}:
            payload.update(reasoning_effort="none", reasoning_format="hidden")
        if json_object:
            payload["response_format"] = {"type": "json_object"}
    return payload


def completion_text(response) -> str:
    """Reject unusable 200 replies so retry/fallback runs, without logging PII."""
    try:
        choice = response.json()["choices"][0]
        content = choice["message"]["content"]
        if choice.get("finish_reason") in {"length", "content_filter", "tool_calls"}:
            raise ValueError("LLM did not finish a usable answer")
        if (
            not isinstance(content, str)
            or not content.strip()
            or "<think>" in content.lower()
        ):
            raise ValueError("LLM returned no usable final text")
        return content.strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError("Malformed LLM response envelope") from exc
