"""
Coaching WebSocket routes — real-time interview sessions.
"""
import json
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from jose import jwt, JWTError

from app.core.config import settings
from app.core.database import get_db, AsyncSessionLocal
from app.models.user import User
from app.models.coaching import CoachingSession
from app.socket.coaching_socket import (
    CoachingWebSocketHandler,
    MSG_START_SESSION,
    MSG_TEXT_ANSWER,
    MSG_AUDIO_CHUNK,
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
    """
    Validate JWT token and return user.
    Used for WebSocket authentication since we cannot use
    normal FastAPI dependencies in WebSocket handlers.
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        user_id: str = payload.get("sub")
        if not user_id:
            return None

        async with AsyncSessionLocal() as db:
            stmt = select(User).where(User.id == user_id)
            result = await db.execute(stmt)
            return result.scalar_one_or_none()

    except JWTError:
        return None


@router.websocket("/sessions/{session_id}/ws")
async def coaching_websocket(
    websocket: WebSocket,
    session_id: UUID,
    token: str = Query(..., description="JWT access token"),
):
    """
    WebSocket endpoint for real-time AI interview coaching.

    Connect with:
    ws://localhost:8000/api/v1/coaching/sessions/{session_id}/ws?token=YOUR_JWT_TOKEN

    Message flow:
    1. Connect → backend sends session_ready with questions
    2. Backend sends first question
    3. Frontend sends text_answer or audio_chunk
    4. Backend evaluates and sends evaluation + next question
    5. After all questions → backend sends session_complete with IRI score
    """
    # Authenticate user
    user = await get_user_from_token(token)
    if not user:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    # Accept WebSocket connection
    await websocket.accept()
    print(f"[WebSocket] User {user.email} connected to session {session_id}")

    # Create handler
    handler = CoachingWebSocketHandler(
        websocket=websocket,
        session_id=str(session_id),
        user=user,
    )

    try:
        async with AsyncSessionLocal() as db:
            # Load session and verify ownership
            session_stmt = select(CoachingSession).where(
                CoachingSession.id == session_id,
                CoachingSession.user_id == user.id,
            )
            session_result = await db.execute(session_stmt)
            session = session_result.scalar_one_or_none()

            if not session:
                await handler.send_error("Session not found.")
                await websocket.close(code=4004, reason="Session not found")
                return

            if session.status == "completed":
                await handler.send_error("This session is already completed.")
                await websocket.close(code=4000, reason="Session completed")
                return

            # Load questions from session messages
            from app.models.coaching import SessionMessage
            questions_stmt = select(SessionMessage).where(
                SessionMessage.session_id == session_id,
                SessionMessage.role == "interviewer",
                SessionMessage.message_type == "question",
            ).order_by(SessionMessage.sequence_no)

            questions_result = await db.execute(questions_stmt)
            question_messages = questions_result.scalars().all()

            # Build questions list
            handler.questions = [
                {
                    "question_number": msg.sequence_no,
                    "question": msg.content,
                    **(msg.evaluation or {}),
                }
                for msg in question_messages
            ]

            if not handler.questions:
                await handler.send_error(
                    "No questions found. Please create a new session."
                )
                await websocket.close()
                return

            # Send session ready message
            await handler.send(MSG_SESSION_READY, {
                "session_id": str(session_id),
                "total_questions": len(handler.questions),
                "message": "Session ready! Starting your interview...",
            })

            # Small delay then send first question
            import asyncio
            await asyncio.sleep(1)
            first_question = handler.questions[0]
            await handler.send_question(first_question)

        # ── Main Message Loop ─────────────────────────────────────────────────
        while handler.is_active:
            try:
                raw_message = await websocket.receive_json()
                msg_type = raw_message.get("type")
                msg_data = raw_message.get("data", {})

                # ── Ping/Pong ─────────────────────────────────────────────────
                if msg_type == MSG_PING:
                    await handler.send(MSG_PONG, {"status": "alive"})

                # ── Text Answer ───────────────────────────────────────────────
                elif msg_type == MSG_TEXT_ANSWER:
                    question_number = msg_data.get("question_number", 1)
                    answer = msg_data.get("answer", "").strip()
                    time_taken = msg_data.get("time_taken_seconds", 60)

                    if not answer:
                        await handler.send_error(
                            "Answer cannot be empty."
                        )
                        continue

                    # Stop the timer
                    await handler.stop_timer()

                    # Evaluate answer
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

                    # Track evaluations
                    handler.evaluations.append(
                        result.get("evaluation", {})
                    )

                    # Send evaluation to frontend
                    await handler.send(MSG_EVALUATION, result)

                    # If last question, wait for frontend to call end_session
                    if result.get("is_last_question"):
                        await handler.send(MSG_EVALUATION, {
                            "is_last_question": True,
                            "message": (
                                "You have completed all questions! "
                                "Send end_session to get your final score."
                            ),
                        })
                    else:
                        # Send next question after short delay
                        import asyncio
                        await asyncio.sleep(2)
                        next_q = result.get("next_question")
                        if next_q:
                            question_data = {
                                "question_number": next_q["question_number"],
                                "question": next_q["question"],
                                "type": next_q.get("type", "behavioral"),
                                "time_limit_seconds": next_q.get(
                                    "time_limit_seconds", 120
                                ),
                                "hints": next_q.get("hints", []),
                                "total_questions": len(handler.questions),
                            }
                            await handler.send(MSG_QUESTION, question_data)
                            await handler.start_timer(
                                seconds=next_q.get("time_limit_seconds", 120),
                                question_number=next_q["question_number"],
                            )

                # ── Audio Chunk (Phase 2 — Gemini Live) ───────────────────────
                elif msg_type == MSG_AUDIO_CHUNK:
                    # For now convert audio to text using speech recognition
                    # Full Gemini Live audio will be added in next step
                    audio_data = msg_data.get("audio", "")
                    question_number = msg_data.get("question_number", 1)

                    # TODO: Process audio with Gemini Live API
                    # For now send back a placeholder
                    await handler.send(MSG_EVALUATION, {
                        "message": (
                            "Audio received. Gemini Live API integration "
                            "coming in next step. Use text_answer for now."
                        ),
                        "question_number": question_number,
                    })

                # ── End Session ───────────────────────────────────────────────
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
                    await handler.send_error(
                        f"Unknown message type: {msg_type}"
                    )

            except WebSocketDisconnect:
                print(
                    f"[WebSocket] User {user.email} disconnected "
                    f"from session {session_id}"
                )
                handler.is_active = False
                break

            except Exception as e:
                print(f"[WebSocket] Error: {e}")
                await handler.send_error(f"An error occurred: {str(e)}")

    except WebSocketDisconnect:
        print(f"[WebSocket] Connection closed for session {session_id}")
    finally:
        await handler.stop_timer()
        print(f"[WebSocket] Session {session_id} handler cleaned up")