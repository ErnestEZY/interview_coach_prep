from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class UserIn(BaseModel):
    email: EmailStr
    password: str
    name: Optional[str] = None

class ManualProfileIn(BaseModel):
    jobTitle: str
    experience: str
    summary: str
    skills: str
    achievement: str

class User(BaseModel):
    id: str
    email: EmailStr
    password_hash: str
    name: Optional[str] = None
    role: str = "user"
    created_at: datetime
    # Weekly quota for questions
    weekly_question_count: int = 0
    weekly_reset_at: Optional[datetime] = None
    # Daily limits for resume analysis and interview sessions
    daily_resume_count: int = 0
    daily_interview_count: int = 0
    daily_reset_at: Optional[datetime] = None
    # Flags for dashboard state
    has_analyzed: bool = False
    target_job_title: Optional[str] = None

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    is_anomaly: Optional[bool] = False
    admin_emails: Optional[List[str]] = []
    alert_reason: Optional[str] = None

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str
    password: str

class ResumeFeedback(BaseModel):
    advantages: List[str]
    disadvantages: List[str]
    suggestions: List[str]
    keywords: List[str]

class ResumeRecord(BaseModel):
    id: str
    user_id: str
    filename: str
    mime_type: str
    consent: bool
    text: str
    feedback: Optional[ResumeFeedback] = None
    status: str = "pending"
    tags: List[str] = []
    notes: Optional[str] = None
    created_at: datetime

class InterviewTurn(BaseModel):
    role: str
    text: str
    at: datetime

class InterviewSession(BaseModel):
    id: str
    user_id: str
    questions_limit: int
    asked_count: int
    transcript: List[InterviewTurn]
    created_at: datetime
    ended_at: Optional[datetime] = None
