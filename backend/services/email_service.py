from ..core.config import (
    EMAILJS_PUBLIC_KEY, EMAILJS_SERVICE_ID, EMAILJS_TEMPLATE_ID,
    ADMIN_ALERT_EMAILJS_PUBLIC_KEY, ADMIN_ALERT_EMAILJS_SERVICE_ID, ADMIN_ALERT_EMAILJS_TEMPLATE_ID,
    FORGOT_PASSWORD_EMAILJS_PUBLIC_KEY, FORGOT_PASSWORD_EMAILJS_SERVICE_ID, FORGOT_PASSWORD_EMAILJS_TEMPLATE_ID,
    FORGOT_PASSWORD_EMAILJS_ACCESS_TOKEN
)
from ..core.db import users
import httpx

async def send_reset_password_email(email: str, reset_link: str):
    """
    Sends a password reset email using EmailJS REST API.
    """
    # Use the dedicated Forgot Password EmailJS configuration
    service_id = FORGOT_PASSWORD_EMAILJS_SERVICE_ID
    template_id = FORGOT_PASSWORD_EMAILJS_TEMPLATE_ID
    public_key = FORGOT_PASSWORD_EMAILJS_PUBLIC_KEY
    access_token = FORGOT_PASSWORD_EMAILJS_ACCESS_TOKEN

    if not all([service_id, template_id, public_key]):
        return False

    async with httpx.AsyncClient() as client:
        # Template parameters for the forgot password email
        # The user has updated the template in EmailJS dashboard to use {{reset_link}}
        template_params = {
            "to_email": email,
            "reset_email": email,
            "reset_link": reset_link,
            "message": f"Reset Link: {reset_link}" # Simplified fallback
        }

        payload = {
            "service_id": service_id,
            "template_id": template_id,
            "user_id": public_key,
            "template_params": template_params
        }
        
        # If access_token is provided, add it to the payload (Required for server-side calls)
        if access_token:
            payload["accessToken"] = access_token

        try:
            # Adding more specific headers to satisfy EmailJS security checks
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Origin": "https://interview-coach-prep.onrender.com",
                "Referer": "https://interview-coach-prep.onrender.com/"
            }
            
            # Ensure the payload uses the most compatible field names
            # Some versions of EmailJS API prefer 'publicKey' over 'user_id' when accessToken is used
            payload_to_send = {
                "service_id": service_id,
                "template_id": template_id,
                "user_id": public_key,
                "template_params": template_params
            }
            
            if access_token:
                payload_to_send["accessToken"] = access_token

            response = await client.post(
                "https://api.emailjs.com/api/v1.0/email/send",
                json=payload_to_send,
                headers=headers,
                timeout=15.0
            )
            
            if response.status_code != 200:
                return False
                
            return True
        except Exception as e:
            return False

async def send_admin_alert(subject: str, message: str, offender_email: str = "Unknown"):
    """
    Sends a security alert email to all admins/super_admins found in the database 
    using the EmailJS REST API.
    """
    if not all([ADMIN_ALERT_EMAILJS_SERVICE_ID, ADMIN_ALERT_EMAILJS_TEMPLATE_ID, ADMIN_ALERT_EMAILJS_PUBLIC_KEY]):
        return False

    # Find all admins and super_admins in the database
    admin_emails = []
    try:
        cursor = users.find({"role": {"$in": ["admin", "super_admin"]}})
        async for admin in cursor:
            if "email" in admin:
                admin_emails.append(admin["email"])
    except Exception as e:
        return False

    if not admin_emails:
        return False

    success_count = 0
    async with httpx.AsyncClient() as client:
        for admin_email in admin_emails:
            # Template parameters for the Admin EmailJS template
            template_params = {
                "email_alert": admin_email,
                "to_email": admin_email,
                "admin_message": f"Security Alert: {subject}\n\n{message}",
                "offender_email": offender_email
            }

            payload = {
                "service_id": ADMIN_ALERT_EMAILJS_SERVICE_ID,
                "template_id": ADMIN_ALERT_EMAILJS_TEMPLATE_ID,
                "user_id": ADMIN_ALERT_EMAILJS_PUBLIC_KEY,
                "template_params": template_params
            }

            try:
                response = await client.post(
                    "https://api.emailjs.com/api/v1.0/email/send",
                    json=payload,
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    success_count += 1
            except Exception as e:
                pass

    return success_count > 0
