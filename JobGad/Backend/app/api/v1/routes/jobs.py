"""
Jobs router — two distinct areas:
  1. Job listings  → public browsing + recruiter management
  2. Job matching  → semantic search + match status tracking
"""
from uuid import UUID
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.v1.dependencies import get_current_user
from app.models.user import User
from app.schemas.job import (
    JobCreate,
    JobUpdate,
    JobResponse,
    JobListResponse,
    JobMatchResponse,
    JobMatchListResponse,
    JobMatchStatusUpdate,
    MatchExplanation,
)
from app.services.job_service import (
    get_job_listings,
    get_job_by_id,
    create_job_listing,
    update_job_listing,
    deactivate_job_listing,
    get_recruiter_listings,
)
from app.services.matching_service import (
    run_job_matching,
    get_my_matches,
    update_match_status,
    explain_match,
)

router = APIRouter()


# ═══════════════════════════════════════════════════════════════════════════════
# JOB LISTINGS  (public browsing + recruiter management)
# ═══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/listings",
    response_model=JobListResponse,
    summary="Browse all active job listings",
)
async def list_job_listings(
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Results per page"),
    search: Optional[str] = Query(default=None, description="Search by title or company"),
    employment_type: Optional[str] = Query(
        default=None,
        description="Filter by type: full-time | part-time | contract | internship",
    ),
    location: Optional[str] = Query(default=None, description="Filter by location keyword"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Browse all active job listings with optional filters and pagination.

    This endpoint is available to all authenticated users (graduates and recruiters).
    """
    jobs, total = await get_job_listings(
        db,
        page=page,
        page_size=page_size,
        search=search,
        employment_type=employment_type,
        location=location,
    )
    return JobListResponse(jobs=jobs, total=total, page=page, page_size=page_size)


@router.get(
    "/listings/{job_id}",
    response_model=JobResponse,
    summary="Get a single job listing by ID",
)
async def get_job_detail(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve the full details of a single active job listing."""
    return await get_job_by_id(db, job_id)


@router.post(
    "/listings",
    response_model=JobResponse,
    status_code=status.HTTP_201_CREATED,
    summary="[Recruiter] Create a new job listing",
)
async def create_listing(
    data: JobCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a new job listing. **Recruiter or Admin role required.**

    The listing is automatically embedded and indexed in Pinecone
    so it appears in graduate job-matching results immediately.
    """
    return await create_job_listing(db, current_user, data)


@router.put(
    "/listings/{job_id}",
    response_model=JobResponse,
    summary="[Recruiter] Update a job listing",
)
async def update_listing(
    job_id: UUID,
    data: JobUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update any fields of a job listing. **Recruiter or Admin role required.**

    If content fields (title, description, requirements) change, the
    Pinecone vector is automatically re-indexed.
    """
    return await update_job_listing(db, current_user, job_id, data)


@router.delete(
    "/listings/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="[Recruiter] Deactivate a job listing",
)
async def deactivate_listing(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Soft-delete a job listing (sets `is_active = False`).
    **Recruiter or Admin role required.**

    The vector is removed from Pinecone so the job stops appearing
    in semantic match results.
    """
    await deactivate_job_listing(db, current_user, job_id)


@router.get(
    "/my-listings",
    response_model=JobListResponse,
    summary="[Recruiter] Get my posted listings",
)
async def get_my_listings(
    include_inactive: bool = Query(default=False, description="Include deactivated listings"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return all job listings posted by the authenticated recruiter.
    **Recruiter or Admin role required.**
    """
    jobs = await get_recruiter_listings(db, current_user, include_inactive=include_inactive)
    return JobListResponse(jobs=jobs, total=len(jobs), page=1, page_size=len(jobs) or 1)


# ═══════════════════════════════════════════════════════════════════════════════
# JOB MATCHING  (semantic AI-powered matching + tracking)
# ═══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/matches/run",
    response_model=JobMatchListResponse,
    summary="Run AI semantic job matching for my profile",
)
async def run_matching(
    top_k: int = Query(default=10, ge=1, le=50, description="Number of matches to return"),
    employment_type: Optional[str] = Query(
        default=None,
        description="Filter matches by job type: full-time | part-time | contract | internship",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Run **AI-powered semantic job matching** for the authenticated user.

    Uses the user's profile (skills, bio, headline, target role) to find
    the most relevant job listings via Pinecone vector search.

    - Results are ranked by cosine similarity
    - Each match is persisted with a score and human-readable explanation
    - Calling this again refreshes scores for existing matches
    """
    matches = await run_job_matching(
        db,
        current_user,
        top_k=top_k,
        employment_type=employment_type,
    )
    return JobMatchListResponse(matches=matches, total=len(matches))


@router.get(
    "/matches",
    response_model=JobMatchListResponse,
    summary="Get my current job matches",
)
async def list_my_matches(
    match_status: Optional[str] = Query(
        default=None,
        description="Filter by status: suggested | saved | applied | rejected",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieve previously computed job matches for the authenticated user.

    Filter by `match_status` to view only saved jobs, applications, etc.
    Run `POST /jobs/matches/run` first to generate initial matches.
    """
    matches = await get_my_matches(db, current_user, status_filter=match_status)
    return JobMatchListResponse(matches=matches, total=len(matches))


@router.patch(
    "/matches/{match_id}/status",
    response_model=JobMatchResponse,
    summary="Update the status of a job match",
)
async def update_job_match_status(
    match_id: UUID,
    data: JobMatchStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update the tracking status of a job match.

    **Status lifecycle:**
    ```
    suggested → saved → applied
                      → rejected
    ```

    - `suggested` — AI-recommended (default)
    - `saved`     — user bookmarked this job
    - `applied`   — user has applied
    - `rejected`  — user dismissed this match
    """
    return await update_match_status(db, current_user, match_id, data.status)


@router.get(
    "/matches/{job_id}/explain",
    response_model=MatchExplanation,
    summary="Get a detailed explanation for a job match",
)
async def explain_job_match(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get a detailed, human-readable explanation for why a specific job was matched
    to the user's profile.

    Returns:
    - **tier** — Excellent / Strong / Good / Partial / Weak Match
    - **similarity_score** — raw cosine similarity (0.0 – 1.0)
    - **match_reason** — plain English explanation
    - **skill_overlap** — matched skills + skills to develop
    """
    return await explain_match(db, current_user, job_id)
