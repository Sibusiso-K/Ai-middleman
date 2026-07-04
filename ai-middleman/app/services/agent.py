"""
agent.py — Stage 2 of the two-stage matching pipeline.

Sends the keyword filter's candidates (up to CANDIDATE_LIMIT, currently 25) to
an LLM (Groq's Llama 3.1 8B, with a Featherless fallback) for intelligent
ranking. The LLM evaluates each candidate against the user's query using strict
scoring rules and returns ranked matches with confidence scores and
human-readable reasoning.

Exposed: LLMAgent class with evaluate_matches(query, candidates) method.
"""

import httpx
import os
import json
import asyncio
from typing import Dict, Any, List
from dotenv import load_dotenv
from pathlib import Path

from app.services.llm_provider import get_chat_configs
from app.services.llm_json import extract_json
from app.log_safe import slog

load_dotenv(Path(__file__).parent.parent.parent / ".env")

class LLMAgent:
    def __init__(self):
        # Ordered list: Groq first (fast) when configured, Featherless as a
        # fallback if Groq's free-tier rate limit is exhausted mid-session.
        self.configs = get_chat_configs()
        self.max_retries = int(os.getenv("AGENT_MAX_ATTEMPTS", "3"))
        # Timeout/backoff are per-provider, not fixed once for the whole
        # instance — otherwise the Featherless fallback silently inherits
        # Groq's short timeout instead of the longer one it actually needs.
        self._timeout_override = os.getenv("AGENT_TIMEOUT_SECONDS")

    def _timeout_for(self, config: dict) -> float:
        if self._timeout_override:
            return float(self._timeout_override)
        return 15.0 if config["name"] == "groq" else 45.0

    def _backoff_for(self, config: dict) -> float:
        # Backoff was tuned for Featherless's flakiness; Groq is fast and
        # reliable, so keep worst-case retry latency bounded on that path.
        return 1.0 if config["name"] == "groq" else 3.0

    async def evaluate_matches(self, query: str, candidates: List[Dict]) -> Dict[str, Any]:
        if not candidates:
            return {
                "analysis": "No candidates found by keyword filter",
                "matches": [],
                "match_quality": "none",
                "clarification_question": "I couldn't find any relevant contacts. Could you tell me more about who you are looking for?"
            }

        prompt = self._build_prompt(query, candidates)

        for config in self.configs:
            for attempt in range(1, self.max_retries + 1):
                try:
                    async with httpx.AsyncClient() as client:
                        response = await client.post(
                            config["api_url"],
                            headers={
                                "Authorization": f"Bearer {config['api_key']}",
                                "Content-Type": "application/json"
                            },
                            json={
                                "model": config["model"],
                                "messages": [{"role": "user", "content": prompt}],
                                "max_tokens": 1024,
                                "temperature": 0.1
                            },
                            timeout=self._timeout_for(config)
                        )

                    if response.status_code == 200:
                        content = response.json()["choices"][0]["message"]["content"]
                        try:
                            return extract_json(content)
                        except json.JSONDecodeError as e:
                            # Malformed / non-JSON reply — retry (transient LLM behaviour).
                            slog(f"[Agent/{config['name']}] unparseable reply (attempt {attempt}/{self.max_retries}): {e}")
                    elif response.status_code == 429 or response.status_code >= 500:
                        slog(f"[Agent/{config['name']}] retryable HTTP {response.status_code} (attempt {attempt}/{self.max_retries})")
                    else:
                        slog(f"[Agent/{config['name']}] non-retryable HTTP {response.status_code}: {response.text[:200]}")
                        break  # try the next provider, if any, rather than giving up outright

                except (httpx.TimeoutException, httpx.TransportError) as e:
                    slog(f"[Agent/{config['name']}] transient error (attempt {attempt}/{self.max_retries}): {type(e).__name__}: {e!r}")

                if attempt < self.max_retries:
                    await asyncio.sleep(self._backoff_for(config) * attempt)

            slog(f"[Agent] {config['name']} exhausted after {self.max_retries} attempts — trying next provider" if config is not self.configs[-1] else f"[Agent] {config['name']} exhausted — no more providers to try")

        return self._fallback_response()

    def _build_prompt(self, query: str, candidates: List[Dict]) -> str:
        candidate_list = "\n".join(
            f"ID: {c['id']} | Name: {c['full_name']} | Title: {c['title']} | "
            f"Company: {c.get('company', '')} | Sector: {c.get('sector', '')} | "
            f"Location: {c.get('location', '')} | "
            f"Can Help With: {c.get('can_help_with', '')} | "
            f"Looking For: {c.get('looking_for', '')} | "
            f"Expertise: {c.get('expertise_tags', '')} | "
            f"VIP: {c.get('is_vip', False)} | "
            f"Relationship Strength: {c.get('relationship_strength', 0)}/5 | "
            f"Comment: {c.get('comment', '')}"
            for c in candidates
        )

        return f"""You are an expert business contact matcher. Your job is to find the BEST matching contacts for a specific request.

USER REQUEST: "{query}"

CANDIDATE CONTACTS:
{candidate_list}

STEP 1 — ANALYZE THE QUERY:
First, determine what the user is actually asking for. Identify:
- Does the query specify a LOCATION (city, country, region)? If not, do NOT use location as a scoring factor.
- Does the query specify a ROLE, SKILL, or EXPERTISE? This is what you should primarily match on.
- Does the query specify a SECTOR or INDUSTRY?
- Does the query specify a SENIORITY level?

STEP 2 — SCORING RULES (apply strictly, only use factors the user actually requested):
1. ROLE/SKILL MATCH (always primary): Does their title, expertise, and what they can help with directly match what the user needs?
2. LOCATION MATCH (only if user specified a location): If the user specified a city or country, contacts in that location score higher. A contact in the wrong location should NEVER score above 0.6. If NO location was specified, ignore location entirely — do not penalize or reward based on location.
3. SECTOR MATCH (only if user specified a sector): If the user asked for a specific industry, match on that.
4. SENIORITY: More senior contacts (Partner, MD, Director) are preferred over junior ones for the same role.
5. RELATIONSHIP STRENGTH: Higher relationship strength (4-5) is preferred over weaker connections (1-2) when skills are equal.
6. VIP STATUS: VIP contacts get a small boost when all else is equal.

CONFIDENCE SCORE GUIDE:
- 0.9-1.0: Perfect match — right role, right location (if requested), right seniority, strong relationship
- 0.7-0.89: Good match — right role, matches most other requested criteria
- 0.5-0.69: Partial match — somewhat related role, or right role but wrong location (if location was requested)
- 0.3-0.49: Weak match — loosely related skills
- Below 0.3: Do not include

TRUTHFULNESS RULES — CRITICAL:
- NEVER claim a contact "matches the location requirement" if the user did NOT specify a location.
- NEVER invent requirements that were not in the user's request.
- NEVER say a contact is "in the right location" unless the user actually asked for a specific location AND the contact is in that location.
- If the user did not specify a location, do NOT mention location at all in your reasoning.
- Only reference criteria that the user actually asked for.

IMPORTANT: Be discriminating. Return at most the top 3 matches, not 5 — quality over quantity. If no contact scores above 0.5, set match_quality to "weak". If none score above 0.3, set match_quality to "none" and ask a clarifying question.

Keep all text SHORT — this is read on a phone. Be concise everywhere.

Respond ONLY with this exact JSON structure:
{{
    "analysis": "One short sentence on what the user needs. Only mention location if the user asked for one.",
    "matches": [
        {{
            "contact_id": 123,
            "name": "Full Name",
            "title": "Job Title",
            "company": "Company Name",
            "location": "Location",
            "confidence": 0.85,
            "reasoning": "One concise sentence (max ~25 words) on why this contact fits THIS request. Only mention location if the user asked for a specific location. Be truthful — do not claim requirements that weren't stated."
        }}
    ],
    "match_quality": "good",
    "clarification_question": ""
}}

Sort matches by confidence score descending. Maximum 3 matches. Only include contacts scoring above 0.3."""

    def _fallback_response(self) -> Dict[str, Any]:
        return {
            "analysis": "LLM temporarily unavailable",
            "matches": [],
            "match_quality": "none",
            "clarification_question": "I'm experiencing temporary difficulties. Please try again in a moment."
        }