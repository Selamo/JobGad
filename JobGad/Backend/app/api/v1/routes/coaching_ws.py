"""
Coaching WebSocket routes — real-time interview with Gemini Live API.
"""
import json
import asyncio
import base64
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.future import select
from jose import jwt, JWTError

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.user import User
from app.models.coaching import CoachingSession, SessionMessage
from app.models.job import JobListing
from app.models.company import Company
from app.socket.coaching_socket import (
    CoachingWebSocketHandler,
    MSG_START_SESSION,
    MSG_AUDIO_CHUNK,
    MSG_TEXT_ANSWER,
    MSG_END_SESSION,
    MSG_PING,
    MSG_SESSION_READY,
    MSG_QUESTION,
    MSG_EVALUATION,
    MSG_SESSION_COMPLETE,
    MSG_PONG,
    MSG_ERROR,
)

router = APIRouter()


async def get_user_from_token(token: str) -> User | None:
    """Validate JWT and return user."""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        user_id = payload.get("sub")
        if not user_id:
            return None

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(User).where(User.id == user_id)
            )
            return result.scalar_one_or_none()

    except JWTError:
        return None


@router.websocket("/sessions/{session_id}/ws")
async def coaching_websocket(
    websocket: WebSocket,
    session_id: UUID,
    token: str = Query(...),
    mode: str = Query(default="audio", description="audio or text"),
):
    """
    WebSocket endpoint for real-time AI interview coaching.

    Modes:
    - audio: Full Gemini Live API with real audio (default)
    - text: Text-based fallback for testing

    Connect:
    ws://localhost:8000/api/v1/coaching/sessions/{id}/ws?token=TOKEN&mode=audio

    Frontend sends:
    - {type: "audio_chunk", data: {audio: "base64...", question_number: 1}}
    - {type: "text_answer", data: {answer: "...", question_number: 1, time_taken_seconds: 45}}
    - {type: "end_session", data: {}}
    - {type: "ping", data: {}}

    Backend sends:
    - {type: "session_ready", data: {...}}
    - {type: "audio_response", data: {data: "base64...", mime_type: "audio/pcm;rate=24000"}}
    - {type: "transcript", data: {role: "interviewer", text: "..."}}
    - {type: "evaluation", data: {...}}
    - {type: "timer", data: {remaining_seconds: 90, total_seconds: 120}}
    - {type: "session_complete", data: {iri_score: {...}}}
    """
    # Authenticate
    user = await get_user_from_token(token)
    if not user:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    await websocket.accept()
    print(f"[WS] {user.email} connected | session={session_id} | mode={mode}")

    handler = CoachingWebSocketHandler(
        websocket=websocket,
        session_id=str(session_id),
        user=user,
    )

    try:
        async with AsyncSessionLocal() as db:
            # Verify session
            session = await db.get(CoachingSession, session_id)
            if not session or str(session.user_id) != str(user.id):
                await handler.send_error("Session not found.")
                await websocket.close(code=4004)
                return

            if session.status == "completed":
                await handler.send_error("Session already completed.")
                await websocket.close(code=4000)
                return

            # Load questions
            q_result = await db.execute(
                select(SessionMessage)
                .where(
                    SessionMessage.session_id == session_id,
                    SessionMessage.role == "interviewer",
                )
                .order_by(SessionMessage.sequence_no)
            )
            question_messages = q_result.scalars().all()

            handler.questions = [
                {
                    "question_number": msg.sequence_no,
                    "question": msg.content,
                    **(msg.evaluation or {}),
                }
                for msg in question_messages
            ]

            if not handler.questions:
                await handler.send_error("No questions found.")
                await websocket.close()
                return

            # Load job details for Gemini Live
            job = await db.get(JobListing, session.target_job_id)
            company_name = "the company"
            if job and job.company_id:
                company = await db.get(Company, job.company_id)
                if company:
                    company_name = company.name

            # Get user IRI score
            from app.services.coaching_service import _get_user_iri
            iri_score = await _get_user_iri(db, user.id)

        # ── Initialize Gemini Live (audio mode) ───────────────────────────────
        if mode == "audio":
            await handler.send(MSG_SESSION_READY, {
                "session_id": str(session_id),
                "total_questions": len(handler.questions),
                "mode": "audio",
                "message": "Connecting to AI interviewer...",
            })

            connected = await handler.init_gemini_live(
                job_title=job.title if job else "the role",
                company_name=company_name,
                job_requirements=job.requirements or "" if job else "",
                iri_score=iri_score,
                session_type=session.session_type or "mixed",
            )

            if not connected:
                await handler.send_error(
                    "Could not connect to Gemini Live. Switching to text mode."
                )
                mode = "text"
            else:
                await handler.send(MSG_SESSION_READY, {
                    "session_id": str(session_id),
                    "total_questions": len(handler.questions),
                    "mode": "audio",
                    "message": "AI interviewer connected! Interview starting...",
                    "personality": handler.gemini_session.personality["level"],
                })

                # Start Gemini Live interview
                await handler.start_gemini_interview()

        # ── Text mode fallback ────────────────────────────────────────────────
        if mode == "text":
            await handler.send(MSG_SESSION_READY, {
                "session_id": str(session_id),
                "total_questions": len(handler.questions),
                "mode": "text",
                "message": "Text mode active. Interview starting...",
            })

            await asyncio.sleep(1)
            first_q = handler.questions[0]
            await handler.send(MSG_QUESTION, {
                "question_number": first_q["question_number"],
                "question": first_q["question"],
                "type": first_q.get("type", "behavioral"),
                "time_limit_seconds": first_q.get("time_limit_seconds", 120),
                "hints": first_q.get("hints", []),
                "total_questions": len(handler.questions),
            })
            await handler.start_timer(
                seconds=first_q.get("time_limit_seconds", 120),
                question_number=first_q["question_number"],
            )

        # ── Main Message Loop ─────────────────────────────────────────────────
        while handler.is_active:
            try:
                raw = await websocket.receive_json()
                msg_type = raw.get("type")
                msg_data = raw.get("data", {})

                # Ping
                if msg_type == MSG_PING:
                    await handler.send(MSG_PONG, {"status": "alive"})

                # Audio chunk from microphone
                elif msg_type == MSG_AUDIO_CHUNK:
                    audio_b64 = msg_data.get("audio", "")
                    if audio_b64 and mode == "audio":
                        # Decode base64 audio and send to Gemini Live
                        audio_bytes = base64.b64decode(audio_b64)
                        await handler.audio_input_queue.put(audio_bytes)

                        # Also track question number for evaluation
                        question_number = msg_data.get("question_number", 1)

                # Text answer
                elif msg_type == MSG_TEXT_ANSWER:
                    question_number = msg_data.get("question_number", 1)
                    answer = msg_data.get("answer", "").strip()
                    time_taken = msg_data.get("time_taken_seconds", 60)

                    if not answer:
                        await handler.send_error("Answer cannot be empty.")
                        continue

                    await handler.stop_timer()

                    # Evaluate with Gemini
                    async with AsyncSessionLocal() as db:
                        from app.services.coaching_service import submit_answer
                        result = await submit_answer(
                            db=db,
                            user=user,
                            session_id=session_id,
                            question_number=question_number,
                            answer=answer,
                            time_taken_seconds=time_taken,
                        )

                    handler.evaluations.append(
                        result.get("evaluation", {})
                    )

                    await handler.send(MSG_EVALUATION, result)

                    # If in audio mode, also send text to Gemini Live
                    if mode == "audio" and handler.gemini_session:
                        await handler.gemini_session.send_text(
                            f"The candidate answered: {answer}"
                        )

                    # Send next question in text mode
                    if not result.get("is_last_question") and mode == "text":
                        await asyncio.sleep(2)
                        next_q = result.get("next_question")
                        if next_q:
                            await handler.send(MSG_QUESTION, {
                                "question_number": next_q["question_number"],
                                "question": next_q["question"],
                                "type": next_q.get("type", "behavioral"),
                                "time_limit_seconds": next_q.get(
                                    "time_limit_seconds", 120
                                ),
                                "hints": next_q.get("hints", []),
                                "total_questions": len(handler.questions),
                            })
                            await handler.start_timer(
                                seconds=next_q.get("time_limit_seconds", 120),
                                question_number=next_q["question_number"],
                            )

                # End session
                elif msg_type == MSG_END_SESSION:
                    await handler.stop_timer()

                    async with AsyncSessionLocal() as db:
                        from app.services.coaching_service import end_session
                        final_result = await end_session(
                            db=db,
                            user=user,
                            session_id=session_id,
                        )

                    await handler.send(MSG_SESSION_COMPLETE, final_result)
                    handler.is_active = False
                    break

                else:
                    await handler.send_error(f"Unknown message: {msg_type}")

            except WebSocketDisconnect:
                print(f"[WS] {user.email} disconnected")
                handler.is_active = False
                break

            except Exception as e:
                print(f"[WS] Error: {e}")
                await handler.send_error(str(e))

    except WebSocketDisconnect:
        print(f"[WS] Connection closed for session {session_id}")
    finally:
        await handler.cleanup()
        print(f"[WS] Session {session_id} cleaned up")