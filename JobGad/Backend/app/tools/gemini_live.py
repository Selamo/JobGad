"""
Gemini Live API — real-time audio conversation handler for interview coaching.
Uses Google's Gemini Live API for bidirectional audio streaming.
"""
import asyncio
import base64
import json
from typing import AsyncGenerator, Optional
import google.generativeai as genai
from google.genai import types
from app.core.config import settings

# Configure Gemini
genai.configure(api_key=settings.GEMINI_API_KEY)


def get_interviewer_personality(iri_score: float) -> dict:
    """
    Get interviewer personality config based on IRI score.
    As score improves, personality becomes more formal.
    """
    if iri_score < 30:
        return {
            "level": "very_friendly",
            "voice": "Aoede",  # Warm, friendly voice
            "style": (
                "You are a very warm and encouraging interview coach. "
                "You speak slowly and clearly. "
                "You give hints when the candidate struggles. "
                "You celebrate small wins enthusiastically. "
                "You never criticize harshly — always frame feedback positively."
            ),
        }
    elif iri_score < 50:
        return {
            "level": "friendly",
            "voice": "Aoede",
            "style": (
                "You are a friendly and supportive interviewer. "
                "You are encouraging but also constructive. "
                "You give clear feedback after each answer. "
                "You help the candidate improve with specific tips."
            ),
        }
    elif iri_score < 70:
        return {
            "level": "balanced",
            "voice": "Charon",  # More neutral voice
            "style": (
                "You are a balanced professional interviewer. "
                "You are neither too friendly nor too strict. "
                "You give honest, constructive feedback. "
                "You maintain a professional tone throughout."
            ),
        }
    elif iri_score < 85:
        return {
            "level": "formal",
            "voice": "Fenrir",  # More formal voice
            "style": (
                "You are a formal corporate interviewer. "
                "You maintain strict professionalism. "
                "You give direct, concise feedback. "
                "You expect structured, detailed answers."
            ),
        }
    else:
        return {
            "level": "very_formal",
            "voice": "Fenrir",
            "style": (
                "You are a senior-level formal interviewer. "
                "You are very demanding and precise. "
                "You expect exceptional answers with specific examples. "
                "You challenge vague answers with follow-up questions."
            ),
        }


def build_interviewer_system_prompt(
    job_title: str,
    company_name: str,
    job_requirements: str,
    questions: list[dict],
    personality: dict,
    session_type: str,
) -> str:
    """
    Build the system prompt for the Gemini Live interviewer.
    """
    questions_text = "\n".join([
        f"Q{q['question_number']}: {q['question']} "
        f"(Time limit: {q.get('time_limit_seconds', 120)}s)"
        for q in questions
    ])

    return f"""
    You are an AI interview coach conducting a {session_type} interview.
    
    PERSONALITY: {personality['style']}
    
    JOB DETAILS:
    - Position: {job_title}
    - Company: {company_name}
    - Key Requirements: {job_requirements[:300]}
    
    YOUR INTERVIEW QUESTIONS (ask them in order):
    {questions_text}
    
    INTERVIEW RULES:
    1. Start by greeting the candidate warmly based on your personality level
    2. Ask ONE question at a time in order
    3. After the candidate answers, give brief feedback (2-3 sentences max)
    4. Then move to the next question
    5. After all {len(questions)} questions, give a brief closing statement
    6. Say "INTERVIEW_COMPLETE" when you are done with all questions
    7. Keep your voice natural and conversational
    8. Do NOT read out the time limits to the candidate
    9. If the candidate is silent for more than 10 seconds, gently prompt them
    10. Speak clearly and at a moderate pace
    
    FEEDBACK STYLE:
    - After each answer say something like: 
      "Good answer! I liked how you..." or 
      "That's a solid start. To make it stronger, you could..."
    - Keep feedback brief before moving to next question
    
    Begin by introducing yourself and asking the first question.
    """


