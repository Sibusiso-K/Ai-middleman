"""
agent.py — Stage 2 of the two-stage matching pipeline.

Sends the 30-50 candidates from the keyword filter to an LLM (Featherless.ai
hosting Llama 3.1 8B) for intelligent ranking. The LLM evaluates each candidate
against the user's query using strict scoring rules and returns ranked matches
with confidence scores and human-readable reasoning.

Exposed: LLMAgent class with evaluate_matches(query, candidates) method.
"""

import httpx
import os
import json
import asyncio
from typing import Dict, Any, List
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent.parent.parent / ".env")

class LLMAgent:
    def __init__(self):
        self.api_key = os.getenv("FEATHERLESS_API_KEY")
        self.api_url = "https://api.featherless.ai/v1/chat/completions"
        self.model = "NousResearch/Meta-Llama-3.1-8B-Instruct"

    async def evaluate_matches(self, query: str, candidates: List[Dict]) -> Dict[str, Any]:
        if not candidates:
            return {
                "analysis": "No candidates found by keyword filter",
                "matches": [],
                "match_quality": "none",
                "clarification_question": "I couldn't find any relevant contacts. Could you tell me more about who you are looking for?"
            }

        prompt = self._build_prompt(query, candidates)

        max_retries = 3
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        self.api_url,
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json"
                        },
                        json={
                            "model": self.model,
                            "messages": [{"role": "user", "content": prompt}],
                            "max_tokens": 1024,
                            "temperature": 0.1
                        },
                        timeout=30.0
                    )

                    if response.status_code == 200:
                        result = response.json()
                        content = result["choices"][0]["message"]["content"]
                        parsed = json.loads(content)
                        return parsed
                    elif response.status_code == 429:
                        retry_after = 5 * (attempt + 1)
                        print(f"Rate limited, retrying in {retry_after}s (attempt {attempt+1}/{max_retries})")
                        await asyncio.sleep(retry_after)
                        continue
                    else:
                        print(f"Featherless error: {response.status_code} {response.text}")
                        return self._fallback_response()

            except Exception as e:
                print(f"LLM Agent error (attempt {attempt+1}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(3)
                    continue
                return self._fallback_response()

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

IMPORTANT: Be discriminating. It is better to return 2-3 strong matches than 5 weak ones. If no contact scores above 0.5, set match_quality to "weak". If none score above 0.3, set match_quality to "none" and ask a clarifying question.

Respond ONLY with this exact JSON structure:
{{
    "analysis": "2-3 sentences explaining what the user needs and what you looked for. Only mention location if the user asked for one.",
    "matches": [
        {{
            "contact_id": 123,
            "name": "Full Name",
            "title": "Job Title",
            "company": "Company Name",
            "location": "Location",
            "confidence": 0.85,
            "reasoning": "Specific explanation referencing this contact's actual skills and why they fit THIS request. Only mention location if the user asked for a specific location. Minimum 2 sentences. Be truthful — do not claim requirements that weren't stated."
        }}
    ],
    "match_quality": "good",
    "clarification_question": ""
}}

Sort matches by confidence score descending. Maximum 5 matches. Only include contacts scoring above 0.3."""

    def _fallback_response(self) -> Dict[str, Any]:
        return {
            "analysis": "LLM temporarily unavailable",
            "matches": [],
            "match_quality": "none",
            "clarification_question": "I'm experiencing temporary difficulties. Please try again in a moment."
        }