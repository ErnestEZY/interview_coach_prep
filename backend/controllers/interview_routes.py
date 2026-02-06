from fastapi import APIRouter, Depends, HTTPException, Form
from datetime import datetime, timedelta, timezone
from bson import ObjectId
from ..core.db import interviews, users, resumes
from ..core.security import get_current_user
from ..core.config import SESSION_MAX_QUESTIONS, INTERVIEW_DEFAULT_QUESTIONS, DAILY_QUESTION_LIMIT
from ..services.interview_engine import interview_reply
from ..services.rate_limit import rate_limit
from ..services.utils import is_gibberish, get_malaysia_time
from ..services.daily_limit import check_daily_limit, increment_daily_limit

router = APIRouter(prefix="/api/interview", tags=["interview"])

@router.get("/limits")
async def get_interview_limits(current=Depends(get_current_user)):
    can_start, remaining = await check_daily_limit(current["id"], "daily_interview_count", 3)
    return {"remaining": remaining, "limit": 3}

async def can_ask(user_id: str) -> bool:
    # Use the daily_limit service to handle reset logic
    await check_daily_limit(user_id, "daily_question_count", DAILY_QUESTION_LIMIT)
    
    oid = ObjectId(user_id)
    u = await users.find_one({"_id": oid})
    return int(u.get("daily_question_count", 0)) < DAILY_QUESTION_LIMIT

async def inc_question(user_id: str):
    oid = ObjectId(user_id)
    await users.update_one({"_id": oid}, {"$inc": {"daily_question_count": 1}})

@router.post("/start")
async def start(
    job_title: str = Form(None),
    resume_feedback: str = Form(None),
    questions_limit: int = Form(None),
    difficulty: str = Form("Beginner"),
    current=Depends(get_current_user),
    _: None = Depends(rate_limit),
):
    u = await users.find_one({"_id": ObjectId(current["id"])})
    
    # Validate questions_limit
    if questions_limit is None:
        questions_limit = INTERVIEW_DEFAULT_QUESTIONS
    
    # Ensure it's within [10, SESSION_MAX_QUESTIONS]
    if questions_limit < 10:
        questions_limit = INTERVIEW_DEFAULT_QUESTIONS
    if questions_limit > SESSION_MAX_QUESTIONS:
        questions_limit = SESSION_MAX_QUESTIONS

    # Validate difficulty
    if difficulty not in ["Beginner", "Intermediate", "Advanced"]:
        difficulty = "Beginner"

    # If not provided in form, try to get from DB
    if not job_title and u:
        job_title = u.get("target_job_title")
    
    import json
    feedback_dict = None
    if resume_feedback:
        try:
            feedback_dict = json.loads(resume_feedback)
        except:
            pass
    
    if not feedback_dict:
        # Try to find latest resume with feedback for this user
        r_doc = await resumes.find_one({"user_id": current["id"]}, sort=[("created_at", -1)])
        if r_doc:
            feedback_dict = r_doc.get("feedback")
            if not job_title:
                job_title = r_doc.get("job_title")

    if not u or not u.get("has_analyzed"):
         if not feedback_dict:
            raise HTTPException(status_code=400, detail="Analyze resume first to start interview")
            
    if not await can_ask(current["id"]):
        raise HTTPException(status_code=429, detail="Daily question quota reached (60 questions per day). Resets at 00:00 Malaysia Time.")
    
    can_start, _ = await check_daily_limit(current["id"], "daily_interview_count", 3)
    if not can_start:
        raise HTTPException(status_code=429, detail="Daily interview session limit reached. Resets at 00:00 Malaysia Time.")
    
    try:
        ai = interview_reply([], job_title=job_title, resume_feedback=feedback_dict, questions_limit=questions_limit, difficulty=difficulty, current_asked_count=0)
    except Exception as e:
        if "429" in str(e) or "rate_limit" in str(e).lower():
            raise HTTPException(status_code=429, detail="Mistral AI rate limit exceeded. Please wait a moment.")
        raise HTTPException(status_code=500, detail=f"AI Error: {str(e)}")

    sid = str(ObjectId())
    doc = {
        "session_id": sid,
        "user_id": current["id"],
        "job_title": job_title,
        "resume_feedback": feedback_dict,
        "questions_limit": questions_limit,
        "difficulty": difficulty,
        "asked_count": 0,
        "invalid_attempts": 0,
        "transcript": [],
        "created_at": get_malaysia_time(),
        "ended_at": None,
    }
    res = await interviews.insert_one(doc)
    await inc_question(current["id"])
    await interviews.update_one({"_id": res.inserted_id}, {"$push": {"transcript": {"role": "assistant", "text": ai, "at": get_malaysia_time()}}, "$inc": {"asked_count": 1}})
    return {"session_id": sid, "message": ai, "asked_count": 1, "questions_limit": questions_limit}

