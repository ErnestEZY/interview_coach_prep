import os
from fastapi import APIRouter, HTTPException, Depends, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from datetime import datetime, timezone, timedelta
from bson import ObjectId
from ..core.db import users, pending_users, reset_tokens
from ..models.schemas import UserIn, Token, ForgotPasswordRequest, ResetPasswordRequest
from ..core.security import (
    hash_password, verify_password, create_access_token, get_current_user,
    create_reset_token, verify_reset_token
)
from ..services.rate_limit import rate_limit
from ..services.email_service import send_reset_password_email
from ..services.audit import log_event, check_admin_ip, trigger_admin_alert
from ..services.utils import get_malaysia_time

from ..core.config import (
    EMAILJS_PUBLIC_KEY, EMAILJS_SERVICE_ID, EMAILJS_TEMPLATE_ID,
    ADMIN_EMAILJS_PUBLIC_KEY, ADMIN_EMAILJS_SERVICE_ID, ADMIN_EMAILJS_TEMPLATE_ID,
    ADMIN_ALERT_EMAILJS_PUBLIC_KEY, ADMIN_ALERT_EMAILJS_SERVICE_ID, ADMIN_ALERT_EMAILJS_TEMPLATE_ID,
    CAREERJET_WIDGET_ID
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

@router.get("/config")
async def get_auth_config():
    """Exposes public configuration for EmailJS and Careerjet to the frontend"""
    return {
        "emailjs_public_key": EMAILJS_PUBLIC_KEY,
        "emailjs_service_id": EMAILJS_SERVICE_ID,
        "emailjs_template_id": EMAILJS_TEMPLATE_ID,
        "admin_emailjs_public_key": ADMIN_EMAILJS_PUBLIC_KEY,
        "admin_emailjs_service_id": ADMIN_EMAILJS_SERVICE_ID,
        "admin_emailjs_template_id": ADMIN_EMAILJS_TEMPLATE_ID,
        "admin_alert_emailjs_public_key": ADMIN_ALERT_EMAILJS_PUBLIC_KEY,
        "admin_alert_emailjs_service_id": ADMIN_ALERT_EMAILJS_SERVICE_ID,
        "admin_alert_emailjs_template_id": ADMIN_ALERT_EMAILJS_TEMPLATE_ID,
        "careerjet_widget_id": CAREERJET_WIDGET_ID
    }

@router.post("/register", dependencies=[Depends(rate_limit)])
async def register(payload: UserIn, request: Request):
    # Ensure email is stripped and lowercase
    email = str(payload.email).strip().lower()
    ip_address = request.client.host if request.client else "unknown"
    
    # Check if user already exists in permanent collection
    existing = await users.find_one({"email": email})
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
    
    now = get_malaysia_time()
    
    # Generate a simple 6-digit OTP for verification
    import random
    otp = str(random.randint(100000, 999999))
    
    # Store registration data in pending_users collection
    pending_doc = {
        "email": email,
        "password_hash": hash_password(payload.password),
        "name": payload.name.strip() if payload.name else None,
        "verification_otp": otp,
        "otp_created_at": now,
        "ip_address": ip_address,
        "created_at": now
    }
    
    # Update or insert (upsert) to handle multiple registration attempts
    await pending_users.update_one(
        {"email": email},
        {"$set": pending_doc},
        upsert=True
    )
    
    # Calculate expiry for frontend display (15 mins as requested)
    expiry_time = (now + timedelta(minutes=15)).strftime("%H:%M")
    
    # We return the OTP so the frontend can send it via EmailJS
    return {
        "message": "Verification code sent. Please verify email to complete registration.",
        "otp": otp,
        "expiry": expiry_time,
        "email": email
    }

@router.post("/verify-email")
async def verify_email(payload: dict):
    email = payload.get("email", "").strip().lower()
    otp = payload.get("otp", "").strip()
    
    # Check if user is in pending_users
    pending_user = await pending_users.find_one({"email": email})
    
    # If not in pending, check if already verified in users collection
    if not pending_user:
        user = await users.find_one({"email": email})
        if user and user.get("is_verified"):
            return {"message": "Email already verified. You can now login."}
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Registration session not found. Please register again.")
    
    if pending_user.get("verification_otp") != otp:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OTP")
    
    # Check if OTP is expired (15 minutes)
    otp_time = pending_user.get("otp_created_at")
    if otp_time:
        if otp_time.tzinfo is None:
            otp_time = otp_time.replace(tzinfo=timezone.utc)
        
        now_utc = datetime.now(timezone.utc)
        diff = now_utc - otp_time
        
        if diff.total_seconds() > 900: # 15 mins
            # Clean up expired pending registration
            await pending_users.delete_one({"email": email})
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OTP expired. Please register again.")
    
    # OTP is valid! Create the permanent account now
    now = get_malaysia_time()
    user_doc = {
        "email": email,
        "password_hash": pending_user["password_hash"],
        "name": pending_user.get("name"),
        "role": "user",
        "created_at": now,
        "last_login_ip": pending_user.get("ip_address", "unknown"),
        "is_verified": True,
        "weekly_question_count": 0,
        "weekly_reset_at": now,
        "daily_resume_count": 0,
        "daily_interview_count": 0,
        "daily_reset_at": now,
    }
    
    await users.insert_one(user_doc)
    
    # Remove from pending_users
    await pending_users.delete_one({"email": email})
    
    return {"message": "Email verified successfully! Your account has been created."}

@router.post("/login", response_model=Token, dependencies=[Depends(rate_limit)])
async def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends()):
    # Ensure username is stripped and lowercase
    username = str(form_data.username).strip().lower()
    ip_address = request.client.host if request.client else "unknown"
    
    user = await users.find_one({"email": username})
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Email not found")
    
    if not verify_password(form_data.password, user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect password")
    
    # Check if user is verified
    if not user.get("is_verified", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Email not verified. Please verify your email first."
        )

    # Prevent admins from using normal user login flow
    if user.get("role") in ("admin", "super_admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin or super_admin cannot login here. Use admin interface.")
    
    # Update last login info
    await users.update_one({"_id": user["_id"]}, {"$set": {"last_login_ip": ip_address}})
    
    token = create_access_token(str(user["_id"]), user.get("role", "user"))
    return Token(access_token=token)

@router.post("/admin_login", response_model=Token, dependencies=[Depends(rate_limit)])
async def admin_login(request: Request, form_data: OAuth2PasswordRequestForm = Depends()):
    # Ensure username is stripped and lowercase
    username = str(form_data.username).strip().lower()
    ip_address = request.client.host if request.client else "unknown"
    
    user = await users.find_one({"email": username})
    if not user:
        await log_event(None, username, "admin_login", ip_address, "failure", {"reason": "user_not_found"})
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Email not found")
    
    # IP Monitoring and Restrictions
    ip_status = await check_admin_ip(username, ip_address)
    
    if not verify_password(form_data.password, user["password_hash"]):
        await log_event(str(user["_id"]), username, "admin_login", ip_address, "failure", {"reason": "wrong_password"})
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect password")
    
    if user.get("role") not in ("admin", "super_admin"):
        await log_event(str(user["_id"]), username, "admin_login", ip_address, "failure", {"reason": "not_admin"})
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admin or super_admin can login here")

    # Handle IP issues (Anomaly Detection)
    is_anomaly = False
    alert_reason = None
    
    # Check if IP is in allowlist
    if not ip_status["is_allowed"]:
        is_anomaly = True
        alert_reason = "Unknown IP access attempt (Not in Allowlist)"
        await log_event(str(user["_id"]), username, "admin_login", ip_address, "warning", {"reason": "unauthorized_ip"})
    
    # Check if IP changed since last login
    if ip_status["is_anomaly"]:
        is_anomaly = True
        # If we already have a reason (from allowlist), append this one
        anomaly_msg = f"IP Anomaly detected (Changed from: {ip_status['last_ip']})"
        alert_reason = f"{alert_reason} | {anomaly_msg}" if alert_reason else anomaly_msg
        await log_event(str(user["_id"]), username, "admin_login", ip_address, "warning", {"reason": "ip_anomaly"})

    # Trigger alert once if any anomaly was detected
    if is_anomaly:
        await trigger_admin_alert(username, ip_address, alert_reason)

    # Update last login info
    await users.update_one({"_id": user["_id"]}, {"$set": {"last_login_ip": ip_address}})
    
    await log_event(str(user["_id"]), username, "admin_login", ip_address, "success")
    token = create_access_token(str(user["_id"]), user.get("role"))
    
    # Fetch admin emails to return for frontend alerting as fallback
    admin_emails = []
    if is_anomaly:
        try:
            cursor = users.find({"role": {"$in": ["admin", "super_admin"]}})
            async for admin in cursor:
                if "email" in admin:
                    admin_emails.append(admin["email"])
        except Exception:
            pass

    return Token(
        access_token=token,
        is_anomaly=is_anomaly,
        admin_emails=admin_emails,
        alert_reason=alert_reason
    )

@router.get("/me")
async def me(current=Depends(get_current_user)):
    return current

@router.post("/forgot-password", dependencies=[Depends(rate_limit)])
async def forgot_password(payload: ForgotPasswordRequest, request: Request):
    email = payload.email.strip().lower()
    
    # Check if user exists in permanent collection
    user = await users.find_one({"email": email})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="We couldn't find an account with that email address. Please check and try again."
        )
    
    # Generate reset token
    token = await create_reset_token(email)
    
    # Determine base URL dynamically or use production override
    # If running on Render (production), we prefer the explicit production URL
    # to ensure cross-device links (e.g. laptop request -> mobile click) work correctly.
    if os.getenv("RENDER") or os.getenv("production"):
        base_url = "https://interview-coach-prep.onrender.com"
    else:
        # Local development fallback
        # Use request.base_url to get the full scheme://host
        # But we need to handle forwarded headers correctly
        scheme = request.headers.get("X-Forwarded-Proto", "http")
        host = request.headers.get("Host", "localhost:8000")
        base_url = f"{scheme}://{host}"
    
    # Construct the reset link
    # Note: We now serve reset_password.html directly from the static directory
    reset_link = f"{base_url}/static/pages/reset_password.html?token={token}"
    
    # Send email
    success = await send_reset_password_email(email, reset_link)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send reset email. Please try again later."
        )
    
    return {"message": "A password reset link has been sent. It may take a few minutes to arrive in your inbox."}

@router.get("/verify-token/{token}")
async def verify_token_endpoint(token: str):
    """
    Returns the email associated with a valid token so the reset page can display it.
    """
    email = await verify_reset_token(token)
    if not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token")
    return {"email": email}

@router.post("/reset-password", dependencies=[Depends(rate_limit)])
async def reset_password(payload: ResetPasswordRequest):
    email = await verify_reset_token(payload.token)
    if not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token")
    
    # Find user
    user = await users.find_one({"email": email})
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    # Update password
    new_password_hash = hash_password(payload.password)
    await users.update_one(
        {"email": email},
        {"$set": {"password_hash": new_password_hash}}
    )
    
    # Delete the token after use to prevent reuse
    await reset_tokens.delete_one({"token": payload.token})
    
    return {"message": "Password updated successfully. You can now login with your new password."}
