"""
Admin service — superadmin management of companies and HR profiles.
"""
from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status

from app.models.user import User
from app.models.company import Company, HRProfile
from app.models.application import Notification


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
            message=f"Your company '{company.name}' has been approved by the admin. You can now post jobs.",
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

    return company


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