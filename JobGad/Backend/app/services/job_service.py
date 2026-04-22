"""
Job service — CRUD for JobListing records + Pinecone vector lifecycle management.

Recruiter operations: create, update, deactivate (soft-delete), list, get.
Public operations: browse active listings with filtering + pagination.
"""
from uuid import UUID
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi import HTTPException, status

from app.models.job import JobListing
from app.models.user import User
from app.schemas.job import JobCreate, JobUpdate
from app.tools.pinecone_tools import upsert_job_vector, delete_job_vector
from app.tools.scoring_tools import build_job_text


# ─── Public: Browse Listings ──────────────────────────────────────────────────

async def get_job_listings(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    search: Optional[str] = None,
    employment_type: Optional[str] = None,
    location: Optional[str] = None,
) -> tuple[list[JobListing], int]:
    """
    Return paginated active job listings with optional filters.
    Returns (jobs, total_count).
    """
    stmt = select(JobListing).where(JobListing.is_active == True)

    if search:
        term = f"%{search}%"
        stmt = stmt.where(
            JobListing.title.ilike(term) | JobListing.company.ilike(term)
        )
    if employment_type:
        stmt = stmt.where(JobListing.employment_type == employment_type)
    if location:
        stmt = stmt.where(JobListing.location.ilike(f"%{location}%"))

    # Count total before pagination
    count_result = await db.execute(stmt)
    total = len(count_result.scalars().all())

    # Apply ordering + pagination
    stmt = (
        stmt.order_by(JobListing.posted_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    return result.scalars().all(), total


async def get_job_by_id(db: AsyncSession, job_id: UUID) -> JobListing:
    """Fetch a single active job listing by ID."""
    stmt = select(JobListing).where(JobListing.id == job_id, JobListing.is_active == True)
    result = await db.execute(stmt)
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job listing not found.",
        )
    return job


# ─── Recruiter: Manage Listings ───────────────────────────────────────────────

def _require_recruiter(user: User) -> None:
    """Raise 403 if the user is not a recruiter or admin."""
    if user.role not in {"recruiter", "admin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only recruiters can manage job listings.",
        )


async def create_job_listing(
    db: AsyncSession,
    user: User,
    data: JobCreate,
) -> JobListing:
    """
    Create a new job listing (recruiter only).
    The listing is automatically embedded and upserted into Pinecone.
    """
    _require_recruiter(user)

    job = JobListing(
        title=data.title,
        company=data.company,
        location=data.location,
        description=data.description,
        requirements=data.requirements,
        salary_range=data.salary_range,
        employment_type=data.employment_type or "full-time",
        source="recruiter",
        source_url=data.source_url,
        is_active=True,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    # Embed and index in Pinecone
    job_text = build_job_text(job)
    try:
        vector_id = await upsert_job_vector(
            job_id=str(job.id),
            text=job_text,
            metadata={
                "title": job.title,
                "company": job.company or "",
                "location": job.location or "",
                "employment_type": job.employment_type or "",
                "is_active": True,
            },
        )
        job.pinecone_vector_id = vector_id
        await db.commit()
    except Exception:
        # Non-fatal: job is created in DB even if Pinecone indexing fails
        pass

    return job


async def update_job_listing(
    db: AsyncSession,
    user: User,
    job_id: UUID,
    data: JobUpdate,
) -> JobListing:
    """Update a job listing and re-index in Pinecone if content changed."""
    _require_recruiter(user)

    stmt = select(JobListing).where(JobListing.id == job_id)
    result = await db.execute(stmt)
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job listing not found.",
        )

    update_data = data.model_dump(exclude_none=True)
    content_changed = any(
        k in update_data for k in ("title", "description", "requirements", "employment_type")
    )

    for field, value in update_data.items():
        setattr(job, field, value)

    await db.commit()
    await db.refresh(job)

    # Re-index in Pinecone if searchable content changed
    if content_changed and job.is_active:
        job_text = build_job_text(job)
        try:
            await upsert_job_vector(
                job_id=str(job.id),
                text=job_text,
                metadata={
                    "title": job.title,
                    "company": job.company or "",
                    "location": job.location or "",
                    "employment_type": job.employment_type or "",
                    "is_active": job.is_active,
                },
            )
        except Exception:
            pass

    return job


async def deactivate_job_listing(
    db: AsyncSession,
    user: User,
    job_id: UUID,
) -> None:
    """
    Soft-delete a job listing (sets is_active = False).
    Also removes the vector from Pinecone so it won't appear in matches.
    """
    _require_recruiter(user)

    stmt = select(JobListing).where(JobListing.id == job_id)
    result = await db.execute(stmt)
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job listing not found.",
        )

    job.is_active = False
    await db.commit()

    # Remove from Pinecone so it stops appearing in matches
    try:
        await delete_job_vector(str(job_id))
    except Exception:
        pass


# ─── Recruiter: Candidate Search ──────────────────────────────────────────────

async def get_recruiter_listings(
    db: AsyncSession,
    user: User,
    include_inactive: bool = False,
) -> list[JobListing]:
    """Return all job listings posted by recruiter (their company's source='recruiter')."""
    _require_recruiter(user)

    stmt = select(JobListing).where(JobListing.source == "recruiter")
    if not include_inactive:
        stmt = stmt.where(JobListing.is_active == True)

    stmt = stmt.order_by(JobListing.posted_at.desc())
    result = await db.execute(stmt)
    return result.scalars().all()
