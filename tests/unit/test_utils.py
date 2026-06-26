"""
Unit Tests — backend/services/utils.py
Tests: is_gibberish (strict and light modes), get_malaysia_time
No database or network required.
"""
import os
import sys
import pytest
from datetime import timedelta

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from backend.services.utils import is_gibberish, get_malaysia_time


class TestIsGibberish:
    # ── Strict mode (job titles, profile fields) ─────────────────────────────
    def test_real_job_title_not_gibberish(self):
        assert is_gibberish("Software Engineer") is False

    def test_short_abbrev_allowed(self):
        for term in ["hr", "ai", "qa", "it", "ceo", "dev"]:
            assert is_gibberish(term) is False, f"{term} should not be gibberish"

    def test_keyboard_mash_is_gibberish(self):
        assert is_gibberish("asdfghjkl") is True

    def test_repeated_chars_is_gibberish(self):
        assert is_gibberish("aaaaaaaaa") is True

    def test_all_numbers_is_gibberish(self):
        assert is_gibberish("12345678") is True

    def test_empty_string_is_gibberish(self):
        assert is_gibberish("") is True

    def test_single_char_is_gibberish(self):
        assert is_gibberish("x") is True

    def test_no_vowels_long_is_gibberish(self):
        assert is_gibberish("bcdfghjklm") is True

    def test_qwerty_pattern_is_gibberish(self):
        assert is_gibberish("qwerty1234") is True

    def test_camelcase_tech_not_gibberish(self):
        for term in ["DevOps", "JavaScript", "MongoDB", "TypeScript"]:
            assert is_gibberish(term) is False, f"{term} should not be gibberish"

    def test_valid_summary_not_gibberish(self):
        text = "Experienced software developer with 3 years of backend work"
        assert is_gibberish(text) is False

    def test_special_chars_heavy_is_gibberish(self):
        assert is_gibberish("!@#$%^&*()") is True

    def test_repeating_pattern_is_gibberish(self):
        assert is_gibberish("abababab") is True

    # ── Light mode (interview answers) ───────────────────────────────────────
    def test_short_answer_not_gibberish_light(self):
        assert is_gibberish("I work with Python", strict=False) is False

    def test_single_word_answer_light(self):
        # Single short word is borderline — light mode is lenient for 2+ words
        assert is_gibberish("Yes absolutely", strict=False) is False

    def test_obvious_mash_still_gibberish_light(self):
        assert is_gibberish("asdfasdf", strict=False) is True

    def test_all_symbols_gibberish_light(self):
        assert is_gibberish("!!!!!!!!!!", strict=False) is True


class TestGetMalaysiaTime:
    def test_returns_datetime(self):
        from datetime import datetime
        result = get_malaysia_time()
        assert isinstance(result, datetime)

    def test_timezone_is_utc_plus_8(self):
        result = get_malaysia_time()
        assert result.utcoffset() == timedelta(hours=8)
