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
                            return self._reconcile_matches(extract_json(content), candidates)
                        except json.JSONDecodeError as e:
                            # Malformed / non-JSON reply — retry (transient LLM behaviour).
                            slog(f"[Agent/{config['name']}] unparseable reply (attempt {attempt}/{self.max_retries}): {e}")
                    elif response.status_code == 429 and config is not self.configs[-1]:
                        # Rate-limited and we have a fallback provider — don't burn
                        # the remaining retries on this hot provider, jump straight
                        # to the next one (which isn't rate-limited).
                        slog(f"[Agent/{config['name']}] rate-limited (429) — switching to next provider")
                        break
                    elif response.status_code == 429 or response.status_code >= 500:
                        slog(f"[Agent/{config['name']}] retryable HTTP {response.status_code} (attempt {attempt}/{self.max_retries})")
                    else:
                        slog(f"[Agent/{config['name']}] non-retryable HTTP {response.status_code}: {response.text[:200]}")
                        break  # try the next provider, if any, rather than giving up outright

                except (httpx.TimeoutException, httpx.TransportError) as e:
                    slog(f"[Agent/{config['name']}] transient error (attempt {attempt}/{self.max_retries}): {type(e).__name__}: {e!r}")

                if attempt < self.max_retries:
                    await asyncio.sleep(self._backoff_for(config) * attempt)

            slog(f"[Agent] {config['name']} done — trying next provider" if config is not self.configs[-1] else f"[Agent] {config['name']} done — no more providers to try")

        return self._fallback_response()

    @staticmethod
    def _reconcile_matches(parsed: Dict[str, Any], candidates: List[Dict]) -> Dict[str, Any]:
        """Overwrite each match's display fields (name/title/company/location)
        with the authoritative candidate our own keyword filter supplied,
        looked up by contact_id, and drop any match whose id isn't a real
        candidate.

        The 8B ranking model reliably picks a real candidate *id* but
        sometimes writes a wrong or hallucinated *name* next to it. Trusting
        our own data guarantees the name shown to the user, and the
        phone/email delivered later (also keyed by that id), point at the same
        real person — otherwise Sam could be told about one contact and handed
        a different one's details."""
        by_id = {c["id"]: c for c in candidates}
        cleaned = []
        for m in parsed.get("matches", []) or []:
            cid = m.get("contact_id")
            try:
                cid = int(cid)
            except (TypeError, ValueError):
                pass
            c = by_id.get(cid)
            if not c:
                slog(f"[Agent] dropping match with unknown contact_id={m.get('contact_id')!r} (name claimed: {m.get('name')!r})")
                continue
            m["contact_id"] = cid
            m["name"] = c.get("full_name", m.get("name"))
            m["title"] = c.get("title", m.get("title"))
            m["company"] = c.get("company", m.get("company"))
            m["location"] = c.get("location", m.get("location"))
            cleaned.append(m)
        parsed["matches"] = cleaned
        if not cleaned and parsed.get("match_quality") != "none":
            parsed["match_quality"] = "none"
        return parsed

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
1. ROLE/SKILL MATCH (always primary): Does their title, expertise, and what they can help with directly match what the user needs? A contact whose ACTUAL role/skill does not do what the user asked for must score BELOW 0.5 — no matter how senior, VIP, or well-connected they are. A great tech founder is NOT a match for a "hedge fund" request; a marketer is NOT a match for a "lawyer" request.
2. LOCATION MATCH (only if user specified a location): If the user specified a city or country, contacts in that location score higher. A contact in the wrong location should NEVER score above 0.6. If NO location was specified, ignore location entirely — do not penalize or reward based on location. Being in the right city does NOT rescue a wrong-role contact — right city + wrong role is still below 0.5.
3. SECTOR MATCH (only if user specified a sector): If the user asked for a specific industry, match on that. A contact in a DIFFERENT sector than the one requested must score BELOW 0.5.
4. SENIORITY: More senior contacts (Partner, MD, Director) are preferred over junior ones for the same role.
5. RELATIONSHIP STRENGTH: Higher relationship strength (4-5) is preferred over weaker connections (1-2) when skills are equal.
6. VIP STATUS: VIP contacts get a small boost when all else is equal.

CONFIDENCE SCORE GUIDE (a score of 0.7+ REQUIRES a genuine role/sector match — not merely the right city or a strong relationship):
- 0.9-1.0: Perfect match — right role AND right sector, right location (if requested), right seniority, strong relationship
- 0.7-0.89: Good match — genuinely does the requested role/sector, matches most other requested criteria
- 0.5-0.69: Partial match — right role but wrong location (if location was requested), or right role but slightly off on seniority
- 0.3-0.49: Weak match — only LOOSELY, SOMEWHAT, or TANGENTIALLY related to what was asked. If you find yourself writing "somewhat related", "loosely related", "adjacent", or "could still help" in your reasoning, the score belongs HERE (below 0.5), not above it.
- Below 0.3: Do not include

CRITICAL: It is far better to return FEWER matches (or none) than to pad the list with wrong-role/wrong-sector contacts scored above 0.5. If nobody genuinely fits, set match_quality to "weak" or "none" — do not inflate a loose match to look confident.

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