"""Integration Tests — Interview API"""
import os, sys, pytest, pytest_asyncio
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport
from datetime import datetime, timezone, timedelta

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path: sys.path.insert(0, ROOT)

from tests.integration.helpers import make_jwt, patch_all_db

UID = "507f191e810c19729de860ea"
SID = "session-test-001"

BASE_USER = {
    "_id": UID, "email": "u@t.com", "role": "user", "is_verified": True,
    "has_analyzed": True, "target_job_title": "Software Engineer",
    "daily_resume_count": 0, "daily_interview_count": 0,
    "daily_question_count": 0, "daily_reset_at": None,
}
SESSION = {
    "_id": SID, "session_id": SID, "user_id": UID,
    "job_title": "Software Engineer", "resume_feedback": {},
    "questions_limit": 10, "difficulty": "Beginner",
    "asked_count": 1, "invalid_attempts": 0,
    "transcript": [{"role": "assistant", "text": "Tell me about yourself.",
                    "at": datetime.now(timezone.utc)}],
    "created_at": datetime.now(timezone.utc), "ended_at": None,
}

@pytest_asyncio.fixture
async def ac():
    from backend.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


class TestInterviewLimits:
    @pytest.mark.asyncio
    async def test_returns_remaining(self, ac):
        patch_all_db(users_val=BASE_USER)
        r = await ac.get("/api/interview/limits",
                         headers={"Authorization": f"Bearer {make_jwt(UID)}"})
        assert r.status_code == 200
        assert "remaining" in r.json()

    @pytest.mark.asyncio
    async def test_unauthenticated_returns_401(self, ac):
        assert (await ac.get("/api/interview/limits")).status_code == 401


class TestInterviewStart:
    @pytest.mark.asyncio
    async def test_start_returns_session_id(self, ac):
        patch_all_db(users_val=BASE_USER,
                     resumes_val={"feedback": {}, "job_title": "Software Engineer"})
        with patch("backend.controllers.interview_routes.interview_reply",
                   return_value="Tell me about yourself."):
            r = await ac.post("/api/interview/start",
                data={"job_title": "Software Engineer", "difficulty": "Beginner",
                      "questions_limit": "10"},
                headers={"Authorization": f"Bearer {make_jwt(UID)}"})
        assert r.status_code == 200
        assert "session_id" in r.json()

    @pytest.mark.asyncio
    async def test_no_analysis_returns_400(self, ac):
        patch_all_db(users_val={**BASE_USER, "has_analyzed": False},
                     resumes_val=None)
        with patch("backend.controllers.interview_routes.interview_reply",
                   return_value="Hi"):
            r = await ac.post("/api/interview/start",
                data={"job_title": "Engineer", "difficulty": "Beginner",
                      "questions_limit": "10"},
                headers={"Authorization": f"Bearer {make_jwt(UID)}"})
        assert r.status_code == 400

    @pytest.mark.asyncio
    async def test_unauthenticated_returns_401(self, ac):
        r = await ac.post("/api/interview/start",
                          data={"job_title": "Dev", "difficulty": "Beginner"})
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_session_limit_reached_returns_429(self, ac):
        patch_all_db(users_val={**BASE_USER, "daily_interview_count": 3,
                                "daily_reset_at": datetime.now(timezone.utc)},
                     resumes_val={"feedback": {}, "job_title": "Dev"})
        with patch("backend.controllers.interview_routes.interview_reply",
                   return_value="Hi"):
            r = await ac.post("/api/interview/start",
                data={"job_title": "Dev", "difficulty": "Beginner",
                      "questions_limit": "10"},
                headers={"Authorization": f"Bearer {make_jwt(UID)}"})
        assert r.status_code == 429


