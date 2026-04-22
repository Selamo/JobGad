from pydantic import BaseModel, HttpUrl, field_validator
from typing import Optional, List
from uuid import UUID
from datetime import datetime


# ─── Job Listing ──────────────────────────────────────────────────────────────

VALID_EMPLOYMENT_TYPES = {"full-time", "part-time", "contract", "internship"}


class JobCreate(BaseModel):
    title: str
    company: str
    location: Optional[str] = None
    description: str
    requirements: Optional[str] = None
    salary_range: Optional[str] = None
    employment_type: Optional[str] = "full-time"
    source_url: Optional[str] = None

    @field_validator("employment_type")
    @classmethod
    def validate_employment_type(cls, v):
        if v and v not in VALID_EMPLOYMENT_TYPES:
            raise ValueError(f"employment_type must be one of: {VALID_EMPLOYMENT_TYPES}")
        return v


class JobUpdate(BaseModel):
    title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    requirements: Optional[str] = None
    salary_range: Optional[str] = None
    employment_type: Optional[str] = None
    source_url: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator("employment_type")
    @classmethod
    def validate_employment_type(cls, v):
        if v and v not in VALID_EMPLOYMENT_TYPES:
            raise ValueError(f"employment_type must be one of: {VALID_EMPLOYMENT_TYPES}")
        return v


class JobResponse(BaseModel):
    id: UUID
    title: str
    company: Optional[str] = None
    location: Optional[str] = None
    description: str
    requirements: Optional[str] = None
    salary_range: Optional[str] = None
    employment_type: Optional[str] = None
    source_url: Optional[str] = None
    is_active: bool
    posted_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class JobListResponse(BaseModel):
    jobs: List[JobResponse]
    total: int
    page: int
    page_size: int


# ─── Job Match ────────────────────────────────────────────────────────────────

VALID_MATCH_STATUSES = {"suggested", "saved", "applied", "rejected"}


class JobMatchResponse(BaseModel):
    id: UUID
    job: JobResponse
    similarity_score: float
    match_reason: Optional[str] = None
    status: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class JobMatchStatusUpdate(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        if v not in VALID_MATCH_STATUSES:
            raise ValueError(f"status must be one of: {VALID_MATCH_STATUSES}")
        return v


class JobMatchListResponse(BaseModel):
    matches: List[JobMatchResponse]
    total: int


# ─── Match Explanation ────────────────────────────────────────────────────────

class SkillOverlap(BaseModel):
    matched: List[str]
    missing: List[str]


class MatchExplanation(BaseModel):
    job: JobResponse
    similarity_score: float
    tier: str
    match_reason: str
    skill_overlap: SkillOverlap
