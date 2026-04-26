"""
Applications routes — graduates apply for jobs and track their applications.
"""
from uuid import UUID
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.v1.dependencies import get_current_user
from app.models.user import User
from app.schemas.application import (
    ApplicationCreate,
    ApplicationResponse,
    ApplicationListResponse,
    ApplicationStatsResponse,
)
from app.services.application_service import (
    apply_for_job,
    get_my_applications,
    get_application_detail,
    withdraw_application,
    get_my_application_stats,
)

router = APIRouter()


@router.post(
    "/",
    response_model=ApplicationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Apply for a job",
)
async def apply(
    data: ApplicationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Apply for a job listing.

    Requirements:
    - You must have a profile created
    - The job must be active and not closed
    - You can only apply once per job

    After applying:
    - HR is notified via in-app notification and email
    - You receive a confirmation notification
    - Track your application status via GET /applications
    """
    return await apply_for_job(
        db,
        current_user,
        data.job_id,
        data.cover_letter,
    )


@router.get(
    "/",
    response_model=ApplicationListResponse,
    summary="Get all my job applications",
)
async def list_my_applications(
    status_filter: Optional[str] = Query(
        default=None,
        description="Filter by status: pending | reviewed | shortlisted | rejected | accepted",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get all your job applications with their current status.

    Status lifecycle:

"""
    applications = await get_my_applications(
        db, current_user, status_filter,
    )
    return ApplicationListResponse(
        applications=applications,
        total=len(applications),
    )


@router.get(
    "/stats",
    response_model=ApplicationStatsResponse,
    summary="Get my application statistics",
)
async def get_application_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get a summary of all your applications by status.
    Useful for tracking your job search progress.
    """
    return await get_my_application_stats(db, current_user)


@router.get(
    "/{application_id}",
    response_model=ApplicationResponse,
    summary="Get a specific application detail",
)
async def get_application(
    application_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the full details of a specific application including HR notes."""
    return await get_application_detail(db, current_user, application_id)


@router.delete(
    "/{application_id}",
    status_code=status.HTTP_200_OK,
    summary="Withdraw a job application",
)
async def withdraw(
    application_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Withdraw a pending or reviewed application.
    You cannot withdraw applications that are already shortlisted or accepted.
    """
    return await withdraw_application(db, current_user, application_id)