"""
llm_json.py — Shared JSON-parsing helper for LLM chat-completion responses.

Small instruction-tuned models routinely wrap their JSON in markdown fences,
surrounding prose, trailing commas, or stray unescaped quotes inside string
values. extract_json() tolerates all of that. Used by both agent.py (match
ranking) and intent_classifier.py (intent + language detection).
"""

import json
import re
from typing import Any, Dict


def extract_json(content: str) -> Dict[str, Any]:
    """Parse a model's reply into JSON, tolerating markdown fences,
    surrounding prose, trailing commas, and stray unescaped quotes inside
    string values (Llama-family models occasionally echo raw text verbatim,
    breaking strict JSON)."""
    text = (content or "").strip()
    if text.startswith("```"):
        # strip ```json … ``` fences
        text = text.split("```", 2)[1] if text.count("```") >= 2 else text.strip("`")
        if text.lstrip().lower().startswith("json"):
            text = text.lstrip()[4:]

    candidates = [text]
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        candidates.append(text[start:end + 1])

    last_error = None
    for candidate in candidates:
        for variant in (candidate, _strip_trailing_commas(candidate)):
            try:
                return json.loads(variant)
            except json.JSONDecodeError as e:
                last_error = e
    raise last_error


def _strip_trailing_commas(text: str) -> str:
    """Removes trailing commas before a closing } or ] — a common
    malformed-JSON pattern from smaller instruction-tuned models."""
    return re.sub(r",(\s*[}\]])", r"\1", text)
