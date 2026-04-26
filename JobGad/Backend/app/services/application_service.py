"""
Application Service — graduates apply for jobs and track their applications.
"""
from uuid import UUID
from typing import Optional
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status

from app.models.user import User
from app.models.job import JobListing
from app.models.profile import Profile
from app.models.application import Application, Notification
from app.models.company import HRProfile


# ─── Helpers ──────────────────────────────────────────────────────────────────

async def _get_graduate_profile(db: AsyncSession, user: User) -> Profile:
    """Get the graduate's profile or raise 404."""
    stmt = (
        select(Profile)
        .where(Profile.user_id == user.id)
        .options(selectinload(Profile.skills))
    )
    result = await db.execute(stmt)
    profile = result.scalar_one_or_none()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found. Please create a profile first.",
        )
    return profile


async def _get_hr_for_job(
    db: AsyncSession,
    job: JobListing,
) -> HRProfile | None:
    """Get the HR profile for the company that posted this job."""
    if not job.company_id:
        return None

    stmt = select(HRProfile).where(
        HRProfile.company_id == job.company_id,
        HRProfile.is_company_admin == True,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


# ─── Apply for a Job ──────────────────────────────────────────────────────────

async def apply_for_job(
    db: AsyncSession,
    user: User,
    job_id: UUID,
    cover_letter: Optional[str] = None,
) -> Application:
    """
    Graduate applies for a job.
    - Checks job is active
    - Checks graduate has a profile
    - Checks not already applied
    - Creates application record
    - Notifies HR via in-app + email
    """
    # Get the job
    stmt = select(JobListing).where(
        JobListing.id == job_id,
        JobListing.is_active == True,
    )
    result = await db.execute(stmt)
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job listing not found or no longer active.",
        )

    if job.status == "closed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This job is no longer accepting applications.",
        )

    # Check deadline
    if job.application_deadline and job.application_deadline < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The application deadline for this job has passed.",
        )

    # Get graduate profile
    profile = await _get_graduate_profile(db, user)

    # Check not already applied
    existing_stmt = select(Application).where(
        Application.job_id == job_id,
        Application.user_id == user.id,
    )
    existing_result = await db.execute(existing_stmt)
    if existing_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You have already applied for this job.",
        )

    # Create application
    application = Application(
        job_id=job_id,
        user_id=user.id,
        profile_id=profile.id,
        cover_letter=cover_letter,
        status="pending",
    )
    db.add(application)
    await db.commit()
    await db.refresh(application)

    # Notify HR — in-app notification
    hr_profile = await _get_hr_for_job(db, job)
    if hr_profile:
        notification = Notification(
            user_id=hr_profile.user_id,
            type="application_received",
            title="New Job Application Received",
            message=f"{user.full_name} has applied for '{job.title}'.",
            related_job_id=job_id,
            related_application_id=application.id,
        )
        db.add(notification)
        await db.commit()

        # Send email to HR
        try:
            from app.services.email_service import send_application_received_email
            from app.models.user import User as UserModel
            hr_user_stmt = select(UserModel).where(
                UserModel.id == hr_profile.user_id
            )
            hr_user_result = await db.execute(hr_user_stmt)
            hr_user = hr_user_result.scalar_one_or_none()

            if hr_user:
                from app.models.company import Company
                company_stmt = select(Company).where(
                    Company.id == job.company_id
                )
                company_result = await db.execute(company_stmt)
                company = company_result.scalar_one_or_none()

                await send_application_received_email(
                    hr_email=hr_user.email,
                    hr_name=hr_user.full_name,
                    applicant_name=user.full_name,
                    job_title=job.title,
                    company_name=company.name if company else "Your Company",
                    application_id=str(application.id),
                )
        except Exception as e:
            print(f"[Application Service] HR email failed (non-fatal): {e}")

    # Notify graduate — confirmation
    grad_notification = Notification(
        user_id=user.id,
        type="application_submitted",
        title="Application Submitted Successfully",
        message=f"Your application for '{job.title}' has been submitted. "
                f"You will be notified of any updates.",
        related_job_id=job_id,
        related_application_id=application.id,
    )
    db.add(grad_notification)
    await db.commit()

    return application


# ─── Get My Applications ──────────────────────────────────────────────────────

async def get_my_applications(
    db: AsyncSession,
    user: User,
    status_filter: Optional[str] = None,
) -> list[Application]:
    """Get all applications submitted by the current graduate."""
    stmt = (
        select(Application)
        .where(Application.user_id == user.id)
        .options(
            selectinload(Application.job),
            selectinload(Application.generated_cv),
        )
        .order_by(Application.applied_at.desc())
    )

    if status_filter:
        stmt = stmt.where(Application.status == status_filter)

    result = await db.execute(stmt)
    return result.scalars().all()


async def get_application_detail(
    db: AsyncSession,
    user: User,
    application_id: UUID,
) -> Application:
    """Get a single application detail for the current graduate."""
    stmt = (
        select(Application)
        .where(
            Application.id == application_id,
            Application.user_id == user.id,
        )
        .options(
            selectinload(Application.job),
            selectinload(Application.generated_cv),
        )
    )
    result = await db.execute(stmt)
    application = result.scalar_one_or_none()

    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found.",
        )
    return application


# ─── Withdraw Application ─────────────────────────────────────────────────────

async def withdraw_application(
    db: AsyncSession,
    user: User,
    application_id: UUID,
) -> dict:
    """
    Graduate withdraws their application.
    Only pending or reviewed applications can be withdrawn.
    """
    stmt = select(Application).where(
        Application.id == application_id,
        Application.user_id == user.id,
    )
    result = await db.execute(stmt)
    application = result.scalar_one_or_none()

    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found.",
        )

    if application.status in {"shortlisted", "accepted"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot withdraw an application that is already {application.status}. "
                   f"Please contact HR directly.",
        )

    await db.delete(application)
    await db.commit()

    return {"message": "Application withdrawn successfully."}


# ─── Application Stats ────────────────────────────────────────────────────────

async def get_my_application_stats(
    db: AsyncSession,
    user: User,
) -> dict:
    """Get application statistics for the current graduate."""
    from sqlalchemy import func

    stmt = select(
        Application.status,
        func.count(Application.id)
    ).where(
        Application.user_id == user.id
    ).group_by(Application.status)

    result = await db.execute(stmt)
    stats = {row[0]: row[1] for row in result.fetchall()}

    total = sum(stats.values())

    return {
        "total_applications": total,
        "pending": stats.get("pending", 0),
        "reviewed": stats.get("reviewed", 0),
        "shortlisted": stats.get("shortlisted", 0),
        "rejected": stats.get("rejected", 0),
        "accepted": stats.get("accepted", 0),
    }