from pydantic import BaseModel, HttpUrl, field_validator
from typing import Optional, List
from uuid import UUID
from datetime import datetime


# ─── Profile ─────────────────────────────────────────────────────────────────

class ProfileCreate(BaseModel):
    headline: Optional[str] = None
    bio: Optional[str] = None
    github_url: Optional[str] = None
    linkedin_url: Optional[str] = None
    portfolio_url: Optional[str] = None
    education_level: Optional[str] = None      # BSc | MSc | HND | PhD
    field_of_study: Optional[str] = None
    institution: Optional[str] = None
    graduation_year: Optional[int] = None
    target_role: Optional[str] = None

class ProfileUpdate(ProfileCreate):
    pass  # Same fields, all optional


# ─── Skills ──────────────────────────────────────────────────────────────────

class SkillCreate(BaseModel):
    name: str
    category: Optional[str] = None      # technical | soft | tool | domain
    proficiency: Optional[str] = None   # beginner | intermediate | advanced | expert

    @field_validator("category")
    @classmethod
    def validate_category(cls, v):
        allowed = {"technical", "soft", "tool", "domain", None}
        if v not in allowed:
            raise ValueError(f"category must be one of: {allowed - {None}}")
        return v

    @field_validator("proficiency")
    @classmethod
    def validate_proficiency(cls, v):
        allowed = {"beginner", "intermediate", "advanced", "expert", None}
        if v not in allowed:
            raise ValueError(f"proficiency must be one of: {allowed - {None}}")
        return v

class SkillResponse(BaseModel):
    id: UUID
    name: str
    category: Optional[str] = None
    proficiency: Optional[str] = None
    source: Optional[str] = None
    confidence: Optional[float] = None

    class Config:
        from_attributes = True


# ─── Profile Response ─────────────────────────────────────────────────────────

class ProfileResponse(BaseModel):
    id: UUID
    user_id: UUID
    headline: Optional[str] = None
    bio: Optional[str] = None
    github_url: Optional[str] = None
    linkedin_url: Optional[str] = None
    portfolio_url: Optional[str] = None
    education_level: Optional[str] = None
    field_of_study: Optional[str] = None
    institution: Optional[str] = None
    graduation_year: Optional[int] = None
    target_role: Optional[str] = None
    iri_score: Optional[float] = None
    profile_completeness: Optional[float] = None
    skills: List[SkillResponse] = []
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ─── Documents ───────────────────────────────────────────────────────────────

class DocumentResponse(BaseModel):
    id: UUID
    type: str
    file_name: Optional[str] = None
    storage_url: Optional[str] = None
    processing_status: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class DocumentListResponse(BaseModel):
    documents: List[DocumentResponse]
    total: int