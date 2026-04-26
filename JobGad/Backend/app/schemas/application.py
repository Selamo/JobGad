from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID
from datetime import datetime


class JobInfo(BaseModel):
    id: UUID
    title: str
    location: Optional[str] = None
    employment_type: Optional[str] = None
    salary_range: Optional[str] = None
    company_id: Optional[UUID] = None

    class Config:
        from_attributes = True


class GeneratedCVInfo(BaseModel):
    id: UUID
    file_name: Optional[str] = None
    storage_url: Optional[str] = None
    file_format: Optional[str] = None
    generated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ApplicationCreate(BaseModel):
    job_id: UUID
    cover_letter: Optional[str] = None


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
    job: Optional[JobInfo] = None
    generated_cv: Optional[GeneratedCVInfo] = None

    class Config:
        from_attributes = True


class ApplicationListResponse(BaseModel):
    applications: List[ApplicationResponse]
    total: int


class ApplicationStatsResponse(BaseModel):
    total_applications: int
    pending: int
    reviewed: int
    shortlisted: int
    rejected: int
    accepted: int