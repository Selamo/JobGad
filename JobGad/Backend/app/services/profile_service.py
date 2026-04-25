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

async def _sync_profile_to_pinecone(profile: Profile) -> None:
    """
    Build profile text and upsert it into Pinecone.
    Called whenever profile or skills change.
    Non-fatal — if Pinecone fails, the rest of the operation still succeeds.
    """
    try:
        from app.tools.pinecone_tools import upsert_profile_vector
        from app.tools.scoring_tools import build_profile_text

        profile_text = build_profile_text(profile)
        if profile_text.strip():
            await upsert_profile_vector(str(profile.id), profile_text)
            print(f"[Pinecone] Profile {profile.id} synced successfully")
    except Exception as e:
        print(f"[Pinecone] Profile sync failed (non-fatal): {e}")

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

    # Reload with relationships
    profile = await _get_profile_or_404(db, user)

    # Sync to Pinecone
    await _sync_profile_to_pinecone(profile)

    return profile


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

    # Reload with relationships so skills are included in embedding
    profile = await _get_profile_or_404(db, user)

    # Re-sync to Pinecone with updated data
    await _sync_profile_to_pinecone(profile)

    return profile


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

    # Reload profile with updated skills and re-sync to Pinecone
    profile = await _get_profile_or_404(db, user)
    await _sync_profile_to_pinecone(profile)

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

    # Reload profile with updated skills and re-sync to Pinecone
    profile = await _get_profile_or_404(db, user)
    await _sync_profile_to_pinecone(profile)


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
    saves the document record, and if it is a CV, auto-extracts skills using AI.
    """
    if not (filename.lower().endswith(".pdf") or filename.lower().endswith(".docx")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF and DOCX files are supported.",
        )

    # Extract text content from the file
    try:
        extracted_text = extract_text(file_bytes, filename)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Could not read file: {str(e)}",
        )

    # Upload file to Supabase Storage
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

    # Save document record to database
    document = Document(
        user_id=user.id,
        type=doc_type,
        file_name=filename,
        storage_url=storage_url,
        extracted_text=extracted_text,
        processing_status="extracted",
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)

    # ── AUTO EXTRACT SKILLS IF THIS IS A CV ──────────────────────────────────
    if doc_type == "cv" and extracted_text:
        try:
            await extract_and_save_skills(db, user, extracted_text)
            # Update document status to show AI processing is done
            document.processing_status = "processed"
            await db.commit()
        except Exception as e:
            # Non-fatal: document is saved even if skill extraction fails
            print(f"[Profile Service] Skill extraction failed: {e}")
    # ─────────────────────────────────────────────────────────────────────────

    return document


async def extract_and_save_skills(
    db: AsyncSession,
    user: User,
    text: str,
) -> list[Skill]:
    """
    Use Gemini AI to extract skills from text and save them to the profile.
    Skips duplicates by skill name (case-insensitive).
    """
    from app.tools.ai_tools import extract_skills_from_text

    try:
        profile = await _get_profile_or_404(db, user)
    except Exception:
        return []

    existing_names = {s.name.lower() for s in profile.skills}
    extracted = await extract_skills_from_text(text)

    if not extracted:
        return []

    new_skills = []
    for skill_data in extracted:
        if skill_data["name"].lower() in existing_names:
            continue

        skill = Skill(
            profile_id=profile.id,
            name=skill_data["name"],
            category=skill_data["category"],
            proficiency=skill_data["proficiency"],
            source="extracted",
            confidence=0.85,
        )
        db.add(skill)
        new_skills.append(skill)
        existing_names.add(skill_data["name"].lower())

    if new_skills:
        await db.commit()
        print(f"[Profile Service] Saved {len(new_skills)} new skills for user {user.id}")

    # Reload profile with all skills and sync to Pinecone
    profile = await _get_profile_or_404(db, user)
    await _sync_profile_to_pinecone(profile)

    return new_skills

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

async def analyze_social_profiles(
    db: AsyncSession,
    user: User,
) -> dict:
    """
    Fetch and analyze all social profile URLs saved on the user's profile.
    Extracts skills from GitHub, GitLab, and portfolio websites.
    Skips duplicates and syncs profile to Pinecone after.
    """
    from app.tools.social_tools import fetch_skills_from_url

    profile = await _get_profile_or_404(db, user)

    # Collect all URLs to analyze
    urls_to_check = []
    if profile.github_url:
        urls_to_check.append(profile.github_url)
    if profile.linkedin_url:
        urls_to_check.append(profile.linkedin_url)
    if profile.portfolio_url:
        urls_to_check.append(profile.portfolio_url)

    if not urls_to_check:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No social URLs found on your profile. Add GitHub, LinkedIn, or portfolio URL first.",
        )

    # Get existing skill names to avoid duplicates
    existing_names = {s.name.lower() for s in profile.skills}

    results = {}
    total_new_skills = 0

    for url in urls_to_check:
        platform, skills = await fetch_skills_from_url(url)

        new_skills_for_platform = 0
        for skill_data in skills:
            if skill_data["name"].lower() in existing_names:
                continue

            skill = Skill(
                profile_id=profile.id,
                name=skill_data["name"],
                category=skill_data["category"],
                proficiency=skill_data["proficiency"],
                source=f"inferred_{platform}",
                confidence=0.75,
            )
            db.add(skill)
            existing_names.add(skill_data["name"].lower())
            new_skills_for_platform += 1
            total_new_skills += 1

        results[platform] = {
            "url": url,
            "skills_found": len(skills),
            "new_skills_added": new_skills_for_platform,
            "status": "success" if skills else "no_skills_found",
        }

    if total_new_skills > 0:
        await db.commit()
        print(f"[Social] Added {total_new_skills} new skills for user {user.id}")

    # Reload and sync to Pinecone
    profile = await _get_profile_or_404(db, user)
    await _sync_profile_to_pinecone(profile)

    return {
        "total_new_skills_added": total_new_skills,
        "platforms_analyzed": results,
    }

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

    # Remove file from storage
    if document.storage_url and document.file_name:
        storage_path = f"{str(user.id)}/{document.file_name}"
        try:
            await delete_file_from_supabase(storage_path)
        except Exception:
            pass

    await db.delete(document)
    await db.commit()