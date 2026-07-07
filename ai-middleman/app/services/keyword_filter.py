"""
keyword_filter.py — Stage 1 of the two-stage matching pipeline.

Performs fast, local keyword-based filtering of the contact database,
reducing 50,000 contacts to at most CANDIDATE_LIMIT candidates before LLM
evaluation.

Two things make the shortlist actually relevant (rather than "whichever VIPs
happened to contain any word"):
  1. Stopword removal — filler/intent words like "need", "favor", "any", "good"
     are dropped so only meaningful role/skill/sector/company terms drive the
     search. Otherwise those common words match huge swaths of the DB.
  2. Relevance-scored ordering — rows are ranked by a weighted count of which
     high-signal fields (title, expertise, sector...) actually match the query
     terms, so the genuinely relevant contact isn't cut from the top-25 by a
     random high-relationship VIP that merely shared a word.

Location-aware: queries containing city/country names prioritise geographically
matching contacts as a tie-breaker after relevance.

Exposed: KeywordFilter class with filter_candidates(query) method.
"""

import re
from typing import List, Dict
import asyncpg

# Max candidates passed to the LLM ranker. Kept small enough to keep the
# Stage-2 prompt within reliable single-response size for an 8B model.
CANDIDATE_LIMIT = 25

# Filler / intent / greeting words that carry no matching signal. Left in, they
# turn into search terms that match most of the 50k contacts (e.g. "can" or
# "need" appears in countless free-text comments), swamping the real query
# terms. Stripped before building the search pattern. Locations are handled
# separately (see location_keywords) so they're removed from keyword terms too.
STOPWORDS = frozenset({
    # articles / prepositions / conjunctions
    "the", "and", "for", "with", "from", "into", "out", "off", "per",
    "that", "this", "these", "those", "some", "any", "all",
    # pronouns / question words
    "you", "your", "yours", "who", "whom", "whose", "our", "her", "his",
    "them", "they", "him", "she", "someone", "somebody", "anyone", "anybody",
    "one", "ones", "guy", "guys", "person", "people", "man", "woman",
    # intent / filler verbs & nouns
    "need", "needs", "want", "wants", "looking", "look", "find", "finding",
    "know", "knows", "connect", "connected", "intro", "introduce", "introduction",
    "recommend", "recommendation", "suggest", "meet", "meeting", "talk", "speak",
    "favor", "favour", "help", "helping", "please", "would", "like", "could",
    "can", "get", "got", "put", "touch", "reach", "hey", "hello", "howzit",
    "good", "great", "solid", "top", "best", "nice", "really", "very", "much",
    "have", "has", "had", "are", "was", "were", "will", "should", "must",
    "there", "here", "about", "just", "also", "still", "back", "now", "then",
    "yeah", "okay", "sure", "thanks", "thank", "cheers",
    # this app's own actor name shouldn't become a search term
    "alex", "sam",
})


