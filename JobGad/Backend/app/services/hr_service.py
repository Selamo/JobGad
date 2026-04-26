"""
HR Service — job posting and application management for approved HR users.
"""
from uuid import UUID
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status

from app.models.user import User
from app.models.company import HRProfile
from app.models.job import JobListing
from app.models.application import Application, Notification
from app.tools.pinecone_tools import upsert_job_vector, delete_job_vector
from app.tools.scoring_tools import build_job_text


# ─── Permission Helpers ───────────────────────────────────────────────────────

async def _get_approved_hr(db: AsyncSession, user: User) -> HRProfile:
    """
    Get the HR profile for the current user.
    Raises 403 if user is not HR or not yet approved.
    """
    if user.role not in {"hr", "admin", "superadmin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only HR users can perform this action.",
        )

    stmt = select(HRProfile).options(
        selectinload(HRProfile.company),
    ).where(HRProfile.user_id == user.id)
    result = await db.execute(stmt)
    hr_profile = result.scalar_one_or_none()

    if not hr_profile:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have an HR profile. Please register as HR first.",
        )

    if hr_profile.status != "approved":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Your HR account is {hr_profile.status}. "
                   f"Please wait for superadmin approval before posting jobs.",
        )

    if hr_profile.company.status != "approved":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your company is not approved yet. "
                   "Please wait for superadmin approval.",
        )

    return hr_profile


# ─── Job Posting ──────────────────────────────────────────────────────────────

async def hr_create_job(
    db: AsyncSession,
    user: User,
    data: dict,
) -> JobListing:
    """
    HR creates a job listing for their company.
    Automatically indexed in Pinecone for AI matching.
    """
    hr_profile = await _get_approved_hr(db, user)

    # Validate department belongs to HR's company if provided
    if data.get("department_id"):
        from app.models.company import Department
        dept_stmt = select(Department).where(
            Department.id == data["department_id"],
            Department.company_id == hr_profile.company_id,
        )
        dept_result = await db.execute(dept_stmt)
        if not dept_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Department not found in your company.",
            )

    job = JobListing(
        title=data["title"],
        location=data.get("location"),
        description=data["description"],
        requirements=data.get("requirements"),
        salary_range=data.get("salary_range"),
        employment_type=data.get("employment_type", "full-time"),
        company_id=hr_profile.company_id,
        department_id=data.get("department_id"),
        posted_by=user.id,
        application_deadline=data.get("application_deadline"),
        status=data.get("status", "published"),
        source="hr_posted",
        is_active=True,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    # Index in Pinecone for AI matching
    if job.status == "published":
        try:
            job_text = build_job_text(job)
            vector_id = await upsert_job_vector(
                job_id=str(job.id),
                text=job_text,
                metadata={
                    "title": job.title,
                    "company": hr_profile.company.name,
                    "location": job.location or "",
                    "employment_type": job.employment_type or "",
                    "is_active": True,
                },
            )
            job.pinecone_vector_id = vector_id
            await db.commit()
            print(f"[HR Service] Job '{job.title}' indexed in Pinecone")
        except Exception as e:
            print(f"[HR Service] Pinecone indexing failed (non-fatal): {e}")

    return job


async def hr_update_job(
    db: AsyncSession,
    user: User,
    job_id: UUID,
    data: dict,
) -> JobListing:
    """
    HR updates one of their company's job listings.
    Re-indexes in Pinecone if content changes.
    """
    hr_profile = await _get_approved_hr(db, user)

    # Load job and verify it belongs to HR's company
    stmt = select(JobListing).where(
        JobListing.id == job_id,
        JobListing.company_id == hr_profile.company_id,
    )
    result = await db.execute(stmt)
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job listing not found in your company.",
        )

    # Track if content changed for Pinecone re-indexing
    content_fields = {"title", "description", "requirements", "employment_type"}
    content_changed = any(k in data for k in content_fields)

    # Update fields
    for field, value in data.items():
        if value is not None:
            setattr(job, field, value)

    await db.commit()
    await db.refresh(job)

    # Re-index in Pinecone if content changed
    if content_changed and job.is_active and job.status == "published":
        try:
            job_text = build_job_text(job)
            await upsert_job_vector(
                job_id=str(job.id),
                text=job_text,
                metadata={
                    "title": job.title,
                    "company": hr_profile.company.name,
                    "location": job.location or "",
                    "employment_type": job.employment_type or "",
                    "is_active": True,
                },
            )
            print(f"[HR Service] Job '{job.title}' re-indexed in Pinecone")
        except Exception as e:
            print(f"[HR Service] Pinecone re-indexing failed (non-fatal): {e}")

    return job


