"""
Admin service — superadmin management of companies and HR profiles.
"""
from sqlalchemy.future import select
from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status

from app.models.user import User
from app.models.company import Company, HRProfile
from app.models.application import Notification
from app.services.email_service import send_company_approved_email


# ─── Permission Helpers ───────────────────────────────────────────────────────

def _require_superadmin(user: User) -> None:
    """Raise 403 if user is not a superadmin."""
    if user.role != "superadmin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only superadmins can perform this action.",
        )


def _require_hr_or_admin(user: User) -> None:
    """Raise 403 if user is not HR, admin or superadmin."""
    if user.role not in {"hr", "admin", "superadmin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only HR or admin users can perform this action.",
        )


# ─── Notification Helper ──────────────────────────────────────────────────────

async def _create_notification(
    db: AsyncSession,
    user_id: UUID,
    type: str,
    title: str,
    message: str,
    related_job_id: UUID = None,
    related_application_id: UUID = None,
) -> None:
    """Create a notification for a user."""
    notification = Notification(
        user_id=user_id,
        type=type,
        title=title,
        message=message,
        related_job_id=related_job_id,
        related_application_id=related_application_id,
    )
    db.add(notification)
    await db.commit()


# ─── Company Management ───────────────────────────────────────────────────────

async def get_all_companies(
    db: AsyncSession,
    user: User,
    status_filter: str = None,
) -> list[Company]:
    """Get all companies, optionally filtered by status."""
    _require_superadmin(user)

    stmt = select(Company).options(
        selectinload(Company.creator),
        selectinload(Company.approver),
    )

    if status_filter:
        stmt = stmt.where(Company.status == status_filter)

    stmt = stmt.order_by(Company.created_at.desc())
    result = await db.execute(stmt)
    return result.scalars().all()


async def approve_company(
    db: AsyncSession,
    user: User,
    company_id: UUID,
) -> Company:
    """Superadmin approves a company."""
    _require_superadmin(user)

    stmt = select(Company).where(Company.id == company_id)
    result = await db.execute(stmt)
    company = result.scalar_one_or_none()

    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found.",
        )

    if company.status == "approved":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Company is already approved.",
        )

    company.status = "approved"
    company.approved_by = user.id
    company.approved_at = datetime.now(timezone.utc)
    company.is_verified = True
    await db.commit()
    await db.refresh(company)

    # Notify the company creator
    if company.created_by:
        await _create_notification(
            db=db,
            user_id=company.created_by,
            type="company_approved",
            title="Company Approved!",
            message=f"Your company '{company.name}' has been approved.",
        )

        # Send email
        creator_stmt = select(User).where(User.id == company.created_by)
        creator_result = await db.execute(creator_stmt)
        creator = creator_result.scalar_one_or_none()
        if creator:
            from app.services.email_service import send_company_approved_email
            await send_company_approved_email(
                email=creator.email,
                full_name=creator.full_name,
                company_name=company.name,
            )

    return company


async def reject_company(
    db: AsyncSession,
    user: User,
    company_id: UUID,
    reason: str,
) -> Company:
    """Superadmin rejects a company with a reason."""
    _require_superadmin(user)

    stmt = select(Company).where(Company.id == company_id)
    result = await db.execute(stmt)
    company = result.scalar_one_or_none()

    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found.",
        )

    company.status = "rejected"
    company.approved_by = user.id
    company.approved_at = datetime.now(timezone.utc)
    company.rejection_reason = reason
    await db.commit()
    await db.refresh(company)

    # Notify the company creator
    if company.created_by:
        await _create_notification(
            db=db,
            user_id=company.created_by,
            type="company_rejected",
            title="Company Registration Rejected",
            message=f"Your company '{company.name}' was rejected. Reason: {reason}",
        )

        # Send email
        creator_stmt = select(User).where(User.id == company.created_by)
        creator_result = await db.execute(creator_stmt)
        creator = creator_result.scalar_one_or_none()
        if creator:
            from app.services.email_service import send_company_rejected_email
            await send_company_rejected_email(
                email=creator.email,
                full_name=creator.full_name,
                company_name=company.name,
                reason=reason,
            )

    return company

async def approve_hr_profile(
    db: AsyncSession,
    user: User,
    hr_profile_id: UUID,
) -> HRProfile:
    """Superadmin approves an HR profile."""
    _require_superadmin(user)

    stmt = select(HRProfile).options(
        selectinload(HRProfile.user),
        selectinload(HRProfile.company),
    ).where(HRProfile.id == hr_profile_id)
    result = await db.execute(stmt)
    hr_profile = result.scalar_one_or_none()

    if not hr_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="HR profile not found.",
        )

    if hr_profile.status == "approved":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="HR profile is already approved.",
        )

    hr_profile.status = "approved"
    hr_profile.approved_by = user.id
    hr_profile.approved_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(hr_profile)

    # In-app notification
    await _create_notification(
        db=db,
        user_id=hr_profile.user_id,
        type="hr_approved",
        title="HR Account Approved!",
        message=f"Your HR account for '{hr_profile.company.name}' has been approved.",
    )

    # Send email
    from app.services.email_service import send_hr_approved_email
    await send_hr_approved_email(
        email=hr_profile.user.email,
        full_name=hr_profile.user.full_name,
        company_name=hr_profile.company.name,
    )

    return hr_profile

async def reject_hr_profile(
    db: AsyncSession,
    user: User,
    hr_profile_id: UUID,
    reason: str,
) -> HRProfile:
    """Superadmin rejects an HR profile with a reason."""
    _require_superadmin(user)

    stmt = select(HRProfile).options(
        selectinload(HRProfile.user),
        selectinload(HRProfile.company),
    ).where(HRProfile.id == hr_profile_id)
    result = await db.execute(stmt)
    hr_profile = result.scalar_one_or_none()

    if not hr_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="HR profile not found.",
        )

    hr_profile.status = "rejected"
    hr_profile.approved_by = user.id
    hr_profile.approved_at = datetime.now(timezone.utc)
    hr_profile.rejection_reason = reason
    await db.commit()
    await db.refresh(hr_profile)

    # In-app notification
    await _create_notification(
        db=db,
        user_id=hr_profile.user_id,
        type="hr_rejected",
        title="HR Account Rejected",
        message=f"Your HR account for '{hr_profile.company.name}' was rejected. Reason: {reason}",
    )

    # Send email
    from app.services.email_service import send_hr_rejected_email
    await send_hr_rejected_email(
        email=hr_profile.user.email,
        full_name=hr_profile.user.full_name,
        company_name=hr_profile.company.name,
        reason=reason,
    )

    return hr_profile

# ─── HR Profile Management ────────────────────────────────────────────────────

async def get_all_hr_profiles(
    db: AsyncSession,
    user: User,
    status_filter: str = None,
) -> list[HRProfile]:
    """Get all HR profiles, optionally filtered by status."""
    _require_superadmin(user)

    stmt = select(HRProfile).options(
        selectinload(HRProfile.user),
        selectinload(HRProfile.company),
    )

    if status_filter:
        stmt = stmt.where(HRProfile.status == status_filter)

    stmt = stmt.order_by(HRProfile.created_at.desc())
    result = awai