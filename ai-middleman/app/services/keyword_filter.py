"""
keyword_filter.py — Stage 1 of the two-stage matching pipeline.

Performs fast, local keyword-based filtering of the contact database,
reducing 50,000 contacts to 30-50 candidates before LLM evaluation.
Location-aware: queries containing city/country names prioritise
geographically matching contacts in the result ordering.

Exposed: KeywordFilter class with filter_candidates(query) method.
"""

import re
from typing import List, Dict
import asyncpg

class KeywordFilter:
    def __init__(self, db_pool: asyncpg.Pool):
        self.db_pool = db_pool

    async def filter_candidates(self, query: str) -> List[Dict]:
        # Extract all tokens
        tokens = [t.lower() for t in re.findall(r'\b\w{3,}\b', query)]
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

        # Check if query contains location keywords
        query_lower = query.lower()
        location_tokens = [loc for loc in location_keywords if loc in query_lower]
        has_location = len(location_tokens) > 0

        regex_pattern = "|".join(tokens)

        if has_location:
            # Location-aware query: prioritise location matches strongly
            location_pattern = "|".join(location_tokens)
            sql = """
                SELECT
                    id, contact_id, full_name, phone, email, company, title,
                    sector, specialty, location, seniority, expertise_tags,
                    can_help_with, looking_for, relationship_strength,
                    how_alex_knows_them, is_vip, comment,
                    CASE
                        WHEN LOWER(location) ~ $2 THEN 3
                        ELSE 0
                    END as location_score
                FROM contacts
                WHERE (
                    LOWER(full_name) ~ $1
                    OR LOWER(title) ~ $1
                    OR LOWER(company) ~ $1
                    OR LOWER(sector) ~ $1
                    OR LOWER(specialty) ~ $1
                    OR LOWER(expertise_tags) ~ $1
                    OR LOWER(can_help_with) ~ $1
                    OR LOWER(looking_for) ~ $1
                    OR LOWER(comment) ~ $1
                    OR LOWER(location) ~ $2
                )
                ORDER BY
                    location_score DESC,
                    is_vip DESC,
                    relationship_strength DESC
                LIMIT 25
            """
            async with self.db_pool.acquire() as conn:
                results = await conn.fetch(sql, regex_pattern, location_pattern)
        else:
            # No location in query: use standard ordering
            sql = """
                SELECT
                    id, contact_id, full_name, phone, email, company, title,
                    sector, specialty, location, seniority, expertise_tags,
                    can_help_with, looking_for, relationship_strength,
                    how_alex_knows_them, is_vip, comment
                FROM contacts
                WHERE (
                    LOWER(full_name) ~ $1
                    OR LOWER(title) ~ $1
                    OR LOWER(company) ~ $1
                    OR LOWER(sector) ~ $1
                    OR LOWER(specialty) ~ $1
                    OR LOWER(expertise_tags) ~ $1
                    OR LOWER(can_help_with) ~ $1
                    OR LOWER(looking_for) ~ $1
                    OR LOWER(comment) ~ $1
                )
                ORDER BY
                    is_vip DESC,
                    relationship_strength DESC
                LIMIT 25
            """
            async with self.db_pool.acquire() as conn:
                results = await conn.fetch(sql, regex_pattern)

        return [dict(row) for row in results]
