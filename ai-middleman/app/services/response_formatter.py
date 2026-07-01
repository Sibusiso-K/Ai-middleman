"""
response_formatter.py — Converts LLM agent JSON output into WhatsApp-ready text.

Takes the structured JSON from the LLM agent (matches, confidence scores,
reasoning) and formats it into a human-readable text message suitable for
WhatsApp delivery. Handles three quality tiers: good, weak, and none.

Exposed: format_response(agent_output) function.
"""

from typing import Dict, Any

def format_response(agent_output: Dict[str, Any]) -> str:
    quality = agent_output.get("match_quality", "none")
    matches = agent_output.get("matches", [])
    clarification = agent_output.get("clarification_question", "")

    if quality == "good" and matches:
        text = "Here are the best contacts I found:\n\n"
        for idx, m in enumerate(matches[:5]):
            text += f"{idx + 1}. *{m['name']}*\n"
            text += f"   {m.get('title', '')} at {m.get('company', '')}\n"
            text += f"   📍 {m.get('location', '')}\n"
            text += f"   ✅ {m.get('reasoning', '')}\n"
            text += f"   Confidence: {int(m.get('confidence', 0) * 100)}%\n\n"
        return text.strip()

    elif quality == "weak" and matches:
        text = "⚠️ I found some partial matches that might fit:\n\n"
        for idx, m in enumerate(matches[:3]):
            text += f"{idx + 1}. *{m['name']}*\n"
            text += f"   {m.get('title', '')} at {m.get('company', '')}\n"
            text += f"   📍 {m.get('location', '')}\n"
            text += f"   {m.get('reasoning', '')}\n\n"
        return text.strip()

    else:
        if clarification:
            return clarification
        return "I couldn't find any contacts matching your request. Could you provide more details?"