async def hr_close_job(
    db: AsyncSession,
    user: User,
    job_id: UUID,
) -> JobListing:
    """
    HR closes a job listing — sets status to closed and removes from Pinecone.
    Closed jobs no longer appear in AI matching results.
    """
    hr_profile = await _get_approved_hr(db, user)

    stmt = select(JobListing).where(
        JobListing.id == job_id,
        JobListing.company_id == hr_profile.company_id,
    )
    result = await db.execute(stmt)
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job listing not found in your company.",
        )

    job.status = "closed"
    job.is_active = False
    await db.commit()
    await db.refresh(job)

    # Remove from Pinecone
    try:
        await delete_job_vector(str(job.id))
        print(f"[HR Service] Job '{job.title}' removed from Pinecone")
    except Exception as e:
        print(f"[HR Service] Pinecone deletion failed (non-fatal): {e}")

    return job


async def hr_get_company_jobs(
    db: AsyncSession,
    user: User,
    include_closed: bool = False,
) -> list[JobListing]:
    """
    Get all jobs posted by HR's company.
    """
    hr_profile = await _get_approved_hr(db, user)

    stmt = select(JobListing).where(
        JobListing.company_id == hr_profile.company_id,
    )

    if not include_closed:
        stmt = stmt.where(JobListing.is_active == True)

    stmt = stmt.order_by(JobListing.posted_at.desc())
    result = await db.execute(stmt)
    return result.scalars().all()


async def hr_get_job_applications(
    db: AsyncSession,
    user: User,
    job_id: UUID,
    status_filter: Optional[str] = None,
) -> list[Application]:
    """
    Get all applications for a specific job in HR's company.
    """
    hr_profile = await _get_approved_hr(db, user)

    # Verify job belongs to HR's company
    job_stmt = select(JobListing).where(
        JobListing.id == job_id,
        JobListing.company_id == hr_profile.company_id,
    )
    job_result = await db.execute(job_stmt)
    if not job_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found in your company.",
        )

    stmt = (
        select(Application)
        .where(Application.job_id == job_id)
        .options(
            selectinload(Application.user),
            selectinload(Application.profile),
            selectinload(Application.generated_cv),
        )
        .order_by(Application.applied_at.desc())
    )

    if status_filter:
        stmt = stmt.where(Application.status == status_filter)

    result = await db.execute(stmt)
    return result.scalars().all()


async def hr_update_application_status(
    db: AsyncSession,
    user: User,
    application_id: UUID,
    new_status: str,
    hr_notes: Optional[str] = None,
) -> Application:
    """
    HR updates the status of an application.
    Notifies the applicant via in-app notification and email.
    """
    hr_profile = await _get_approved_hr(db, user)

    valid_statuses = {"reviewed", "shortlisted", "rejected", "accepted"}
    if new_status not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status. Must be one of: {valid_statuses}",
        )

    # Load application with related data
    stmt = (
        select(Application)
        .options(
            selectinload(Application.user),
            selectinload(Application.job),
        )
        .where(Application.id == application_id)
    )
    result = await db.execute(stmt)
    application = result.scalar_one_or_none()

    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found.",
        )

    # Verify job belongs to HR's company
    if application.job.company_id != hr_profile.company_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only manage applications for your company's jobs.",
        )

    # Update status
    old_status = application.status
    application.status = new_status
    application.reviewed_at = datetime.now(timezone.utc)
    application.reviewed_by = user.id
    if hr_notes:
        application.hr_notes = hr_notes

    await db.commit()
    await db.refresh(application)

    # Send in-app notification to applicant
    notification = Notification(
        user_id=application.user_id,
        type="status_changed",
        title="Application Status Updated",
        message=f"Your application for '{application.job.title}' "
                f"at '{hr_profile.company.name}' is now {new_status.upper()}.",
        related_job_id=application.job_id,
        related_application_id=application.id,
    )
    db.add(notification)
    await db.commit()

    # Send email to applicant
    try:
        from app.services.email_service import send_application_status_email
        await send_application_status_email(
            email=application.user.email,
            full_name=application.user.full_name,
            job_title=application.job.title,
            company_name=hr_profile.company.name,
            new_status=new_status,
            hr_notes=hr_notes,
        )
    except Exception as e:
        print(f"[HR Service] Email notification failed (non-fatal): {e}")

    return application


async def hr_get_all_applications(
    db: AsyncSession,
    user: User,
    status_filter: Optional[str] = None,
) -> list[Application]:
    """
    Get ALL applications across all jobs in HR's company.
    """
    hr_profile = await _get_approved_hr(db, user)

    # Get all job IDs for this company
    jobs_stmt = select(JobListing.id).where(
        JobListing.company_id == hr_profile.company_id,
    )
    jobs_result = await db.execute(jobs_stmt)
    job_ids = [row[0] for row in jobs_result.fetchall()]

    if not job_ids:
        return []

    stmt = (
        select(Application)
        .where(Application.job_id.in_(job_ids))
        .options(
            selectinload(Application.user),
            selectinload(Application.job),
            selectinload(Application.profile),
            selectinload(Application.generated_cv),
        )
        .order_by(Application.applied_at.desc())
    )

    if status_filter:
        stmt = stmt.where(Application.status == status_filter)

    result = await db.execute(stmt)
    return result.scalars().all()