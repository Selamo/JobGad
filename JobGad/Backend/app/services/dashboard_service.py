"""
Dashboard Service — stats and overview for graduates and HR users.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import func
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
    # ── Profile ───────────────────────────────────────────────────────────────
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
        skills_stmt = select(func.count(Skill.id)).where(Skill.profile_id == profile.id)
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
        total_matches_result = await db.execute(
            select(func.count(JobMatch.id)).where(JobMatch.profile_id == profile.id)
        )
        total_matches = total_matches_result.scalar() or 0

        week_ago = datetime.now(timezone.utc) - timedelta(days=7)
        new_matches_result = await db.execute(
            select(func.count(JobMatch.id)).where(
                JobMatch.profile_id == profile.id,
                JobMatch.created_at >= week_ago,
            )
        )
        new_matches = new_matches_result.scalar() or 0

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
                "top_match_score": round(top_match.similarity_score * 100, 1),
                "top_match_title": top_job.title,
            }
        else:
            matches_data["total"] = total_matches
            matches_data["new_this_week"] = new_matches

    # ── Applications ──────────────────────────────────────────────────────────
    apps_result = await db.execute(
        select(Application.status, func.count(Application.id))
        .where(Application.user_id == user.id)
        .group_by(Application.status)
    )
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

    # ── Recent Applications — with eager loading ───────────────────────────────
    recent_apps_stmt = (
        select(Application)
        .options(
            selectinload(Application.job).selectinload(JobListing.company)
        )
        .where(Application.user_id == user.id)
        .order_by(Application.applied_at.desc())
        .limit(5)
    )
    recent_apps_result = await db.execute(recent_apps_stmt)
    recent_apps = recent_apps_result.scalars().all()

    recent_applications = [
        {
            "id": str(app.id),
            "job": {
                "title": app.job.title if app.job else "",
                "company": app.job.company.name if app.job and app.job.company else "",
            },
            "status": app.status,
            "applied_at": str(app.applied_at),
        }
        for app in recent_apps
    ]

    # ── Coaching & IRI ────────────────────────────────────────────────────────
    sessions_result = await db.execute(
        select(func.count(CoachingSession.id)).where(
            CoachingSession.user_id == user.id,
            CoachingSession.status == "completed",
        )
    )
    total_sessions = sessions_result.scalar() or 0

    iri_result = await db.execute(
        select(Iriscore)
        .where(Iriscore.user_id == user.id)
        .order_by(Iriscore.snapshot_at.desc())
        .limit(1)
    )
    latest_iri = iri_result.scalar_one_or_none()

    iri_history_result = await db.execute(
        select(Iriscore)
        .where(Iriscore.user_id == user.id)
        .order_by(Iriscore.snapshot_at.asc())
        .limit(10)
    )
    iri_history = iri_history_result.scalars().all()

    coaching_data = {
        "total_sessions": total_sessions,
        "current_iri": latest_iri.overall_score if latest_iri else 0,
        "communication": latest_iri.communication if latest_iri else 0,
        "technical_accuracy": latest_iri.technical_accuracy if latest_iri else 0,
        "confidence": latest_iri.confidence if latest_iri else 0,
        "structure": latest_iri.structure if latest_iri else 0,
        "iri_history": [
            {"score": iri.overall_score, "date": str(iri.snapshot_at)}
            for iri in iri_history
        ],
        "readiness_level": _get_readiness_level(
            latest_iri.overall_score if latest_iri else 0
        ),
    }

    # ── Generated CVs ─────────────────────────────────────────────────────────
    cvs_result = await db.execute(
        select(func.count(GeneratedCV.id)).where(GeneratedCV.user_id == user.id)
    )
    total_cvs = cvs_result.scalar() or 0

    # ── Unread Notifications ──────────────────────────────────────────────────
    notif_result = await db.execute(
        select(func.count(Notification.id)).where(
            Notification.user_id == user.id,
            Notification.is_read == False,
        )
    )
    unread_notifications = notif_result.scalar() or 0

    # ── Next Steps ────────────────────────────────────────────────────────────
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
    # Get HR profile
    hr_result = await db.execute(
        select(HRProfile).where(HRProfile.user_id == user.id)
    )
    hr_profile = hr_result.scalar_one_or_none()

    if not hr_profile:
        company_result = await db.execute(
            select(Company).where(Company.created_by == user.id)
        )
        company = company_result.scalar_one_or_none()

        if company and company.status == "approved":
            from datetime import timezone as tz
            hr_profile = HRProfile(
                user_id=user.id,
                company_id=company.id,
                job_title="HR Manager",
                is_company_admin=True,
                status="approved",
                approved_at=datetime.now(tz.utc),
            )
            db.add(hr_profile)
            await db.commit()
            await db.refresh(hr_profile)
        elif company and company.status == "pending":
            return {
                "error": "Company pending approval.",
                "message": "Your company is awaiting admin approval.",
                "company": {"name": company.name, "status": company.status},
            }
        else:
            return {
                "error": "HR profile not found.",
                "message": "Please register as HR first.",
            }

    # Get company
    company_result = await db.execute(
        select(Company).where(Company.id == hr_profile.company_id)
    )
    company = company_result.scalar_one_or_none()

    company_data = {
        "id": str(company.id) if company else None,
        "name": company.name if company else "Unknown",
        "industry": company.industry if company else None,
        "status": company.status if company else None,
        "is_verified": company.is_verified if company else False,
    }

    # Jobs overview
    jobs_result = await db.execute(
        select(JobListing.status, func.count(JobListing.id))
        .where(JobListing.company_id == hr_profile.company_id)
        .group_by(JobListing.status)
    )
    jobs_by_status = {row[0]: row[1] for row in jobs_result.fetchall()}
    total_jobs = sum(jobs_by_status.values())

    # Count active jobs separately
    active_jobs_result = await db.execute(
        select(func.count(JobListing.id))
        .where(
            JobListing.company_id == hr_profile.company_id,
            JobListing.is_active == True,
        )
    )
    active_jobs = active_jobs_result.scalar() or 0

    jobs_data = {
        "total": total_jobs,
        "active": active_jobs,
        "published": jobs_by_status.get("published", 0),
        "draft": jobs_by_status.get("draft", 0),
        "closed": jobs_by_status.get("closed", 0),
    }

    # Get company job IDs
    job_ids_result = await db.execute(
        select(JobListing.id).where(JobListing.company_id == hr_profile.company_id)
    )
    company_job_ids = [row[0] for row in job_ids_result.fetchall()]

    applications_data = {
        "total": 0, "pending": 0, "reviewed": 0,
        "shortlisted": 0, "rejected": 0, "accepted": 0,
        "new_today": 0, "new_this_week": 0,
    }

    if company_job_ids:
        apps_result = await db.execute(
            select(Application.status, func.count(Application.id))
            .where(Application.job_id.in_(company_job_ids))
            .group_by(Application.status)
        )
        apps_by_status = {row[0]: row[1] for row in apps_result.fetchall()}

        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        new_today_result = await db.execute(
            select(func.count(Application.id)).where(
                Application.job_id.in_(company_job_ids),
                Application.applied_at >= today_start,
            )
        )

        week_ago = datetime.now(timezone.utc) - timedelta(days=7)
        new_week_result = await db.execute(
            select(func.count(Application.id)).where(
                Application.job_id.in_(company_job_ids),
                Application.applied_at >= week_ago,
            )
        )

        applications_data = {
            "total": sum(apps_by_status.values()),
            "pending": apps_by_status.get("pending", 0),
            "reviewed": apps_by_status.get("reviewed", 0),
            "shortlisted": apps_by_status.get("shortlisted", 0),
            "rejected": apps_by_status.get("rejected", 0),
            "accepted": apps_by_status.get("accepted", 0),
            "new_today": new_today_result.scalar() or 0,
            "new_this_week": new_week_result.scalar() or 0,
        }

    # Recent applications
    recent_applications = []
    if company_job_ids:
        recent_result = await db.execute(
            select(Application, JobListing, User)
            .join(JobListing, Application.job_id == JobListing.id)
            .join(User, Application.user_id == User.id)
            .where(Application.job_id.in_(company_job_ids))
            .order_by(Application.applied_at.desc())
            .limit(5)
        )
        recent_applications = [
            {
                "id": str(app.id),
                "applicant_name": applicant.full_name,
                "applicant_email": applicant.email,
                "job_title": job.title,
                "status": app.status,
                "applied_at": str(app.applied_at),
            }
            for app, job, applicant in recent_result.fetchall()
        ]

    # Unread notifications
    notif_result = await db.execute(
        select(func.count(Notification.id)).where(
            Notification.user_id == user.id,
            Notification.is_read == False,
        )
    )
    unread_notifications = notif_result.scalar() or 0

    return {
        "user": {
            "full_name": user.full_name,
            "email": user.email,
            "role": user.role,
        },
        "hr_profile": {
            "status": hr_profile.status,
            "job_title": hr_profile.job_title,
            "is_company_admin": hr_profile.is_company_admin,
            "can_post_jobs": hr_profile.status == "approved",
        },
        "company": company_data,
        "jobs": jobs_data,
        "applications": applications_data,
        "recent_applications": recent_applications,
        "unread_notifications": unread_notifications,
    }


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _get_readiness_level(score: float) -> str:
    if score >= 85:  return "Excellent — Interview Ready!"
    elif score >= 70: return "Strong — Almost Ready"
    elif score >= 55: return "Good — Making Progress"
    elif score >= 40: return "Developing — Keep Practicing"
    else:             return "Beginner — Just Getting Started"


def _get_graduate_next_steps(
    profile_data: dict,
    applications_data: dict,
    coaching_data: dict,
    matches_data: dict,
) -> list:
    steps = []

    if not profile_data["exists"]:
        steps.append({"priority": 1, "action": "Create your profile",
            "description": "Start by setting up your profile to unlock job matching.",
            "link": "/profile", "icon": "user"})
    elif profile_data["completeness"] < 80:
        steps.append({"priority": 1, "action": "Complete your profile",
            "description": f"Your profile is {profile_data['completeness']}% complete. Add more details to improve job matches.",
            "link": "/profile", "icon": "user"})

    if profile_data["skills_count"] < 5:
        steps.append({"priority": 2, "action": "Add your skills",
            "description": "Upload your CV or add skills manually to improve matching accuracy.",
            "link": "/profile", "icon": "star"})

    if matches_data["total"] == 0:
        steps.append({"priority": 3, "action": "Run job matching",
            "description": "Run AI job matching to find the best opportunities for your profile.",
            "link": "/jobs", "icon": "search"})

    if coaching_data["total_sessions"] == 0:
        steps.append({"priority": 4, "action": "Start interview practice",
            "description": "Practice with our AI interviewer to build confidence and improve your IRI score.",
            "link": "/coaching", "icon": "mic"})
    elif coaching_data["current_iri"] < 70:
        steps.append({"priority": 4, "action": "Keep practicing interviews",
            "description": f"Your IRI is {coaching_data['current_iri']}/100. Practice more to reach 70+.",
            "link": "/coaching", "icon": "mic"})

    if matches_data["total"] > 0 and applications_data["total"] == 0:
        steps.append({"priority": 5, "action": "Apply for matched jobs",
            "description": f"You have {matches_data['total']} job matches waiting. Start applying!",
            "link": "/jobs", "icon": "briefcase"})

    steps.sort(key=lambda x: x["priority"])
    return steps[:3]