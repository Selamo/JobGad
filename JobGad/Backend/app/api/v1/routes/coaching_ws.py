"""
Coaching WebSocket routes — real-time interview with Gemini Live API.
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
    print(f"[WS] {user.email} connected | session={session_id} | mode={mode}")

    handler = CoachingWebSocketHandler(
        websocket=websocket,
        session_id=str(session_id),
        user=user,
    )

    try:
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
                .where(SessionMessage.session_id == session_id, SessionMessage.role == "interviewer")
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

            job = await db.get(JobListing, session.target_job_id)
            company_name = "the company"
            if job and job.company_id:
                company = await db.get(Company, job.company_id)
                if company:
                    company_name = company.name

            from app.services.coaching_service import _get_user_iri
            iri_score = await _get_user_iri(db, user.id)

        # ── Determine final mode ──────────────────────────────────────────────
        final_mode = "text"  # default to text

        if mode == "audio":
            await handler.send(MSG_SESSION_READY, {
                "session_id": str(session_id),
                "total_questions": len(handler.questions),
                "mode": "audio",
                "message": "Connecting to AI interviewer...",
            })
            try:
                connected = await asyncio.wait_for(
                    handler.init_gemini_live(
                        job_title=job.title if job else "the role",
                        company_name=company_name,
                        job_requirements=job.requirements or "" if job else "",
                        iri_score=iri_score,
                        session_type=session.session_type or "mixed",
                    ),
                    timeout=15.0
                )
                if connected:
                    final_mode = "audio"
            except Exception as e:
                print(f"[WS] Gemini Live failed: {e}, falling back to text mode")
                final_mode = "text"

        # ── Start audio mode ──────────────────────────────────────────────────
        if final_mode == "audio":
            await handler.send(MSG_SESSION_READY, {
                "session_id": str(session_id),
                "total_questions": len(handler.questions),
                "mode": "audio",
                "message": "AI interviewer connected! Interview starting...",
                "personality": handler.gemini_session.personality["level"],
            })
            await handler.start_gemini_interview()

        # ── Start text mode ───────────────────────────────────────────────────
        else:
            final_mode = "text"
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

                if msg_type == MSG_PING:
                    await handler.send(MSG_PONG, {"status": "alive"})

                elif msg_type == MSG_AUDIO_CHUNK:
                    if final_mode == "audio":
                        audio_b64 = msg_data.get("audio", "")
                        if audio_b64:
                            audio_bytes = base64.b64decode(audio_b64)
                            await handler.audio_input_queue.put(audio_bytes)

                elif msg_type == MSG_TEXT_ANSWER:
                    question_number = msg_data.get("question_number", 1)
                    answer = msg_data.get("answer", "").strip()
                    time_taken = msg_data.get("time_taken_seconds", 60)

                    print(f"[WS] MSG_TEXT_ANSWER received | Q#{question_number} | answer_len={len(answer)} | final_mode={final_mode}")

                    if answer == "__audio_complete__":
                        answer = "[Audio response — transcription unavailable. Please use text mode for best results.]"

                    if not answer:
                        await handler.send_error("Answer cannot be empty.")
                        continue

                    await handler.stop_timer()

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
                        print(f"[WS] submit_answer completed successfully")
                    except Exception as submit_err:
                        print(f"[WS] submit_answer FAILED: {type(submit_err).__name__}: {submit_err}")
                        await handler.send_error(f"Evaluation failed: {str(submit_err)}")
                        continue

                    print(f"[WS] Evaluation done | is_last={result.get('is_last_question')} | has_eval={bool(result.get('evaluation'))}")
                    print(f"[WS] handler.questions count={len(handler.questions)} | numbers={[q['question_number'] for q in handler.questions]}")

                    handler.evaluations.append(result.get("evaluation", {}))
                    await handler.send(MSG_EVALUATION, result)
                    print(f"[WS] MSG_EVALUATION sent to frontend")

                    if final_mode == "audio" and handler.gemini_session:
                        await handler.gemini_session.send_text(f"The candidate answered: {answer}")

                    if not result.get("is_last_question") and final_mode == "text":
                        print(f"[WS] Looking for next question Q#{question_number + 1} ...")
                        await handler.send(MSG_PONG, {"status": "loading_next"})
                        await asyncio.sleep(0.5)

                        next_q_number = question_number + 1
                        next_q = next(
                            (q for q in handler.questions if q["question_number"] == next_q_number),
                            None,
                        )

                        if next_q:
                            await handler.send(MSG_QUESTION, {
                                "question_number": next_q["question_number"],
                                "question":        next_q["question"],
                                "type":            next_q.get("type", "behavioral"),
                                "time_limit_seconds": next_q.get("time_limit_seconds", 120),
                                "hints":           next_q.get("hints", []),
                                "total_questions": len(handler.questions),
                            })
                            await handler.start_timer(
                                seconds=next_q.get("time_limit_seconds", 120),
                                question_number=next_q["question_number"],
                            )
                            print(f"[WS] MSG_QUESTION Q#{next_q_number} sent to frontend ✓")
                        else:
                            print(f"[WS] ERROR — Q#{next_q_number} NOT FOUND in handler.questions!")
                            await handler.send_error(f"Could not load question {next_q_number}. Please end session.")

                    elif result.get("is_last_question"):
                        print(f"[WS] Last question answered — waiting for MSG_END_SESSION from frontend")

                elif msg_type == MSG_END_SESSION:
                    await handler.stop_timer()
                    try:
                        async with AsyncSessionLocal() as db:
                            from app.services.coaching_service import end_session
                            final_result = await end_session(db=db, user=user, session_id=session_id)
                        await handler.send(MSG_SESSION_COMPLETE, final_result)
                    except Exception as end_err:
                        print(f"[WS] end_session FAILED: {type(end_err).__name__}: {end_err}")
                        await handler.send_error(f"Failed to end session: {str(end_err)}")
                    handler.is_active = False
                    break

                else:
                    await handler.send_error(f"Unknown message type: {msg_type}")

            except WebSocketDisconnect:
                print(f"[WS] {user.email} disconnected")
                handler.is_active = False
                break
            except Exception as e:
                print(f"[WS] Error in message loop: {type(e).__name__}: {e}")
                await handler.send_error(str(e))

    except WebSocketDisconnect:
        print(f"[WS] Connection closed for session {session_id}")
    except Exception as e:
        print(f"[WS] Fatal error: {type(e).__name__}: {e}")
        try:
            await handler.send_error(f"Server error: {str(e)}")
        except Exception:
            pass
    finally:
        await handler.cleanup()
        print(f"[WS] Session {session_id} cleaned up")