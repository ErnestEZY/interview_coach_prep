"""Integration Tests — Admin API"""
import os, sys, pytest, pytest_asyncio
from unittest.mock import AsyncMock
from httpx import AsyncClient, ASGITransport
from datetime import datetime, timezone, timedelta

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path: sys.path.insert(0, ROOT)

from tests.integration.helpers import make_jwt, patch_all_db, make_col

ADMIN_ID = "507f191e810c19729de860ea"
USER_ID  = "507f191e810c19729de860eb"
RES_ID   = "507f191e810c19729de860ec"

ADMIN = {"_id": ADMIN_ID, "email": "admin@icp-solution.com",
         "role": "admin", "is_verified": True}
USER  = {"_id": USER_ID,  "email": "u@t.com",
         "role": "user",  "is_verified": True}
RESUME = {
    "_id": RES_ID, "user_id": USER_ID, "filename": "cv.pdf",
    "status": "pending", "tags": ["Python"],
    "feedback": {"Score": 75, "Advantages": []},
    "text": "Software Engineer", "mime_type": "application/pdf",
    "file_id": None, "notes": "",
    "created_at": datetime.now(timezone.utc),
}

@pytest_asyncio.fixture
async def ac():
    from backend.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


class TestAdminRoleEnforcement:
    @pytest.mark.asyncio
    async def test_regular_user_forbidden(self, ac):
        patch_all_db(users_val=USER)
        r = await ac.get("/api/admin/resumes",
                         headers={"Authorization": f"Bearer {make_jwt(USER_ID, 'user')}"})
        assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_unauthenticated_returns_401(self, ac):
        assert (await ac.get("/api/admin/resumes")).status_code == 401

    @pytest.mark.asyncio
    async def test_user_cannot_delete_resume(self, ac):
        patch_all_db(users_val=USER)
        r = await ac.delete(f"/api/admin/resumes/{RES_ID}",
                            headers={"Authorization": f"Bearer {make_jwt(USER_ID, 'user')}"})
        assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_user_cannot_patch_resume(self, ac):
        patch_all_db(users_val=USER)
        r = await ac.patch(f"/api/admin/resumes/{RES_ID}",
                           data={"status": "reviewed"},
                           headers={"Authorization": f"Bearer {make_jwt(USER_ID, 'user')}"})
        assert r.status_code == 403


class TestAdminListResumes:
    @pytest.mark.asyncio
    async def test_returns_list(self, ac):
        patch_all_db(users_val=ADMIN, resumes_items=[RESUME])
        r = await ac.get("/api/admin/resumes",
                         headers={"Authorization": f"Bearer {make_jwt(ADMIN_ID, 'admin')}"})
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    @pytest.mark.asyncio
    async def test_empty_when_no_records(self, ac):
        patch_all_db(users_val=ADMIN, resumes_items=[])
        r = await ac.get("/api/admin/resumes",
                         headers={"Authorization": f"Bearer {make_jwt(ADMIN_ID, 'admin')}"})
        assert r.status_code == 200
        assert r.json() == []

    @pytest.mark.asyncio
    async def test_filter_by_status_accepted(self, ac):
        patch_all_db(users_val=ADMIN, resumes_items=[])
        r = await ac.get("/api/admin/resumes?status=reviewed",
                         headers={"Authorization": f"Bearer {make_jwt(ADMIN_ID, 'admin')}"})
        assert r.status_code == 200


class TestAdminGetResume:
    @pytest.mark.asyncio
    async def test_existing_resume_returns_detail(self, ac):
        patch_all_db(users_val=ADMIN, resumes_val=RESUME)
        r = await ac.get(f"/api/admin/resumes/{RES_ID}",
                         headers={"Authorization": f"Bearer {make_jwt(ADMIN_ID, 'admin')}"})
        assert r.status_code == 200
        assert "filename" in r.json() and "feedback" in r.json()

    @pytest.mark.asyncio
    async def test_nonexistent_returns_404(self, ac):
        patch_all_db(users_val=ADMIN, resumes_val=None)
        r = await ac.get(f"/api/admin/resumes/{RES_ID}",
                         headers={"Authorization": f"Bearer {make_jwt(ADMIN_ID, 'admin')}"})
        assert r.status_code == 404


class TestAdminPatchResume:
    @pytest.mark.asyncio
    async def test_patch_status_updated(self, ac):
        patch_all_db(users_val=ADMIN, modified_count=1)
        r = await ac.patch(f"/api/admin/resumes/{RES_ID}",
                           data={"status": "reviewed"},
                           headers={"Authorization": f"Bearer {make_jwt(ADMIN_ID, 'admin')}"})
        assert r.status_code == 200
        assert r.json().get("updated") is True


class TestAdminDeleteResume:
    @pytest.mark.asyncio
    async def test_delete_returns_deleted(self, ac):
        patch_all_db(users_val=ADMIN, resumes_val={**RESUME, "file_id": None},
                     deleted_count=1)
        r = await ac.delete(f"/api/admin/resumes/{RES_ID}",
                            headers={"Authorization": f"Bearer {make_jwt(ADMIN_ID, 'admin')}"})
        assert r.status_code == 200
        assert r.json().get("deleted") is True

    @pytest.mark.asyncio
    async def test_nonexistent_returns_404(self, ac):
        patch_all_db(users_val=ADMIN, resumes_val=None)
        r = await ac.delete(f"/api/admin/resumes/{RES_ID}",
                            headers={"Authorization": f"Bearer {make_jwt(ADMIN_ID, 'admin')}"})
        assert r.status_code == 404


class TestAdminMetrics:
    @pytest.mark.asyncio
    async def test_returns_interview_count(self, ac):
        cols = patch_all_db(users_val=ADMIN)
        cols["interviews"].count_documents = AsyncMock(return_value=42)
        import backend.controllers.admin_routes as adm
        adm.interviews = cols["interviews"]
        r = await ac.get("/api/admin/metrics",
                         headers={"Authorization": f"Bearer {make_jwt(ADMIN_ID, 'admin')}"})
        assert r.status_code == 200
        assert "interview_count" in r.json()
