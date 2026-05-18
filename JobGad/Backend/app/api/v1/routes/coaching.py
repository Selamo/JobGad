"""
Coaching routes — session management and IRI scoring.
"""
from uuid import UUID
from typing import Optional
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from pydantic import BaseModel

from app.core.database import get_db
from app.api.v1.dependencies import get_current_user
from app.models.user import User
from app.models.coaching import CoachingSession, SessionMessage, Iriscore
from app.models.job import JobListing
from app.models.profile import Profile

router = APIRouter()


class CreateSessionRequest(BaseModel):
    job_id: UUID
    session_type: str = "mixed"


# ─── Create Session ───────────────────────────────────────────────────────────

@router.post("/sessions", summary="Create a new coaching session")
async def create_coaching_session(
    data: CreateSessionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a new interview coaching session.
    Generates AI questions based on the job and session type.
    """
    # Verify job exists
    job_stmt = select(JobListing).where(JobListing.id == data.job_id)
    job_result = await db.execute(job_stmt)
    job = job_result.scalar_one_or_none()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job listing not found.",
        )

    # Get company name
    company_name = "the company"
    if job.company_id:
        from app.models.company import Company
        company_stmt = select(Company).where(Company.id == job.company_id)
        company_result = await db.execute(company_stmt)
        company = company_result.scalar_one_or_none()
        if company:
            company_name = company.name

    # Get user profile and skills
    profile_stmt = (
        select(Profile)
        .where(Profile.user_id == current_user.id)
        .options(selectinload(Profile.skills))
    )
    profile_result = await db.execute(profile_stmt)
    profile = profile_result.scalar_one_or_none()

    skills = [s.name for s in profile.skills] if profile else []
    target_role = profile.target_role if profile else None

    # Generate questions using Gemini AI
    questions = await _generate_questions(
        job_title=job.title,
        company_name=company_name,
        job_requirements=job.requirements or "",
        job_description=job.description or "",
        session_type=data.session_type,
        candidate_skills=skills,
        target_role=target_role,
    )

    # Create session
    session = CoachingSession(
        user_id=current_user.id,
        target_job_id=data.job_id,
        session_type=data.session_type,
        status="active",
        started_at=datetime.now(timezone.utc),
    )
    db.add(session)
    await db.flush()

    # Save questions as session messages
    for i, q in enumerate(questions, start=1):
        msg = SessionMessage(
            session_id=session.id,
            role="interviewer",
            content=q["question"],
            message_type="question",
            sequence_no=i,
            evaluation={
                "type": q.get("type", "behavioral"),
                "time_limit_seconds": q.get("time_limit_seconds", 120),
                "hints": q.get("hints", []),
            },
        )
        db.add(msg)

    await db.commit()
    await db.refresh(session)

    return {
        "session_id": str(session.id),
        "job_title": job.title,
        "company": company_name,
        "session_type": data.session_type,
        "status": session.status,
        "total_questions": len(questions),
        "started_at": str(session.started_at),
    }


# ─── List Sessions ────────────────────────────────────────────────────────────

@router.get("/sessions", summary="Get all my coaching sessions")
async def get_sessions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all coaching sessions for the current user."""
    stmt = (
        select(CoachingSession)
        .where(CoachingSession.user_id == current_user.id)
        .options(selectinload(CoachingSession.target_job))
        .order_by(CoachingSession.started_at.desc())
    )
    result = await db.execute(stmt)
    sessions = result.scalars().all()

    return [
        {
            "session_id": str(s.id),
            "job_title": s.target_job.title if s.target_job else "General Practice",
            "session_type": s.session_type,
            "status": s.status,
            "overall_score": s.overall_score,
            "started_at": str(s.started_at),
            "ended_at": str(s.ended_at) if s.ended_at else None,
            "iri_score": {
                "overall_score": s.overall_score,
            } if s.overall_score else None,
        }
        for s in sessions
    ]


# ─── Get Session ──────────────────────────────────────────────────────────────

@router.get("/sessions/{session_id}", summary="Get a specific session")
async def get_session(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get details for a specific coaching session."""
    stmt = (
        select(CoachingSession)
        .where(
            CoachingSession.id == session_id,
            CoachingSession.user_id == current_user.id,
        )
        .options(
            selectinload(CoachingSession.target_job),
            selectinload(CoachingSession.messages),
        )
    )
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found.",
        )

    return {
        "session_id": str(session.id),
        "job_title": session.target_job.title if session.target_job else "General Practice",
        "session_type": session.session_type,
        "status": session.status,
        "overall_score": session.overall_score,
        "started_at": str(session.started_at),
        "ended_at": str(session.ended_at) if session.ended_at else None,
        "messages": [
            {
                "id": str(m.id),
                "role": m.role,
                "content": m.content,
                "message_type": m.message_type,
                "sequence_no": m.sequence_no,
                "evaluation": m.evaluation,
            }
            for m in sorted(session.messages, key=lambda x: x.sequence_no or 0)
        ],
    }


# ─── IRI Score ────────────────────────────────────────────────────────────────

@router.get("/iri", summary="Get current IRI score")
async def get_iri_score(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the current Interview Readiness Index score and history."""
    # Get latest IRI score
    iri_stmt = (
        select(Iriscore)
        .where(Iriscore.user_id == current_user.id)
        .order_by(Iriscore.snapshot_at.desc())
    )
    iri_result = await db.execute(iri_stmt)
    iri_scores = iri_result.scalars().all()

    latest = iri_scores[0] if iri_scores else None

    # Get session history for chart
    sessions_stmt = (
        select(CoachingSession)
        .where(
            CoachingSession.user_id == current_user.id,
            CoachingSession.status == "completed",
            CoachingSession.overall_score.is_not(None),
        )
        .order_by(CoachingSession.started_at.asc())
    )
    sessions_result = await db.execute(sessions_stmt)
    completed_sessions = sessions_result.scalars().all()

    current_iri = latest.overall_score if latest else 0

    def get_readiness_level(score: float) -> str:
        if score == 0:   return "Not Started"
        if score < 30:   return "Needs Work"
        if score < 50:   return "Developing"
        if score < 70:   return "Competent"
        if score < 85:   return "Strong"
        return "Expert"

    return {
        "current_iri": current_iri,
        "readiness_level": get_readiness_level(current_iri),
        "total_sessions": len(completed_sessions),
        "breakdown": {
            "communication":      latest.communication      if latest else 0,
            "technical_accuracy": latest.technical_accuracy if latest else 0,
            "confidence":         latest.confidence         if latest else 0,
            "structure":          latest.structure          if latest else 0,
        },
        "history": [
            {
                "score": s.overall_score,
                "date":  str(s.ended_at or s.started_at),
            }
            for s in completed_sessions
            if s.overall_score
        ],
    }


# ─── Question Generator ───────────────────────────────────────────────────────

async def _generate_questions(
    job_title: str,
    company_name: str,
    job_requirements: str,
    job_description: str,
    session_type: str,
    candidate_skills: list,
    target_role: Optional[str],
) -> list:
    """Generate 5 interview questions using Gemini AI."""
    import asyncio
    import json
    import google.generativeai as genai
    from app.core.config import settings

    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-1.5-flash")

    prompt = f"""
You are an expert interviewer. Generate exactly 5 interview questions for a candidate.

JOB: {job_title} at {company_name}
SESSION TYPE: {session_type}
JOB REQUIREMENTS: {job_requirements[:600]}
CANDIDATE SKILLS: {', '.join(candidate_skills) or 'Not specified'}

INSTRUCTIONS:
- For "behavioral": focus on soft skills, teamwork, past experiences
- For "technical": focus on technical knowledge relevant to the role
- For "mixed": mix of both behavioral and technical
- Each question should have hints to guide the candidate
- Time limits: behavioral = 120s, technical = 150s

Return ONLY valid JSON array, no markdown, no explanation:
[
  {{
    "question_number": 1,
    "question": "Tell me about yourself and why you are interested in this role.",
    "type": "behavioral",
    "time_limit_seconds": 120,
    "hints": ["Focus on relevant experience", "Mention your skills", "Connect to the role"]
  }},
  {{
    "question_number": 2,
    "question": "Describe a challenging project you worked on.",
    "type": "behavioral",
    "time_limit_seconds": 120,
    "hints": ["Use the STAR method", "Focus on your contribution", "Mention the outcome"]
  }}
]

Generate all 5 questions following this exact format.
"""

    def _sync_generate():
        try:
            response = model.generate_content(prompt)
            raw = response.text.strip()
            if raw.startswith("```"):
                parts = raw.split("```")
                raw = parts[1] if len(parts) > 1 else raw
                if raw.startswith("json"):
                    raw = raw[4:]
            return json.loads(raw.strip())
        except Exception as e:
            print(f"[Coaching] Question generation failed: {e}")
            return None

    result = await asyncio.get_event_loop().run_in_executor(None, _sync_generate)

    if result and isinstance(result, list) and len(result) > 0:
        return result

    # Fallback questions
    return [
        {"question_number": 1, "question": f"Tell me about yourself and why you are interested in the {job_title} role.", "type": "behavioral", "time_limit_seconds": 120, "hints": ["Focus on relevant experience", "Mention your skills"]},
        {"question_number": 2, "question": "Describe a challenging project you worked on and how you handled it.", "type": "behavioral", "time_limit_seconds": 120, "hints": ["Use the STAR method", "Focus on your contribution"]},
        {"question_number": 3, "question": f"What skills do you have that make you a good fit for {company_name}?", "type": "behavioral", "time_limit_seconds": 120, "hints": ["Match skills to job requirements", "Give examples"]},
        {"question_number": 4, "question": "Where do you see yourself in 3 years and how does this role fit into your career goals?", "type": "behavioral", "time_limit_seconds": 120, "hints": ["Be specific", "Show ambition", "Connect to the company"]},
        {"question_number": 5, "question": "Do you have any questions for us about the role or the company?", "type": "behavioral", "time_limit_seconds": 60, "hints": ["Ask about team culture", "Ask about growth opportunities"]},
    ]