"""
Coaching WebSocket — real-time interview session handler.
Bridges the Next.js frontend with Gemini Live API.
"""
import json
import asyncio
import base64
from uuid import UUID
from datetime import datetime, timezone

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.coaching import CoachingSession, SessionMessage
from app.models.user import User


# ─── Message Types ────────────────────────────────────────────────────────────

# Frontend → Backend
MSG_START_SESSION = "start_session"
MSG_AUDIO_CHUNK = "audio_chunk"
MSG_TEXT_ANSWER = "text_answer"
MSG_END_SESSION = "end_session"
MSG_PING = "ping"

# Backend → Frontend
MSG_SESSION_READY = "session_ready"
MSG_QUESTION = "question"
MSG_AUDIO_RESPONSE = "audio_response"
MSG_TRANSCRIPT = "transcript"
MSG_EVALUATION = "evaluation"
MSG_SESSION_COMPLETE = "session_complete"
MSG_ERROR = "error"
MSG_PONG = "pong"
MSG_TIMER = "timer"
MSG_TURN_COMPLETE = "turn_complete"


class CoachingWebSocketHandler:
    """
    Handles a single coaching WebSocket connection.
    Manages Gemini Live session and message routing.
    """

    def __init__(
        self,
        websocket: WebSocket,
        session_id: str,
        user: User,
    ):
        self.websocket = websocket
        self.session_id = session_id
        self.user = user
        self.questions = []
        self.evaluations = []
        self.is_active = True
        self.timer_task = None
        self.gemini_session = None

        # Queues for Gemini Live communication
        self.audio_input_queue = asyncio.Queue()
        self.audio_output_queue = asyncio.Queue()
        self.text_output_queue = asyncio.Queue()
        self.control_queue = asyncio.Queue()

    async def send(self, message_type: str, data: dict):
        """Send JSON message to frontend."""
        try:
            await self.websocket.send_json({
                "type": message_type,
                "data": data,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        except Exception as e:
            print(f"[WebSocket] Send failed: {e}")
            self.is_active = False

    async def send_error(self, message: str):
        """Send error to frontend."""
        await self.send(MSG_ERROR, {"message": message})

    async def start_timer(self, seconds: int, question_number: int):
        """Start countdown timer for current question."""
        if self.timer_task:
            self.timer_task.cancel()

        async def countdown():
            for remaining in range(seconds, -1, -1):
                if not self.is_active:
                    break
                await self.send(MSG_TIMER, {
                    "remaining_seconds": remaining,
                    "total_seconds": seconds,
                    "question_number": question_number,
                    "time_up": remaining == 0,
                })
                if remaining == 0:
                    break
                await asyncio.sleep(1)

        self.timer_task = asyncio.create_task(countdown())

    async def stop_timer(self):
        """Stop current timer."""
        if self.timer_task:
            self.timer_task.cancel()
            self.timer_task = None

    async def forward_gemini_audio(self):
        """
        Forward audio from Gemini to the frontend.
        Runs as a background task.
        """
        while self.is_active:
            try:
                chunk = await asyncio.wait_for(
                    self.audio_output_queue.get(),
                    timeout=0.1,
                )
                await self.send(MSG_AUDIO_RESPONSE, chunk)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                print(f"[WebSocket] Audio forward error: {e}")
                break

    async def forward_gemini_text(self):
        """
        Forward text/events from Gemini to the frontend.
        Runs as a background task.
        """
        while self.is_active:
            try:
                event = await asyncio.wait_for(
                    self.text_output_queue.get(),
                    timeout=0.1,
                )

                event_type = event.get("type")

                if event_type == "transcript":
                    await self.send(MSG_TRANSCRIPT, {
                        "role": event["role"],
                        "text": event["text"],
                    })

                elif event_type == "turn_complete":
                    await self.send(MSG_TURN_COMPLETE, {
                        "message": "AI finished speaking",
                    })

                elif event_type == "interview_complete":
                    await self.send(MSG_EVALUATION, {
                        "is_last_question": True,
                        "message": "Interview complete. Send end_session to get your score.",
                    })

                elif event_type == "error":
                    await self.send_error(event.get("message", "Gemini error"))

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                print(f"[WebSocket] Text forward error: {e}")
                break

    async def init_gemini_live(
        self,
        job_title: str,
        company_name: str,
        job_requirements: str,
        iri_score: float,
        session_type: str,
    ) -> bool:
        """
        Initialize and connect to Gemini Live API.
        """
        from app.tools.gemini_live import GeminiLiveSession

        self.gemini_session = GeminiLiveSession(
            job_title=job_title,
            company_name=company_name,
            job_requirements=job_requirements,
            questions=self.questions,
            iri_score=iri_score,
            session_type=session_type,
        )

        connected = await self.gemini_session.connect()
        return connected

    async def start_gemini_interview(self):
        """
        Start the Gemini Live interview in background tasks.
        """
        if not self.gemini_session:
            return

        # Start Gemini session in background
        asyncio.create_task(
            self.gemini_session.run_interview(
                audio_input_queue=self.audio_input_queue,
                audio_output_queue=self.audio_output_queue,
                text_output_queue=self.text_output_queue,
                control_queue=self.control_queue,
            )
        )

        # Start forwarding audio and text to frontend
        asyncio.create_task(self.forward_gemini_audio())
        asyncio.create_task(self.forward_gemini_text())

    async def cleanup(self):
        """Clean up resources."""
        self.is_active = False
        await self.stop_timer()
        await self.control_queue.put("stop")
        if self.gemini_session:
            await self.gemini_session.disconnect()