@router.post("/{session_id}/reply")
async def reply(session_id: str, user_text: str = Form(...), current=Depends(get_current_user), _: None = Depends(rate_limit)):
    s = await interviews.find_one({"session_id": session_id, "user_id": current["id"]})
    if not s:
        raise HTTPException(status_code=404, detail="Not found")
    if s.get("ended_at"):
        return {"ended": True, "message": "Session has ended"}
    
    job_title = s.get("job_title", "")
    resume_feedback = s.get("resume_feedback")
    questions_limit = s.get("questions_limit", INTERVIEW_DEFAULT_QUESTIONS)
    difficulty = s.get("difficulty", "Beginner")

    if is_gibberish(user_text):
        msg = "I didn’t quite catch that. Please answer in clear words. Please try answering the previous question again in your own words."
        await interviews.update_one(
            {"session_id": session_id},
            {"$push": {"transcript": {"role": "user", "text": user_text, "at": get_malaysia_time()}}},
        )
        await interviews.update_one(
            {"session_id": session_id},
            {"$push": {"transcript": {"role": "assistant", "text": msg, "at": get_malaysia_time()}}},
        )
        await interviews.update_one(
            {"session_id": session_id},
            {"$inc": {"invalid_attempts": 1}}
        )
        s2 = await interviews.find_one({"session_id": session_id})
        invalids = int(s2.get("invalid_attempts", 0))
        if invalids >= 3:
            explain = (
                "We received multiple responses that looked like random characters or non-words. "
                "To keep the interview productive, this session is now closed. "
                "Because the interview was not completed with valid answers, the Interview Readiness Score is N/A."
            )
            await increment_daily_limit(current["id"], "daily_interview_count")
            await interviews.update_one(
                {"session_id": session_id},
                {
                    "$set": {
                        "ended_at": get_malaysia_time(),
                        "readiness_score": None,
                        "readiness_feedback": explain,
                    },
                    "$push": {"transcript": {"role": "assistant", "text": explain, "at": get_malaysia_time()}}
                }
            )
            return {"message": explain, "ended": True}
        return {"message": msg}
    if not await can_ask(current["id"]):
        raise HTTPException(status_code=429, detail="Daily question quota reached (60 questions per day). Resets at 00:00 Malaysia Time.")
    history = [{"role": t["role"], "content": t["text"]} for t in s.get("transcript", [])]
    history.append({"role": "user", "content": user_text})
    
    current_asked_count = s.get("asked_count", 0)
    try:
        ai = interview_reply(history, job_title=job_title, resume_feedback=resume_feedback, questions_limit=questions_limit, difficulty=difficulty, current_asked_count=current_asked_count)
    except Exception as e:
        if "429" in str(e) or "rate_limit" in str(e).lower():
            raise HTTPException(status_code=429, detail="Mistral AI rate limit exceeded. Please wait a moment.")
        raise HTTPException(status_code=500, detail=f"AI Error: {str(e)}")
    
    # Check for AI signaling completion
    ai_ended = "[FINISH]" in ai
    ai = ai.replace("[FINISH]", "").strip()

    await inc_question(current["id"])
    await interviews.update_one(
        {"session_id": session_id},
        {"$push": {"transcript": {"role": "user", "text": user_text, "at": get_malaysia_time()}}},
    )
    await interviews.update_one(
        {"session_id": session_id},
        {
            "$push": {"transcript": {"role": "assistant", "text": ai, "at": get_malaysia_time()}},
            "$inc": {"asked_count": 1},
        },
    )
    
    # Session ends ONLY if we've asked enough questions AND (AI signals it OR we hit the hard limit)
    # limit + 1 is the magic number because:
    # - Start: asked_count=0 -> AI sends Q1 -> asked_count=1
    # - User R1 -> AI sends Q2 -> asked_count=2
    # ...
    # - User R10 -> AI sends Wrap-up -> asked_count=11
    asked_now = int(s.get("asked_count", 0)) + 1
    limit = int(s.get("questions_limit", SESSION_MAX_QUESTIONS))
    
    # Force end if we reach limit + 1, OR if AI signals end and we have at least 'limit' questions
    ended_now = (asked_now > limit) or (ai_ended and asked_now >= limit)

    if ended_now:
        # Check if session was already ended to avoid double counting
        s_check = await interviews.find_one({"session_id": session_id})
        if s_check and not s_check.get("ended_at"):
            import re
            # Extract readiness score and feedback from the AI message
            # Format expected: "Interview Readiness Score: XX/100"
            score_match = re.search(r"Interview Readiness Score:\s*(\d+)/100", ai, re.IGNORECASE)
            readiness_score = int(score_match.group(1)) if score_match else None
            
            # The feedback is usually the rest of the text around the score
            # We'll store the whole concluding message as feedback for now, 
            # or try to extract the specific part if possible.
            # For simplicity, let's store the message and the extracted score.
            
            # Clean up the feedback text to remove the score line and [FINISH] tag
            feedback_text = ai.replace("[FINISH]", "").strip()
            if score_match:
                # Remove the "Interview Readiness Score: XX/100" part from the feedback text
                feedback_text = re.sub(r"Interview Readiness Score:\s*\d+/100", "", feedback_text, flags=re.IGNORECASE).strip()
            
            await increment_daily_limit(current["id"], "daily_interview_count")
            await interviews.update_one(
                {"session_id": session_id}, 
                {
                    "$set": {
                        "ended_at": get_malaysia_time(),
                        "readiness_score": readiness_score,
                        "readiness_feedback": feedback_text,
                    }
                }
            )
        return {"message": ai, "ended": True, "asked_count": asked_now, "questions_limit": limit}
    return {"message": ai, "asked_count": asked_now, "questions_limit": limit}

