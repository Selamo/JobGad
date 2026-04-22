from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status

from app.models.profile import Profile, Skill, Document
from app.models.user import User
from app.schemas.profile import ProfileCreate, ProfileUpdate, SkillCreate
from app.tools.document_tools import extract_text
from app.core.storage import upload_file_to_supabase, delete_file_from_supabase


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _calculate_completeness(profile: Profile) -> float:
    """
    Calculates profile completeness as a percentage (0.0 – 100.0).
    Each of the 9 tracked fields contributes equally.
    """
    fields = [
        profile.headline,
        profile.bio,
        profile.github_url,
        profile.linkedin_url,
        profile.education_level,
        profile.field_of_study,
        profile.institution,
        profile.graduation_year,
        profile.target_role,
    ]
    filled = sum(1 for f in fields if f is not None and str(f).strip() != "")
    return round((filled / len(fields)) * 100, 2)


async def _get_profile_or_404(db: AsyncSession, user: User) -> Profile:
    """Internal helper — fetches profile with skills eagerly loaded or raises 404."""
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
            detail="Profile not found. Please create one first.",
        )
    return profile


# ─── Profile CRUD ─────────────────────────────────────────────────────────────

async def create_profile(db: AsyncSession, user: User, data: ProfileCreate) -> Profile:
    """Create a fresh profile for a user. Fails if one already exists."""
    stmt = select(Profile).where(Profile.user_id == user.id)
    result = await db.execute(stmt)
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Profile already exists. Use PUT /profile/me to update it.",
        )

    profile = Profile(user_id=user.id, **data.model_dump(exclude_none=True))
    profile.profile_completeness = _calculate_completeness(profile)

    db.add(profile)
    await db.commit()
    await db.refresh(profile)

    # Reload with relationships so the response is fully populated
    return await _get_profile_or_404(db, user)


async def get_profile(db: AsyncSession, user: User) -> Profile:
    """Fetch the current user's profile (with skills)."""
    return await _get_profile_or_404(db, user)


async def update_profile(db: AsyncSession, user: User, data: ProfileUpdate) -> Profile:
    """Update any subset of profile fields."""
    profile = await _get_profile_or_404(db, user)

    update_data = data.model_dump(exclude_none=True)
    for field, value in update_data.items():
        setattr(profile, field, value)

    profile.profile_completeness = _calculate_completeness(profile)

    await db.commit()
    await db.refresh(profile)
    return await _get_profile_or_404(db, user)


async def delete_profile(db: AsyncSession, user: User) -> None:
    """
    Permanently delete the user's profile and all related skills.
    Documents are tied to the user, not the profile, so they are NOT deleted here.
    """
    profile = await _get_profile_or_404(db, user)
    await db.delete(profile)
    await db.commit()


# ─── Skill Management ─────────────────────────────────────────────────────────

async def add_skill(db: AsyncSession, user: User, data: SkillCreate) -> Skill:
    """Manually add a skill to the user's profile."""
    profile = await _get_profile_or_404(db, user)

    skill = Skill(
        profile_id=profile.id,
        name=data.name,
        category=data.category,
        proficiency=data.proficiency,
        source="self_reported",
        confidence=1.0,
    )
    db.add(skill)
    await db.commit()
    await db.refresh(skill)
    return skill


async def delete_skill(db: AsyncSession, user: User, skill_id: UUID) -> None:
    """Delete a specific skill from the user's profile."""
    profile = await _get_profile_or_404(db, user)

    stmt = select(Skill).where(Skill.id == skill_id, Skill.profile_id == profile.id)
    result = await db.execute(stmt)
    skill = result.scalar_one_or_none()

    if not skill:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Skill not found on your profile.",
        )
    await db.delete(skill)
    await db.commit()


# ─── Document Management ──────────────────────────────────────────────────────

async def upload_document(
    db: AsyncSession,
    user: User,
    file_bytes: bytes,
    filename: str,
    doc_type: str,
) -> Document:
    """
    Extracts text from a PDF/DOCX file, uploads it to Supabase Storage,
    and saves the document record to the database.
    """
    if not (filename.lower().endswith(".pdf") or filename.lower().endswith(".docx")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF and DOCX files are supported.",
        )

    # Extract text content
    try:
        extracted_text = extract_text(file_bytes, filename)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Could not read file: {str(e)}",
        )

    # Upload to Supabase Storage
    try:
        storage_url = await upload_file_to_supabase(
            file_bytes=file_bytes,
            file_name=filename,
            user_id=str(user.id),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"File upload failed: {str(e)}",
        )

    # Persist document record
    document = Document(
        user_id=user.id,
        type=doc_type,
        file_name=filename,
        storage_url=storage_url,
        extracted_text=extracted_text,
        processing_status="extracted",  # text extracted; pending AI analysis
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)
    return document


async def get_documents(db: AsyncSession, user: User) -> list[Document]:
    """Return all documents uploaded by the current user."""
    stmt = select(Document).where(Document.user_id == user.id).order_by(Document.created_at.desc())
    result = await db.execute(stmt)
    return result.scalars().all()


async def delete_document(db: AsyncSession, user: User, document_id: UUID) -> None:
    """
    Delete a document record from the DB and remove the file from Supabase Storage.
    Only the owning user can delete their documents.
    """
    stmt = select(Document).where(Document.id == document_id, Document.user_id == user.id)
    result = await db.execute(stmt)
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    # Remove file from storage — storage_path matches the upload pattern: user_id/filename
    if document.storage_url and document.file_name:
        storage_path = f"{str(user.id)}/{document.file_name}"
        try:
            await delete_file_from_supabase(storage_path)
        except Exception:
            # Non-fatal: DB record still gets removed even if storage delete fails
            pass

    await db.delete(document)
    await db.commit()