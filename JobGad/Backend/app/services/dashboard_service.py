"""
Dashboard Service — stats and overview for graduates and HR users.
"""
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, and_
from datetime import datetime, timezone, timedelta

from app.models.user import User
from app.models.profile import Profile, Skill
from app.models.job import JobListing, JobMatch
from app.models.application import Application, GeneratedCV, Notification
from app.models.coaching import CoachingSession, Iriscore
from app.models.company import HRProfile, Company


# ─── Graduate Dashboard ───────────────────────────────────────────────────────

async def get_graduate_dashboard(
    db: AsyncSession,
    user: User,
) -> dict:
    """
    Get complete dashboard stats for a graduate user.
    Returns everything needed for the graduate home screen.
    """

    # ── Profile Completeness ──────────────────────────────────────────────────
    profile_stmt = select(Profile).where(Profile.user_id == user.id)
    profile_result = await db.execute(profile_stmt)
    profile = profile_result.scalar_one_or_none()

    profile_data = {
        "exists": False,
        "completeness": 0,
        "headline": None,
        "target_role": None,
        "skills_count": 0,
        "iri_score": 0,
    }

    if profile:
        # Count skills
        skills_stmt = select(func.count(Skill.id)).where(
            Skill.profile_id == profile.id
        )
        skills_result = await db.execute(skills_stmt)
        skills_count = skills_result.scalar() or 0

        profile_data = {
            "exists": True,
            "completeness": profile.profile_completeness or 0,
            "headline": profile.headline,
            "target_role": profile.target_role,
            "skills_count": skills_count,
            "iri_score": profile.iri_score or 0,
        }

    # ── Job Matches ───────────────────────────────────────────────────────────
    matches_data = {
        "total": 0,
        "new_this_week": 0,
        "top_match_score": 0,
        "top_match_title": None,
    }

    if profile:
        # Total matches
        total_matches_stmt = select(func.count(JobMatch.id)).where(
            JobMatch.profile_id == profile.id,
        )
        total_matches_result = await db.execute(total_matches_stmt)
        total_matches = total_matches_result.scalar() or 0

        # New matches this week
        week_ago = datetime.now(timezone.utc) - timedelta(days=7)
        new_matches_stmt = select(func.count(JobMatch.id)).where(
            JobMatch.profile_id == profile.id,
            JobMatch.created_at >= week_ago,
        )
        new_matches_result = await db.execute(new_matches_stmt)
        new_matches = new_matches_result.scalar() or 0

        # Top match
        top_match_stmt = (
            select(JobMatch, JobListing)
            .join(JobListing, JobMatch.job_id == JobListing.id)
            .where(JobMatch.profile_id == profile.id)
            .order_by(JobMatch.similarity_score.desc())
            .limit(1)
        )
        top_match_result = await db.execute(top_match_stmt)
        top_match_row = top_match_result.first()

        if top_match_row:
            top_match, top_job = top_match_row
            matches_data = {
                "total": total_matches,
                "new_this_week": new_matches,
                "top_match_score": round(
                    top_match.similarity_score * 100, 1
                ),
                "top_match_title": top_job.title,
            }
        else:
            matches_data["total"] = total_matches
            matches_data["new_this_week"] = new_matches

    # ── Applications ──────────────────────────────────────────────────────────
    apps_stmt = select(
        Application.status,
        func.count(Application.id),
    ).where(
        Application.user_id == user.id
    ).group_by(Application.status)

    apps_result = await db.execute(apps_stmt)
    apps_by_status = {row[0]: row[1] for row in apps_result.fetchall()}

    total_apps = sum(apps_by_status.values())

    applications_data = {
        "total": total_apps,
        "pending": apps_by_status.get("pending", 0),
        "reviewed": apps_by_status.get("reviewed", 0),
        "shortlisted": apps_by_status.get("shortlisted", 0),
        "rejected": apps_by_status.get("rejected", 0),
        "accepted": apps_by_status.get("accepted", 0),
    }

    # ── Recent Applications ───────────────────────────────────────────────────
    recent_apps_stmt = (
        select(Application, JobListing)
        .join(JobListing, Application.job_id == JobListing.id)
        .where(Application.user_id == user.id)
        .order_by(Application.applied_at.desc())
        .limit(5)
    )
    recent_apps_result = await db.execute(recent_apps_stmt)
    recent_apps = recent_apps_result.fetchall()

    recent_applications = [
        {
            "id": str(app.id),
            "job_title": job.title,
            "company": job.company,
            "status": app.status,
            "applied_at": str(app.applied_at),
        }
        for app, job in recent_apps
    ]

    # ── Coaching & IRI ────────────────────────────────────────────────────────
    # Total sessions
    sessions_stmt = select(func.count(CoachingSession.id)).where(
        CoachingSession.user_id == user.id,
        CoachingSession.status == "completed",
    )
    sessions_result = await db.execute(sessions_stmt)
    total_sessions = sessions_result.scalar() or 0

    # Latest IRI
    iri_stmt = (
        select(Iriscore)
        .where(Iriscore.user_id == user.id)
        .order_by(Iriscore.snapshot_at.desc())
        .limit(1)
    )
    iri_result = await db.execute(iri_stmt)
    latest_iri = iri_result.scalar_one_or_none()

    # IRI history for chart (last 10 sessions)
    iri_history_stmt = (
        select(Iriscore)
        .where(Iriscore.user_id == user.id)
        .order_by(Iriscore.snapshot_at.asc())
        .limit(10)
    )
    iri_history_result = await db.execute(iri_history_stmt)
    iri_history = iri_history_result.scalars().all()

    coaching_data = {
        "total_sessions": total_sessions,
        "current_iri": latest_iri.overall_score if latest_iri else 0,
        "communication": latest_iri.communication if latest_iri else 0,
        "technical_accuracy": latest_iri.technical_accuracy if latest_iri else 0,
        "confidence": latest_iri.confidence if latest_iri else 0,
        "structure": latest_iri.structure if latest_iri else 0,
        "iri_history": [
            {
                "score": iri.overall_score,
                "date": str(iri.snapshot_at),
            }
            for iri in iri_history
        ],
        "readiness_level": _get_readiness_level(
            latest_iri.overall_score if latest_iri else 0
        ),
    }

    # ── Generated CVs ─────────────────────────────────────────────────────────
    cvs_stmt = select(func.count(GeneratedCV.id)).where(
        GeneratedCV.user_id == user.id
    )
    cvs_result = await db.execute(cvs_stmt)
    total_cvs = cvs_result.scalar() or 0

    # ── Unread Notifications ──────────────────────────────────────────────────
    notif_stmt = select(func.count(Notification.id)).where(
        Notification.user_id == user.id,
        Notification.is_read == False,
    )
    notif_result = await db.execute(notif_stmt)
    unread_notifications = notif_result.scalar() or 0

    # ── Next Steps (recommendations) ─────────────────────────────────────────
    next_steps = _get_graduate_next_steps(
        profile_data=profile_data,
        applications_data=applications_data,
        coaching_data=coaching_data,
        matches_data=matches_data,
    )

    return {
        "user": {
            "full_name": user.full_name,
            "email": user.email,
            "role": user.role,
            "member_since": str(user.created_at),
        },
        "profile": profile_data,
        "job_matches": matches_data,
        "applications": applications_data,
        "recent_applications": recent_applications,
        "coaching": coaching_data,
        "generated_cvs": total_cvs,
        "unread_notifications": unread_notifications,
        "next_steps": next_steps,
    }


