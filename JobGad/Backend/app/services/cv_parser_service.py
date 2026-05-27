"""
CV Parser Service — extracts profile data from uploaded CV using Groq AI.
Auto-fills profile fields: headline, bio, education, skills, target role, links.
"""
import json
import asyncio
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.models.profile import Profile, Skill, Document
from app.models.user import User
from app.core.config import settings


async def parse_cv_and_update_profile(
    db: AsyncSession,
    user: User,
    document_id: str,
) -> dict:
    """
    Parse an uploaded CV document and auto-fill the user's profile.

    Steps:
    1. Load the document and extract its text
    2. Send to Groq AI for structured extraction
    3. Update profile fields with extracted data
    4. Add extracted skills
    5. Return summary of what was updated
    """
    from app.models.profile import Document as DocumentModel

    # Load document
    stmt = select(DocumentModel).where(
        DocumentModel.id == document_id,
        DocumentModel.user_id == user.id,
    )
    result = await db.execute(stmt)
    document = result.scalar_one_or_none()

    if not document:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=404, detail="Document not found.")

    if not document.extracted_text:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=400,
            detail="No text found in this document. Try re-uploading it.",
        )

    # Parse CV with Groq
    parsed = await _extract_profile_from_cv(document.extracted_text, user.full_name)

    # Load or create profile
    profile_stmt = (
        select(Profile)
        .where(Profile.user_id == user.id)
        .options(selectinload(Profile.skills))
    )
    profile_result = await db.execute(profile_stmt)
    profile = profile_result.scalar_one_or_none()

    if not profile:
        profile = Profile(user_id=user.id)
        db.add(profile)
        await db.flush()

    # Track what was updated
    updated_fields = []

    # Update profile fields — only fill if currently empty
    if parsed.get("headline") and not profile.headline:
        profile.headline = parsed["headline"][:255]
        updated_fields.append("headline")

    if parsed.get("bio") and not profile.bio:
        profile.bio = parsed["bio"]
        updated_fields.append("bio")

    if parsed.get("github_url") and not profile.github_url:
        profile.github_url = parsed["github_url"][:500]
        updated_fields.append("github_url")

    if parsed.get("linkedin_url") and not profile.linkedin_url:
        profile.linkedin_url = parsed["linkedin_url"][:500]
        updated_fields.append("linkedin_url")

    if parsed.get("education_level") and not profile.education_level:
        profile.education_level = parsed["education_level"][:100]
        updated_fields.append("education_level")

    if parsed.get("field_of_study") and not profile.field_of_study:
        profile.field_of_study = parsed["field_of_study"][:255]
        updated_fields.append("field_of_study")

    if parsed.get("institution") and not profile.institution:
        profile.institution = parsed["institution"][:255]
        updated_fields.append("institution")

    if parsed.get("graduation_year") and not profile.graduation_year:
        try:
            profile.graduation_year = int(parsed["graduation_year"])
            updated_fields.append("graduation_year")
        except (ValueError, TypeError):
            pass

    if parsed.get("target_role") and not profile.target_role:
        profile.target_role = parsed["target_role"][:255]
        updated_fields.append("target_role")

    # Add extracted skills — skip duplicates
    existing_skill_names = {s.name.lower() for s in profile.skills}
    skills_added = []

    for skill_data in parsed.get("skills", []):
        skill_name = skill_data.get("name", "").strip()
        if not skill_name or skill_name.lower() in existing_skill_names:
            continue

        skill = Skill(
            profile_id=profile.id,
            name=skill_name[:255],
            category=skill_data.get("category", "technical"),
            proficiency=skill_data.get("proficiency", "intermediate"),
            source="extracted",
            confidence=0.85,
        )
        db.add(skill)
        existing_skill_names.add(skill_name.lower())
        skills_added.append(skill_name)

    # Recalculate profile completeness
    _recalculate_completeness(profile)

    await db.commit()
    await db.refresh(profile)

    return {
        "success": True,
        "updated_fields": updated_fields,
        "skills_added": skills_added,
        "skills_count": len(skills_added),
        "profile_completeness": profile.profile_completeness,
        "parsed_data": {
            "name": parsed.get("name"),
            "headline": parsed.get("headline"),
            "education": parsed.get("education_level"),
            "institution": parsed.get("institution"),
            "target_role": parsed.get("target_role"),
            "skills_found": len(parsed.get("skills", [])),
        },
        "message": (
            f"Profile updated! Filled {len(updated_fields)} fields and added {len(skills_added)} skills."
            if updated_fields or skills_added
            else "No new data found to add — your profile may already be complete."
        ),
    }


async def _extract_profile_from_cv(cv_text: str, full_name: str) -> dict:
    """Use Groq to extract structured profile data from CV text."""

    prompt = f"""You are an expert CV parser. Extract structured profile information from this CV.

CANDIDATE NAME: {full_name}

CV TEXT:
{cv_text[:4000]}

Extract and return ONLY valid JSON with this exact structure:
{{
    "name": "full name from CV",
    "headline": "professional headline or current role (max 255 chars)",
    "bio": "professional summary or objective statement (2-4 sentences)",
    "target_role": "the role they are targeting or most recent role title",
    "education_level": "highest education level (Bachelor's Degree | Master's Degree | PhD | HND | OND | High School)",
    "field_of_study": "main field or major",
    "institution": "university or school name",
    "graduation_year": "year of most recent graduation as number",
    "github_url": "github URL if present or null",
    "linkedin_url": "linkedin URL if present or null",
    "skills": [
        {{
            "name": "skill name",
            "category": "technical | soft | tool | domain",
            "proficiency": "beginner | intermediate | advanced | expert"
        }}
    ]
}}

Rules:
- Extract ALL skills mentioned anywhere in the CV
- Infer proficiency from context (years of experience, project descriptions)
- If a field is not found, use null
- Return ONLY the JSON, no markdown, no explanation
"""

    def _call_groq():
        try:
            from groq import Groq
            client = Groq(api_key=settings.GROQ_API_KEY)
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a CV parser. Always respond with valid JSON only. No markdown, no backticks.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=3000,
            )
            raw = response.choices[0].message.content.strip()
            if raw.startswith("```"):
                parts = raw.split("```")
                raw = parts[1] if len(parts) > 1 else raw
                if raw.startswith("json"):
                    raw = raw[4:]
            return json.loads(raw.strip())
        except Exception as e:
            print(f"[CV Parser] Groq extraction failed: {e}")
            return {}

    return await asyncio.get_event_loop().run_in_executor(None, _call_groq)


def _recalculate_completeness(profile: Profile) -> None:
    """Recalculate profile completeness percentage."""
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
    filled = sum(1 for f in fields if f)
    profile.profile_completeness = round((filled / len(fields)) * 100, 1)