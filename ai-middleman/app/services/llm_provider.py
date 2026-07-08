"""
llm_provider.py — Picks which chat-completions provider the LLM-calling
services (intent_classifier, agent, draft_generator) should use.

Groq, Featherless, and HuggingFace's Inference Providers router all expose an
OpenAI-compatible /v1/chat/completions endpoint (same request/response shape),
so switching/adding providers is just a matter of pointing at a different
URL/key/model — no per-service code changes needed. Groq is preferred when
GROQ_API_KEY is set (much faster inference on the free tier); Featherless is
the second fallback; HuggingFace (Qwen3-8B via the nscale provider, routed
through router.huggingface.co) is a third, last-resort fallback — added as a
demo-day safety net, not a sustainable everyday provider: HF's free tier is
only $0.10/month of routed-request credit shared across every provider it
proxies to, so it's meant to absorb a handful of calls when both Groq and
Featherless are degraded, not carry real production traffic.
"""

import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent.parent.parent / ".env")


def _groq_config() -> dict:
    return {
        "name": "groq",
        "api_key": os.getenv("GROQ_API_KEY"),
        "api_url": os.getenv("GROQ_API_URL", "https://api.groq.com/openai/v1/chat/completions"),
        "model": os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"),
    }


def _featherless_config() -> dict:
    return {
        "name": "featherless",
        "api_key": os.getenv("FEATHERLESS_API_KEY") or os.getenv("OPENROUTER_API_KEY"),
        "api_url": os.getenv("FEATHERLESS_API_URL", "https://api.featherless.ai/v1/chat/completions"),
        "model": os.getenv("FEATHERLESS_MODEL", "NousResearch/Meta-Llama-3.1-8B-Instruct"),
    }


def _huggingface_config() -> dict:
    # Third, last-resort fallback via HF's Inference Providers router. Default
    # model pins the nscale provider explicitly (":nscale" suffix) rather than
    # ":fastest"/":auto", so behaviour doesn't silently change if HF re-routes
    # to a different backend later.
    #
    # Deliberately NOT Qwen3-8B: tested and confirmed it defaults to "thinking
    # mode" — it burns the token budget on a hidden reasoning_content field and
    # returns message.content = null unless the prompt is rewritten with a
    # "/no_think" directive per-call. That would mean special-casing the
    # prompt text for one provider across all three call sites (agent.py,
    # intent_classifier.py, draft_generator.py), which all currently assume
    # one universal prompt string works for every provider. Llama-3.1-8B-
    # Instruct via nscale was tested and returns clean, non-thinking JSON
    # content with the exact same prompts already in use — safer, zero-touch
    # drop-in given how close this was added to the demo.
    return {
        "name": "huggingface",
        "api_key": os.getenv("HUGGINGFACE_API_KEY"),
        "api_url": os.getenv("HUGGINGFACE_API_URL", "https://router.huggingface.co/v1/chat/completions"),
        "model": os.getenv("HUGGINGFACE_MODEL", "meta-llama/Llama-3.1-8B-Instruct:nscale"),
    }


def get_chat_config() -> dict:
    """Returns {"api_key", "api_url", "model"} for whichever provider is active."""
    return _groq_config() if os.getenv("GROQ_API_KEY") else _featherless_config()


def get_chat_configs(include_huggingface: bool = True) -> list[dict]:
    """Returns an ordered list of provider configs to try: Groq first (fast)
    when configured, Featherless second if Groq's free-tier rate limit is
    exhausted, and HuggingFace (Llama-3.1-8B-Instruct via nscale) last if that
    key is set and include_huggingface is True — a small safety net for when
    BOTH of the above are degraded at once, not a provider meant to carry
    sustained traffic (see module docstring).

    include_huggingface defaults to True but agent.py (Stage 2 matching)
    explicitly passes False: tested against the real multi-candidate matching
    prompt, this HF fallback only reached valid JSON on roughly 1 of 3 calls
    (it frequently narrates prose analysis and never emits the JSON at all,
    even with a larger max_tokens budget) — unreliable for the one call site
    where correctness matters most. It tested reliably clean for the simpler
    intent-classification and draft-generation prompts, so it stays enabled
    there."""
    configs = []
    if os.getenv("GROQ_API_KEY"):
        configs.append(_groq_config())
    if os.getenv("FEATHERLESS_API_KEY") or os.getenv("OPENROUTER_API_KEY"):
        configs.append(_featherless_config())
    if include_huggingface and os.getenv("HUGGINGFACE_API_KEY"):
        configs.append(_huggingface_config())
    return configs or [get_chat_config()]


def using_groq() -> bool:
    return bool(os.getenv("GROQ_API_KEY"))
