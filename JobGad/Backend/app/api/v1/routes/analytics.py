"""
Analytics routes — charts and stats for admin, HR, and graduate users.
"""
from datetime import datetime, timezone, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func

from app.core.database import get_db
from app.api.v1.dependencies import get_current_user
from app.models.user import User
from app.models.company import Company, HRProfile
from app.models.job import JobListing, JobMatch
from app.models.application import Application
from app.models.coaching import CoachingSession, Iriscore
from app.models.profile import Profile

router = APIRouter()


# ─── Admin Analytics ──────────────────────────────────────────────────────────

@router.get("/admin", summary="Admin platform analytics")
async def admin_analytics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "superadmin":
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Superadmin only.")

    # User registrations over last 30 days
    days = 30
    now = datetime.now(timezone.utc)
    registrations = []
    for i in range(days - 1, -1, -1):
        day_start = (now - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end   = day_start + timedelta(days=1)
        result = await db.execute(
            select(func.count(User.id)).where(
                User.created_at >= day_start,
                User.created_at < day_end,
            )
        )
        registrations.append({
            "date": day_start.strftime("%d %b"),
            "users": result.scalar() or 0,
        })

    # Applications over last 30 days
    applications_trend = []
    for i in range(days - 1, -1, -1):
        day_start = (now - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end   = day_start + timedelta(days=1)
        result = await db.execute(
            select(func.count(Application.id)).where(
                Application.applied_at >= day_start,
                Application.applied_at < day_end,
            )
        )
        applications_trend.append({
            "date": day_start.strftime("%d %b"),
            "applications": result.scalar() or 0,
        })

    # Companies by industry
    industry_result = await db.execute(
        select(Company.industry, func.count(Company.id))
        .group_by(Company.industry)
        .order_by(func.count(Company.id).desc())
        .limit(8)
    )
    companies_by_industry = [
        {"industry": row[0] or "Other", "count": row[1]}
        for row in industry_result.fetchall()
    ]

    # IRI score distribution
    iri_ranges = [
        ("0-20", 0, 20), ("21-40", 21, 40), ("41-60", 41, 60),
        ("61-80", 61, 80), ("81-100", 81, 100),
    ]
    iri_distribution = []
    for label, low, high in iri_ranges:
        result = await db.execute(
            select(func.count(Iriscore.id)).where(
                Iriscore.overall_score >= low,
                Iriscore.overall_score <= high,
            )
        )
        iri_distribution.append({"range": label, "count": result.scalar() or 0})

    # Users by role
    role_result = await db.execute(
        select(User.role, func.count(User.id)).group_by(User.role)
    )
    users_by_role = [
        {"role": row[0], "count": row[1]}
        for row in role_result.fetchall()
    ]

    # Top companies by job count
    top_companies_result = await db.execute(
        select(Company.name, func.count(JobListing.id).label("jobs"))
        .outerjoin(JobListing, JobListing.company_id == Company.id)
        .group_by(Company.id, Company.name)
        .order_by(func.count(JobListing.id).desc())
        .limit(6)
    )
    top_companies = [
        {"name": row[0], "jobs": row[1]}
        for row in top_companies_result.fetchall()
    ]

    return {
        "registrations_trend": registrations,
        "applications_trend": applications_trend,
        "companies_by_industry": companies_by_industry,
        "iri_distribution": iri_distribution,
        "users_by_role": users_by_role,
        "top_companies_by_jobs": top_companies,
    }


# ─── HR Analytics ─────────────────────────────────────────────────────────────

@router.get("/hr", summary="HR analytics for their company")
async def hr_analytics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Get HR profile
    hr_result = await db.execute(
        select(HRProfile).where(HRProfile.user_id == current_user.id)
    )
    hr_profile = hr_result.scalar_one_or_none()
    if not hr_profile:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="HR profile not found.")

    # Get company job IDs
    job_ids_result = await db.execute(
        select(JobListing.id).where(JobListing.company_id == hr_profile.company_id)
    )
    job_ids = [row[0] for row in job_ids_result.fetchall()]

    # Applications over last 30 days
    now = datetime.now(timezone.utc)
    applications_trend = []
    for i in range(29, -1, -1):
        day_start = (now - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end   = day_start + timedelta(days=1)
        count = 0
        if job_ids:
            result = await db.execute(
                select(func.count(Application.id)).where(
                    Application.job_id.in_(job_ids),
                    Application.applied_at >= day_start,
                    Application.applied_at < day_end,
                )
            )
            count = result.scalar() or 0
        applications_trend.append({
            "date": day_start.strftime("%d %b"),
            "applications": count,
        })

    # Application funnel
    funnel_data = []
    if job_ids:
        for status in ["pending", "reviewed", "shortlisted", "accepted", "rejected"]:
            result = await db.execute(
                select(func.count(Application.id)).where(
                    Application.job_id.in_(job_ids),
                    Application.status == status,
                )
            )
            funnel_data.append({"status": status.capitalize(), "count": result.scalar() or 0})

    # Top jobs by applications
    top_jobs = []
    if job_ids:
        top_jobs_result = await db.execute(
            select(JobListing.title, func.count(Application.id).label("apps"))
            .outerjoin(Application, Application.job_id == JobListing.id)
            .where(JobListing.company_id == hr_profile.company_id)
            .group_by(JobListing.id, JobListing.title)
            .order_by(func.count(Application.id).desc())
            .limit(6)
        )
        top_jobs = [
            {"title": row[0][:30] + "..." if len(row[0]) > 30 else row[0], "applications": row[1]}
            for row in top_jobs_result.fetchall()
        ]

    # Application status breakdown (pie)
    status_breakdown = []
    if job_ids:
        status_result = await db.execute(
            select(Application.status, func.count(Application.id))
            .where(Application.job_id.in_(job_ids))
            .group_by(Application.status)
        )
        status_breakdown = [
            {"status": row[0].capitalize(), "value": row[1]}
            for row in status_result.fetchall()
        ]

    return {
        "applications_trend": applications_trend,
        "application_funnel": funnel_data,
        "top_jobs": top_jobs,
        "status_breakdown": status_breakdown,
    }


# ─── Graduate Analytics ───────────────────────────────────────────────────────

@router.get("/graduate", summary="Graduate personal analytics")
async def graduate_analytics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # IRI history
    iri_result = await db.execute(
        select(Iriscore)
        .where(Iriscore.user_id == current_user.id)
        .order_by(Iriscore.snapshot_at.asc())
    )
    iri_scores = iri_result.scalars().all()
    iri_history = [
        {
            "session": f"S{i+1}",
            "score": round(s.overall_score, 1),
            "communication": round(s.communication or 0, 1),
            "technical": round(s.technical_accuracy or 0, 1),
            "confidence": round(s.confidence or 0, 1),
            "structure": round(s.structure or 0, 1),
            "date": s.snapshot_at.strftime("%d %b"),
        }
        for i, s in enumerate(iri_scores)
    ]

    # Application status breakdown
    apps_result = await db.execute(
        select(Application.status, func.count(Application.id))
        .where(Application.user_id == current_user.id)
        .group_by(Application.status)
    )
    application_breakdown = [
        {"status": row[0].capitalize(), "value": row[1]}
        for row in apps_result.fetchall()
    ]

    # Applications over last 30 days
    now = datetime.now(timezone.utc)
    applications_trend = []
    for i in range(29, -1, -1):
        day_start = (now - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end   = day_start + timedelta(days=1)
        result = await db.execute(
            select(func.count(Application.id)).where(
                Application.user_id == current_user.id,
                Application.applied_at >= day_start,
                Application.applied_at < day_end,
            )
        )
        applications_trend.append({
            "date": day_start.strftime("%d %b"),
            "applications": result.scalar() or 0,
        })

    # Skills count over time (approximate from profile)
    profile_result = await db.execute(
        select(Profile).where(Profile.user_id == current_user.id)
    )
    profile = profile_result.scalar_one_or_none()

    # Score breakdown radar data (latest IRI)
    latest_iri = iri_scores[-1] if iri_scores else None
    radar_data = [
        {"subject": "Communication",  "score": round(latest_iri.communication or 0, 1) if latest_iri else 0},
        {"subject": "Technical",      "score": round(latest_iri.technical_accuracy or 0, 1) if latest_iri else 0},
        {"subject": "Confidence",     "score": round(latest_iri.confidence or 0, 1) if latest_iri else 0},
        {"subject": "Structure",      "score": round(latest_iri.structure or 0, 1) if latest_iri else 0},
    ]

    return {
        "iri_history": iri_history,
        "application_breakdown": application_breakdown,
        "applications_trend": applications_trend,
        "radar_data": radar_data,
        "total_sessions": len(iri_scores),
        "current_iri": round(latest_iri.overall_score, 1) if latest_iri else 0,
        "profile_completeness": profile.profile_completeness if profile else 0,
    }