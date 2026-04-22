"""
Matching service — semantic job matching using Pinecone vector search.

Flow:
  1. Build a text representation of the user's profile (skills, bio, target role, etc.)
  2. Query Pinecone for the most similar job vectors
  3. Load the matching JobListing rows from Postgres
  4. Upsert JobMatch records with similarity scores and match_reason text
  5. Return the ranked matches to the caller
"""
from uuid import UUID
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy.dialects.postgresql import insert as pg_insert
from fastapi import HTTPException, status

from app.models.job import JobListing, JobMatch
from app.models.profile import Profile
from app.models.user import User
from app.tools.pinecone_tools import query_similar_jobs, upsert_profile_vector
from app.tools.scoring_tools import (
    build_profile_text,
    build_match_reason,
    find_skill_overlap,
    score_to_tier,
)
from app.services.profile_service import _get_profile_or_404


# ─── Helpers ──────────────────────────────────────────────────────────────────

async def _load_profile_with_skills(db: AsyncSession, user: User) -> Profile:
    """Load the user's profile with skills eagerly loaded."""
    return await _get_profile_or_404(db, user)


# ─── Core Matching ────────────────────────────────────────────────────────────

async def run_job_matching(
    db: AsyncSession,
    user: User,
    top_k: int = 10,
    employment_type: Optional[str] = None,
) -> list[JobMatch]:
    """
    Run semantic job matching for the current user and persist results.

    Steps:
      1. Load profile + skills
      2. Embed profile text → query Pinecone
      3. Load matched JobListing rows from DB
      4. Upsert JobMatch rows (score + reason)
      5. Return list of JobMatch objects (with job eagerly loaded)
    """
    profile = await _load_profile_with_skills(db, user)

    # Build embeddable text from profile data
    profile_text = build_profile_text(profile)
    if not profile_text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Your profile is too sparse to run job matching. "
                   "Please add your skills, headline, and bio first.",
        )

    # Also upsert/update the profile vector in Pinecone
    await upsert_profile_vector(str(profile.id), profile_text)

    # Build Pinecone filter (only active jobs, optionally by type)
    pinecone_filter: dict = {"is_active": True}
    if employment_type:
        pinecone_filter["employment_type"] = employment_type

    # Semantic search
    pinecone_results = await query_similar_jobs(
        profile_text=profile_text,
        top_k=top_k,
        filter=pinecone_filter,
    )

    if not pinecone_results:
        return []

    # Extract job UUIDs from Pinecone vector IDs ("job_<uuid>")
    job_ids = []
    score_map = {}
    for r in pinecone_results:
        raw_id = r["id"].removeprefix("job_")
        try:
            job_uuid = UUID(raw_id)
            job_ids.append(job_uuid)
            score_map[job_uuid] = r["score"]
        except ValueError:
            continue

    if not job_ids:
        return []

    # Load the actual job rows from Postgres
    stmt = select(JobListing).where(JobListing.id.in_(job_ids), JobListing.is_active == True)
    result = await db.execute(stmt)
    jobs = {j.id: j for j in result.scalars().all()}

    # Upsert JobMatch rows for each found job
    for job_id in job_ids:
        job = jobs.get(job_id)
        if not job:
            continue

        score = score_map[job_id]
        reason = build_match_reason(score, profile, job)

        # Check if a match row already exists
        existing_stmt = select(JobMatch).where(
            JobMatch.profile_id == profile.id,
            JobMatch.job_id == job_id,
        )
        existing_result = await db.execute(existing_stmt)
        existing = existing_result.scalar_one_or_none()

        if existing:
            # Update score and reason — preserve user-set status
            existing.similarity_score = score
            existing.match_reason = reason
        else:
            db.add(JobMatch(
                profile_id=profile.id,
                job_id=job_id,
                similarity_score=score,
                match_reason=reason,
                status="suggested",
            ))

    await db.commit()

    # Reload and return all matches with jobs eagerly loaded, ordered by score
    matches_stmt = (
        select(JobMatch)
        .where(JobMatch.profile_id == profile.id, JobMatch.job_id.in_(job_ids))
        .options(selectinload(JobMatch.job))
        .order_by(JobMatch.similarity_score.desc())
    )
    matches_result = await db.execute(matches_stmt)
    return matches_result.scalars().all()


# ─── Retrieve Existing Matches ────────────────────────────────────────────────

async def get_my_matches(
    db: AsyncSession,
    user: User,
    status_filter: Optional[str] = None,
) -> list[JobMatch]:
    """
    Return all previously computed job matches for this user,
    optionally filtered by status.
    """
    profile = await _load_profile_with_skills(db, user)

    stmt = (
        select(JobMatch)
        .where(JobMatch.profile_id == profile.id)
        .options(selectinload(JobMatch.job))
        .order_by(JobMatch.similarity_score.desc())
    )

    if status_filter:
        stmt = stmt.where(JobMatch.status == status_filter)

    result = await db.execute(stmt)
    return result.scalars().all()


# ─── Update Match Status ──────────────────────────────────────────────────────

async def update_match_status(
    db: AsyncSession,
    user: User,
    match_id: UUID,
    new_status: str,
) -> JobMatch:
    """
    Update a match's status (suggested → saved → applied | rejected).
    Only the owning user can update their match.
    """
    profile = await _load_profile_with_skills(db, user)

    stmt = (
        select(JobMatch)
        .where(JobMatch.id == match_id, JobMatch.profile_id == profile.id)
        .options(selectinload(JobMatch.job))
    )
    result = await db.execute(stmt)
    match = result.scalar_one_or_none()

    if not match:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job match not found.",
        )

    match.status = new_status
    await db.commit()
    await db.refresh(match)

    # Re-load with job relationship
    result = await db.execute(stmt)
    return result.scalar_one()


# ─── Match Explanation ────────────────────────────────────────────────────────

async def explain_match(
    db: AsyncSession,
    user: User,
    job_id: UUID,
) -> dict:
    """
    Return a detailed explanation for a specific job match.
    """
    profile = await _load_profile_with_skills(db, user)

    # Load the match
    stmt = (
        select(JobMatch)
        .where(JobMatch.profile_id == profile.id, JobMatch.job_id == job_id)
        .options(selectinload(JobMatch.job))
    )
    result = await db.execute(stmt)
    match = result.scalar_one_or_none()

    if not match:
        # Check if job exists at all
        job_stmt = select(JobListing).where(JobListing.id == job_id)
        job_result = await db.execute(job_stmt)
        job = job_result.scalar_one_or_none()
        if not job:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No match found for this job. Run job matching first.",
        )

    job = match.job
    overlap = find_skill_overlap(profile, job)

    return {
        "job": job,
        "similarity_score": match.similarity_score,
        "tier": score_to_tier(match.similarity_score),
        "match_reason": match.match_reason,
        "skill_overlap": overlap,
    }
