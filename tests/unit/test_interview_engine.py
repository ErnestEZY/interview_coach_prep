"""
Unit Tests — backend/services/interview_engine.py
Tests: is_technical_role classification, provider_router usage verification.
No real network calls — provider_router.chat_main is mocked.
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


# ── Provider router usage ────────────────────────────────────────────────────

class TestModelUsage:
    """Verify interview_engine uses provider_router.chat_main, not direct Mistral."""

    def test_uses_provider_router(self):
        """interview_engine must delegate to _interview_call which uses chat_main."""
        import inspect
        import backend.services.interview_engine as ie
        src = inspect.getsource(ie)
        # Verify it imports and uses chat_main from provider_router
        assert "chat_main" in src, "interview_engine must use chat_main from provider_router"
        assert "Mistral(" not in src, "interview_engine must not instantiate Mistral directly"

    def test_does_not_use_mistral_directly(self):
        """interview_engine must not import or call Mistral directly."""
        import inspect
        import backend.services.interview_engine as ie
        src = inspect.getsource(ie)
        assert "Mistral(" not in src, "interview_engine must not instantiate Mistral directly"
        assert "mistral-small-latest" not in src, "interview_engine must not reference Mistral model IDs"

    def test_does_not_use_nemo(self):
        import inspect
        import backend.services.interview_engine as ie
        src = inspect.getsource(ie)
        assert "open-mistral-nemo" not in src

    def test_does_not_use_mistral_large(self):
        import inspect
        import backend.services.interview_engine as ie
        src = inspect.getsource(ie)
        assert "mistral-large-latest" not in src
