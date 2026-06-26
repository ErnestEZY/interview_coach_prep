"""
Unit Tests — backend/core/security.py
Tests: hash_password, verify_password, create_access_token, JWT decode
No database or network required.
"""
import os
import sys
import pytest
from datetime import timedelta, timezone

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from backend.core.security import hash_password, verify_password, create_access_token
import jwt


class TestPasswordHashing:
    def test_hash_returns_string(self):
        h = hash_password("MyP@ss123")
        assert isinstance(h, str)
        assert len(h) > 0

    def test_hash_not_plaintext(self):
        h = hash_password("MyP@ss123")
        assert h != "MyP@ss123"

    def test_verify_correct_password(self):
        h = hash_password("Correct1!")
        assert verify_password("Correct1!", h) is True

    def test_verify_wrong_password(self):
        h = hash_password("Correct1!")
        assert verify_password("WrongPass!", h) is False

    def test_hash_is_deterministic_verify(self):
        """Same password should always verify against its hash."""
        for pw in ["abc123!", "P@$$w0rd", "短い"]:
            h = hash_password(pw)
            assert verify_password(pw, h) is True

    def test_different_passwords_different_hashes(self):
        h1 = hash_password("Password1!")
        h2 = hash_password("Password2!")
        assert h1 != h2

    def test_long_password_hashed_correctly(self):
        """Passwords over 72 bytes should still verify (SHA-256 pre-hash)."""
        long_pw = "A" * 100 + "!1"
        h = hash_password(long_pw)
        assert verify_password(long_pw, h) is True

    def test_empty_password_verify_false(self):
        h = hash_password("SomePass1!")
        assert verify_password("", h) is False


class TestJWTToken:
    def test_create_token_returns_string(self):
        token = create_access_token("user123", "user")
        assert isinstance(token, str)
        assert len(token) > 0

    def test_token_contains_correct_sub(self):
        token = create_access_token("myuserid", "user")
        payload = jwt.decode(token, os.environ["JWT_SECRET"],
                             algorithms=["HS256"])
        assert payload["sub"] == "myuserid"

    def test_token_contains_correct_role(self):
        token = create_access_token("myuserid", "admin")
        payload = jwt.decode(token, os.environ["JWT_SECRET"],
                             algorithms=["HS256"])
        assert payload["role"] == "admin"

    def test_token_expires(self):
        token = create_access_token("u1", "user",
                                    expires_delta=timedelta(seconds=-1))
        with pytest.raises(jwt.ExpiredSignatureError):
            jwt.decode(token, os.environ["JWT_SECRET"],
                       algorithms=["HS256"])

    def test_wrong_secret_rejected(self):
        token = create_access_token("u1", "user")
        with pytest.raises(jwt.InvalidSignatureError):
            jwt.decode(token, "wrong-secret", algorithms=["HS256"])

    def test_tampered_payload_rejected(self):
        token = create_access_token("u1", "user")
        parts = token.split(".")
        # Flip last character of payload
        bad_payload = parts[1][:-1] + ("A" if parts[1][-1] != "A" else "B")
        bad_token = ".".join([parts[0], bad_payload, parts[2]])
        with pytest.raises(Exception):
            jwt.decode(bad_token, os.environ["JWT_SECRET"],
                       algorithms=["HS256"])
