"""
Search Service — combines PostgreSQL keyword search with 
Pinecone semantic search for the best job discovery experience.
"""
from uuid import UUID
from typing import Optional
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import or_, and_, func

from app.models.job import JobListing
from app.models.company import Company


# ─── Search Filters ───────────────────────────────────────────────────────────

class JobSearchFilters:
    """All available search filters."""
    def __init__(
        self,
        keyword: Optional[str] = None,
        location: Optional[str] = None,
        employment_type: Optional[str] = None,
        company_name: Optional[str] = None,
        posted_within_days: Optional[int] = None,
        min_salary: Optional[str] = None,
        sort_by: str = "best_match",
    ):
        self.keyword = keyword
        self.location = location
        self.employment_type = employment_type
        self.company_name = company_name
        self.posted_within_days = posted_within_days
        self.min_salary = min_salary
        self.sort_by = sort_by


# ─── PostgreSQL Keyword Search ────────────────────────────────────────────────

async def keyword_search(
    db: AsyncSession,
    filters: JobSearchFilters,
    limit: int = 50,
) -> list[dict]:
    """
    Search jobs using PostgreSQL keyword matching and filters.
    Returns list of jobs with a keyword_score.
    """
    stmt = (
        select(JobListing)
        .where(JobListing.is_active == True)
        .where(JobListing.status == "published")
    )

    # Keyword filter — search in title, description, requirements
    if filters.keyword:
        keyword = f"%{filters.keyword}%"
        stmt = stmt.where(
            or_(
                JobListing.title.ilike(keyword),
                JobListing.description.ilike(keyword),
                JobListing.requirements.ilike(keyword),
            )
        )

    # Location filter
    if filters.location:
        stmt = stmt.where(
            JobListing.location.ilike(f"%{filters.location}%")
        )

    # Employment type filter
    if filters.employment_type:
        stmt = stmt.where(
            JobListing.employment_type == filters.employment_type
        )

    # Posted within X days filter
    if filters.posted_within_days:
        cutoff = datetime.utcnow() - timedelta(days=filters.posted_within_days)
        stmt = stmt.where(JobListing.posted_at >= cutoff)

    # Sort
    if filters.sort_by == "most_recent":
        stmt = stmt.order_by(JobListing.posted_at.desc())
    else:
        stmt = stmt.order_by(JobListing.posted_at.desc())

    stmt = stmt.limit(limit)
    result = await db.execute(stmt)
    jobs = result.scalars().all()

    # Calculate keyword score for each job
    keyword_results = []
    for job in jobs:
        score = 0.5  # Base score for keyword match

        if filters.keyword:
            kw = filters.keyword.lower()
            # Higher score if keyword in title
            if kw in (job.title or "").lower():
                score = 1.0
            # Medium score if in requirements
            elif kw in (job.requirements or "").lower():
                score = 0.7
            # Lower score if only in description
            elif kw in (job.description or "").lower():
                score = 0.5

        keyword_results.append({
            "job_id": str(job.id),
            "job": job,
            "keyword_score": score,
            "source": "keyword",
        })

    return keyword_results


# ─── Pinecone Semantic Search ─────────────────────────────────────────────────

async def semantic_search(
    query: str,
    filters: JobSearchFilters,
    top_k: int = 20,
) -> list[dict]:
    """
    Search jobs using Pinecone semantic/vector search.
    Returns list of jobs with semantic similarity scores.
    """
    if not query or not query.strip():
        return []

    try:
        from app.tools.pinecone_tools import query_similar_jobs

        # Build Pinecone filter
        pinecone_filter = {"is_active": True}
        if filters.employment_type:
            pinecone_filter["employment_type"] = filters.employment_type
        if filters.location:
            pinecone_filter["location"] = {"$regex": filters.location}

        results = await query_similar_jobs(
            profile_text=query,
            top_k=top_k,
            filter=pinecone_filter,
        )

        semantic_results = []
        for r in results:
            raw_id = r["id"].removeprefix("job_")
            try:
                job_uuid = UUID(raw_id)
                semantic_results.append({
                    "job_id": raw_id,
                    "job_uuid": job_uuid,
                    "semantic_score": r["score"],
                    "metadata": r.get("metadata", {}),
                    "source": "semantic",
                })
            except ValueError:
                continue

        return semantic_results

    except Exception as e:
        print(f"[Search] Semantic search failed: {e}")
        return []


# ─── Load Jobs from DB by IDs ─────────────────────────────────────────────────

