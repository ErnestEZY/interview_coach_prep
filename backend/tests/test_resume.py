import os
import pytest
from httpx import AsyncClient
from backend.main import app

if os.getenv("RUN_DB_TESTS", "0") != "1":
    pytest.skip("Skipping DB-dependent tests", allow_module_level=True)
import io
from docx import Document

async def get_token(ac: AsyncClient):
    email = "resume_tester@example.com"
    password = "Pass123!"
    r = await ac.post("/api/auth/register", json={"email": email, "password": password})
    return r.json()["access_token"]

def make_docx_bytes(text="Hello Resume"):
    buf = io.BytesIO()
    doc = Document()
    doc.add_paragraph(text)
    doc.save(buf)
    buf.seek(0)
    return buf.getvalue()

@pytest.mark.asyncio
async def test_upload_docx_feedback():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        token = await get_token(ac)
        files = {"file": ("resume.docx", make_docx_bytes(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
        data = {"consent": "true"}
        r = await ac.post("/api/resume/upload", files=files, data=data, headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        fb = r.json()["feedback"]
        assert "Advantages" in fb and "Disadvantages" in fb and "Suggestions" in fb and "Keywords" in fb
