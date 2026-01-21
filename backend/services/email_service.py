from ..config import (
    EMAILJS_PUBLIC_KEY, EMAILJS_SERVICE_ID, EMAILJS_TEMPLATE_ID,
    ADMIN_ALERT_EMAILJS_PUBLIC_KEY, ADMIN_ALERT_EMAILJS_SERVICE_ID, ADMIN_ALERT_EMAILJS_TEMPLATE_ID
)
from ..db import users
import logging
import httpx

logger = logging.getLogger(__name__)

async def send_admin_alert(subject: str, message: str, offender_email: str = "Unknown"):
    """
    Sends a security alert email to all admins/super_admins found in the database 
    using the EmailJS REST API.
    """
    if not all([ADMIN_ALERT_EMAILJS_SERVICE_ID, ADMIN_ALERT_EMAILJS_TEMPLATE_ID, ADMIN_ALERT_EMAILJS_PUBLIC_KEY]):
        logger.error("Admin EmailJS configuration missing. Cannot send email alert.")
        return False

    # Find all admins and super_admins in the database
    admin_emails = []
    try:
        cursor = users.find({"role": {"$in": ["admin", "super_admin"]}})
        async for admin in cursor:
            if "email" in admin:
                admin_emails.append(admin["email"])
        
        # Log found admins for debugging
        logger.info(f"Found {len(admin_emails)} admins for security alert: {admin_emails}")
    except Exception as e:
        logger.error(f"Error fetching admin emails from database: {str(e)}")
        return False

    if not admin_emails:
        logger.warning("No users with admin or super_admin role found in database. Alert only logged to terminal.")
        logger.info(f"PENDING ALERT: {subject} - {message}")
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
                logger.debug(f"Sending alert to {admin_email}...")
                logger.debug(f"Payload: {payload}")
                response = await client.post(
                    "https://api.emailjs.com/api/v1.0/email/send",
                    json=payload,
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    logger.info(f"Security alert email sent to {admin_email} via EmailJS")
                    success_count += 1
                else:
                    logger.error(f"Failed to send EmailJS alert to {admin_email}: {response.status_code} - {response.text}")
            except Exception as e:
                logger.error(f"Exception while sending EmailJS alert to {admin_email}: {str(e)}")

    return success_count > 0
