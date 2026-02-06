from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from datetime import datetime, timezone, timedelta
from bson import ObjectId
import os
import base64
from ..core.db import resumes, users, fs
from ..models.schemas import ResumeFeedback, ManualProfileIn
from ..core.security import get_current_user
from ..services.resume_parser import extract_resume_text
from ..services.ai_feedback import get_feedback
from ..services.rate_limit import rate_limit
from ..services.utils import is_gibberish, get_malaysia_time
from ..services.daily_limit import check_daily_limit, increment_daily_limit

router = APIRouter(prefix="/api/resume", tags=["resume"])

@router.get("/limits")
async def get_resume_limits(current=Depends(get_current_user)):
    can_upload, remaining = await check_daily_limit(current["id"], "daily_resume_count", 5)
    return {"remaining": remaining, "limit": 5}

@router.post("/upload")
async def upload_resume(
    file: UploadFile = File(...),
    job_title: str = Form(...),
    consent: bool = Form(False),
    current=Depends(get_current_user),
    _: None = Depends(rate_limit),
):
    if current.get("role") != "user":
        raise HTTPException(status_code=403, detail="Only regular users can upload resumes")
    
    can_upload, remaining = await check_daily_limit(current["id"], "daily_resume_count", 5)
    if not can_upload:
        raise HTTPException(status_code=429, detail="Daily resume analysis limit reached. Resets at 00:00 Malaysia Time.")

    if is_gibberish(job_title):
        raise HTTPException(status_code=400, detail="Invalid job title. Please provide a clear title.")

    name = file.filename
    tmp_path = os.path.join("backend", "tmp_" + name.replace(" ", "_"))
    file_bytes = await file.read()
    with open(tmp_path, "wb") as f:
        f.write(file_bytes)
    try:
        text, mime = extract_resume_text(tmp_path)
    except Exception as e:
        os.remove(tmp_path)
        raise HTTPException(status_code=400, detail=str(e))
    os.remove(tmp_path)
    try:
        feedback = get_feedback(text)
    except Exception as e:
        if "429" in str(e) or "rate_limit" in str(e).lower():
            raise HTTPException(status_code=429, detail="Mistral AI rate limit exceeded. Please wait a moment.")
        raise HTTPException(status_code=500, detail=f"AI Analysis failed: {str(e)}")

    # Validate if it's actually a resume
    # We add a small fallback check: if the text is long enough and contains certain keywords, 
    # we might override the AI's false negative if it's borderline.
    is_valid_resume = feedback.get("IsResume", True)
    resume_text_lower = text.lower()
    keywords_check = ["experience", "education", "skills", "projects", "achievement", "summary", "contact"]
    has_structure = sum(1 for kw in keywords_check if kw in resume_text_lower) >= 2
    
    if not is_valid_resume and has_structure and len(text) > 300:
        # Override false negative from AI if the text clearly has resume-like structure
        is_valid_resume = True
        feedback["IsResume"] = True
        if feedback.get("Score") == 0:
            feedback["Score"] = 40 # Give a base score if it was 0

    if not is_valid_resume:
        raise HTTPException(
            status_code=400, 
            detail="The uploaded file does not appear to be a professional resume or CV. Please ensure the file contains your professional experience, education, and skills."
        )
    
    # Use AI detected job title if it's available and the provided one is generic
    ai_detected_title = feedback.get("DetectedJobTitle")
    final_job_title = job_title
    if ai_detected_title and (len(job_title) < 3 or job_title.lower() in ["software", "engineer", "intern", "manager"]):
        final_job_title = ai_detected_title

    # Increment daily count only after successful analysis
    await increment_daily_limit(current["id"], "daily_resume_count")
    
    # Update user status and target job title
    user_id_obj = None
    try:
        user_id_obj = ObjectId(current["id"])
    except:
        user_id_obj = current["id"]

    update_data = {"has_analyzed": True, "target_job_title": final_job_title}
    if feedback.get("Location"):
        update_data["target_location"] = feedback["Location"]

    await users.update_one(
        {"_id": user_id_obj}, 
        {"$set": update_data}
    )

    if consent:
        # Store file in GridFS
        try:
            grid_id = await fs.upload_from_stream(name, file_bytes)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to store file: {e}")
        doc = {
            "resume_id": str(ObjectId()),
            "user_id": current["id"],
            "filename": name,
            "mime_type": mime,
            "consent": consent,
            "file_id": str(grid_id),
            "text": text,
            "job_title": final_job_title,
            "feedback": feedback,
            "status": "pending",
            "tags": feedback.get("Keywords", []),
            "notes": "",
            "created_at": get_malaysia_time(),
        }
        res = await resumes.insert_one(doc)
        return {"id": str(res.inserted_id), "feedback": feedback, "job_title": final_job_title}
    else:
        return {"id": None, "feedback": feedback, "job_title": final_job_title}

@router.post("/manual-upload")
async def manual_upload_profile(
    data: ManualProfileIn,
    current=Depends(get_current_user),
    _: None = Depends(rate_limit),
):
    if current.get("role") != "user":
        raise HTTPException(status_code=403, detail="Only regular users can build profiles")
    
    can_upload, remaining = await check_daily_limit(current["id"], "daily_resume_count", 5)
    if not can_upload:
        raise HTTPException(status_code=429, detail="Daily profile analysis limit reached. Resets at 00:00 Malaysia Time.")

    # Construct virtual resume text
    text = f"""
    TARGET JOB TITLE: {data.jobTitle}
    EXPERIENCE: {data.experience}
    PROFESSIONAL SUMMARY: {data.summary}
    TOP SKILLS: {data.skills}
    KEY ACHIEVEMENT: {data.achievement}
    """
    
    feedback = get_feedback(text)

    # Increment daily count
    await increment_daily_limit(current["id"], "daily_resume_count")
    
    final_job_title = feedback.get("DetectedJobTitle") or data.jobTitle
    
    # We DO NOT store this in the database as per user request
    # We also DO NOT update user document's has_analyzed status permanently
    
    return {"feedback": feedback, "job_title": final_job_title}

@router.get("/my")
async def my_resumes(current=Depends(get_current_user)):
    if current.get("role") != "user":
        raise HTTPException(status_code=403, detail="Only regular users can view their resumes")
    cur = resumes.find({"user_id": current["id"]})
    items = []
    async for r in cur:
        items.append(
            {
                "id": str(r["_id"]),
                "filename": r["filename"],
                "status": r.get("status", "pending"),
                "created_at": r.get("created_at"),
                "tags": r.get("tags", []),
                "feedback": r.get("feedback"),
                "job_title": r.get("job_title", ""),
            }
        )
    return items
