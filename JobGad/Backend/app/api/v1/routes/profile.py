from uuid import UUID
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

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