# ─── HR Dashboard ─────────────────────────────────────────────────────────────

async def get_hr_dashboard(
    db: AsyncSession,
    user: User,
) -> dict:
    """
    Get complete dashboard stats for an HR user.
    Returns everything needed for the HR home screen.
    """
    # Get HR profile and company
    hr_stmt = (
        select(HRProfile)
        .where(HRProfile.user_id == user.id)
    )
    hr_result = await db.execute(hr_stmt)
    hr_profile = hr_result.scalar_one_or_none()

    if not hr_profile:
        return {
            "error": "HR profile not found.",
            "message": "Please register as HR first.",
        }

    # Get company
    company_stmt = select(Company).where(
        Company.id == hr_profile.company_id
    )
    company_result = await db.execute(company_stmt)
    company = company_result.scalar_one_or_none()

    company_data = {
        "id": str(company.id) if company else None,
        "name": company.name if company else "Unknown",
        "industry": company.industry if company else None,
        "status": company.status if company else None,
        "is_verified": company.is_verified if company else False,
    }

    # ── Jobs Overview ─────────────────────────────────────────────────────────
    jobs_stmt = select(
        JobListing.status,
        func.count(JobListing.id),
    ).where(
        JobListing.company_id == hr_profile.company_id
    ).group_by(JobListing.status)

    jobs_result = await db.execute(jobs_stmt)
    jobs_by_status = {row[0]: row[1] for row in jobs_result.fetchall()}

    total_jobs = sum(jobs_by_status.values())

    jobs_data = {
        "total": total_jobs,
        "published": jobs_by_status.get("published", 0),
        "draft": jobs_by_status.get("draft", 0),
        "closed": jobs_by_status.get("closed", 0),
    }

    # ── Applications Overview ─────────────────────────────────────────────────
    # Get all job IDs for this company
    company_job_ids_stmt = select(JobListing.id).where(
        JobListing.company_id == hr_profile.company_id
    )
    company_job_ids_result = await db.execute(company_job_ids_stmt)
    company_job_ids = [row[0] for row in company_job_ids_result.fetchall()]

    applications_data = {
        "total": 0,
        "pending": 0,
        "reviewed": 0,
        "shortlisted": 0,
        "rejected": 0,
        "accepted": 0,
        "new_today": 0,
        "new_this_week": 0,
    }

    if company_job_ids:
        # Applications by status
        apps_stmt = select(
            Application.status,
            func.count(Application.id),
        ).where(
            Application.job_id.in_(company_job_ids)
        ).group_by(Application.status)

        apps_result = await db.execute(apps_stmt)
        apps_by_status = {
            row[0]: row[1] for row in apps_result.fetchall()
        }

        # New today
        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        new_today_stmt = select(func.count(Application.id)).where(
            Application.job_id.in_(company_job_ids),
            Application.applied_at >= today_start,
        )
        new_today_result = await db.execute(new_today_stmt)
        new_today = new_today_result.scalar() or 0

        # New this week
        week_ago = datetime.now(timezone.utc) - timedelta(days=7)
        new_week_stmt = select(func.count(Application.id)).where(
            Application.job_id.in_(company_job_ids),
            Application.applied_at >= week_ago,
        )
        new_week_result = await db.execute(new_week_stmt)
        new_week = new_week_result.scalar() or 0

        applications_data = {
            "total": sum(apps_by_status.values()),
            "pending": apps_by_status.get("pending", 0),
            "reviewed": apps_by_status.get("reviewed", 0),
            "shortlisted": apps_by_status.get("shortlisted", 0),
            "rejected": apps_by_status.get("rejected", 0),
            "accepted": apps_by_status.get("accepted", 0),
            "new_today": new_today,
            "new_this_week": new_week,
        }

    # ── Recent Applications ───────────────────────────────────────────────────
    recent_applications = []
    if company_job_ids:
        recent_stmt = (
            select(Application, JobListing, User)
            .join(JobListing, Application.job_id == JobListing.id)
            .join(User, Application.user_id == User.id)
            .where(Application.job_id.in_(company_job_ids))
            .order_by(Application.applied_at.desc())
            .limit(5)
        )
        recent_result = await db.execute(recent_stmt)
        recent_rows = recent_result.fetchall()

        recent_applications = [
            {
                "id": str(app.id),
                "applicant_name": applicant.full_name,
                "applicant_email": applicant.email,
                "job_title": job.title,
                "status": app.status,
                "applied_at": str(app.applied_at),
            }
            for app, job, applicant in recent_rows
        ]

    # ── Top Jobs by Applications ──────────────────────────────────────────────
    top_jobs = []
    if company_job_ids:
        top_jobs_stmt = (
            select(
                JobListing.title,
                JobListing.id,
                func.count(Application.id).label("app_count"),
            )
            .outerjoin(Application, Application.job_id == JobListing.id)
            .where(JobListing.company_id == hr_profile.company_id)
            .group_by(JobListing.id, JobListing.title)
            .order_by(func.count(Application.id).desc())
            .limit(5)
        )
        top_jobs_result = await db.execute(top_jobs_stmt)
        top_jobs = [
            {
                "job_id": str(row[1]),
                "title": row[0],
                "application_count": row[2],
            }
            for row in top_jobs_result.fetchall()
        ]

    # ── Unread Notifications ──────────────────────────────────────────────────
    notif_stmt = select(func.count(Notification.id)).where(
        Notification.user_id == user.id,
        Notification.is_read == False,
    )
    notif_result = await db.execute(notif_stmt)
    unread_notifications = notif_result.scalar() or 0

    # ── HR Profile Status ─────────────────────────────────────────────────────
    hr_status_data = {
        "status": hr_profile.status,
        "job_title": hr_profile.job_title,
        "is_company_admin": hr_profile.is_company_admin,
        "can_post_jobs": hr_profile.status == "approved",
    }

    return {
        "user": {
            "full_name": user.full_name,
            "email": user.email,
            "role": user.role,
        },
        "hr_profile": hr_status_data,
        "company": company_data,
        "jobs": jobs_data,
        "applications": applications_data,
        "recent_applications": recent_applications,
        "top_jobs_by_applications": top_jobs,
        "unread_notifications": unread_notifications,
    }


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _get_readiness_level(score: float) -> str:
    """Convert IRI score to readiness level label."""
    if score >= 85:
        return "Excellent — Interview Ready!"
    elif score >= 70:
        return "Strong — Almost Ready"
    elif score >= 55:
        return "Good — Making Progress"
    elif score >= 40:
        return "Developing — Keep Practicing"
    else:
        return "Beginner — Just Getting Started"


