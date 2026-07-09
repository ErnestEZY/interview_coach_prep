"""
Integration Tests — AI Writing Assist API
Tests: /api/assist/summary, /api/assist/bullets, /api/assist/manual-field
Mistral API is mocked — only route auth, validation, and response shape tested.
"""
import os
import sys
import pytest
import pytest_asyncio
from unittest.mock import patch
from httpx import AsyncClient, ASGITransport

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tests.integration.helpers import make_jwt, patch_all_db

UID = "507f191e810c19729de860ea"
BASE_USER = {
    "_id": UID, "email": "u@t.com", "role": "user",
    "is_verified": True, "has_analyzed": True,
    "daily_resume_count": 0, "daily_interview_count": 0,
    "daily_question_count": 0, "daily_reset_at": None,
}
AUTH = {"Authorization": f"Bearer {make_jwt(UID)}"}


@pytest_asyncio.fixture
async def ac():
    from backend.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


# ── /api/assist/summary ──────────────────────────────────────────────────────

class TestAssistSummary:
    @pytest.mark.asyncio
    async def test_requires_auth(self, ac):
        r = await ac.post("/api/assist/summary", json={"text": "hello"})
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_empty_text_returns_400(self, ac):
        patch_all_db(users_val=BASE_USER)
        r = await ac.post("/api/assist/summary",
                          json={"text": "   "}, headers=AUTH)
        assert r.status_code == 400

    @pytest.mark.asyncio
    async def test_valid_input_returns_result(self, ac):
        patch_all_db(users_val=BASE_USER)
        with patch("backend.services.assist._call_nemo",
                   return_value="Improved professional summary text."):
            r = await ac.post("/api/assist/summary",
                              json={"text": "I am a developer.", "job_title": "Engineer"},
                              headers=AUTH)
        assert r.status_code == 200
        assert "result" in r.json()
        assert len(r.json()["result"]) > 0

    @pytest.mark.asyncio
    async def test_result_has_no_markdown(self, ac):
        patch_all_db(users_val=BASE_USER)
        with patch("backend.services.assist._call_nemo",
                   return_value="**Bold** and *italic* removed."):
            r = await ac.post("/api/assist/summary",
                              json={"text": "some summary"}, headers=AUTH)
        result = r.json().get("result", "")
        assert "**" not in result
        assert r.status_code == 200


# ── /api/assist/bullets ──────────────────────────────────────────────────────

class TestAssistBullets:
    @pytest.mark.asyncio
    async def test_requires_auth(self, ac):
        r = await ac.post("/api/assist/bullets", json={"bullets": ["test"]})
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_empty_bullets_returns_400(self, ac):
        patch_all_db(users_val=BASE_USER)
        r = await ac.post("/api/assist/bullets",
                          json={"bullets": ["  ", ""]}, headers=AUTH)
        assert r.status_code == 400

    @pytest.mark.asyncio
    async def test_valid_bullets_returns_list(self, ac):
        patch_all_db(users_val=BASE_USER)
        with patch("backend.services.assist._call_nemo",
                   return_value="1. Developed a REST API reducing latency by 20%.\n"
                                "2. Collaborated with team to ship new features."):
            r = await ac.post("/api/assist/bullets",
                              json={"bullets": ["built api", "worked with team"],
                                    "section": "experience"},
                              headers=AUTH)
        assert r.status_code == 200
        assert isinstance(r.json()["result"], list)
        assert len(r.json()["result"]) >= 1

    @pytest.mark.asyncio
    async def test_result_count_matches_input(self, ac):
        patch_all_db(users_val=BASE_USER)
        with patch("backend.services.assist._call_nemo",
                   return_value="1. Engineered feature X.\n2. Reduced bug count by 30%."):
            r = await ac.post("/api/assist/bullets",
                              json={"bullets": ["built x", "fixed bugs"],
                                    "section": "experience"},
                              headers=AUTH)
        assert r.status_code == 200
        assert len(r.json()["result"]) == 2


# ── /api/assist/manual-field ─────────────────────────────────────────────────

class TestAssistManualField:
    @pytest.mark.asyncio
    async def test_requires_auth(self, ac):
        r = await ac.post("/api/assist/manual-field",
                          json={"field": "summary", "text": "test"})
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_field_name_returns_422(self, ac):
        patch_all_db(users_val=BASE_USER)
        r = await ac.post("/api/assist/manual-field",
                          json={"field": "invalid_field", "text": "hello"},
                          headers=AUTH)
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_empty_text_returns_400(self, ac):
        patch_all_db(users_val=BASE_USER)
        r = await ac.post("/api/assist/manual-field",
                          json={"field": "summary", "text": "  "},
                          headers=AUTH)
        assert r.status_code == 400

    @pytest.mark.asyncio
    async def test_summary_field_returns_result(self, ac):
        patch_all_db(users_val=BASE_USER)
        with patch("backend.services.assist._call_nemo",
                   return_value="Results-driven developer with 3 years of experience."):
            r = await ac.post("/api/assist/manual-field",
                              json={"field": "summary", "text": "developer 3 years",
                                    "char_limit": 500},
                              headers=AUTH)
        assert r.status_code == 200
        assert "result" in r.json()

    @pytest.mark.asyncio
    async def test_achievement_field_returns_result(self, ac):
        patch_all_db(users_val=BASE_USER)
        with patch("backend.services.assist._call_nemo",
                   return_value="Developed an inventory system reducing tracking time by 40%."):
            r = await ac.post("/api/assist/manual-field",
                              json={"field": "achievement",
                                    "text": "built inventory system",
                                    "char_limit": 500},
                              headers=AUTH)
        assert r.status_code == 200
        assert len(r.json()["result"]) > 0

    @pytest.mark.asyncio
    async def test_skills_field_returns_result(self, ac):
        patch_all_db(users_val=BASE_USER)
        with patch("backend.services.assist._call_nemo",
                   return_value="Python, FastAPI, MongoDB, Docker, REST APIs"):
            r = await ac.post("/api/assist/manual-field",
                              json={"field": "skills", "text": "python fastapi",
                                    "char_limit": 300},
                              headers=AUTH)
        assert r.status_code == 200
        assert "Python" in r.json()["result"] or len(r.json()["result"]) > 0
