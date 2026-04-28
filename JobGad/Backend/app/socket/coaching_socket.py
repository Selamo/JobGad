"""
Coaching WebSocket — real-time interview session handler.
Bridges the Next.js frontend with Gemini Live API.
"""
import json
import asyncio
from uuid import UUID
from datetime import datetime, timezone

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.coaching import CoachingSession, SessionMessage
from app.models.user import User


# ─── Message Types ────────────────────────────────────────────────────────────
# These are the message types sent between frontend and backend

# Frontend → Backend
MSG_START_SESSION = "start_session"       # Start the interview
MSG_AUDIO_CHUNK = "audio_chunk"           # Audio data from microphone
MSG_TEXT_ANSWER = "text_answer"           # Text answer (fallback)
MSG_END_SESSION = "end_session"           # User ends session
MSG_PING = "ping"                         # Keep connection alive

# Backend → Frontend
MSG_SESSION_READY = "session_ready"       # Session created, ready to start
MSG_QUESTION = "question"                 # New question from AI
MSG_AUDIO_RESPONSE = "audio_response"    # AI audio response
MSG_EVALUATION = "evaluation"            # Answer evaluation
MSG_SESSION_COMPLETE = "session_complete" # Session ended with IRI
MSG_ERROR = "error"                       # Error message
MSG_PONG = "pong"                        # Ping response
MSG_TIMER = "timer"                      # Timer update


class CoachingWebSocketHandler:
    """
    Handles a single coaching session WebSocket connection.
    One instance per connected user.
    """

    def __init__(self, websocket: WebSocket, session_id: str, user: User):
        self.websocket = websocket
        self.session_id = session_id
        self.user = user
        self.current_question_index = 0
        self.questions = []
        self.evaluations = []
        self.is_active = True
        self.timer_task = None

    async def send(self, message_type: str, data: dict):
        """Send a JSON message to the frontend."""
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
        """Send an error message to the frontend."""
        await self.send(MSG_ERROR, {"message": message})

    async def start_timer(self, seconds: int, question_number: int):
        """Start a countdown timer for the current question."""
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
                    # Time is up — notify frontend
                    await self.send(MSG_EVALUATION, {
                        "question_number": question_number,
                        "time_up": True,
                        "message": "Time is up! Moving to the next question.",
                    })
                    break
                await asyncio.sleep(1)

        self.timer_task = asyncio.create_task(countdown())

    async def stop_timer(self):
        """Stop the current timer."""
        if self.timer_task:
            self.timer_task.cancel()
            self.timer_task = None

    async def send_question(self, question: dict):
        """Send a question to the frontend."""
        await self.send(MSG_QUESTION, {
            "question_number": question["question_number"],
            "question": question["question"],
            "type": question.get("type", "behavioral"),
            "time_limit_seconds": question.get("time_limit_seconds", 120),
            "hints": question.get("hints", []),
            "total_questions": len(self.questions),
        })

        # Start timer for this question
        await self.start_timer(
            seconds=question.get("time_limit_seconds", 120),
            question_number=question["question_number"],
        )