def _get_graduate_next_steps(
    profile_data: dict,
    applications_data: dict,
    coaching_data: dict,
    matches_data: dict,
) -> list[dict]:
    """
    Generate personalized next step recommendations
    based on the graduate's current progress.
    """
    steps = []

    # Profile not complete
    if not profile_data["exists"]:
        steps.append({
            "priority": 1,
            "action": "Create your profile",
            "description": "Start by setting up your profile to unlock job matching.",
            "link": "/profile",
            "icon": "user",
        })
    elif profile_data["completeness"] < 80:
        steps.append({
            "priority": 1,
            "action": "Complete your profile",
            "description": (
                f"Your profile is {profile_data['completeness']}% complete. "
                f"Add more details to improve job matches."
            ),
            "link": "/profile",
            "icon": "user",
        })

    # No skills
    if profile_data["skills_count"] < 5:
        steps.append({
            "priority": 2,
            "action": "Add your skills",
            "description": (
                "Upload your CV or add skills manually to improve matching accuracy."
            ),
            "link": "/profile/skills",
            "icon": "star",
        })

    # No matches yet
    if matches_data["total"] == 0:
        steps.append({
            "priority": 3,
            "action": "Run job matching",
            "description": (
                "Run AI job matching to find the best opportunities for your profile."
            ),
            "link": "/jobs/matches",
            "icon": "search",
        })

    # No coaching sessions
    if coaching_data["total_sessions"] == 0:
        steps.append({
            "priority": 4,
            "action": "Start interview practice",
            "description": (
                "Practice with our AI interviewer to build confidence and improve your IRI score."
            ),
            "link": "/coaching",
            "icon": "mic",
        })
    elif coaching_data["current_iri"] < 70:
        steps.append({
            "priority": 4,
            "action": "Keep practicing interviews",
            "description": (
                f"Your IRI is {coaching_data['current_iri']}/100. "
                f"Practice more to reach 70+ for better job prospects."
            ),
            "link": "/coaching",
            "icon": "mic",
        })

    # Has matches but no applications
    if matches_data["total"] > 0 and applications_data["total"] == 0:
        steps.append({
            "priority": 5,
            "action": "Apply for matched jobs",
            "description": (
                f"You have {matches_data['total']} job matches waiting. "
                f"Start applying!"
            ),
            "link": "/jobs/matches",
            "icon": "briefcase",
        })

    # Sort by priority
    steps.sort(key=lambda x: x["priority"])
    return steps[:3]  # Return top 3 most important steps