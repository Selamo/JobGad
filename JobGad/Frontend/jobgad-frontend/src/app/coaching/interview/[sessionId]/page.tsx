'use client'
import { useEffect, useState, useCallback, useRef } from 'react'
import { useRouter, useParams } from 'next/navigation'
import { useInterviewSocket } from '@/hooks/useInterviewSocket'
import { useMicrophone } from '@/hooks/useMicrophone'
import { useAudioPlayer } from '@/hooks/useAudioPlayer'
import { ScoreRing, ProgressBar } from '@/components/ui'
import { Mic, MicOff, Send, Square, Wifi, WifiOff } from 'lucide-react'

type SessionState = 'connecting' | 'ready' | 'interviewing' | 'evaluating' | 'completed' | 'error'

interface Question {
  question_number: number
  question: string
  type: string
  time_limit_seconds: number
  hints: string[]
}

interface EvalScores {
  clarity: number
  confidence: number
  technical_accuracy: number
  structure: number
  relevance: number
}

interface Evaluation {
  scores: EvalScores
  overall_score: number
  strengths: string[]
  improvements: string[]
  encouragement: string
}

interface IRIResult {
  overall_score: number
  communication: number
  technical_accuracy: number
  confidence: number
  structure: number
  readiness_level: string
  next_step: string
}

interface TranscriptEntry {
  role: string
  text: string
}

