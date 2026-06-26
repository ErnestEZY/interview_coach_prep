"""Shared helpers for integration / security tests."""
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock


def make_jwt(user_id: str = "507f191e810c19729de860ea",
             role: str = "user",
             expired: bool = False) -> str:
    import jwt
    secret = os.environ.get("JWT_SECRET", "pytest-secret-key")
    delta  = timedelta(hours=-1) if expired else timedelta(hours=2)
    return jwt.encode(
        {"sub": user_id, "role": role,
         "exp": datetime.now(timezone.utc) + delta, "sid": "DISABLED"},
        secret, algorithm="HS256")


class _AsyncCursor:
    """Proper async iterator for mocking Motor cursors."""
    def __init__(self, items):
        self._items = list(items)
        self._idx   = 0
    def __aiter__(self):
        return self
    async def __anext__(self):
        if self._idx >= len(self._items):
            raise StopAsyncIteration
        v = self._items[self._idx]; self._idx += 1
        return v
    def sort(self, *a, **kw):
        return self


def make_col(find_one_val=None, find_items=None,
             deleted_count=1, modified_count=1,
             inserted_id="507f191e810c19729de860ea"):
    col = AsyncMock()
    col.find_one        = AsyncMock(return_value=find_one_val)
    col.insert_one      = AsyncMock(return_value=MagicMock(inserted_id=inserted_id))
    col.update_one      = AsyncMock(return_value=MagicMock(modified_count=modified_count))
    col.delete_one      = AsyncMock(return_value=MagicMock(deleted_count=deleted_count))
    col.create_index    = AsyncMock()
    col.count_documents = AsyncMock(return_value=0)
    col.find            = MagicMock(return_value=_AsyncCursor(find_items or []))
    return col


# Modules that import db collections directly (need patching at each binding)
_DB_CONSUMERS = [
    "backend.core.db",
    "backend.core.security",
    "backend.controllers.auth_routes",
    "backend.controllers.resume_routes",
    "backend.controllers.interview_routes",
    "backend.controllers.admin_routes",
    "backend.controllers.job_routes",
    "backend.services.audit",
    "backend.services.daily_limit",
]

def patch_all_db(users_val=None, pending_val=None, reset_val=None,
                 resumes_val=None, interviews_val=None,
                 resumes_items=None, interviews_items=None,
                 deleted_count=1, modified_count=1):
    """
    Replace every imported collection reference across all controller/service
    modules so mocks are seen regardless of how the module imported the name.
    """
    import importlib, sys

    u   = make_col(find_one_val=users_val)
    pu  = make_col(find_one_val=pending_val)
    rt  = make_col(find_one_val=reset_val)
    res = make_col(find_one_val=resumes_val,    find_items=resumes_items,
                   deleted_count=deleted_count, modified_count=modified_count)
    inv = make_col(find_one_val=interviews_val, find_items=interviews_items,
                   deleted_count=deleted_count)
    al  = make_col()

    mapping = {
        "users": u, "pending_users": pu, "reset_tokens": rt,
        "resumes": res, "interviews": inv, "audit_logs": al,
    }

    for mod_name in _DB_CONSUMERS:
        mod = sys.modules.get(mod_name)
        if mod is None:
            try:
                mod = importlib.import_module(mod_name)
            except Exception:
                continue
        for attr, val in mapping.items():
            if hasattr(mod, attr):
                setattr(mod, attr, val)

    return mapping
