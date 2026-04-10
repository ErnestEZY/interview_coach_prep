from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
from ..core.db import audit_logs, users
from ..core.config import ADMIN_ALLOWLIST
from .email_service import send_admin_alert
from .utils import get_malaysia_time
import logging

# Configure logging for console alerts
logger = logging.getLogger("security_audit")
logging.basicConfig(level=logging.INFO)

async def log_event(
    user_id: Optional[str],
    email: str,
    event_type: str,
    ip_address: str,
    status: str,
    details: Optional[Dict[str, Any]] = None
):
    """Records an event in the audit log collection."""
    log_doc = {
        "user_id": user_id,
        "email": email,
        "event_type": event_type,
        "ip_address": ip_address,
        "status": status,
        "details": details or {},
        "timestamp": get_malaysia_time()
    }
    await audit_logs.insert_one(log_doc)
    
    if status == "failure":
        logger.warning(f"SECURITY ALERT: {event_type} failed for {email} from IP {ip_address}")

async def check_admin_ip(email: str, ip_address: str) -> Dict[str, Any]:
    """
    Checks if the admin login attempt is from an allowed IP or an anomaly.
    Returns a dict with 'is_allowed', 'is_anomaly', and 'message'.
    """
    # 1. IP Allowlist Check
    # Normalize for comparison
    clean_ip = ip_address.strip()
    is_allowed = clean_ip in [ip.strip() for ip in ADMIN_ALLOWLIST]
    
    # 2. Anomaly Detection
    user = await users.find_one({"email": email})
    is_anomaly = False
    last_ip = None
    if user:
        last_ip = user.get("last_login_ip")
        # If there's a last_ip and it's different from current, it's an anomaly
        if last_ip and last_ip != clean_ip:
            is_anomaly = True
            
    # DEBUG LOG for verification during testing
    print(f"[SECURITY DEBUG] Admin IP Check for {email}:")
    print(f"  - Current IP: {clean_ip}")
    print(f"  - Is in Allowlist: {is_allowed}")
    print(f"  - Previous IP: {last_ip}")
    print(f"  - Is Anomaly: {is_anomaly}")

    return {
        "is_allowed": is_allowed,
        "is_anomaly": is_anomaly,
        "last_ip": last_ip
    }

async def trigger_admin_alert(email: str, ip_address: str, reason: str):
    """Sends an email alert for suspicious admin activity."""
    alert_msg = f"Security Alert for Admin Account: {email}\n\nReason: {reason}\nIP Address: {ip_address}\nTimestamp: {get_malaysia_time()}"
    
    # VISUAL CONSOLE ALERT
    print(f"\n{'='*60}")
    print(f"!!! SECURITY ALERT TRIGGERED !!!")
    print(f"Admin: {email}")
    print(f"Reason: {reason}")
    print(f"IP: {ip_address}")
    print(f"{'='*60}\n")
    
    logger.critical(alert_msg)
    
    # send_admin_alert now fetches admin emails from the database automatically
    subject = f"Security Alert: Suspicious Admin Activity ({email})"
    print(f"[DEBUG] Calling send_admin_alert for {email}...")
    await send_admin_alert(subject, alert_msg, offender_email=email)
    print(f"[DEBUG] send_admin_alert call completed.")