class TestInterviewReply:
    @pytest.mark.asyncio
    async def test_valid_reply_returns_next_question(self, ac):
        patch_all_db(users_val=BASE_USER, interviews_val=SESSION)
        with patch("backend.controllers.interview_routes.interview_reply",
                   return_value="What is your greatest strength?"), \
             patch("backend.controllers.interview_routes.rag_engine.validate_input",
                   new_callable=AsyncMock,
                   return_value={"safe": True, "category": "relevant"}):
            r = await ac.post(f"/api/interview/{SID}/reply",
                data={"user_text": "I have strong Python skills."},
                headers={"Authorization": f"Bearer {make_jwt(UID)}"})
        assert r.status_code == 200
        assert "message" in r.json()

    @pytest.mark.asyncio
    async def test_ended_session_returns_ended_flag(self, ac):
        ended = {**SESSION, "ended_at": datetime.now(timezone.utc)}
        patch_all_db(users_val=BASE_USER, interviews_val=ended)
        with patch("backend.controllers.interview_routes.rag_engine.validate_input",
                   new_callable=AsyncMock, return_value={"safe": True}):
            r = await ac.post(f"/api/interview/{SID}/reply",
                data={"user_text": "Answer"},
                headers={"Authorization": f"Bearer {make_jwt(UID)}"})
        assert r.status_code == 200
        assert r.json().get("ended") is True

    @pytest.mark.asyncio
    async def test_session_not_found_returns_404(self, ac):
        patch_all_db(users_val=BASE_USER, interviews_val=None)
        with patch("backend.controllers.interview_routes.rag_engine.validate_input",
                   new_callable=AsyncMock, return_value={"safe": True}):
            r = await ac.post("/api/interview/nonexistent/reply",
                data={"user_text": "Answer"},
                headers={"Authorization": f"Bearer {make_jwt(UID)}"})
        assert r.status_code == 404


class TestInterviewEnd:
    @pytest.mark.asyncio
    async def test_end_active_session(self, ac):
        patch_all_db(users_val=BASE_USER, interviews_val=SESSION)
        with patch("backend.controllers.interview_routes.interview_reply",
                   return_value="Goodbye. [FINISH]"):
            r = await ac.post(f"/api/interview/{SID}/end",
                              headers={"Authorization": f"Bearer {make_jwt(UID)}"})
        assert r.status_code == 200
        assert r.json().get("ended") is True

    @pytest.mark.asyncio
    async def test_already_ended_returns_already_ended(self, ac):
        ended = {**SESSION, "ended_at": datetime.now(timezone.utc)}
        patch_all_db(users_val=BASE_USER, interviews_val=ended)
        r = await ac.post(f"/api/interview/{SID}/end",
                          headers={"Authorization": f"Bearer {make_jwt(UID)}"})
        assert r.status_code == 200
        assert r.json().get("already_ended") is True


class TestInterviewHistory:
    @pytest.mark.asyncio
    async def test_returns_list(self, ac):
        patch_all_db(users_val=BASE_USER,
                     interviews_items=[{**SESSION, "readiness_score": 74,
                                        "readiness_feedback": "Good",
                                        "readiness_breakdown": {}}])
        r = await ac.get("/api/interview/history",
                         headers={"Authorization": f"Bearer {make_jwt(UID)}"})
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    @pytest.mark.asyncio
    async def test_unauthenticated_returns_401(self, ac):
        assert (await ac.get("/api/interview/history")).status_code == 401


class TestInterviewDelete:
    @pytest.mark.asyncio
    async def test_delete_existing_session(self, ac):
        patch_all_db(users_val=BASE_USER, deleted_count=1)
        r = await ac.delete(f"/api/interview/{SID}",
                            headers={"Authorization": f"Bearer {make_jwt(UID)}"})
        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_delete_nonexistent_returns_404(self, ac):
        patch_all_db(users_val=BASE_USER, deleted_count=0)
        r = await ac.delete("/api/interview/nonexistent-xyz",
                            headers={"Authorization": f"Bearer {make_jwt(UID)}"})
        assert r.status_code == 404
