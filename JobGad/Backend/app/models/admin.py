from pydantic import BaseModel
from typing import Optional
from uuid import UUID
from datetime import datetime


class CompanyCreate(BaseModel):
    name: str
    description: Optional[str] = None
    industry: Optional[str] = None
    website: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    address: Optional[str] = None


class CompanyResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str] = None
    industry: Optional[str] = None
    website: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    status: str
    is_verified: bool
    rejection_reason: Optional[str] = None
    created_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class HRProfileCreate(BaseModel):
    company_id: UUID
    job_title: Optional[str] = None
    is_company_admin: Optional[bool] = False


class HRProfileResponse(BaseModel):
    id: UUID
    user_id: UUID
    company_id: UUID
    job_title: Optional[str] = None
    is_company_admin: bool
    status: str
    rejection_reason: Optional[str] = None
    created_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ApprovalAction(BaseModel):
    reason: Optional[str] = None  # Required for rejection


class SuperAdminRegister(BaseModel):
    email: str
    password: str
    full_name: str
    superadmin_secret: str  # Secret key to prevent unauthorized superadmin creation