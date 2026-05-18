"""
Coaching Service — session management, answer evaluation, IRI scoring.
"""
from uuid import UUID
from typing import Optional
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi import HTTPException, status

from app.models.user import User
from app.models.coaching import CoachingSession, SessionMessage, Iriscore


async def _get_user_iri(db: AsyncSession, user_id: UUID) -> float:
    """Get current IRI score for a user."""
    stmt = (
        select(Iriscore)
        .where(Iriscore.user_id == user_id)
        .order_by(Iriscore.snapshot_at.desc())
    )
    result = await db.execute(stmt)
    latest = result.scalar_one_or_none()
    return latest.overall_score if latest else 0.0


async def submit_answer(
    db: AsyncSession,
    user: User,
    session_id: UUID,
    question_number: int,
    answer: str,
    time_taken_seconds: int = 60,
) -> dict:
    """Evaluate a candidate's answer using Gemini AI."""
    import asyncio
    import json
    import google.generativeai as genai
    from app.core.config import settings

    # Get session
    session = await db.get(CoachingSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    # Get the question
    q_stmt = select(SessionMessage).where(
        SessionMessage.session_id == session_id,
        SessionMessage.role == "interviewer",
        SessionMessage.sequence_no == question_number,
    )
    q_result = await db.execute(q_stmt)
    question_msg = q_result.scalar_one_or_none()

    question_text = question_msg.content if question_msg else "Unknown question"

    # Get all questions count
    total_stmt = select(SessionMessage).where(
        SessionMessage.session_id == session_id,
        SessionMessage.role == "interviewer",
    )
    total_result = await db.execute(total_stmt)
    total_questions = len(total_result.scalars().all())

    # Evaluate with Gemini
    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-1.5-flash")

    prompt = f"""
You are an expert interview coach evaluating a candidate's answer.

QUESTION: {question_text}
CANDIDATE ANSWER: {answer}
TIME TAKEN: {time_taken_seconds} seconds

Evaluate the answer on these dimensions (score 0-100 each):
- clarity: How clear and understandable was the answer?
- confidence: How confident did the candidate sound?
- technical_accuracy: How technically accurate was the content?
- structure: How well structured was the answer?
- relevance: How relevant was the answer to the question?

Return ONLY valid JSON, no markdown:
{{
    "scores": {{
        "clarity": 70,
        "confidence": 65,
        "technical_accuracy": 60,
        "structure": 70,
        "relevance": 75
    }},
    "overall_score": 68,
    "strengths": ["Good use of examples", "Clear communication"],
    "improvements": ["Add more technical depth", "Structure answer better"],
    "encouragement": "Good effort! Focus on structuring your answer using the STAR method.",
    "follow_up": "Can you elaborate on the technical aspects of that project?"
}}
"""

    def _sync_evaluate():
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
            print(f"[Coaching] Evaluation failed: {e}")
            return None

    eval_result = await asyncio.get_event_loop().run_in_executor(None, _sync_evaluate)

    if not eval_result:
        eval_result = {
            "scores": {"clarity": 60, "confidence": 60, "technical_accuracy": 60, "structure": 60, "relevance": 60},
            "overall_score": 60,
            "strengths": ["Attempted the question"],
            "improvements": ["Provide more detail"],
            "encouragement": "Keep going, you are doing well!",
            "follow_up": None,
        }

    # Save answer as session message
    answer_msg = SessionMessage(
        session_id=session_id,
        role="candidate",
        content=answer,
        message_type="answer",
        sequence_no=question_number,
        evaluation=eval_result,
    )
    db.add(answer_msg)
    await db.commit()

    is_last = question_number >= total_questions

    # Get next question if not last
    next_question = None
    if not is_last:
        next_q_stmt = select(SessionMessage).where(
            SessionMessage.session_id == session_id,
            SessionMessage.role == "interviewer",
            SessionMessage.sequence_no == question_number + 1,
        )
        next_q_result = await db.execute(next_q_stmt)
        next_q_msg = next_q_result.scalar_one_or_none()
        if next_q_msg:
            next_question = {
                "question_number": next_q_msg.sequence_no,
                "question": next_q_msg.content,
                "type": (next_q_msg.evaluation or {}).get("type", "behavioral"),
                "time_limit_seconds": (next_q_msg.evaluation or {}).get("time_limit_seconds", 120),
                "hints": (next_q_msg.evaluation or {}).get("hints", []),
            }

    return {
        "question_number": question_number,
        "is_last_question": is_last,
        "evaluation": eval_result,
        "next_question": next_question,
    }


async def end_session(
    db: AsyncSession,
    user: User,
    session_id: UUID,
) -> dict:
    """End a session, calculate IRI score, and save."""
    session = await db.get(CoachingSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    # Get all answer evaluations
    answers_stmt = select(SessionMessage).where(
        SessionMessage.session_id == session_id,
        SessionMessage.role == "candidate",
    )
    answers_result = await db.execute(answers_stmt)
    answers = answers_result.scalars().all()

    if not answers:
        return {"message": "No answers recorded.", "iri_score": {"overall_score": 0}}

    # Calculate average scores
    clarity = []
    confidence = []
    technical = []
    structure = []
    relevance = []

    for a in answers:
        if a.evaluation and "scores" in a.evaluation:
            scores = a.evaluation["scores"]
            clarity.append(scores.get("clarity", 0))
            confidence.append(scores.get("confidence", 0))
            technical.append(scores.get("technical_accuracy", 0))
            structure.append(scores.get("structure", 0))
            relevance.append(scores.get("relevance", 0))

    def avg(lst): return sum(lst) / len(lst) if lst else 0

    avg_clarity     = avg(clarity)
    avg_confidence  = avg(confidence)
    avg_technical   = avg(technical)
    avg_structure   = avg(structure)
    avg_relevance   = avg(relevance)

    # Weighted IRI score
    overall = (
        avg_clarity    * 0.25 +
        avg_confidence * 0.20 +
        avg_technical  * 0.25 +
        avg_structure  * 0.20 +
        avg_relevance  * 0.10
    )

    # Update session
    session.status = "completed"
    session.ended_at = datetime.now(timezone.utc)
    session.overall_score = overall

    # Save IRI score snapshot
    iri = Iriscore(
        user_id=user.id,
        overall_score=overall,
        communication=avg_clarity,
        technical_accuracy=avg_technical,
        confidence=avg_confidence,
        structure=avg_structure,
        sessions_count=1,
        snapshot_at=datetime.now(timezone.utc),
    )
    db.add(iri)

    # Update profile IRI score
    from app.models.profile import Profile
    profile_stmt = select(Profile).where(Profile.user_id == user.id)
    profile_result = await db.execute(profile_stmt)
    profile = profile_result.scalar_one_or_none()
    if profile:
        profile.iri_score = overall

    await db.commit()

    def get_readiness_level(score: float) -> str:
        if score < 30:  return "Needs Work"
        if score < 50:  return "Developing"
        if score < 70:  return "Competent"
        if score < 85:  return "Strong"
        return "Expert"

    return {
        "iri_score": {
            "overall_score": round(overall, 1),
            "communication": round(avg_clarity, 1),
            "technical_accuracy": round(avg_technical, 1),
            "confidence": round(avg_confidence, 1),
            "structure": round(avg_structure, 1),
            "readiness_level": get_readiness_level(overall),
            "next_step": f"Your IRI is {round(overall, 1)}. {get_readiness_level(overall)} — keep practising!",
        }
    }