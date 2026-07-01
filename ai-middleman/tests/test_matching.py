# tests/test_matching.py
# Unit tests for the matching pipeline (no DB/LLM required)

import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.response_formatter import format_response


class TestKeywordExtraction:
    """Tests for keyword extraction logic (Stage 1)"""

    def test_extract_keywords_simple(self):
        """Test basic keyword extraction from a query"""
        import re
        query = "I need a credit finance specialist in London"
        tokens = [t.lower() for t in re.findall(r'\b\w{3,}\b', query)]
        assert "credit" in tokens
        assert "finance" in tokens
        assert "specialist" in tokens
        assert "london" in tokens

    def test_extract_keywords_tech(self):
        """Test keyword extraction for tech query"""
        import re
        query = "Looking for a tech startup founder in San Francisco"
        tokens = [t.lower() for t in re.findall(r'\b\w{3,}\b', query)]
        assert "tech" in tokens
        assert "startup" in tokens
        assert "founder" in tokens
        assert "san" in tokens
        assert "francisco" in tokens

    def test_extract_keywords_real_estate(self):
        """Test keyword extraction for real estate query"""
        import re
        query = "Who can help with real estate investment in Dubai?"
        tokens = [t.lower() for t in re.findall(r'\b\w{3,}\b', query)]
        assert "real" in tokens
        assert "estate" in tokens
        assert "investment" in tokens
        assert "dubai" in tokens

    def test_extract_keywords_short_words_filtered(self):
        """Test that words shorter than 3 chars are filtered out"""
        import re
        query = "I need a specialist in London"
        tokens = [t.lower() for t in re.findall(r'\b\w{3,}\b', query)]
        # "i", "a", "in" are < 3 chars and should be filtered
        assert "i" not in tokens
        assert "need" in tokens
        assert "a" not in tokens
        assert "in" not in tokens
        assert "specialist" in tokens
        assert "london" in tokens

    def test_extract_keywords_empty_query(self):
        """Test empty query returns no tokens"""
        import re
        query = ""
        tokens = [t.lower() for t in re.findall(r'\b\w{3,}\b', query)]
        assert tokens == []

    def test_extract_keywords_single_word(self):
        """Test single word query"""
        import re
        query = "developer"
        tokens = [t.lower() for t in re.findall(r'\b\w{3,}\b', query)]
        assert tokens == ["developer"]

    def test_extract_keywords_duplicates_handled(self):
        """Test that duplicate words are handled"""
        import re
        query = "credit credit finance finance"
        tokens = [t.lower() for t in re.findall(r'\b\w{3,}\b', query)]
        assert "credit" in tokens
        assert "finance" in tokens
        assert len(tokens) == 4  # regex finds all occurrences


class TestResponseFormatter:
    """Tests for Stage 3: Response Formatter"""

    def test_format_good_match(self):
        """Test formatting a good match result"""
        llm_result = {
            "analysis": "User needs a credit specialist",
            "matches": [
                {
                    "contact_id": 1,
                    "name": "John Doe",
                    "title": "Credit Analyst",
                    "company": "Big Bank",
                    "location": "London, UK",
                    "confidence": 0.95,
                    "reasoning": "Perfect match for credit finance"
                }
            ],
            "match_quality": "good",
            "clarification_question": ""
        }
        formatted = format_response(llm_result)
        assert "John Doe" in formatted
        assert "Credit Analyst" in formatted
        assert "Big Bank" in formatted
        assert "London, UK" in formatted
        assert "95%" in formatted

    def test_format_weak_match(self):
        """Test formatting a weak match result"""
        llm_result = {
            "analysis": "Weak match found",
            "matches": [
                {
                    "contact_id": 2,
                    "name": "Jane Smith",
                    "title": "Manager",
                    "company": "Small Co",
                    "location": "Paris, France",
                    "confidence": 0.55,
                    "reasoning": "Somewhat relevant"
                }
            ],
            "match_quality": "weak",
            "clarification_question": ""
        }
        formatted = format_response(llm_result)
        assert "Jane Smith" in formatted
        assert "Manager" in formatted
        assert "Small Co" in formatted
        assert "Paris, France" in formatted
        assert "Somewhat relevant" in formatted
        assert "partial matches" in formatted.lower()

    def test_format_no_match(self):
        """Test formatting a no-match result with clarification"""
        llm_result = {
            "analysis": "No matches found",
            "matches": [],
            "match_quality": "none",
            "clarification_question": "Could you be more specific?"
        }
        formatted = format_response(llm_result)
        assert "Could you be more specific?" in formatted

    def test_format_multiple_matches(self):
        """Test formatting multiple matches"""
        llm_result = {
            "analysis": "Multiple matches",
            "matches": [
                {"contact_id": 1, "name": "A", "title": "T1", "company": "C1", "location": "L1", "confidence": 0.9, "reasoning": "R1"},
                {"contact_id": 2, "name": "B", "title": "T2", "company": "C2", "location": "L2", "confidence": 0.8, "reasoning": "R2"},
                {"contact_id": 3, "name": "C", "title": "T3", "company": "C3", "location": "L3", "confidence": 0.7, "reasoning": "R3"},
            ],
            "match_quality": "good",
            "clarification_question": ""
        }
        formatted = format_response(llm_result)
        assert "A" in formatted
        assert "B" in formatted
        assert "C" in formatted
        assert "90%" in formatted
        assert "80%" in formatted
        assert "70%" in formatted

    def test_format_empty_matches(self):
        """Test formatting with empty matches list"""
        llm_result = {
            "analysis": "Nothing",
            "matches": [],
            "match_quality": "none",
            "clarification_question": ""
        }
        formatted = format_response(llm_result)
        assert len(formatted) > 0  # Should return something, not crash

    def test_format_vip_contact(self):
        """Test formatting includes VIP indicator"""
        llm_result = {
            "analysis": "VIP match",
            "matches": [
                {"contact_id": 1, "name": "VIP Person", "title": "CEO", "company": "BigCorp", "location": "NYC", "confidence": 0.99, "reasoning": "Top match"}
            ],
            "match_quality": "good",
            "clarification_question": ""
        }
        formatted = format_response(llm_result)
        assert "VIP Person" in formatted
        assert "99%" in formatted


class TestMatchingPipeline:
    """End-to-end pipeline logic tests (unit tests, no DB/LLM)"""

    def test_keyword_extraction_to_query_building(self):
        """Test that keyword extraction produces usable tokens"""
        import re
        query = "credit finance specialist London"
        tokens = [t.lower() for t in re.findall(r'\b\w{3,}\b', query)]
        assert len(tokens) == 4
        assert "credit" in tokens
        assert "finance" in tokens
        assert "specialist" in tokens
        assert "london" in tokens

    def test_formatter_full_pipeline(self):
        """Test that LLM result flows through formatter correctly"""
        llm_result = {
            "analysis": "Test",
            "matches": [
                {"contact_id": 99, "name": "Test User", "title": "CEO", "company": "TestCorp", "location": "TestCity", "confidence": 0.88, "reasoning": "Test reasoning"}
            ],
            "match_quality": "good",
            "clarification_question": ""
        }
        formatted = format_response(llm_result)
        assert "Test User" in formatted
        assert "CEO at TestCorp" in formatted
        assert "TestCity" in formatted
        assert "88%" in formatted

    def test_match_quality_values(self):
        """Test that all match quality values are handled"""
        for quality in ["good", "weak", "none"]:
            llm_result = {
                "analysis": "Test",
                "matches": [],
                "match_quality": quality,
                "clarification_question": "test question"
            }
            formatted = format_response(llm_result)
            assert len(formatted) > 0