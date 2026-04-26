"""
CV Service — generates tailored CVs using AI and saves them.
"""
from uuid import UUID
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status
from fastapi.responses import StreamingResponse
import io

from app.models.user import User
from app.models.profile import Profile
from app.models.job import JobListing
from app.models.application import GeneratedCV, Notification
from app.models.company import Company
from app.core.storage import upload_file_to_supabase


async def _get_profile_with_skills(db: AsyncSession, user: User) -> Profile:
    """Get user profile with skills loaded."""
    stmt = (
        select(Profile)
        .where(Profile.user_id == user.id)
        .options(selectinload(Profile.skills))
    )
    result = await db.execute(stmt)
    profile = result.scalar_one_or_none()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found. Please create a profile first.",
        )
    return profile


async def generate_and_save_cv(
    db: AsyncSession,
    user: User,
    job_id: UUID,
    file_format: str = "pdf",
    additional_answers: Optional[dict] = None,
) -> GeneratedCV:
    """
    Generate a tailored CV for a specific job and save it.
    
    Steps:
    1. Load user profile + skills
    2. Load job details
    3. Call Gemini to generate CV content
    4. Format as PDF or DOCX
    5. Upload to Supabase Storage
    6. Save GeneratedCV record
    7. Notify user via in-app + email
    """
    if file_format not in {"pdf", "docx"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="file_format must be 'pdf' or 'docx'",
        )

    # Load profile
    profile = await _get_profile_with_skills(db, user)

    # Load job
    job_stmt = select(JobListing).where(JobListing.id == job_id)
    job_result = await db.execute(job_stmt)
    job = job_result.scalar_one_or_none()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job listing not found.",
        )

    # Get company name
    company_name = "Company"
    if job.company_id:
        company_stmt = select(Company).where(Company.id == job.company_id)
        company_result = await db.execute(company_stmt)
        company = company_result.scalar_one_or_none()
        if company:
            company_name = company.name

    # Build profile dict for AI
    profile_dict = {
        "full_name": user.full_name,
        "email": user.email,
        "headline": profile.headline,
        "bio": profile.bio,
        "education_level": profile.education_level,
        "field_of_study": profile.field_of_study,
        "institution": profile.institution,
        "graduation_year": profile.graduation_year,
        "target_role": profile.target_role,
        "skills": [s.name for s in profile.skills],
        "github_url": profile.github_url,
        "linkedin_url": profile.linkedin_url,
    }

    # Build job dict for AI
    job_dict = {
        "title": job.title,
        "company": company_name,
        "location": job.location,
        "employment_type": job.employment_type,
        "description": job.description,
        "requirements": job.requirements,
    }

    # Generate CV content using Gemini
    from app.tools.cv_generator import (
        generate_cv_content,
        generate_cv_with_clarifications,
    )

    if additional_answers:
        cv_data = await generate_cv_with_clarifications(
            profile=profile_dict,
            job=job_dict,
            answers=additional_answers,
        )
    else:
        cv_data = await generate_cv_content(
            profile=profile_dict,
            job=job_dict,
        )

    # Check if AI needs more info
    missing_questions = cv_data.get("missing_info_questions", [])

    # Format the CV
    from app.tools.cv_formatter import generate_cv_pdf, generate_cv_docx

    if file_format == "pdf":
        file_bytes = generate_cv_pdf(cv_data)
        content_type = "application/pdf"
        extension = "pdf"
    else:
        file_bytes = generate_cv_docx(cv_data)
        content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        extension = "docx"

    # Generate filename
    safe_name = user.full_name.replace(" ", "_").lower()
    safe_job = job.title.replace(" ", "_").lower()[:20]
    filename = f"cv_{safe_name}_{safe_job}.{extension}"

    # Upload to Supabase Storage
    try:
        storage_url = await upload_file_to_supabase(
            file_bytes=file_bytes,
            file_name=f"cvs/{filename}",
            user_id=str(user.id),
            bucket="documents",
        )
    except Exception as e:
        print(f"[CV Service] Upload failed: {e}")
        storage_url = None

    # Save GeneratedCV record
    import json
    generated_cv = GeneratedCV(
        user_id=user.id,
        job_id=job_id,
        file_name=filename,
        storage_url=storage_url,
        file_format=file_format,
        content_snapshot=json.dumps(cv_data),
    )
    db.add(generated_cv)
    await db.commit()
    await db.refresh(generated_cv)

    # Store file bytes temporarily for download
    generated_cv._file_bytes = file_bytes
    generated_cv._missing_questions = missing_questions
    generated_cv._content_type = content_type

    # Send in-app notification
    notification = Notification(
        user_id=user.id,
        type="cv_ready",
        title="Your AI CV is Ready!",
        message=f"Your tailored CV for '{job.title}' at '{company_name}' "
                f"has been generated and is ready for download.",
        related_job_id=job_id,
    )
    db.add(notification)
    await db.commit()

    # Send email notification
    try:
        from app.services.email_service import send_cv_ready_email
        await send_cv_ready_email(
            email=user.email,
            full_name=user.full_name,
            job_title=job.title,
            company_name=company_name,
            download_url=storage_url or "Login to JobGad to download",
        )
    except Exception as e:
        print(f"[CV Service] Email failed (non-fatal): {e}")

    return generated_cv


async def get_my_generated_cvs(
    db: AsyncSession,
    user: User,
) -> list[GeneratedCV]:
    """Get all CVs generated by the current user."""
    stmt = (
        select(GeneratedCV)
        .where(GeneratedCV.user_id == user.id)
        .options(selectinload(GeneratedCV.job))
        .order_by(GeneratedCV.generated_at.desc())
    )
    result = await db.execute(stmt)
    return result.scalars().all()