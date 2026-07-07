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

# Role/topic words → the contact sector they imply. Contacts often describe
# themselves in domain vocabulary that never contains the query's word: a
# corporate lawyer's fields say "competition law", "M&A", "legal diligence" —
# never "lawyer" or even "corporate". Without this, a "lawyer" query scores
# those real lawyers 0 and surfaces healthcare "Head of Corporate Dev" people
# instead (whose title literally contains "corporate"). Mapping the intent word
# to its sector lets the right sector win. Only unambiguous words are mapped —
# ambiguous ones (e.g. "partner", "investment") are deliberately left out.
# Values are lowercase regex fragments matched against the DB sector column.
SECTOR_HINTS = {
    "lawyer": "legal", "lawyers": "legal", "attorney": "legal",
    "attorneys": "legal", "litigation": "legal", "litigator": "legal",
    "solicitor": "legal", "barrister": "legal", "counsel": "legal",
    "healthcare": "healthcare", "medical": "healthcare", "pharma": "healthcare",
    "biotech": "healthcare", "clinical": "healthcare", "medtech": "healthcare",
    "energy": "energy", "renewable": "energy", "renewables": "energy",
    "solar": "energy", "wind": "energy",
    "property": "real estate", "estate": "real estate", "realty": "real estate",
    "recruiter": "recruiting", "recruiting": "recruiting",
    "recruitment": "recruiting", "talent": "recruiting", "headhunter": "recruiting",
    "fintech": "tech", "software": "tech", "saas": "tech", "developer": "tech",
    "engineer": "tech", "engineering": "tech", "cto": "tech",
    "banker": "finance", "banking": "finance", "hedge": "finance",
}

# Seniority words → the actual contacts.seniority values they mean. The
# column never literally contains the word "senior" — real values are things
# like "MD", "Partner", "Director", "Principal", "VP", "Associate", "Analyst"
# — so a query like "anyone from JP Morgan in a senior position" needs this
# mapping or the seniority signal never fires no matter which fields are
# searched. Values are regex fragments matched against the seniority column.
SENIORITY_HINTS = {
    "senior": "MD|Partner|Director|Chairman|Principal|VP|Founder",
    "seniority": "MD|Partner|Director|Chairman|Principal|VP|Founder",
    "leadership": "MD|Partner|Director|Chairman|Founder",
    "executive": "MD|Partner|Director|Chairman|Founder",
    "exec": "MD|Partner|Director|Chairman|Founder",
    "junior": "Analyst|Associate",
    "entry-level": "Analyst",
    "entry": "Analyst",
}


