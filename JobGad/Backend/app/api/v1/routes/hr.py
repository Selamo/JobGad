"""
HR routes — job posting and application management for approved HR users.
"""
from uuid import UUID
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

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
    """
    Update the status of a job application.

    **Status lifecycle:**
    """