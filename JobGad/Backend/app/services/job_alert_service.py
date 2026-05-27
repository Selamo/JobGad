"""
Job Alert Service — notifies graduates when new jobs match their profile.
Triggered when HR posts a new job listing.
"""
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.models.profile import Profile
from app.models.job import JobListing, JobMatch
from app.models.application import Notification
from app.models.user import User


async def notify_matching_graduates(
    db: AsyncSession,
    job: JobListing,
    company_name: str,
    min_score: float = 0.5,
) -> int:
    """
    Find all graduates whose profile matches this job above min_score.
    Send in-app notification and email to each one.
    Returns number of graduates notified.
    """
    try:
        # Get all existing matches for this job above threshold
        matches_stmt = (
            select(JobMatch)
            .options(
                selectinload(JobMatch.profile).selectinload(Profile.user),
            )
            .where(
                JobMatch.job_id == job.id,
                JobMatch.similarity_score >= min_score,
            )
        )
        matches_result = await db.execute(matches_stmt)
        matches = matches_result.scalars().all()

        if not matches:
            return 0

        notified = 0
        for match in matches:
            profile = match.profile
            if not profile or not profile.user:
                continue

            user = profile.user

            # Check user is a graduate and is active
            if user.role != "graduate" or not user.is_active:
                continue

            # Create in-app notification
            notification = Notification(
                user_id=user.id,
                type="job_alert",
                title="New Job Match Found!",
                message=(
                    f"A new job '{job.title}' at '{company_name}' matches your profile "
                    f"with a {int(match.similarity_score * 100)}% score. Check it out!"
                ),
                related_job_id=job.id,
            )
            db.add(notification)

            # Send email alert
            try:
                from app.services.email_service import send_job_alert_email
                await send_job_alert_email(
                    email=user.email,
                    full_name=user.full_name,
                    job_title=job.title,
                    company_name=company_name,
                    match_score=int(match.similarity_score * 100),
                    job_location=job.location or "Not specified",
                    employment_type=job.employment_type or "Not specified",
                )
            except Exception as e:
                print(f"[Job Alert] Email failed for {user.email}: {e}")

            notified += 1

        await db.commit()
        print(f"[Job Alert] Notified {notified} graduates for job '{job.title}'")
        return notified

    except Exception as e:
        print(f"[Job Alert] Service error: {e}")
        return 0