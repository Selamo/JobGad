from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID
from datetime import datetime


# ─── Job Posting ──────────────────────────────────────────────────────────────

VALID_EMPLOYMENT_TYPES = {"full-time", "part-time", "contract", "internship"}
VALID_JOB_STATUSES = {"draft", "published", "closed"}


class HRJobCreate(BaseModel):
    title: str
    location: Optional[str] = None
    description: str
    requirements: Optional[str] = None
    salary_range: Optional[str] = None
    employment_type: Optional[str] = "full-time"
    department_id: Optional[UUID] = None
    application_deadline: Optional[datetime] = None
    status: Optional[str] = "published"


class HRJobUpdate(BaseModel):
    title: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    requirements: Optional[str] = None
    salary_range: Optional[str] = None
    employment_type: Optional[str] = None
    department_id: Optional[UUID] = None
    application_deadline: Optional[datetime] = None
    status: Optional[str] = None


class HRJobResponse(BaseModel):
    id: UUID
    title: str
    location: Optional[str] = None
    description: str
    requirements: Optional[str] = None
    salary_range: Optional[str] = None
    employment_type: Optional[str] = None
    company_id: Optional[UUID] = None
    department_id: Optional[UUID] = None
    posted_by: Optional[UUID] = None
    application_deadline: Optional[datetime] = None
    status: str
    is_active: bool
    posted_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ─── Application Management ───────────────────────────────────────────────────

class ApplicationStatusUpdate(BaseModel):
    status: str
    hr_notes: Optional[str] = None


class ApplicantInfo(BaseModel):
    id: UUID
    full_name: str
    email: str

    class Config:
        from_attributes = True


class ApplicationResponse(BaseModel):
    id: UUID
    job_id: UUID
    user_id: UUID
    profile_id: UUID
    status: str
    cover_letter: Optional[str] = None
    hr_notes: Optional[str] = None
    applied_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None
    user: Optional[ApplicantInfo] = None

    class Config:
        from_attributes = True


class ApplicationListResponse(BaseModel):
    applications: List[ApplicationResponse]
    total: int