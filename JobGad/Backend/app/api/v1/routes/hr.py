"""
HR routes — job posting and application management for approved HR users.
"""
from uuid import UUID
from typing import Optional

from fastapi import APIRouter, Depends, Query, status, HTTPException
from sqlalchemy.future import select
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func
from app.core.database import get_db
from app.api.v1.dependencies import get_current_user
from app.models.user import User
from app.schemas.hr import (
    HRJobCreate,
    HRJobUpdate,
    HRJobResponse,
    ApplicationStatusUpdate,
    ApplicationResponse,
    ApplicationListResponse,
)
from app.services.hr_service import (
    hr_create_job,
    hr_update_job,
    hr_close_job,
    hr_get_company_jobs,
    hr_get_job_applications,
    hr_update_application_status,
    hr_get_all_applications,
    hr_update_job,
    _get_approved_hr
)

router = APIRouter()


# ─── Job Management ───────────────────────────────────────────────────────────

@router.post(
    "/jobs",
    response_model=HRJobResponse,
    status_code=status.HTTP_201_CREATED,
    summary="[HR] Post a new job for your company",
)
async def post_job(
    data: HRJobCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Post a new job listing for your company.

    Requirements:
    - You must have an approved HR profile
    - Your company must be approved by superadmin
    - Job is automatically indexed in Pinecone for AI matching

    Status options:
    - **draft** — saved but not visible to graduates yet
    - **published** — live and appearing in job matches
    """
    return await hr_create_job(db, current_user, data.model_dump())


@router.put(
    "/jobs/{job_id}",
    response_model=HRJobResponse,
    summary="[HR] Update a job listing",
)
async def update_job(
    job_id: UUID,
    data: HRJobUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update any fields of a job listing in your company.
    If content changes, the job is automatically re-indexed in Pinecone.
    """
    return await hr_update_job(
        db, current_user, job_id,
        data.model_dump(exclude_none=True),
    )


@router.patch(
    "/jobs/{job_id}/close",
    response_model=HRJobResponse,
    summary="[HR] Close a job listing",
)
async def close_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Close a job listing.
    Closed jobs are removed from AI matching and no longer accept applications.
    """
    return await hr_close_job(db, current_user, job_id)


@router.get(
    "/jobs",
    response_model=list[HRJobResponse],
    summary="[HR] Get all jobs for your company",
)
async def get_company_jobs(
    include_closed: bool = Query(
        default=False,
        description="Include closed job listings",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get all job listings posted by your company.
    Optionally include closed listings.
    """
    return await hr_get_company_jobs(db, current_user, include_closed)


# ─── Application Management ───────────────────────────────────────────────────

@router.get(
    "/applications",
    response_model=ApplicationListResponse,
    summary="[HR] Get all applications across all company jobs",
)
async def get_all_applications(
    status_filter: Optional[str] = Query(
        default=None,
        description="Filter by status: pending | reviewed | shortlisted | rejected | accepted",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get all applications received across all jobs in your company.
    Filter by status to manage your pipeline efficiently.
    """
    applications = await hr_get_all_applications(
        db, current_user, status_filter,
    )
    return ApplicationListResponse(
        applications=applications,
        total=len(applications),
    )


@router.get(
    "/jobs/{job_id}/applications",
    response_model=ApplicationListResponse,
    summary="[HR] Get all applications for a specific job",
)
async def get_job_applications(
    job_id: UUID,
    status_filter: Optional[str] = Query(
        default=None,
        description="Filter by status: pending | reviewed | shortlisted | rejected | accepted",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get all applications for a specific job listing in your company.
    """
    applications = await hr_get_job_applications(
        db, current_user, job_id, status_filter,
    )
    return ApplicationListResponse(
        applications=applications,
        total=len(applications),
    )


@router.patch(
    "/applications/{application_id}/status",
    response_model=ApplicationResponse,
    summary="[HR] Update application status",
)
async def update_application_status(
    application_id: UUID,
    data: ApplicationStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update the status of an application (reviewed, shortlisted, rejected, accepted)."""
    return await hr_update_application_status(
        db=db,
        user=current_user,
        application_id=application_id,
        new_status=data.status,
        hr_notes=data.hr_notes,
    )


@router.patch(
    "/jobs/{job_id}",
    response_model=HRJobResponse,
    summary="[HR] Edit a job listing",
)
async def edit_job(
    job_id: UUID,
    data: HRJobUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update an existing job listing. Only the posting company's HR can edit."""
    return await hr_update_job(db, current_user, job_id, data.model_dump(exclude_unset=True))

@router.get(
    "/applications/{application_id}/applicant",
    summary="[HR] View full applicant profile",
)
async def get_applicant_profile(
    application_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the full profile of a graduate who applied to your job."""
    from sqlalchemy.orm import selectinload
    from app.models.application import Application
    from app.models.profile import Profile, Skill
    from app.models.coaching import Iriscore

    hr_profile = await _get_approved_hr(db, current_user)

    # Load application with all relationships
    stmt = (
        select(Application)
        .options(
            selectinload(Application.user),
            selectinload(Application.profile).selectinload(Profile.skills),
            selectinload(Application.job),
            selectinload(Application.generated_cv),
        )
        .where(Application.id == application_id)
    )
    result = await db.execute(stmt)
    application = result.scalar_one_or_none()

    if not application:
        raise HTTPException(status_code=404, detail="Application not found.")

    # Verify job belongs to HR's company
    if application.job.company_id != hr_profile.company_id:
        raise HTTPException(status_code=403, detail="Access denied.")

    user = application.user
    profile = application.profile

    # Get latest IRI score
    iri_stmt = (
        select(Iriscore)
        .where(Iriscore.user_id == user.id)
        .order_by(Iriscore.snapshot_at.desc())
        .limit(1)
    )
    iri_result = await db.execute(iri_stmt)
    latest_iri = iri_result.scalar_one_or_none()

    # Get completed coaching sessions count
    from app.models.coaching import CoachingSession
    sessions_stmt = select(func.count(CoachingSession.id)).where(
        CoachingSession.user_id == user.id,
        CoachingSession.status == "completed",
    )
    sessions_result = await db.execute(sessions_stmt)
    sessions_count = sessions_result.scalar() or 0

    return {
        "application": {
            "id": str(application.id),
            "status": application.status,
            "cover_letter": application.cover_letter,
            "applied_at": str(application.applied_at),
            "hr_notes": application.hr_notes,
        },
        "user": {
            "id": str(user.id),
            "full_name": user.full_name,
            "email": user.email,
        },
        "profile": {
            "headline": profile.headline if profile else None,
            "bio": profile.bio if profile else None,
            "education_level": profile.education_level if profile else None,
            "field_of_study": profile.field_of_study if profile else None,
            "institution": profile.institution if profile else None,
            "graduation_year": profile.graduation_year if profile else None,
            "target_role": profile.target_role if profile else None,
            "github_url": profile.github_url if profile else None,
            "linkedin_url": profile.linkedin_url if profile else None,
            "profile_completeness": profile.profile_completeness if profile else 0,
            "skills": [
                {
                    "name": s.name,
                    "category": s.category,
                    "proficiency": s.proficiency,
                }
                for s in (profile.skills if profile else [])
            ],
        },
        "iri": {
            "overall_score": latest_iri.overall_score if latest_iri else 0,
            "communication": latest_iri.communication if latest_iri else 0,
            "technical_accuracy": latest_iri.technical_accuracy if latest_iri else 0,
            "confidence": latest_iri.confidence if latest_iri else 0,
            "structure": latest_iri.structure if latest_iri else 0,
            "total_sessions": sessions_count,
        },
        "generated_cv": {
            "id": str(application.generated_cv.id),
            "file_name": application.generated_cv.file_name,
            "file_format": application.generated_cv.file_format,
        } if application.generated_cv else None,
    }