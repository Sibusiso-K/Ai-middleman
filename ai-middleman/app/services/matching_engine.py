"""
matching_engine.py — Orchestrator for the two-stage matching pipeline.

Wires together Stage 1 (KeywordFilter) and Stage 2 (LLMAgent), passing
candidates from the keyword filter to the LLM for intelligent ranking.
Returns a complete result dict with matches, confidence scores, and a
WhatsApp-ready formatted response.

Exposed: MatchingEngine class with match(query) method.
"""

import os
import asyncpg
from app.services.keyword_filter import KeywordFilter
from app.services.agent import LLMAgent
from app.services.response_formatter import format_response
from app.log_safe import slog

# When on, log exactly what Stage 1 hands the LLM (input) and what the LLM
# ranks back (output) — the "what went in / what came out" view needed to
# diagnose inaccurate suggestions. Default on for now (pre-demo); set
# MATCH_DEBUG=0 in .env to silence.
MATCH_DEBUG = os.getenv("MATCH_DEBUG", "1") not in ("0", "false", "False", "")


def _log_candidates(query: str, candidates: list) -> None:
    slog(f"[Match/in] query={query!r} — {len(candidates)} candidate(s) to LLM:")
    for c in candidates:
        slog(
            f"   #{c.get('id')} {c.get('full_name')} | {c.get('title')} @ "
            f"{c.get('company')} | {c.get('sector')} | {c.get('location')} "
            f"| relevance={c.get('relevance_score')} loc={c.get('location_score')}"
        )


def _log_matches(agent_output: dict) -> None:
    matches = agent_output.get("matches") or []
    slog(f"[Match/out] match_quality={agent_output.get('match_quality')} — {len(matches)} ranked match(es):")
    for m in matches:
        slog(
            f"   {m.get('name')} | {m.get('title')} @ {m.get('company')} "
            f"| conf={m.get('confidence')} | {m.get('reasoning')}"
        )


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

        if MATCH_DEBUG:
            _log_candidates(query, candidates)

        # Stage 2: LLM agent ranks and scores candidates. The draft reply is
        # written separately by DraftGenerator (see friend.py) — a large
        # single-call "rank + draft" prompt proved unreliable for the 8B model.
        slog(f"[Stage 2] Running LLM agent for: '{query}'")
        agent_output = await self.agent.evaluate_matches(query, candidates)
        slog(f"[Stage 2] LLM returned match_quality={agent_output.get('match_quality', 'unknown')}")

        if MATCH_DEBUG:
            _log_matches(agent_output)

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
