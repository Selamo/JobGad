"""
Admin routes — superadmin management of companies, HR profiles, and users.
"""
from uuid import UUID
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.database import get_db
from app.core.config import settings
from app.core.security import get_password_hash
from app.api.v1.dependencies import get_current_user
from app.models.user import User
from app.models.company import Company, HRProfile
from app.schemas.admin import (
    CompanyCreate,
    CompanyResponse,
    HRProfileCreate,
    HRProfileResponse,
    ApprovalAction,
    SuperAdminRegister,
)
from app.services.admin_service import (
    get_all_companies,
    approve_company,
    reject_company,
    get_all_hr_profiles,
    approve_hr_profile,
    reject_hr_profile,
    get_admin_dashboard,
)

router = APIRouter()

# ─── Superadmin Registration ──────────────────────────────────────────────────

@router.post(
    "/register",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    summary="Register a superadmin account",
)
async def register_superadmin(
    data: SuperAdminRegister,
    db: AsyncSession = Depends(get_db),
):
    """
    Register a superadmin account.
    Requires a secret key set in your .env file as SUPERADMIN_SECRET.
    This prevents unauthorized superadmin creation.
    """
    # Verify secret key
    if data.superadmin_secret != settings.SUPERADMIN_SECRET:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid superadmin secret key.",
        )

    # Check if email already exists
    stmt = select(User).where(User.email == data.email)
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered.",
        )

    # Create superadmin user
    superadmin = User(
        email=data.email,
        full_name=data.full_name,
        hashed_password=get_password_hash(data.password),
        role="superadmin",
        is_active=True,
        is_verified=True,
    )
    db.add(superadmin)
    await db.commit()
    await db.refresh(superadmin)

    return {
        "message": "Superadmin account created successfully.",
        "email": superadmin.email,
        "role": superadmin.role,
    }


# ─── Dashboard ────────────────────────────────────────────────────────────────

@router.get(
    "/dashboard",
    summary="Get superadmin dashboard statistics",
)
async def admin_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Overview stats — users, companies, HR profiles, jobs, applications."""
    return await get_admin_dashboard(db, current_user)


# ─── Company Management ───────────────────────────────────────────────────────

@router.post(
    "/companies",
    response_model=CompanyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new company",
)
async def register_company(
    data: CompanyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Register a new company in the system.
    Can be done by superadmin or by an HR user on behalf of their company.
    Company starts with status=pending until superadmin approves it.
    """
    # Check if company name already exists
    stmt = select(Company).where(Company.name == data.name)
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A company with this name already exists.",
        )

    company = Company(
        name=data.name,
        description=data.description,
        industry=data.industry,
        website=data.website,
        city=data.city,
        country=data.country,
        address=data.address,
        created_by=current_user.id,
        # Superadmins get auto-approved
        status="approved" if current_user.role == "superadmin" else "pending",
        is_verified=current_user.role == "superadmin",
    )
    db.add(company)
    await db.commit()
    await db.refresh(company)

    return company


@router.get(
    "/companies",
    response_model=list[CompanyResponse],
    summary="[Superadmin] List all companies",
)
async def list_companies(
    status_filter: Optional[str] = Query(
        default=None,
        description="Filter by status: pending | approved | rejected"
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all registered companies with optional status filter."""
    return await get_all_companies(db, current_user, status_filter)


@router.patch(
    "/companies/{company_id}/approve",
    response_model=CompanyResponse,
    summary="[Superadmin] Approve a company",
)
async def approve_company_endpoint(
    company_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Approve a pending company registration."""
    return await approve_company(db, current_user, company_id)


@router.patch(
    "/companies/{company_id}/reject",
    response_model=CompanyResponse,
    summary="[Superadmin] Reject a company",
)
async def reject_company_endpoint(
    company_id: UUID,
    data: ApprovalAction,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Reject a company registration with a reason."""
    if not data.reason:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A rejection reason is required.",
        )
    return await reject_company(db, current_user, company_id, data.reason)


# ─── HR Profile Management ────────────────────────────────────────────────────

@router.post(
    "/hr-profiles",
    response_model=HRProfileResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register as HR for a company",
)
async def register_hr_profile(
    data: HRProfileCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Register the current user as HR for a specific company.
    The company must be approved first.
    HR profile starts as pending until superadmin approves it.
    """
    # Check company exists and is approved
    stmt = select(Company).where(Company.id == data.company_id)
    result = await db.execute(stmt)
    company = result.scalar_one_or_none()

    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found.",
        )

    if company.status != "approved":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Company is not approved yet. Wait for superadmin approval.",
        )

    # Check if user already has an HR profile
    stmt = select(HRProfile).where(HRProfile.user_id == current_user.id)
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You already have an HR profile.",
        )

    hr_profile = HRProfile(
        user_id=current_user.id,
        company_id=data.company_id,
        job_title=data.job_title,
        is_company_admin=data.is_company_admin or False,
        status="pending",
    )
    db.add(hr_profile)

    # Update user role to hr
    current_user.role = "hr"
    await db.commit()
    await db.refresh(hr_profile)

    return hr_profile


@router.get(
    "/hr-profiles",
    response_model=list[HRProfileResponse],
    summary="[Superadmin] List all HR profiles",
)
async def list_hr_profiles(
    status_filter: Optional[str] = Query(
        default=None,
        description="Filter by status: pending | approved | rejected"
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all HR profiles with optional status filter."""
    return await get_all_hr_profiles(db, current_user, status_filter)


@router.patch(
    "/hr-profiles/{hr_profile_id}/approve",
    response_model=HRProfileResponse,
    summary="[Superadmin] Approve an HR profile",
)
async def approve_hr_endpoint(
    hr_profile_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Approve a pending HR profile so they can start posting jobs."""
    return await approve_hr_profile(db, current_user, hr_profile_id)


@router.patch(
    "/hr-profiles/{hr_profile_id}/reject",
    response_model=HRProfileResponse,
    summary="[Superadmin] Reject an HR profile",
)
async def reject_hr_endpoint(
    hr_profile_id: UUID,
    data: ApprovalAction,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Reject an HR profile with a reason."""
    if not data.reason:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A rejection reason is required.",
        )
    return await reject_hr_profile(db, current_user, hr_profile_id, data.reason)