class GeminiLiveSession:
    """
    Manages a Gemini Live API session for real-time audio interview.
    """

    def __init__(
        self,
        job_title: str,
        company_name: str,
        job_requirements: str,
        questions: list[dict],
        iri_score: float = 0,
        session_type: str = "mixed",
    ):
        self.job_title = job_title
        self.company_name = company_name
        self.job_requirements = job_requirements
        self.questions = questions
        self.iri_score = iri_score
        self.session_type = session_type
        self.personality = get_interviewer_personality(iri_score)
        self.session = None
        self.is_connected = False
        self.current_question = 1
        self.transcript = []

    async def connect(self) -> bool:
        """
        Connect to Gemini Live API.
        Returns True if successful.
        """
        try:
            client = genai.Client(api_key=settings.GEMINI_API_KEY)

            system_prompt = build_interviewer_system_prompt(
                job_title=self.job_title,
                company_name=self.company_name,
                job_requirements=self.job_requirements,
                questions=self.questions,
                personality=self.personality,
                session_type=self.session_type,
            )

            # Configure Live API session
            config = types.LiveConnectConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=self.personality["voice"],
                        )
                    )
                ),
                system_instruction=types.Content(
                    parts=[types.Part(text=system_prompt)]
                ),
            )

            self.client = client
            self.config = config
            self.is_connected = True
            print(
                f"[Gemini Live] Configured for {self.job_title} "
                f"with {self.personality['level']} personality"
            )
            return True

        except Exception as e:
            print(f"[Gemini Live] Connection failed: {e}")
            self.is_connected = False
            return False

    async def run_interview(
        self,
        audio_input_queue: asyncio.Queue,
        audio_output_queue: asyncio.Queue,
        text_output_queue: asyncio.Queue,
        control_queue: asyncio.Queue,
    ):
        """
        Run the live interview session.
        
        audio_input_queue: receives raw audio bytes from microphone
        audio_output_queue: sends audio bytes to frontend for playback
        text_output_queue: sends transcript text to frontend
        control_queue: receives control signals (stop, pause, etc.)
        """
        try:
            client = genai.Client(api_key=settings.GEMINI_API_KEY)

            async with client.aio.live.connect(
                model="models/gemini-2.0-flash-live-001",
                config=self.config,
            ) as session:
                self.session = session
                print("[Gemini Live] Connected to Gemini Live API")

                # Send initial trigger to start the interview
                await session.send(
                    input="Please begin the interview now.",
                    end_of_turn=True,
                )

                # Run send and receive concurrently
                await asyncio.gather(
                    self._send_audio(
                        session,
                        audio_input_queue,
                        control_queue,
                    ),
                    self._receive_audio(
                        session,
                        audio_output_queue,
                        text_output_queue,
                        control_queue,
                    ),
                )

        except Exception as e:
            print(f"[Gemini Live] Session error: {e}")
            await text_output_queue.put({
                "type": "error",
                "message": str(e),
            })

    async def _send_audio(
        self,
        session,
        audio_input_queue: asyncio.Queue,
        control_queue: asyncio.Queue,
    ):
        """
        Send audio chunks from the microphone to Gemini Live.
        Reads from audio_input_queue continuously.
        """
        while True:
            try:
                # Check for control signals
                try:
                    control = control_queue.get_nowait()
                    if control == "stop":
                        print("[Gemini Live] Stopping audio send")
                        break
                except asyncio.QueueEmpty:
                    pass

                # Get audio chunk from queue
                try:
                    audio_chunk = await asyncio.wait_for(
                        audio_input_queue.get(),
                        timeout=0.1,
                    )

                    if audio_chunk is None:
                        # None signals end of stream
                        await session.send(
                            input=types.LiveClientRealtimeInput(
                                media_chunks=[
                                    types.Blob(
                                        data=b"",
                                        mime_type="audio/pcm;rate=16000",
                                    )
                                ]
                            )
                        )
                        break

                    # Send audio to Gemini
                    await session.send(
                        input=types.LiveClientRealtimeInput(
                            media_chunks=[
                                types.Blob(
                                    data=audio_chunk,
                                    mime_type="audio/pcm;rate=16000",
                                )
                            ]
                        )
                    )

                except asyncio.TimeoutError:
                    continue

            except Exception as e:
                print(f"[Gemini Live] Send audio error: {e}")
                break

    async def _receive_audio(
        self,
        session,
        audio_output_queue: asyncio.Queue,
        text_output_queue: asyncio.Queue,
        control_queue: asyncio.Queue,
    ):
        """
        Receive audio and text responses from Gemini Live.
        Puts audio chunks in audio_output_queue for playback.
        Puts text in text_output_queue for display.
        """
        async for response in session.receive():
            try:
                # Check for control signals
                try:
                    control = control_queue.get_nowait()
                    if control == "stop":
                        break
                except asyncio.QueueEmpty:
                    pass

                # Handle audio response
                if response.data:
                    # Raw audio bytes — send to frontend for playback
                    audio_b64 = base64.b64encode(response.data).decode()
                    await audio_output_queue.put({
                        "type": "audio_chunk",
                        "data": audio_b64,
                        "mime_type": "audio/pcm;rate=24000",
                    })

                # Handle text response
                if response.text:
                    text = response.text
                    self.transcript.append({
                        "role": "interviewer",
                        "text": text,
                    })

                    await text_output_queue.put({
                        "type": "transcript",
                        "role": "interviewer",
                        "text": text,
                    })

                    # Check if interview is complete
                    if "INTERVIEW_COMPLETE" in text:
                        await text_output_queue.put({
                            "type": "interview_complete",
                            "message": "Interview completed by AI",
                        })
                        break

                # Handle turn completion
                if response.server_content:
                    if response.server_content.turn_complete:
                        await text_output_queue.put({
                            "type": "turn_complete",
                        })

            except Exception as e:
                print(f"[Gemini Live] Receive error: {e}")
                break

    async def send_text(self, text: str):
        """Send a text message to Gemini (for text fallback mode)."""
        if self.session:
            await self.session.send(
                input=text,
                end_of_turn=True,
            )

    async def disconnect(self):
        """Disconnect from Gemini Live."""
        self.is_connected = False
        self.session = None
        print("[Gemini Live] Disconnected")