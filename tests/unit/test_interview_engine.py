"""
Unit Tests — backend/services/interview_engine.py
Tests: is_technical_role classification, model usage verification.
No real network calls — Mistral API is mocked.
"""
import os
import sys
import pytest
from unittest.mock import MagicMock, patch

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from backend.services.interview_engine import is_technical_role


# ── is_technical_role ────────────────────────────────────────────────────────

class TestIsTechnicalRole:
    def test_software_engineer_is_technical(self):
        assert is_technical_role("Software Engineer") is True

    def test_data_scientist_is_technical(self):
        assert is_technical_role("Data Scientist") is True

    def test_backend_developer_is_technical(self):
        assert is_technical_role("Backend Developer") is True

    def test_devops_is_technical(self):
        assert is_technical_role("DevOps Engineer") is True

    def test_frontend_is_technical(self):
        assert is_technical_role("Frontend Developer") is True

    def test_cybersecurity_is_technical(self):
        assert is_technical_role("Cybersecurity Analyst") is True

    def test_hr_manager_is_not_technical(self):
        assert is_technical_role("HR Manager") is False

    def test_marketing_executive_is_not_technical(self):
        assert is_technical_role("Marketing Executive") is False

    def test_accountant_is_not_technical(self):
        assert is_technical_role("Accountant") is False

    def test_empty_string_is_not_technical(self):
        assert is_technical_role("") is False

    def test_case_insensitive(self):
        assert is_technical_role("SOFTWARE ENGINEER") is True
        assert is_technical_role("software engineer") is True


# ── Model usage ──────────────────────────────────────────────────────────────

class TestModelUsage:
    """Verify interview_engine uses mistral-small-latest, not large or nemo."""

    def test_uses_mistral_small_latest(self):
        """interview_reply must call mistral-small-latest."""
        captured = {}

        def fake_complete(**kwargs):
            captured["model"] = kwargs.get("model")
            mock_resp = MagicMock()
            mock_resp.choices[0].message.content = (
                "Hello! Thanks for joining. Could you introduce yourself "
                "and share why you are interested in this role?"
            )
            return mock_resp

        mock_client = MagicMock()
        mock_client.chat.complete.side_effect = fake_complete

        with patch("backend.services.interview_engine.Mistral", return_value=mock_client):
            from backend.services.interview_engine import interview_reply
            interview_reply(
                history=[],
                job_title="Software Engineer",
                questions_limit=5,
                difficulty="Beginner",
                current_asked_count=0,
            )

        assert captured.get("model") == "mistral-small-latest", (
            f"Expected 'mistral-small-latest', got '{captured.get('model')}'"
        )

    def test_model_constant_not_overridden(self):
        """Confirm no accidental override — interview must not use large or nemo."""
        import inspect
        import backend.services.interview_engine as ie
        src = inspect.getsource(ie)
        assert "mistral-small-latest" in src
        assert "mistral-large-latest" not in src
        assert "open-mistral-nemo" not in src
