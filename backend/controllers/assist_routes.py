"""
AI Writing Assist Routes
POST /api/assist/summary         — rewrite a professional summary
POST /api/assist/bullets         — rewrite experience/project bullets
POST /api/assist/manual-field    — rewrite a manual profile form field
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional

from ..core.security import get_current_user
from ..services.assist import improve_summary, improve_bullets, improve_manual_field

router = APIRouter(prefix="/api/assist", tags=["assist"])


# ── Request / Response models ────────────────────────────────────────────────

class SummaryRequest(BaseModel):
    text: str = Field(..., min_length=1)
    job_title: Optional[str] = ""
    char_limit: Optional[int] = 250


class BulletsRequest(BaseModel):
    bullets: List[str] = Field(..., min_items=1)
    role_context: Optional[str] = ""
    section: Optional[str] = "experience"   # "experience" | "projects"
    char_limit: Optional[int] = 250


class ManualFieldRequest(BaseModel):
    field: str = Field(..., pattern="^(summary|skills|achievement)$")
    text: str = Field(..., min_length=1)
    job_title: Optional[str] = ""
    char_limit: Optional[int] = 500


class TextResponse(BaseModel):
    result: str


class BulletsResponse(BaseModel):
    result: List[str]


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/summary", response_model=TextResponse)
async def assist_summary(
    body: SummaryRequest,
    current_user: dict = Depends(get_current_user),
):
    """Improve a professional summary field."""
    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Please write something first before using AI assist.")
    try:
        result = improve_summary(text, body.job_title or "", body.char_limit or 250)
        return {"result": result}
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI assist failed: {str(e)}")


@router.post("/bullets", response_model=BulletsResponse)
async def assist_bullets(
    body: BulletsRequest,
    current_user: dict = Depends(get_current_user),
):
    """Improve experience or project bullet points."""
    bullets = [b.strip() for b in body.bullets if b.strip()]
    if not bullets:
        raise HTTPException(status_code=400, detail="Please write at least one bullet point before using AI assist.")
    try:
        result = improve_bullets(
            bullets,
            body.role_context or "",
            body.section or "experience",
            body.char_limit or 250,
        )
        return {"result": result}
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI assist failed: {str(e)}")


@router.post("/manual-field", response_model=TextResponse)
async def assist_manual_field(
    body: ManualFieldRequest,
    current_user: dict = Depends(get_current_user),
):
    """Improve a manual profile form field (summary, skills, achievement)."""
    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Please write something first before using AI assist.")
    try:
        result = improve_manual_field(
            body.field,
            text,
            body.job_title or "",
            body.char_limit or 500,
        )
        return {"result": result}
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI assist failed: {str(e)}")
