from uuid import UUID
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import Optional

from app.core.database import get_db
from app.api.v1.dependencies import get_current_user
from app.models.user import User
from app.schemas.profile import (
    ProfileCreate,
    ProfileUpdate,
    ProfileResponse,
    SkillCreate,
    SkillResponse,
    DocumentResponse,
    DocumentListResponse,
)
from app.services.profile_service import (
    create_profile,
    get_profile,
    update_profile,
    delete_profile,
    add_skill,
    delete_skill,
    upload_document,
    get_documents,
    delete_document,
)

router = APIRouter()

ALLOWED_DOC_TYPES = {"cv", "portfolio", "transcript", "project"}
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB


# ─── Profile CRUD ─────────────────────────────────────────────────────────────

@router.post(
    "/me",
    response_model=ProfileResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create my profile",
)
async def create_my_profile(
    data: ProfileCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a new profile for the authenticated user.
    Returns **400** if a profile already exists — use `PUT /profile/me` to update it.
    """
    return await create_profile(db, current_user, data)


@router.get(
    "/me",
    response_model=ProfileResponse,
    summary="Get my profile",
)
async def get_my_profile(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve the authenticated user's profile including all skills."""
    return await get_profile(db, current_user)


@router.put(
    "/me",
    response_model=ProfileResponse,
    summary="Update my profile",
)
async def update_my_profile(
    data: ProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update any subset of profile fields.
    Only the fields you include in the request body will be changed.
    `profile_completeness` is recalculated automatically.
    """
    return await update_profile(db, current_user, data)


@router.delete(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete my profile",
)
async def delete_my_profile(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Permanently delete the authenticated user's profile and all associated skills.
    Uploaded documents are preserved — delete them individually via `DELETE /profile/documents/{id}`.
    """
    await delete_profile(db, current_user)


# ─── Completeness & Skills Summary ────────────────────────────────────────────

@router.get(
    "/me/completeness",
    summary="Get profile completeness score",
)
async def get_profile_completeness(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns how complete the user's profile is as a percentage.
    Completeness is based on 9 key fields: headline, bio, GitHub URL, LinkedIn URL,
    education level, field of study, institution, graduation year, and target role.
    """
    profile = await get_profile(db, current_user)
    return {
        "profile_completeness": profile.profile_completeness,
        "message": (
            "Profile is 100% complete!"
            if profile.profile_completeness == 100
            else f"Your profile is {profile.profile_completeness}% complete. Keep going!"
        ),
    }


@router.get(
    "/me/skills",
    response_model=list[SkillResponse],
    summary="Get my skills",
)
async def get_my_skills(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns all skills on the authenticated user's profile."""
    profile = await get_profile(db, current_user)
    return profile.skills


# ─── Skill Management ─────────────────────────────────────────────────────────

@router.post(
    "/me/skills",
    response_model=SkillResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a skill to my profile",
)
async def add_my_skill(
    data: SkillCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Manually add a skill to your profile.

    - **name**: skill name (e.g. `Python`, `Team Leadership`)
    - **category**: `technical` | `soft` | `tool` | `domain`
    - **proficiency**: `beginner` | `intermediate` | `advanced` | `expert`

    Skills added this way will have `source = self_reported`.
    """
    return await add_skill(db, current_user, data)


@router.delete(
    "/me/skills/{skill_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a skill from my profile",
)
async def delete_my_skill(
    skill_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove a specific skill from your profile by its ID."""
    await delete_skill(db, current_user, skill_id)


# ─── Document Management ──────────────────────────────────────────────────────

@router.get(
    "/documents",
    response_model=DocumentListResponse,
    summary="List my uploaded documents",
)
async def list_my_documents(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns all documents uploaded by the authenticated user, newest first."""
    docs = await get_documents(db, current_user)
    return DocumentListResponse(documents=docs, total=len(docs))


@router.post(
    "/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a document (CV, portfolio, transcript, project)",
)
async def upload_my_document(
    file: UploadFile = File(...),
    doc_type: str = Form(default="cv"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload a CV or supporting document. Accepted formats: **PDF**, **DOCX**.
    Maximum file size: **5 MB**.

    - `doc_type`: `cv` | `portfolio` | `transcript` | `project`

    Text is automatically extracted from the document and stored for AI analysis.
    """
    if doc_type not in ALLOWED_DOC_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"doc_type must be one of: {sorted(ALLOWED_DOC_TYPES)}",
        )

    file_bytes = await file.read()

    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File too large. Maximum allowed size is 5 MB.",
        )

    return await upload_document(
        db=db,
        user=current_user,
        file_bytes=file_bytes,
        filename=file.filename,
        doc_type=doc_type,
    )


@router.delete(
    "/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a document",
)
async def delete_my_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a document by its ID.
    The file is removed from Supabase Storage and the DB record is erased.
    Only the document owner can perform this action.
    """
    await delete_document(db, current_user, document_id)

@router.post(
    "/documents/{document_id}/extract-skills",
    response_model=list[SkillResponse],
    summary="Manually trigger AI skill extraction from an uploaded document",
)
async def extract_skills_from_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Manually trigger Gemini AI skill extraction from an already-uploaded document.
    Useful if auto-extraction failed on upload or you want to re-run it.
    Only works on documents belonging to the current user.
    """
    from app.services.profile_service import extract_and_save_skills
    from app.models.profile import Document as DocumentModel

    stmt = select(DocumentModel).where(
        DocumentModel.id == document_id,
        DocumentModel.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    if not document.extracted_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No text found in this document. Try re-uploading it.",
        )

    skills = await extract_and_save_skills(db, current_user, document.extracted_text)

    return skills


@router.get(
    "/me/skill-gap",
    summary="Get AI-powered skill gap analysis for your target role",
)
# @router.get(
#     "/me/skill-gap",
#     summary="Get AI-powered skill gap analysis for your target role",
# )


async def get_skill_gap_analysis(
    job_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Compares your current skills against your target role and returns:
    - matching_skills: skills you already have
    - missing_skills: skills you still need
    - recommendations: specific actions to take
    - readiness_score: how ready you are (0-100)

    Optionally pass a job_id to analyze against a specific job instead
    of your general target role.
    """
    from app.tools.ai_tools import generate_skill_gap_analysis
    from app.models.job import JobListing

    profile = await get_profile(db, current_user)

    if not profile.target_role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please set a target_role on your profile first.",
        )

    if not profile.skills:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please add some skills to your profile first.",
        )

    skill_names = [s.name for s in profile.skills]
    job_requirements = ""
    analysis_target = profile.target_role

    # If job_id provided, analyze against that specific job
    if job_id:
        stmt = select(JobListing).where(
            JobListing.id == job_id,
            JobListing.is_active == True,
        )
        result = await db.execute(stmt)
        job = result.scalar_one_or_none()

        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job listing not found.",
            )

        job_requirements = job.requirements or job.description
        analysis_target = job.title

    analysis = await generate_skill_gap_analysis(
        profile_skills=skill_names,
        target_role=analysis_target,
        job_requirements=job_requirements,
    )

    return {
        "target_role": analysis_target,
        "total_skills": len(skill_names),
        "your_skills": skill_names,
        **analysis,
    }


@router.get(
    "/me/learning-roadmap",
    summary="Get a personalized learning roadmap based on your skill gaps",
)
async def get_learning_roadmap(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generates a personalized week-by-week learning roadmap to fill
    your skill gaps and become ready for your target role.

    Includes:
    - Phased learning plan with durations
    - Free and paid learning resources
    - Recommended projects to build
    - Daily study time recommendations
    """
    from app.tools.ai_tools import generate_skill_gap_analysis, generate_learning_roadmap

    profile = await get_profile(db, current_user)

    if not profile.target_role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please set a target_role on your profile first.",
        )

    skill_names = [s.name for s in profile.skills]

    # First get the skill gap to know what is missing
    gap = await generate_skill_gap_analysis(
        profile_skills=skill_names,
        target_role=profile.target_role,
    )

    missing_skills = gap.get("missing_skills", [])
    readiness_score = gap.get("readiness_score", 0)

    # Generate learning roadmap based on the gaps
    roadmap = await generate_learning_roadmap(
        missing_skills=missing_skills,
        target_role=profile.target_role,
        current_proficiency="intermediate" if readiness_score > 50 else "beginner",
    )

    return {
        "target_role": profile.target_role,
        "current_readiness_score": readiness_score,
        "missing_skills": missing_skills,
        "roadmap": roadmap,
    }


@router.post(
    "/me/cv-review",
    summary="Get AI-powered CV improvement suggestions",
)
async def get_cv_review(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Analyzes your most recently uploaded CV and returns:
    - Overall CV score (0-100)
    - Strengths and weaknesses
    - Specific improvement suggestions
    - Keywords to add for your target role
    - Suggested sections to include

    You must have uploaded a CV document first.
    """
    from app.tools.ai_tools import generate_skill_gap_analysis, generate_cv_improvement_suggestions
    from app.models.profile import Document as DocumentModel

    profile = await get_profile(db, current_user)

    if not profile.target_role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please set a target_role on your profile first.",
        )

    # Get most recently uploaded CV
    stmt = (
        select(DocumentModel)
        .where(
            DocumentModel.user_id == current_user.id,
            DocumentModel.type == "cv",
        )
        .order_by(DocumentModel.created_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    cv_doc = result.scalar_one_or_none()

    if not cv_doc or not cv_doc.extracted_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No CV found. Please upload a CV document first.",
        )

    skill_names = [s.name for s in profile.skills]

    # Get skill gap to know what is missing
    gap = await generate_skill_gap_analysis(
        profile_skills=skill_names,
        target_role=profile.target_role,
    )
    missing_skills = gap.get("missing_skills", [])

    # Generate CV improvement suggestions
    suggestions = await generate_cv_improvement_suggestions(
        cv_text=cv_doc.extracted_text,
        target_role=profile.target_role,
        missing_skills=missing_skills,
    )

    return {
        "target_role": profile.target_role,
        "cv_file": cv_doc.file_name,
        "skill_gap_summary": {
            "readiness_score": gap.get("readiness_score", 0),
            "missing_skills": missing_skills[:5],
        },
        "cv_review": suggestions,
    }