@router.post("/{session_id}/end")
async def end(session_id: str, current=Depends(get_current_user)):
    # Check if session was already ended to avoid double counting
    s = await interviews.find_one({"session_id": session_id, "user_id": current["id"]})
    if s and not s.get("ended_at"):
        # Generate a final message from AI explaining why no score is given
        job_title = s.get("job_title", "")
        resume_feedback = s.get("resume_feedback")
        questions_limit = s.get("questions_limit", INTERVIEW_DEFAULT_QUESTIONS)
        difficulty = s.get("difficulty", "Intermediate")
        asked_count = s.get("asked_count", 0)
        
        history = [{"role": t["role"], "content": t["text"]} for t in s.get("transcript", [])]
        # Inform the AI that the user ended the session early and ask it to explain why no score is generated
        history.append({
            "role": "user", 
            "content": "[SYSTEM MESSAGE]: The user has ended the interview session early. Please explain to the user that the session is now closed. Explicitly state that because the interview was not completed, a Readiness Score cannot be generated (it will be shown as N/A). Provide some brief, encouraging words about their progress so far. Be professional and polite."
        })
        
        # Call AI to get the explanation message
        ai_msg = interview_reply(
            history, 
            job_title=job_title, 
            resume_feedback=resume_feedback, 
            questions_limit=questions_limit, 
            difficulty=difficulty,
            current_asked_count=asked_count,
            force_end=True
        )
        ai_msg = ai_msg.replace("[FINISH]", "").strip()

        await increment_daily_limit(current["id"], "daily_interview_count")
        await interviews.update_one(
            {"session_id": session_id, "user_id": current["id"]}, 
            {
                "$set": {
                    "ended_at": get_malaysia_time(),
                    "readiness_score": None,
                    "readiness_feedback": ai_msg
                },
                "$push": {"transcript": {"role": "assistant", "text": ai_msg, "at": get_malaysia_time()}}
            }
        )
        return {"ended": True, "message": ai_msg}
    return {"ended": True, "already_ended": True}

@router.post("/reset-quota")
async def reset_quota(current=Depends(get_current_user)):
    """Reset the daily quotas for the current user (Testing only)"""
    oid = ObjectId(current["id"])
    now = get_malaysia_time()
    await users.update_one(
        {"_id": oid},
        {
            "$set": {
                "daily_question_count": 0,
                "daily_resume_count": 0,
                "daily_interview_count": 0,
                "daily_reset_at": now
            }
        }
    )
    return {"message": "Quotas reset successfully"}

@router.get("/history")
async def history(current=Depends(get_current_user)):
    cur = interviews.find({"user_id": current["id"]}).sort("created_at", -1)
    items = []
    async for s in cur:
        items.append({
            "id": str(s["_id"]), 
            "asked_count": s.get("asked_count", 0), 
            "created_at": s["created_at"], 
            "ended_at": s.get("ended_at"),
            "readiness_score": s.get("readiness_score"),
            "readiness_feedback": s.get("readiness_feedback")
        })
    return items

@router.get("/{session_id}")
async def detail(session_id: str, current=Depends(get_current_user)):
    s = await interviews.find_one({"_id": ObjectId(session_id), "user_id": current["id"]})
    if not s:
        s = await interviews.find_one({"session_id": session_id, "user_id": current["id"]})
    if not s:
        raise HTTPException(status_code=404, detail="Not found")
    return {
        "id": str(s.get("_id")),
        "session_id": s.get("session_id"),
        "asked_count": s.get("asked_count", 0),
        "questions_limit": s.get("questions_limit", INTERVIEW_DEFAULT_QUESTIONS),
        "created_at": s.get("created_at"),
        "ended_at": s.get("ended_at"),
        "transcript": s.get("transcript", []),
        "readiness_score": s.get("readiness_score"),
        "readiness_feedback": s.get("readiness_feedback"),
    }

@router.delete("/{session_id}")
async def delete_session(session_id: str, current=Depends(get_current_user)):
    try:
        oid = ObjectId(session_id)
        # Try to delete by _id
        res = await interviews.delete_one({"_id": oid, "user_id": current["id"]})
    except:
        # If not a valid ObjectId, try deleting by session_id string
        res = await interviews.delete_one({"session_id": session_id, "user_id": current["id"]})
        
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Interview session not found")
        
    return {"message": "Interview session deleted successfully"}
