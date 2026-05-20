"""
Gemini Live API — real-time audio conversation handler for interview coaching.
"""
import asyncio
import base64
from typing import Optional

from app.core.config import settings

try:
    from google import genai
    from google.genai import types
    GEMINI_LIVE_AVAILABLE = True
except ImportError:
    GEMINI_LIVE_AVAILABLE = False
    genai = None
    types = None
    print("[Gemini Live] google-genai package not available, audio mode disabled")


def get_interviewer_personality(iri_score: float) -> dict:
    if iri_score < 30:
        return {
            "level": "very_friendly",
            "voice": "Aoede",
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
            "voice": "Charon",
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
            "voice": "Fenrir",
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
    questions: list,
    personality: dict,
    session_type: str,
) -> str:
    questions_text = "\n".join([
        f"Q{q['question_number']}: {q['question']} "
        f"(Time limit: {q.get('time_limit_seconds', 120)}s)"
        for q in questions
    ])

    return f"""You are an AI interview coach conducting a {session_type} interview.

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

Begin by introducing yourself and asking the first question."""


class GeminiLiveSession:

    def __init__(
        self,
        job_title: str,
        company_name: str,
        job_requirements: str,
        questions: list,
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
        self.client = None
        self.config = None
        self.transcript = []

    async def connect(self) -> bool:
        # Check if Gemini Live package is available
        if not GEMINI_LIVE_AVAILABLE:
            print("[Gemini Live] Package not available — audio mode disabled")
            return False

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
            print(f"[Gemini Live] Configured for {self.job_title} with {self.personality['level']} personality")
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
        if not GEMINI_LIVE_AVAILABLE or not self.client:
            await text_output_queue.put({"type": "error", "message": "Audio mode not available"})
            return

        try:
            async with self.client.aio.live.connect(
                model="models/gemini-2.0-flash-live-001",
                config=self.config,
            ) as session:
                self.session = session
                print("[Gemini Live] Connected to Gemini Live API")

                await session.send(
                    input="Please begin the interview now.",
                    end_of_turn=True,
                )

                await asyncio.gather(
                    self._send_audio(session, audio_input_queue, control_queue),
                    self._receive_audio(session, audio_output_queue, text_output_queue, control_queue),
                )

        except Exception as e:
            print(f"[Gemini Live] Session error: {e}")
            await text_output_queue.put({"type": "error", "message": str(e)})

    async def _send_audio(self, session, audio_input_queue, control_queue):
        while True:
            try:
                try:
                    control = control_queue.get_nowait()
                    if control == "stop":
                        break
                except asyncio.QueueEmpty:
                    pass

                try:
                    audio_chunk = await asyncio.wait_for(audio_input_queue.get(), timeout=0.1)
                    if audio_chunk is None:
                        break
                    await session.send(
                        input=types.LiveClientRealtimeInput(
                            media_chunks=[types.Blob(data=audio_chunk, mime_type="audio/pcm;rate=16000")]
                        )
                    )
                except asyncio.TimeoutError:
                    continue

            except Exception as e:
                print(f"[Gemini Live] Send audio error: {e}")
                break

    async def _receive_audio(self, session, audio_output_queue, text_output_queue, control_queue):
        async for response in session.receive():
            try:
                try:
                    control = control_queue.get_nowait()
                    if control == "stop":
                        break
                except asyncio.QueueEmpty:
                    pass

                if response.data:
                    audio_b64 = base64.b64encode(response.data).decode()
                    await audio_output_queue.put({
                        "type": "audio_chunk",
                        "data": audio_b64,
                        "mime_type": "audio/pcm;rate=24000",
                    })

                if response.text:
                    text = response.text
                    self.transcript.append({"role": "interviewer", "text": text})
                    await text_output_queue.put({"type": "transcript", "role": "interviewer", "text": text})
                    if "INTERVIEW_COMPLETE" in text:
                        await text_output_queue.put({"type": "interview_complete"})
                        break

                if response.server_content and response.server_content.turn_complete:
                    await text_output_queue.put({"type": "turn_complete"})

            except Exception as e:
                print(f"[Gemini Live] Receive error: {e}")
                break

    async def send_text(self, text: str):
        if self.session:
            await self.session.send(input=text, end_of_turn=True)

    async def disconnect(self):
        self.is_connected = False
        self.session = None
        print("[Gemini Live] Disconnected")