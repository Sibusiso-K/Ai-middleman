"""
matching_engine.py — Orchestrator for the two-stage matching pipeline.

Wires together Stage 1 (KeywordFilter) and Stage 2 (LLMAgent), passing
candidates from the keyword filter to the LLM for intelligent ranking.
Returns a complete result dict with matches, confidence scores, and a
WhatsApp-ready formatted response.

Exposed: MatchingEngine class with match(query) method.
"""

import asyncpg
from app.services.keyword_filter import KeywordFilter
from app.services.agent import LLMAgent
from app.services.response_formatter import format_response
from app.log_safe import slog

class MatchingEngine:
    def __init__(self, db_pool: asyncpg.Pool):
        self.keyword_filter = KeywordFilter(db_pool)
        self.agent = LLMAgent()

    async def match(self, query: str, candidates: list | None = None) -> dict:
        # Callers that already fetched candidates concurrently with an
        # independent check (e.g. intent classification) can pass them in
        # directly, skipping a redundant second DB round-trip.
        if candidates is None:
            slog(f"[Stage 1] Running keyword filter for: '{query}'")
            candidates = await self.keyword_filter.filter_candidates(query)
            slog(f"[Stage 1] Found {len(candidates)} candidates")

        if not candidates:
            return {
                "query": query,
                "candidates_count": 0,
                "candidates_found": 0,
                "match_quality": "none",
                "matches": [],
                "formatted_response": "I couldn't find any contacts matching your request. Could you provide more details?",
                "clarification_question": "I couldn't find any relevant contacts. Could you tell me more about who you are looking for?",
                "draft_reply": "",
            }

        # Stage 2: LLM agent ranks and scores candidates. The draft reply is
        # written separately by DraftGenerator (see friend.py) — a large
        # single-call "rank + draft" prompt proved unreliable for the 8B model.
        slog(f"[Stage 2] Running LLM agent for: '{query}'")
        agent_output = await self.agent.evaluate_matches(query, candidates)
        slog(f"[Stage 2] LLM returned match_quality={agent_output.get('match_quality', 'unknown')}")

        # Build formatted response from agent output
        formatted = format_response(agent_output)

        return {
            "query": query,
            "candidates_count": len(candidates),
            "candidates_found": len(candidates),
            "match_quality": agent_output.get("match_quality", "none"),
            "matches": agent_output.get("matches", []),
            "formatted_response": formatted,
            "clarification_question": agent_output.get("clarification_question", ""),
            "draft_reply": agent_output.get("draft_reply", ""),
        }
