"""
response_formatter.py — Converts LLM agent JSON output into WhatsApp-ready text.

Privacy rule: NEVER reveals real contact names, phone numbers, or emails.
Shows contact ID codes and reasoning only. User selects by number (1-5).

Exposed: format_response(agent_output) -> str
"""

from typing import Dict, Any


def format_response(agent_output: Dict[str, Any]) -> str:
    quality = agent_output.get("match_quality", "none")
    matches = agent_output.get("matches", [])
    clarification = agent_output.get("clarification_question", "")

    if quality == "good" and matches:
        text = "✅ Here are the best matches I found:\n\n"
        for idx, m in enumerate(matches[:5]):
            contact_id = m.get('contact_id', 'N/A')
            confidence_pct = int(m.get('confidence', 0) * 100)
            confidence_bar = "🟢" if confidence_pct >= 70 else "🟡" if confidence_pct >= 40 else "🔴"
            text += f"{idx + 1}. *Ref: C-{contact_id}*\n"
            text += f"   {m.get('title', '')} at {m.get('company', '')}\n"
            text += f"   📍 {m.get('location', '')}\n"
            text += f"   {confidence_bar} {m.get('reasoning', '')}\n"
            text += f"   Match: {confidence_pct}%\n\n"
        text += "━━━━━━━━━━━━━━━━━━━━\n"
        text += "Reply with *1*, *2*, *3*, *4*, or *5* to request an introduction."
        return text.strip()

    elif quality == "weak" and matches:
        text = "⚠️ I found some partial matches:\n\n"
        for idx, m in enumerate(matches[:3]):
            contact_id = m.get('contact_id', 'N/A')
            text += f"{idx + 1}. *Ref: C-{contact_id}*\n"
            text += f"   {m.get('title', '')} at {m.get('company', '')}\n"
            text += f"   📍 {m.get('location', '')}\n"
            text += f"   {m.get('reasoning', '')}\n\n"
        text += "Reply with a number to request an introduction, or refine your search."
        return text.strip()

    else:
        if clarification:
            return clarification
        return "I couldn't find matching contacts. Could you provide more details about who you need?"