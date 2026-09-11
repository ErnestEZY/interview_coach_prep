"""
OAuth Routes — Google and GitHub
GET /api/auth/oauth/google          → redirect to Google consent
GET /api/auth/oauth/google/callback → handle Google callback
GET /api/auth/oauth/github          → redirect to GitHub consent
GET /api/auth/oauth/github/callback → handle GitHub callback

Flow:
1. User clicks OAuth button → frontend navigates to /api/auth/oauth/{provider}
2. Backend redirects to provider consent screen
3. Provider redirects back to /api/auth/oauth/{provider}/callback with ?code=...
4. Backend exchanges code for user info
5. Find or create user, link provider if needed
6. Issue JWT, redirect to /static/pages/oauth_callback.html?token=...
7. Frontend picks up token from URL, stores it, redirects to dashboard
"""

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse
from urllib.parse import urlencode
from bson import ObjectId

from ..core.config import (
    GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET,
    GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET,
    OAUTH_REDIRECT_BASE
)
from ..core.db import users
from ..core.security import create_access_token
from ..services.utils import get_malaysia_time

router = APIRouter(prefix="/api/auth/oauth", tags=["oauth"])

GOOGLE_REDIRECT_URI = f"{OAUTH_REDIRECT_BASE}/api/auth/oauth/google/callback"
GITHUB_REDIRECT_URI = f"{OAUTH_REDIRECT_BASE}/api/auth/oauth/github/callback"

# ── Helpers ───────────────────────────────────────────────────────────────────

def _oauth_error_redirect(message: str) -> RedirectResponse:
    """Redirect to login page with an error message in the query string."""
    return RedirectResponse(
        url=f"/static/pages/login.html?oauth_error={message}",
        status_code=302
    )

async def _find_or_create_user(email: str, name: str, provider: str, provider_id: str) -> dict:
    """
    Core account linking logic:
    - If email exists: add provider to auth_providers list (link) and login
    - If email does not exist: create new user
    - Admin accounts block OAuth login
    """
    email = email.strip().lower()
    existing = await users.find_one({"email": email})

    if existing:
        # Block admin accounts from OAuth
        if existing.get("role") in ("admin", "super_admin"):
            raise ValueError("Admin accounts cannot use OAuth login.")

        # Link provider if not already linked
        current_providers = existing.get("auth_providers") or ["local"]
        if provider not in current_providers:
            current_providers.append(provider)
            await users.update_one(
                {"_id": existing["_id"]},
                {"$set": {"auth_providers": current_providers}}
            )
        return existing

    # Create new user — OAuth users are pre-verified, no OTP needed
    now = get_malaysia_time()
    doc = {
        "email": email,
        "name": name or email.split("@")[0],
        "password_hash": None,          # No password for OAuth users
        "role": "user",
        "is_verified": True,            # Email verified by provider
        "has_analyzed": False,
        "auth_providers": [provider],   # Track which providers are linked
        "target_job_title": None,
        "daily_resume_count": 0,
        "daily_interview_count": 0,
        "daily_assist_count": 0,
        "daily_reset_at": now,
        "weekly_question_count": 0,
        "weekly_reset_at": now,
        "created_at": now,
        "failed_login_attempts": 0,
        "lockout_until": None,
    }
    result = await users.insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc


# ── Google ─────────────────────────────────────────────────────────────────────

@router.get("/google")
async def google_login():
    """Redirect user to Google OAuth consent screen."""
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=503, detail="Google OAuth not configured.")
    params = urlencode({
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "online",
    })
    return RedirectResponse(
        url=f"https://accounts.google.com/o/oauth2/v2/auth?{params}",
        status_code=302
    )


