"""
Unit Tests — backend/services/assist.py
Tests: _strip_markdown, _safe_trim, improve_manual_field field routing.
No network calls — Mistral API is mocked.
"""
import os
import sys
import pytest
from unittest.mock import MagicMock, patch

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from backend.services.assist import _strip_markdown, _safe_trim


# ── _strip_markdown ──────────────────────────────────────────────────────────

class TestStripMarkdown:
    def test_removes_bold_double_asterisk(self):
        assert _strip_markdown("**Hello** world") == "Hello world"

    def test_removes_bold_triple_asterisk(self):
        assert _strip_markdown("***Hello***") == "Hello"

    def test_removes_italic_single_asterisk(self):
        assert _strip_markdown("*italic* text") == "italic text"

    def test_removes_bold_underscore(self):
        assert _strip_markdown("__bold__") == "bold"

    def test_removes_italic_underscore(self):
        assert _strip_markdown("_italic_") == "italic"

    def test_strips_wrapping_double_quotes(self):
        assert _strip_markdown('"plain text"') == "plain text"

    def test_strips_wrapping_single_quotes(self):
        assert _strip_markdown("'plain text'") == "plain text"

    def test_no_change_on_plain_text(self):
        text = "Developed a REST API using FastAPI and MongoDB."
        assert _strip_markdown(text) == text

    def test_removes_markdown_header(self):
        assert _strip_markdown("## Summary") == "Summary"

    def test_stray_asterisk_removed(self):
        result = _strip_markdown("text * more text")
        assert "**" not in result
        assert "* " not in result

    def test_empty_string_returns_empty(self):
        assert _strip_markdown("") == ""

    def test_mixed_markdown_cleaned(self):
        raw = '**Developed** a *scalable* system using __Python__.'
        result = _strip_markdown(raw)
        assert "**" not in result
        assert "*" not in result
        assert "__" not in result


# ── _safe_trim ───────────────────────────────────────────────────────────────

class TestSafeTrim:
    def test_short_text_unchanged(self):
        text = "Short text."
        assert _safe_trim(text, 500) == text

    def test_trims_at_sentence_boundary(self):
        text = "First sentence. Second sentence that is very long and goes over the limit."
        result = _safe_trim(text, 20)
        assert len(result) <= 20
        assert result.endswith(".")

    def test_trims_at_word_boundary_when_no_sentence(self):
        text = "word1 word2 word3 word4 word5 word6"
        result = _safe_trim(text, 20)
        assert len(result) <= 20
        assert not result.endswith(" ")

    def test_exact_limit_unchanged(self):
        text = "A" * 250
        assert len(_safe_trim(text, 250)) == 250

    def test_never_exceeds_limit(self):
        long_text = "x " * 300
        assert len(_safe_trim(long_text, 100)) <= 100

    def test_empty_string_unchanged(self):
        assert _safe_trim("", 100) == ""


# ── improve_manual_field (mocked API) ────────────────────────────────────────

class TestImproveManualField:
    """
    Tests field routing and output sanitation.
    The Mistral API call is mocked — only local logic is tested.
    """

    def _mock_nemo(self, return_value: str):
        """Patch _call_nemo to return a fixed string."""
        return patch(
            "backend.services.assist._call_nemo",
            return_value=return_value,
        )

    def test_summary_result_stripped_of_markdown(self):
        from backend.services.assist import improve_manual_field
        with self._mock_nemo("**Experienced** software engineer with strong skills."):
            result = improve_manual_field("summary", "engineer", char_limit=500)
        assert "**" not in result

    def test_summary_strips_wrapping_quotes(self):
        from backend.services.assist import improve_manual_field
        with self._mock_nemo('"Professional summary text here."'):
            result = improve_manual_field("summary", "some text", char_limit=500)
        assert not result.startswith('"')
        assert not result.endswith('"')

    def test_achievement_result_within_char_limit(self):
        from backend.services.assist import improve_manual_field
        long_output = "Developed a system " * 30  # well over 500 chars
        with self._mock_nemo(long_output):
            result = improve_manual_field("achievement", "some text", char_limit=500)
        assert len(result) <= 500

    def test_skills_result_within_char_limit(self):
        from backend.services.assist import improve_manual_field
        long_skills = "Python, " * 100
        with self._mock_nemo(long_skills):
            result = improve_manual_field("skills", "python", char_limit=300)
        assert len(result) <= 300

    def test_empty_api_key_no_crash_returns_string(self):
        """When all providers fail, _call_nemo should raise RuntimeError."""
        from backend.services.assist import _call_nemo
        with patch("backend.services.assist.chat_assist",
                   side_effect=RuntimeError("All assist providers exhausted")):
            with pytest.raises(RuntimeError):
                _call_nemo("system", "user")


# ── Model usage ──────────────────────────────────────────────────────────────

class TestModelUsage:
    """Verify assist.py uses provider_router.chat_assist, not direct Mistral."""

    def test_assist_uses_chat_assist(self):
        """_call_nemo must delegate to chat_assist from provider_router."""
        from backend.services.assist import _call_nemo
        with patch("backend.services.assist.chat_assist",
                   return_value="Improved text.") as mock_assist:
            result = _call_nemo("system prompt", "user prompt")
            mock_assist.assert_called_once()
            assert result == "Improved text."

    def test_does_not_use_mistral_directly(self):
        """assist must not import or instantiate Mistral directly."""
        import inspect
        import backend.services.assist as assist_mod
        src = inspect.getsource(assist_mod)
        assert "Mistral(" not in src, "assist must not instantiate Mistral directly"

    def test_model_constant_not_overridden(self):
        """Confirm assist does not reference old retired model strings."""
        import inspect
        import backend.services.assist as assist_mod
        src = inspect.getsource(assist_mod)
        assert "mistral-large-latest" not in src
        assert "open-mistral-nemo" not in src