class KeywordFilter:
    def __init__(self, db_pool: asyncpg.Pool):
        self.db_pool = db_pool

    # Fields that count toward relevance, with weights. Higher weight = stronger
    # signal that a match here means the contact really does what was asked.
    # looking_for / comment are intentionally excluded from scoring (low signal,
    # often incidental) but stay in the WHERE clause for recall. seniority is
    # its own column ("Junior"/"Senior"/"Partner"/"Director"...) — queries like
    # "anyone from JPMorgan in a senior position" need it searched directly,
    # since "senior" doesn't reliably appear inside title text. location is
    # searched here too as a fallback: the dedicated location_pattern/
    # location_expr mechanism below only recognises a curated list of major
    # cities, so a contact based in e.g. "Cape Town" or "Tel Aviv" (real
    # values in this dataset, not in that curated list) was previously
    # invisible to any location-based query at all — this closes that gap
    # for every city, not just the curated ones. how_alex_knows_them
    # (freeform relationship context, e.g. "University friend — Wits CS")
    # is included at low weight so "anyone I know from Wits" can surface a
    # contact even when their role/company text alone wouldn't match.
    _RELEVANCE_FIELDS = [
        ("title", 3),
        ("expertise_tags", 2),
        ("can_help_with", 2),
        ("sector", 2),
        ("specialty", 2),
        ("seniority", 2),
        ("location", 2),
        ("company", 1),
        ("full_name", 1),
        ("how_alex_knows_them", 1),
    ]

    # Fields searched to decide whether a row is a candidate at all (recall).
    _WHERE_FIELDS = [
        "full_name", "title", "company", "sector", "specialty", "seniority",
        "location", "how_alex_knows_them",
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

        # Sector hints from the query's role/topic words (see SECTOR_HINTS).
        hint_sectors = sorted({SECTOR_HINTS[t] for t in tokens if t in SECTOR_HINTS})
        hint_pattern = "|".join(hint_sectors) if hint_sectors else None

        # Seniority hints from words like "senior"/"junior" (see SENIORITY_HINTS)
        # — the seniority column never literally contains these words.
        seniority_hints = sorted({SENIORITY_HINTS[t] for t in tokens if t in SENIORITY_HINTS})
        seniority_pattern = "|".join(seniority_hints) if seniority_hints else None

        sql, params = self._build_sql(kw_pattern, location_pattern, hint_pattern, seniority_pattern)
        async with self.db_pool.acquire() as conn:
            results = await conn.fetch(sql, *params)
        return [dict(row) for row in results]

    @staticmethod
    def _field_expr(field: str) -> str:
        """SQL expression to compare a field against a keyword pattern.
        Company gets spaces stripped before comparison so casual spellings
        without spaces ("JPMorgan") still match the DB's spaced form
        ("JP Morgan") — kw_pattern terms are always single, space-free tokens,
        so this is a one-directional normalisation that's safe for every
        other field to skip."""
        if field == "company":
            return "REPLACE(LOWER(company), ' ', '')"
        return f"LOWER({field})"

    def _build_sql(self, kw_pattern, location_pattern, hint_pattern=None, seniority_pattern=None):
        """Assemble the candidate query from whichever signals are present:
        keyword terms, a location, a sector hint, a seniority hint, or a mix.
        relevance_score is always the primary sort so role/sector/seniority
        relevance wins over incidental VIP status."""
        select_cols = (
            "id, contact_id, full_name, phone, email, company, title, "
            "sector, specialty, location, seniority, expertise_tags, "
            "can_help_with, looking_for, relationship_strength, "
            "how_alex_knows_them, is_vip, comment"
        )
        params = []
        kw_idx = loc_idx = hint_idx = seniority_idx = None
        if kw_pattern is not None:
            params.append(kw_pattern)
            kw_idx = len(params)
        if location_pattern is not None:
            params.append(location_pattern)
            loc_idx = len(params)
        if hint_pattern is not None:
            params.append(hint_pattern)
            hint_idx = len(params)
        if seniority_pattern is not None:
            params.append(seniority_pattern)
            seniority_idx = len(params)

        # relevance_score: weighted sum of high-signal keyword-field matches,
        # plus a sector-hint boost so the sector the query implies (e.g.
        # "lawyer" -> Legal) outranks a wrong-sector contact that merely shares
        # a word ("corporate" in a healthcare "Corporate Dev" title), plus a
        # seniority-hint boost so "senior" actually favours MD/Partner/Director
        # contacts (the column never contains that literal word — see
        # SENIORITY_HINTS).
        relevance_terms = []
        if kw_idx is not None:
            relevance_terms += [
                f"(CASE WHEN {self._field_expr(field)} ~ ${kw_idx} THEN {weight} ELSE 0 END)"
                for field, weight in self._RELEVANCE_FIELDS
            ]
        if hint_idx is not None:
            relevance_terms.append(
                f"(CASE WHEN LOWER(sector) ~ ${hint_idx} THEN 4 ELSE 0 END)"
            )
        if seniority_idx is not None:
            relevance_terms.append(
                f"(CASE WHEN seniority ~* ${seniority_idx} THEN 3 ELSE 0 END)"
            )
        relevance_expr = " + ".join(relevance_terms) if relevance_terms else "0"

        location_expr = (
            f"CASE WHEN LOWER(location) ~ ${loc_idx} THEN 3 ELSE 0 END"
            if loc_idx is not None else "0"
        )

        # WHERE: a row qualifies if it matches any searched field on the keyword
        # pattern, is in the requested location, is in the hinted sector, or is
        # in the hinted seniority band.
        where_clauses = []
        if kw_idx is not None:
            where_clauses.append(
                "(" + " OR ".join(f"{self._field_expr(f)} ~ ${kw_idx}" for f in self._WHERE_FIELDS) + ")"
            )
        if loc_idx is not None:
            where_clauses.append(f"LOWER(location) ~ ${loc_idx}")
        if hint_idx is not None:
            where_clauses.append(f"LOWER(sector) ~ ${hint_idx}")
        if seniority_idx is not None:
            where_clauses.append(f"seniority ~* ${seniority_idx}")
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