@router.get("/google/callback")
async def google_callback(code: str = None, error: str = None):
    """Handle Google OAuth callback."""
    if error or not code:
        return _oauth_error_redirect("Google+login+was+cancelled+or+failed.")

    async with httpx.AsyncClient() as client:
        # Exchange code for tokens
        token_resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            }
        )
        if token_resp.status_code != 200:
            return _oauth_error_redirect("Failed+to+exchange+Google+auth+code.")

        token_data = token_resp.json()
        access_token = token_data.get("access_token")

        # Fetch user info
        user_resp = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        if user_resp.status_code != 200:
            return _oauth_error_redirect("Failed+to+fetch+Google+user+info.")

        info = user_resp.json()
        email = info.get("email")
        name = info.get("name", "")
        provider_id = info.get("id", "")

    if not email:
        return _oauth_error_redirect("Google+did+not+return+an+email+address.")

    try:
        user = await _find_or_create_user(email, name, "google", provider_id)
    except ValueError as e:
        return _oauth_error_redirect(str(e).replace(" ", "+"))

    jwt = create_access_token(str(user["_id"]), user.get("role", "user"))
    return RedirectResponse(
        url=f"/static/pages/oauth_callback.html?token={jwt}",
        status_code=302
    )


# ── GitHub ─────────────────────────────────────────────────────────────────────

@router.get("/github")
async def github_login():
    """Redirect user to GitHub OAuth consent screen."""
    if not GITHUB_CLIENT_ID:
        raise HTTPException(status_code=503, detail="GitHub OAuth not configured.")
    params = urlencode({
        "client_id": GITHUB_CLIENT_ID,
        "redirect_uri": GITHUB_REDIRECT_URI,
        "scope": "user:email",
    })
    return RedirectResponse(
        url=f"https://github.com/login/oauth/authorize?{params}",
        status_code=302
    )


@router.get("/github/callback")
async def github_callback(code: str = None, error: str = None):
    """Handle GitHub OAuth callback."""
    if error or not code:
        return _oauth_error_redirect("GitHub+login+was+cancelled+or+failed.")

    async with httpx.AsyncClient() as client:
        # Exchange code for access token
        token_resp = await client.post(
            "https://github.com/login/oauth/access_token",
            headers={"Accept": "application/json"},
            data={
                "client_id": GITHUB_CLIENT_ID,
                "client_secret": GITHUB_CLIENT_SECRET,
                "code": code,
                "redirect_uri": GITHUB_REDIRECT_URI,
            }
        )
        if token_resp.status_code != 200:
            return _oauth_error_redirect("Failed+to+exchange+GitHub+auth+code.")

        token_data = token_resp.json()
        access_token = token_data.get("access_token")

        # Fetch user profile
        user_resp = await client.get(
            "https://api.github.com/user",
            headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
        )
        if user_resp.status_code != 200:
            return _oauth_error_redirect("Failed+to+fetch+GitHub+user+info.")

        info = user_resp.json()
        name = info.get("name") or info.get("login", "")
        provider_id = str(info.get("id", ""))
        email = info.get("email")

        # GitHub may not return a public email — fetch from emails endpoint
        if not email:
            emails_resp = await client.get(
                "https://api.github.com/user/emails",
                headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
            )
            if emails_resp.status_code == 200:
                for e in emails_resp.json():
                    if e.get("primary") and e.get("verified"):
                        email = e.get("email")
                        break

    if not email:
        # GitHub account has no verified email — redirect with special flag
        return RedirectResponse(
            url="/static/pages/oauth_email_required.html?provider=github",
            status_code=302
        )

    try:
        user = await _find_or_create_user(email, name, "github", provider_id)
    except ValueError as e:
        return _oauth_error_redirect(str(e).replace(" ", "+"))

    jwt = create_access_token(str(user["_id"]), user.get("role", "user"))
    return RedirectResponse(
        url=f"/static/pages/oauth_callback.html?token={jwt}",
        status_code=302
    )


# ── GitHub — Email fallback for accounts with no public email ────────────────

@router.post("/github/email")
async def github_email_fallback(payload: dict):
    """
    Called when GitHub user has no public email.
    User enters their email manually — we create/link the account.
    Session state (provider_id) is not retained between redirect and this call,
    so we create a temporary GitHub-linked account with just the email.
    """
    email = payload.get("email", "").strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Invalid email address.")

    try:
        user = await _find_or_create_user(email, email.split("@")[0], "github", "")
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))

    jwt = create_access_token(str(user["_id"]), user.get("role", "user"))
    return {"access_token": jwt, "token_type": "bearer"}