export default function InterviewRoom() {
  const params    = useParams()
  const router    = useRouter()
  const sessionId = params.sessionId as string

  const [state, setState]           = useState<SessionState>('connecting')
  const [mode, setMode]             = useState<'audio' | 'text'>('audio')
  const [question, setQuestion]     = useState<Question | null>(null)
  const [evaluation, setEvaluation] = useState<Evaluation | null>(null)
  const [transcript, setTranscript] = useState<TranscriptEntry[]>([])
  const [iriResult, setIriResult]   = useState<IRIResult | null>(null)
  const [timerSec, setTimerSec]     = useState(120)
  const [totalSec, setTotalSec]     = useState(120)
  const [statusMsg, setStatusMsg]   = useState('Connecting to AI interviewer...')
  const [personality, setPersonality] = useState('friendly')
  const [totalQ, setTotalQ]         = useState(5)
  const [doneQ, setDoneQ]           = useState(0)
  const [isLastQ, setIsLastQ]       = useState(false)
  const [textAnswer, setTextAnswer] = useState('')
  const [error, setError]           = useState('')
  const answerStart   = useRef(Date.now())
  const transcriptRef = useRef<HTMLDivElement>(null)

  const { enqueueAudio, stopAudio }                                          = useAudioPlayer()
  const { startRecording, stopRecording, requestPermission, isRecording }    = useMicrophone()
  const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') || '' : ''

  const handleMessage = useCallback((msg: { type: string; data: Record<string, unknown> }) => {
    switch (msg.type) {
      case 'session_ready':
        setState('ready')
        setMode((msg.data.mode as 'audio' | 'text') || 'audio')
        setTotalQ((msg.data.total_questions as number) || 5)
        setPersonality((msg.data.personality as string) || 'friendly')
        setStatusMsg((msg.data.message as string) || 'AI interviewer ready!')
        break
      case 'question': {
        const q = msg.data as unknown as Question
        setQuestion(q)
        setEvaluation(null)
        setTextAnswer('')
        setTimerSec(q.time_limit_seconds)
        setTotalSec(q.time_limit_seconds)
        setState('interviewing')
        answerStart.current = Date.now()
        if (mode === 'text' && typeof window !== 'undefined' && 'speechSynthesis' in window) {
          const u = new SpeechSynthesisUtterance(q.question)
          u.rate = 0.9
          window.speechSynthesis.speak(u)
        }
        break
      }
      case 'audio_response': {
        const audioData = (msg.data as { data: string }).data
        if (audioData) enqueueAudio(audioData)
        setState('interviewing')
        break
      }
      case 'transcript':
        setTranscript(p => [...p, { role: msg.data.role as string, text: msg.data.text as string }])
        setTimeout(() => {
          if (transcriptRef.current) transcriptRef.current.scrollTop = transcriptRef.current.scrollHeight
        }, 50)
        break
      case 'timer':
        setTimerSec(msg.data.remaining_seconds as number)
        break
      case 'evaluation':
        setState('evaluating')
        if (msg.data.evaluation) setEvaluation(msg.data.evaluation as Evaluation)
        setDoneQ(msg.data.question_number as number)
        setIsLastQ(!!(msg.data.is_last_question))
        break
      case 'session_complete':
        stopAudio()
        setIriResult((msg.data as { iri_score: IRIResult }).iri_score)
        setState('completed')
        break
      case 'error':
        setError((msg.data.message as string) || 'Something went wrong.')
        setState('error')
        break
    }
  }, [mode, enqueueAudio, stopAudio])

  const { connect, disconnect, sendAudioChunk, sendTextAnswer, endSession, isConnected } =
    useInterviewSocket({
      sessionId, token, mode,
      onMessage: handleMessage,
      onConnect: () => setStatusMsg('Connected! Interview starting...'),
      onDisconnect: () => setState('error'),
      onError: (err) => { setError(err); setState('error') },
    })

  useEffect(() => {
    if (token) connect()
    return () => { disconnect(); stopAudio(); stopRecording() }
  }, [])

  async function handleStartRecording() {
    try {
      await requestPermission()
      answerStart.current = Date.now()
      await startRecording((chunk) => {
        if (question) sendAudioChunk(chunk, question.question_number)
      })
    } catch {
      setError('Microphone access denied. Switch to text mode.')
    }
  }

  function handleSubmitText() {
    if (!textAnswer.trim() || !question) return
    const timeTaken = Math.floor((Date.now() - answerStart.current) / 1000)
    sendTextAnswer(textAnswer, question.question_number, timeTaken)
    setState('evaluating')
  }

  function handleEndSession() {
    endSession()
    stopAudio()
    stopRecording()
  }

  const timerColor =
    timerSec > 60 ? 'var(--green)'  :
    timerSec > 30 ? 'var(--yellow)' : 'var(--red)'

  const timerPct = (timerSec / totalSec) * 100

  // Completed screen
  if (state === 'completed' && iriResult) {
    return (
      <div style={{ minHeight: '100vh', background: 'var(--bg-base)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24 }}>
        <div style={{ maxWidth: 480, width: '100%', textAlign: 'center' }}>
          <div className="animate-fade-up">
            <p className="label-caps" style={{ marginBottom: 12 }}>Session complete</p>
            <h1 style={{ fontFamily: 'Outfit, sans-serif', fontSize: 28, fontWeight: 700, marginBottom: 8 }}>Your IRI Score</h1>
            <p style={{ fontSize: 14, color: 'var(--text-muted)', marginBottom: 32 }}>{iriResult.readiness_level}</p>
            <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 28 }}>
              <ScoreRing score={iriResult.overall_score} size={120} />
            </div>
            <div className="card" style={{ marginBottom: 16 }}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 16 }}>
                {[
                  ['Communication', iriResult.communication],
                  ['Confidence',    iriResult.confidence],
                  ['Technical',     iriResult.technical_accuracy],
                  ['Structure',     iriResult.structure],
                ].map(([label, val]) => (
                  <div key={label as string} style={{ background: 'var(--bg-elevated)', borderRadius: 8, padding: '10px 12px', textAlign: 'center' }}>
                    <div style={{ fontFamily: 'DM Mono, monospace', fontSize: 20, fontWeight: 500, color: 'var(--blue-bright)' }}>{Math.round(val as number)}</div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 3 }}>{label}</div>
                  </div>
                ))}
              </div>
              <div style={{ padding: '12px 14px', background: 'rgba(37,99,235,0.08)', borderRadius: 8, borderLeft: '3px solid var(--blue-mid)' }}>
                <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6 }}>{iriResult.next_step}</p>
              </div>
            </div>
            <button className="btn btn-primary btn-lg" style={{ width: '100%' }} onClick={() => router.push('/coaching')}>
              Back to coaching
            </button>
          </div>
        </div>
      </div>
    )
  }

  // Error screen
  if (state === 'error') {
    return (
      <div style={{ minHeight: '100vh', background: 'var(--bg-base)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ textAlign: 'center', maxWidth: 380, padding: 24 }}>
          <div style={{ width: 48, height: 48, borderRadius: 12, background: 'var(--red-dim)', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 16px' }}>
            <WifiOff size={22} style={{ color: 'var(--red)' }} />
          </div>
          <h2 style={{ fontFamily: 'Outfit, sans-serif', fontSize: 20, fontWeight: 600, marginBottom: 8 }}>Connection error</h2>
          <p style={{ fontSize: 14, color: 'var(--text-secondary)', marginBottom: 24, lineHeight: 1.6 }}>{error || 'Something went wrong with the interview connection.'}</p>
          <button className="btn btn-primary" onClick={() => router.push('/coaching')}>Back to coaching</button>
        </div>
      </div>
    )
  }

  // Main interview UI
  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg-base)', display: 'flex', flexDirection: 'column' }}>

      {/* Header */}
      <div style={{ background: 'var(--bg-surface)', borderBottom: '1px solid var(--border-subtle)', padding: '0 24px', height: 56, display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexShrink: 0 }}>
        <div>
          <span style={{ fontFamily: 'Outfit, sans-serif', fontSize: 16, fontWeight: 600 }}>AI Interview</span>
          <span style={{ fontSize: 12, color: 'var(--text-muted)', marginLeft: 10, textTransform: 'capitalize' }}>
            {personality.replace('_', ' ')} mode
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>{doneQ} / {totalQ} questions</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            {isConnected
              ? <Wifi size={14} style={{ color: 'var(--green)' }} />
              : <WifiOff size={14} style={{ color: 'var(--red)' }} />
            }
            <span style={{ fontSize: 12, color: isConnected ? 'var(--green)' : 'var(--red)' }}>
              {isConnected ? 'Connected' : 'Disconnected'}
            </span>
          </div>
        </div>
      </div>

      {/* Body */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>

        {/* Main column */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', padding: 20, gap: 14, overflowY: 'auto' }}>

          {/* Question card */}
          <div className="card">
            {!question ? (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: 160, gap: 12 }}>
                <div className="spinner spinner-lg" />
                <p style={{ fontSize: 13, color: 'var(--text-muted)' }}>{statusMsg}</p>
              </div>
            ) : (
              <>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span className="label-caps">Question {question.question_number} of {totalQ}</span>
                    <span className="badge badge-blue" style={{ textTransform: 'capitalize' }}>{question.type}</span>
                  </div>
                  <span style={{ fontFamily: 'DM Mono, monospace', fontSize: 18, fontWeight: 600, color: timerColor }}>
                    {Math.floor(timerSec / 60)}:{String(timerSec % 60).padStart(2, '0')}
                  </span>
                </div>
                <div className="progress-track" style={{ marginBottom: 16 }}>
                  <div style={{ height: '100%', borderRadius: 100, background: timerColor, width: `${timerPct}%`, transition: 'width 1s linear, background 0.5s' }} />
                </div>
                <p style={{ fontSize: 16, color: 'var(--text-primary)', lineHeight: 1.7, marginBottom: 14 }}>
                  {question.question}
                </p>
                {question.hints.length > 0 && (
                  <div style={{ background: 'rgba(37,99,235,0.07)', border: '1px solid rgba(37,99,235,0.15)', borderRadius: 8, padding: '10px 14px' }}>
                    <p style={{ fontSize: 11, fontWeight: 600, color: 'var(--blue-bright)', letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 6 }}>Hints</p>
                    {question.hints.map((h, i) => (
                      <p key={i} style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: i < question.hints.length - 1 ? 4 : 0 }}>· {h}</p>
                    ))}
                  </div>
                )}
              </>
            )}
          </div>

          {/* Answer controls */}
          {question && state === 'interviewing' && (
            <div className="card">
              {mode === 'audio' ? (
                <div style={{ textAlign: 'center' }}>
                  <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 14 }}>
                    {isRecording ? 'Recording — release to stop' : 'Hold button to answer'}
                  </p>
                  <button
                    onMouseDown={handleStartRecording}
                    onMouseUp={stopRecording}
                    onTouchStart={handleStartRecording}
                    onTouchEnd={stopRecording}
                    style={{ width: 72, height: 72, borderRadius: '50%', border: 'none', cursor: 'pointer', background: isRecording ? 'var(--red)' : 'var(--blue-mid)', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto', transition: 'all 0.15s', boxShadow: isRecording ? '0 0 0 8px rgba(239,68,68,0.2)' : 'none' }}>
                    {isRecording ? <MicOff size={28} color="white" /> : <Mic size={28} color="white" />}
                  </button>
                  <button className="btn btn-ghost btn-sm" style={{ marginTop: 14 }} onClick={() => setMode('text')}>
                    Switch to text mode
                  </button>
                </div>
              ) : (
                <div>
                  <textarea className="input" rows={4} placeholder="Type your answer here..."
                    value={textAnswer} onChange={e => setTextAnswer(e.target.value)}
                    onKeyDown={e => { if (e.key === 'Enter' && e.ctrlKey) handleSubmitText() }}
                    style={{ resize: 'none', marginBottom: 10 }} />
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Ctrl + Enter to submit</span>
                    <button className="btn btn-primary" onClick={handleSubmitText} disabled={!textAnswer.trim()}>
                      <Send size={13} /> Submit answer
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Evaluation feedback */}
          {evaluation && state === 'evaluating' && (
            <div className="card animate-fade-up">
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
                <h3 style={{ fontFamily: 'Outfit, sans-serif', fontSize: 15, fontWeight: 600 }}>Feedback</h3>
                <div style={{ fontFamily: 'DM Mono, monospace', fontSize: 20, fontWeight: 600, color: evaluation.overall_score >= 70 ? 'var(--green)' : 'var(--yellow)' }}>
                  {evaluation.overall_score}/100
                </div>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 14 }}>
                {Object.entries(evaluation.scores).map(([k, v]) => (
                  <ProgressBar key={k} label={k.replace('_', ' ')} value={v as number} />
                ))}
              </div>
              {evaluation.strengths.map((s, i) => (
                <p key={i} style={{ fontSize: 12, color: 'var(--green)', marginBottom: 3 }}>+ {s}</p>
              ))}
              {evaluation.improvements.map((s, i) => (
                <p key={i} style={{ fontSize: 12, color: 'var(--yellow)', marginBottom: 3 }}>→ {s}</p>
              ))}
              <p style={{ fontSize: 13, color: 'var(--text-secondary)', fontStyle: 'italic', marginTop: 8, marginBottom: 16, lineHeight: 1.5 }}>
                {evaluation.encouragement}
              </p>
              {isLastQ ? (
                <button className="btn btn-primary" style={{ width: '100%' }} onClick={handleEndSession}>
                  <Square size={13} /> End session and get IRI score
                </button>
              ) : (
                <p style={{ fontSize: 12, color: 'var(--text-muted)', textAlign: 'center' }}>Next question coming up...</p>
              )}
            </div>
          )}
        </div>

        {/* Transcript panel */}
        <div style={{ width: 260, background: 'var(--bg-surface)', borderLeft: '1px solid var(--border-subtle)', display: 'flex', flexDirection: 'column', flexShrink: 0 }}>
          <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--border-subtle)' }}>
            <p className="label-caps">Live transcript</p>
          </div>
          <div ref={transcriptRef} style={{ flex: 1, overflowY: 'auto', padding: 12, display: 'flex', flexDirection: 'column', gap: 8 }}>
            {transcript.length === 0 ? (
              <p style={{ fontSize: 12, color: 'var(--text-muted)', textAlign: 'center', marginTop: 24 }}>Transcript will appear here</p>
            ) : (
              transcript.map((t, i) => (
                <div key={i} style={{ padding: '8px 10px', borderRadius: 8, fontSize: 12, lineHeight: 1.55, background: t.role === 'interviewer' ? 'rgba(37,99,235,0.08)' : 'var(--bg-elevated)', border: `1px solid ${t.role === 'interviewer' ? 'rgba(37,99,235,0.15)' : 'var(--border-subtle)'}` }}>
                  <span style={{ fontSize: 10, fontWeight: 600, color: t.role === 'interviewer' ? 'var(--blue-bright)' : 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', display: 'block', marginBottom: 4 }}>
                    {t.role === 'interviewer' ? 'AI Interviewer' : 'You'}
                  </span>
                  <span style={{ color: 'var(--text-secondary)' }}>{t.text}</span>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  )
}