class KeywordFilter:
    def __init__(self, db_pool: asyncpg.Pool):
        self.db_pool = db_pool

    # Fields that count toward relevance, with weights. Higher weight = stronger
    # signal that a match here means the contact really does what was asked.
    # looking_for / comment are intentionally excluded from scoring (low signal,
    # often incidental) but stay in the WHERE clause for recall.
    _RELEVANCE_FIELDS = [
        ("title", 3),
        ("expertise_tags", 2),
        ("can_help_with", 2),
        ("sector", 2),
        ("specialty", 2),
        ("company", 1),
        ("full_name", 1),
    ]

    # Fields searched to decide whether a row is a candidate at all (recall).
    _WHERE_FIELDS = [
        "full_name", "title", "company", "sector", "specialty",
        "expertise_tags", "can_help_with", "looking_for", "comment",
    ]

    async def filter_candidates(self, query: str) -> List[Dict]:
        tokens = [t.lower() for t in re.findall(r"\b\w{3,}\b", query)]
        if not tokens:
            return []

        # Known location keywords to detect and prioritise
        location_keywords = [
            'london', 'new york', 'york', 'dubai', 'singapore', 'johannesburg',
            'toronto', 'sydney', 'mumbai', 'paris', 'frankfurt', 'zurich',
            'geneva', 'amsterdam', 'chicago', 'boston', 'angeles', 'francisco',
            'paulo', 'hong kong', 'shanghai', 'berlin', 'tokyo', 'africa',
            'europe', 'asia', 'usa', 'uk', 'uae', 'canada', 'australia'
        ]
        query_lower = query.lower()
        location_tokens = [loc for loc in location_keywords if loc in query_lower]
        has_location = len(location_tokens) > 0

        # Location single-word tokens, so they can be excluded from keyword terms
        # (they're matched separately via the location pattern).
        location_words = set()
        for loc in location_tokens:
            location_words.update(loc.split())

        # Meaningful search terms = tokens minus stopwords minus location words.
        kw_terms = [t for t in tokens if t not in STOPWORDS and t not in location_words]
        if not kw_terms and not has_location:
            # No location and nothing but stopwords left (e.g. "howzit need a
            # favor") — there is genuinely nothing to search on. Return nothing
            # so the engine responds with an honest "tell me more" rather than
            # matching random contacts on filler words.
            return []

        # Leading word-boundary pattern (\y in Postgres regex). The boundary is
        # only at the START of each term, not the end, so "law" no longer matches
        # mid-word ("flawless") and "art" no longer matches "Bart", while still
        # matching suffix/plural variants that matter for recall ("advisor" ->
        # "advisory"/"advisors", "investor" -> "investors"). De-duplicated.
        kw_pattern = r"\y(" + "|".join(sorted(set(kw_terms))) + r")" if kw_terms else None
        location_pattern = "|".join(location_tokens) if has_location else None

        sql, params = self._build_sql(kw_pattern, location_pattern)
        async with self.db_pool.acquire() as conn:
            results = await conn.fetch(sql, *params)
        return [dict(row) for row in results]

    def _build_sql(self, kw_pattern, location_pattern):
        """Assemble the candidate query from whichever signals are present:
        keyword terms, a location, or both. relevance_score is always the
        primary sort so role/skill relevance wins over incidental VIP status."""
        select_cols = (
            "id, contact_id, full_name, phone, email, company, title, "
            "sector, specialty, location, seniority, expertise_tags, "
            "can_help_with, looking_for, relationship_strength, "
            "how_alex_knows_them, is_vip, comment"
        )
        params = []
        kw_idx = loc_idx = None
        if kw_pattern is not None:
            params.append(kw_pattern)
            kw_idx = len(params)
        if location_pattern is not None:
            params.append(location_pattern)
            loc_idx = len(params)

        # relevance_score: weighted sum of high-signal field matches.
        if kw_idx is not None:
            relevance_expr = " + ".join(
                f"(CASE WHEN LOWER({field}) ~ ${kw_idx} THEN {weight} ELSE 0 END)"
                for field, weight in self._RELEVANCE_FIELDS
            )
        else:
            relevance_expr = "0"

        location_expr = (
            f"CASE WHEN LOWER(location) ~ ${loc_idx} THEN 3 ELSE 0 END"
            if loc_idx is not None else "0"
        )

        # WHERE: a row qualifies if it matches any searched field on the keyword
        # pattern, or (when a location was given) is in that location.
        where_clauses = []
        if kw_idx is not None:
            where_clauses.append(
                "(" + " OR ".join(f"LOWER({f}) ~ ${kw_idx}" for f in self._WHERE_FIELDS) + ")"
            )
        if loc_idx is not None:
            where_clauses.append(f"LOWER(location) ~ ${loc_idx}")
        where_sql = " OR ".join(where_clauses) if where_clauses else "TRUE"

        sql = f"""
            SELECT
                {select_cols},
                ({relevance_expr}) AS relevance_score,
                ({location_expr}) AS location_score
            FROM contacts
            WHERE {where_sql}
            ORDER BY
                relevance_score DESC,
                location_score DESC,
                is_vip DESC,
                relationship_strength DESC
            LIMIT {CANDIDATE_LIMIT}
        """
        return sql, params
