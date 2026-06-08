"""
Coaching WebSocket — reliable interview with voice and text input support.
Gemini Live is disabled in favour of stable text-mode question delivery.
Browser Speech Recognition handles voice-to-text on the frontend.
"""
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


async def get_user_from_token(token: str):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            return None
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(User).where(User.id == user_id))
            return result.scalar_one_or_none()
    except JWTError:
        return None


@router.websocket("/sessions/{session_id}/ws")
async def coaching_websocket(
    websocket: WebSocket,
    session_id: UUID,
    token: str = Query(...),
    mode: str = Query(default="audio"),
):
    user = await get_user_from_token(token)
    if not user:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    await websocket.accept()
    print(f"[WS] {user.email} connected | session={session_id}")

    handler = CoachingWebSocketHandler(
        websocket=websocket,
        session_id=str(session_id),
        user=user,
    )

    try:
        # ── Load session and questions ────────────────────────────────────────
        async with AsyncSessionLocal() as db:
            session = await db.get(CoachingSession, session_id)
            if not session or str(session.user_id) != str(user.id):
                await handler.send_error("Session not found.")
                await websocket.close(code=4004)
                return

            if session.status == "completed":
                await handler.send_error("Session already completed.")
                await websocket.close(code=4000)
                return

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
                    "question":        msg.content,
                    **(msg.evaluation or {}),
                }
                for msg in question_messages
            ]

            if not handler.questions:
                await handler.send_error("No questions found for this session.")
                await websocket.close()
                return

        print(f"[WS] Loaded {len(handler.questions)} questions")

        # ── Send session ready ────────────────────────────────────────────────
        # Always deliver questions as text for reliability.
        # Frontend shows mic button (mode=audio) so voice answers still work
        # via browser Speech Recognition — transcribed to text before sending.
        await handler.send(MSG_SESSION_READY, {
            "session_id":      str(session_id),
            "total_questions": len(handler.questions),
            "mode":            "audio",
            "personality":     "friendly",
            "message":         "AI Interviewer connected! Interview starting...",
        })

        await asyncio.sleep(0.8)

        # ── Send first question ───────────────────────────────────────────────
        first_q = handler.questions[0]
        await handler.send(MSG_QUESTION, {
            "question_number":    first_q["question_number"],
            "question":           first_q["question"],
            "type":               first_q.get("type", "behavioral"),
            "time_limit_seconds": first_q.get("time_limit_seconds", 120),
            "hints":              first_q.get("hints", []),
            "total_questions":    len(handler.questions),
        })
        await handler.start_timer(
            seconds=first_q.get("time_limit_seconds", 120),
            question_number=first_q["question_number"],
        )
        print(f"[WS] Q1 of {len(handler.questions)} sent to frontend")

        # ── Main message loop ─────────────────────────────────────────────────
        while handler.is_active:
            try:
                raw      = await websocket.receive_json()
                msg_type = raw.get("type")
                msg_data = raw.get("data", {})

                # ── Keepalive ping ────────────────────────────────────────────
                if msg_type == MSG_PING:
                    await handler.send(MSG_PONG, {"status": "alive"})

                # ── Audio chunks — ignored, browser handles transcription ──────
                elif msg_type == MSG_AUDIO_CHUNK:
                    pass

                # ── Answer received ───────────────────────────────────────────
                elif msg_type == MSG_TEXT_ANSWER:
                    question_number = msg_data.get("question_number", 1)
                    answer          = msg_data.get("answer", "").strip()
                    time_taken      = msg_data.get("time_taken_seconds", 60)

                    print(f"[WS] Answer received | Q#{question_number} | len={len(answer)}")

                    if answer == "__audio_complete__":
                        answer = "[Voice response received]"

                    if not answer:
                        await handler.send_error("Answer cannot be empty.")
                        continue

                    await handler.stop_timer()

                    # Evaluate the answer
                    try:
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
                    except Exception as err:
                        print(f"[WS] Evaluation error: {type(err).__name__}: {err}")
                        await handler.send_error("Evaluation failed. Please try again.")
                        continue

                    handler.evaluations.append(result.get("evaluation", {}))

                    # Send evaluation feedback to frontend
                    await handler.send(MSG_EVALUATION, result)
                    print(f"[WS] Evaluation sent | Q#{question_number} | is_last={result.get('is_last_question')}")

                    # Send next question unless this was the last one
                    if not result.get("is_last_question"):
                        # Brief keepalive so the connection stays alive during the pause
                        await handler.send(MSG_PONG, {"status": "loading_next"})
                        await asyncio.sleep(0.5)

                        next_q_number = question_number + 1
                        next_q = next(
                            (q for q in handler.questions
                             if q["question_number"] == next_q_number),
                            None,
                        )

                        if next_q:
                            await handler.send(MSG_QUESTION, {
                                "question_number":    next_q["question_number"],
                                "question":           next_q["question"],
                                "type":               next_q.get("type", "behavioral"),
                                "time_limit_seconds": next_q.get("time_limit_seconds", 120),
                                "hints":              next_q.get("hints", []),
                                "total_questions":    len(handler.questions),
                            })
                            await handler.start_timer(
                                seconds=next_q.get("time_limit_seconds", 120),
                                question_number=next_q["question_number"],
                            )
                            print(f"[WS] Q#{next_q_number} sent to frontend ✓")
                        else:
                            print(f"[WS] ERROR: Q#{next_q_number} not found in handler.questions")
                            await handler.send_error(
                                f"Could not load question {next_q_number}. Please end the session."
                            )
                    else:
                        print(f"[WS] All questions answered — waiting for end session")

                # ── End session ───────────────────────────────────────────────
                elif msg_type == MSG_END_SESSION:
                    await handler.stop_timer()
                    try:
                        async with AsyncSessionLocal() as db:
                            from app.services.coaching_service import end_session
                            final_result = await end_session(
                                db=db, user=user, session_id=session_id
                            )
                        await handler.send(MSG_SESSION_COMPLETE, final_result)
                        print(f"[WS] Session completed for {user.email}")
                    except Exception as err:
                        print(f"[WS] End session error: {type(err).__name__}: {err}")
                        await handler.send_error("Failed to complete session.")
                    handler.is_active = False
                    break

                else:
                    await handler.send_error(f"Unknown message type: {msg_type}")

            except WebSocketDisconnect:
                print(f"[WS] {user.email} disconnected")
                handler.is_active = False
                break
            except Exception as e:
                print(f"[WS] Loop error: {type(e).__name__}: {e}")
                await handler.send_error(str(e))

    except WebSocketDisconnect:
        print(f"[WS] Connection closed | session={session_id}")
    except Exception as e:
        print(f"[WS] Fatal error: {type(e).__name__}: {e}")
        try:
            await handler.send_error(f"Server error: {str(e)}")
        except Exception:
            pass
    finally:
        await handler.cleanup()
        print(f"[WS] Session {session_id} cleaned up")