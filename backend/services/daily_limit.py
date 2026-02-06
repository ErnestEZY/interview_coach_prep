from datetime import datetime, timedelta, timezone
from bson import ObjectId
from ..core.db import users
from .utils import get_malaysia_time

async def check_daily_limit(user_id: str, limit_type: str, max_attempts: int):
    """
    Checks if a user has reached their daily limit for a specific action.
    Resets at 00:00 Malaysia Time (GMT+8).
    limit_type: 'daily_resume_count' or 'daily_interview_count'
    """
    oid = ObjectId(user_id)
    u = await users.find_one({"_id": oid})
    if not u:
        return True, 0

    now_my = get_malaysia_time()
    # Reset at 00:00 MY time
    reset_at = u.get("daily_reset_at")
    
    # Ensure reset_at is timezone-aware and in Malaysia time
    if reset_at:
        if reset_at.tzinfo is None:
            # MongoDB returns naive datetimes in UTC. 
            # We must mark it as UTC first, then convert to Malaysia time.
            reset_at = reset_at.replace(tzinfo=timezone.utc).astimezone(timezone(timedelta(hours=8)))
        else:
            # If it's already aware, just convert to Malaysia time
            reset_at = reset_at.astimezone(timezone(timedelta(hours=8)))
    
    # Start of today in Malaysia time
    today_start_my = now_my.replace(hour=0, minute=0, second=0, microsecond=0)
    
    needs_reset = False
    if reset_at is None:
        needs_reset = True
    else:
        # If reset_at was before today 00:00 MY time
        if reset_at < today_start_my:
            needs_reset = True

    if needs_reset:
        await users.update_one(
            {"_id": oid},
            {"$set": {
                "daily_reset_at": now_my,
                "daily_resume_count": 0,
                "daily_interview_count": 0,
                "daily_question_count": 0
            }}
        )
        return True, max_attempts

    current_count = u.get(limit_type, 0)
    remaining = max_attempts - current_count
    return current_count < max_attempts, remaining

async def increment_daily_limit(user_id: str, limit_type: str):
    oid = ObjectId(user_id)
    await users.update_one({"_id": oid}, {"$inc": {limit_type: 1}})
