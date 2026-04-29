"""
Search routes — combined keyword + semantic job search.
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.v1.dependencies import get_current_user
from app.models.user import User
from app.services.search_service import (
    combined_search,
    JobSearchFilters,
)

router = APIRouter()


@router.get(
    "/jobs",
    summary="Search jobs using combined keyword + semantic search",
)
async def search_jobs(
    q: Optional[str] = Query(
        default=None,
        description="Search query — natural language or keywords",
    ),
    location: Optional[str] = Query(
        default=None,
        description="Filter by location e.g. Douala, Remote",
    ),
    employment_type: Optional[str] = Query(
        default=None,
        description="full-time | part-time | contract | internship",
    ),
    company: Optional[str] = Query(
        default=None,
        description="Filter by company name",
    ),
    posted_within: Optional[int] = Query(
        default=None,
        description="Posted within X days e.g. 7 for last week",
    ),
    sort_by: str = Query(
        default="best_match",
        description="best_match | most_recent",
    ),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Search for jobs using a combination of:
    - **Keyword search** — finds exact matches in titles and descriptions
    - **Semantic search** — finds related jobs based on meaning

    Examples:
    - `?q=Python backend developer`
    - `?q=machine learning&location=Douala`
    - `?q=software engineer&employment_type=internship`
    - `?location=Remote&employment_type=full-time`
    - `?q=web development&posted_within=7`

    Results are ranked by a combined score:
    - Jobs matching both keyword and semantic search rank highest
    - Each result includes a `match_reason` explaining why it was found
    """
    filters = JobSearchFilters(
        keyword=q,
        location=location,
        employment_type=employment_type,
        company_name=company,
        posted_within_days=posted_within,
        sort_by=sort_by,
    )

    search_result = await combined_search(
        db=db,
        query=q or "",
        filters=filters,
        page=page,
        page_size=page_size,
    )

    # Format response
    formatted_results = []
    for item in search_result["results"]:
        job = item["job"]
        formatted_results.append({
            "id": str(job.id),
            "title": job.title,
            "company": job.company,
            "location": job.location,
            "employment_type": job.employment_type,
            "salary_range": job.salary_range,
            "posted_at": str(job.posted_at) if job.posted_at else None,
            "status": job.status,
            "combined_score": round(item["combined_score"], 3),
            "keyword_score": round(item["keyword_score"], 3),
            "semantic_score": round(item["semantic_score"], 3),
            "found_in": item["found_in"],
            "match_reason": item["match_reason"],
        })

    return {
        "results": formatted_results,
        "total": search_result["total"],
        "page": search_result["page"],
        "page_size": search_result["page_size"],
        "total_pages": search_result["total_pages"],
        "query": search_result["query"],
        "filters_applied": search_result["filters_applied"],
    }


@router.get(
    "/jobs/suggestions",
    summary="Get search suggestions based on partial query",
)
async def search_suggestions(
    q: str = Query(..., min_length=2, description="Partial search query"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get autocomplete suggestions as the user types.
    Returns matching job titles and companies.
    """
    from sqlalchemy.future import select
    from app.models.job import JobListing
    from sqlalchemy import or_

    keyword = f"%{q}%"
    stmt = (
        select(JobListing.title, JobListing.company)
        .where(
            JobListing.is_active == True,
            or_(
                JobListing.title.ilike(keyword),
                JobListing.company.ilike(keyword),
            ),
        )
        .limit(8)
        .distinct()
    )

    result = await db.execute(stmt)
    rows = result.fetchall()

    suggestions = []
    seen = set()

    for title, company in rows:
        if title and title.lower() not in seen:
            suggestions.append({
                "text": title,
                "type": "job_title",
            })
            seen.add(title.lower())

        if company and company.lower() not in seen:
            suggestions.append({
                "text": company,
                "type": "company",
            })
            seen.add(company.lower())

    return {
        "query": q,
        "suggestions": suggestions[:8],
    }


@router.get(
    "/graduates",
    summary="[HR] Search graduates by skills and profile",
)
async def search_graduates(
    skills: Optional[str] = Query(
        default=None,
        description="Comma-separated skills e.g. Python,React,Docker",
    ),
    target_role: Optional[str] = Query(
        default=None,
        description="Target role filter",
    ),
    education_level: Optional[str] = Query(
        default=None,
        description="BSc | MSc | HND | PhD",
    ),
    min_iri: Optional[float] = Query(
        default=None,
        description="Minimum IRI score (0-100)",
    ),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Search for graduate candidates by skills, role, and IRI score.
    **HR or Admin role required.**
    """
    if current_user.role not in {"hr", "admin", "superadmin"}:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only HR users can search graduates.",
        )

    from sqlalchemy.future import select
    from sqlalchemy.orm import selectinload
    from app.models.profile import Profile, Skill
    from app.models.user import User as UserModel

    stmt = (
        select(Profile)
        .options(
            selectinload(Profile.skills),
            selectinload(Profile.user),
        )
        .join(UserModel, Profile.user_id == UserModel.id)
        .where(UserModel.role == "graduate")
    )

    # Filter by education level
    if education_level:
        stmt = stmt.where(Profile.education_level == education_level)

    # Filter by target role
    if target_role:
        stmt = stmt.where(
            Profile.target_role.ilike(f"%{target_role}%")
        )

    # Filter by minimum IRI score
    if min_iri is not None:
        stmt = stmt.where(Profile.iri_score >= min_iri)

    result = await db.execute(stmt)
    profiles = result.scalars().all()

    # Filter by skills (post-processing)
    if skills:
        required_skills = [s.strip().lower() for s in skills.split(",")]
        filtered_profiles = []
        for profile in profiles:
            profile_skills = {s.name.lower() for s in profile.skills}
            if any(rs in profile_skills for rs in required_skills):
                filtered_profiles.append(profile)
        profiles = filtered_profiles

    # Paginate
    total = len(profiles)
    start = (page - 1) * page_size
    paginated = profiles[start:start + page_size]

    return {
        "graduates": [
            {
                "profile_id": str(p.id),
                "full_name": p.user.full_name if p.user else "Unknown",
                "headline": p.headline,
                "target_role": p.target_role,
                "education_level": p.education_level,
                "field_of_study": p.field_of_study,
                "institution": p.institution,
                "iri_score": p.iri_score,
                "profile_completeness": p.profile_completeness,
                "skills": [
                    {
                        "name": s.name,
                        "category": s.category,
                        "proficiency": s.proficiency,
                    }
                    for s in p.skills[:10]
                ],
            }
            for p in paginated
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }