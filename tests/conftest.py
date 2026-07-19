"""
ICP Test Suite — conftest.py
Patches Motor before any backend module is imported so Python 3.14 never
tries to grab an event loop during module-level code.
"""
import os
import sys
import asyncio
from unittest.mock import AsyncMock, MagicMock

# Set event loop policy for Windows to prevent RuntimeError
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# ── Env defaults (set before any backend import) ─────────────────────────────
os.environ.setdefault("MONGO_URI",             "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME",               "icp_test")
os.environ.setdefault("JWT_SECRET",            "pytest-secret-key")
os.environ.setdefault("JWT_ALGORITHM",         "HS256")
os.environ.setdefault("MISTRAL_API_KEY",       "fake-key-for-tests")
os.environ.setdefault("ADMIN_INVITE_CODE",     "test-invite-123")
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "9999")

# ── Patch Motor at import time ───────────────────────────────────────────────
import unittest.mock as _um

_um.patch("motor.motor_asyncio.AsyncIOMotorClient",
          return_value=MagicMock(
              admin=MagicMock(command=AsyncMock(return_value={"ok": 1}))
          )).start()
_um.patch("motor.motor_asyncio.AsyncIOMotorGridFSBucket",
          return_value=MagicMock()).start()

# ── Seed db module with mock collections ────────────────────────────────────
import backend.core.db as _db

def _col():
    c = AsyncMock()
    c.find_one       = AsyncMock(return_value=None)
    c.insert_one     = AsyncMock(return_value=MagicMock(inserted_id="507f191e810c19729de860ea"))
    c.update_one     = AsyncMock(return_value=MagicMock(modified_count=1))
    c.delete_one     = AsyncMock(return_value=MagicMock(deleted_count=1))
    c.create_index   = AsyncMock()
    c.count_documents= AsyncMock(return_value=0)

    class _Cur:
        def __aiter__(self): return self
        async def __anext__(self): raise StopAsyncIteration
        def sort(self, *a, **kw): return self

    c.find = MagicMock(return_value=_Cur())
    return c

for _name in ["users","pending_users","reset_tokens",
              "resumes","interviews","audit_logs","usage"]:
    setattr(_db, _name, _col())

# Add event loop policy fixture for pytest-asyncio
import pytest

@pytest.fixture(scope="session")
def event_loop_policy():
    if sys.platform == "win32":
        return asyncio.WindowsProactorEventLoopPolicy()
    return asyncio.DefaultEventLoopPolicy()