async def load_jobs_by_ids(
    db: AsyncSession,
    job_ids: list[UUID],
) -> dict[str, JobListing]:
    """Load JobListing records from DB by their IDs."""
    if not job_ids:
        return {}

    stmt = select(JobListing).where(
        JobListing.id.in_(job_ids),
        JobListing.is_active == True,
    )
    result = await db.execute(stmt)
    jobs = result.scalars().all()
    return {str(j.id): j for j in jobs}


# ─── Combined Search ──────────────────────────────────────────────────────────

async def combined_search(
    db: AsyncSession,
    query: str,
    filters: JobSearchFilters,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """
    Main search function that combines keyword and semantic search.

    Algorithm:
    1. Run keyword search on PostgreSQL
    2. Run semantic search on Pinecone
    3. Merge results with weighted scoring
    4. Apply any remaining filters
    5. Return paginated results

    Final Score = (keyword_score × 0.4) + (semantic_score × 0.6)
    Jobs in both searches get a bonus boost.
    """
    # Run both searches concurrently
    import asyncio

    keyword_task = keyword_search(db, filters, limit=50)
    semantic_task = semantic_search(query or "", filters, top_k=30)

    keyword_results, semantic_results = await asyncio.gather(
        keyword_task,
        semantic_task,
    )

    # Build score maps
    keyword_map = {r["job_id"]: r for r in keyword_results}
    semantic_map = {r["job_id"]: r for r in semantic_results}

    # Get all unique job IDs
    all_job_ids = set(keyword_map.keys()) | set(semantic_map.keys())

    # Load any jobs found in semantic but not in keyword
    semantic_only_ids = [
        UUID(jid) for jid in semantic_map.keys()
        if jid not in keyword_map
    ]
    extra_jobs = await load_jobs_by_ids(db, semantic_only_ids)

    # Merge and score
    merged = {}
    for job_id in all_job_ids:
        keyword_entry = keyword_map.get(job_id)
        semantic_entry = semantic_map.get(job_id)

        # Get the job object
        if keyword_entry:
            job = keyword_entry["job"]
        elif job_id in extra_jobs:
            job = extra_jobs[job_id]
        else:
            continue

        # Calculate scores
        kw_score = keyword_entry["keyword_score"] if keyword_entry else 0
        sem_score = semantic_entry["semantic_score"] if semantic_entry else 0

        # Combined score
        combined_score = (kw_score * 0.4) + (sem_score * 0.6)

        # Boost if found in both
        if keyword_entry and semantic_entry:
            combined_score = min(1.0, combined_score * 1.15)

        # Determine match sources
        sources = []
        if keyword_entry:
            sources.append("keyword")
        if semantic_entry:
            sources.append("semantic")

        merged[job_id] = {
            "job": job,
            "combined_score": combined_score,
            "keyword_score": kw_score,
            "semantic_score": sem_score,
            "found_in": sources,
            "match_reason": _build_match_reason(
                job=job,
                query=query,
                kw_score=kw_score,
                sem_score=sem_score,
                in_both=bool(keyword_entry and semantic_entry),
            ),
        }

    # Sort by combined score
    sorted_results = sorted(
        merged.values(),
        key=lambda x: x["combined_score"],
        reverse=True,
    )

    # Apply company name filter (post-processing)
    if filters.company_name:
        cn = filters.company_name.lower()
        sorted_results = [
            r for r in sorted_results
            if cn in (r["job"].company or "").lower()
        ]

    # Paginate
    total = len(sorted_results)
    start = (page - 1) * page_size
    end = start + page_size
    paginated = sorted_results[start:end]

    return {
        "results": paginated,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
        "query": query,
        "filters_applied": {
            "keyword": filters.keyword,
            "location": filters.location,
            "employment_type": filters.employment_type,
            "company_name": filters.company_name,
        },
    }


def _build_match_reason(
    job: JobListing,
    query: str,
    kw_score: float,
    sem_score: float,
    in_both: bool,
) -> str:
    """Build a human-readable match reason."""
    if in_both:
        return (
            f"Strong match — found by both keyword and semantic search. "
            f"This job closely matches your search for '{query}'."
        )
    elif sem_score > 0.8:
        return (
            f"Excellent semantic match — this role is highly relevant "
            f"to '{query}' even though exact keywords may differ."
        )
    elif sem_score > 0.6:
        return (
            f"Good semantic match — this role relates well to '{query}'."
        )
    elif kw_score >= 0.8:
        return (
            f"Direct keyword match — '{query}' found in job title."
        )
    else:
        return f"Potential match for '{query}'."