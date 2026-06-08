'use client'
import { useEffect, useState, useCallback, useRef } from 'react'
import { useRouter, useParams } from 'next/navigation'
import { useInterviewSocket } from '@/hooks/useInterviewSocket'
import { useMicrophone } from '@/hooks/useMicrophone'
import { useAudioPlayer } from '@/hooks/useAudioPlayer'
import { ProgressBar } from '@/components/ui'
import {
  Mic, MicOff, Pause, Play, PhoneOff,
  ChevronRight, Wifi, WifiOff, Send,
} from 'lucide-react'

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

type SessionState = 'connecting' | 'interviewing' | 'evaluating' | 'completed' | 'error'

interface Question {
  question_number: number
  question: string
  type: string
  time_limit_seconds: number
  hints: string[]
}

interface EvalScores {
  clarity: number; confidence: number
  technical_accuracy: number; structure: number; relevance: number
}

interface Evaluation {
  scores: EvalScores
  overall_score: number
  strengths: string[]
  improvements: string[]
  encouragement: string
}

interface IRIResult {
  overall_score: number; communication: number
  technical_accuracy: number; confidence: number
  structure: number; readiness_level: string; next_step: string
}

// ─────────────────────────────────────────────────────────────────────────────
// Sub-components
// ─────────────────────────────────────────────────────────────────────────────

function WaveBars({ active, color = '#3b82f6' }: { active: boolean; color?: string }) {
  const heights = [30, 55, 75, 45, 90, 60, 35, 80, 50, 70, 40, 65]
  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      gap: 4, height: 56,
    }}>
      {heights.map((h, i) => (
        <div key={i} style={{
          width: 4,
          borderRadius: 2,
          background: active ? color : 'var(--border-default)',
          height: active ? undefined : 5,
          minHeight: 5,
          maxHeight: 48,
          animationName:           active ? 'waveBar' : 'none',
          animationDuration:       `${0.6 + (i % 4) * 0.15}s`,
          animationDelay:          `${(i * 0.07) % 0.5}s`,
          animationTimingFunction: 'ease-in-out',
          animationIterationCount: 'infinite',
          animationDirection:      'alternate',
          '--wave-h':              `${h}%`,
          transformOrigin:         'bottom',
        } as React.CSSProperties} />
      ))}
    </div>
  )
}

function CircularTimer({
  seconds, total, color,
}: { seconds: number; total: number; color: string }) {
  const r      = 36
  const circ   = 2 * Math.PI * r
  const pct    = total > 0 ? seconds / total : 0
  const offset = circ * (1 - pct)
  const mins   = Math.floor(seconds / 60)
  const secs   = String(seconds % 60).padStart(2, '0')
  return (
    <svg width="88" height="88" viewBox="0 0 88 88">
      <circle cx="44" cy="44" r={r} fill="none"
        stroke="var(--bg-elevated)" strokeWidth="5" />
      <circle cx="44" cy="44" r={r} fill="none"
        stroke={color} strokeWidth="5"
        strokeDasharray={circ}
        strokeDashoffset={offset}
        strokeLinecap="round"
        transform="rotate(-90 44 44)"
        style={{ transition: 'stroke-dashoffset 1s linear, stroke 0.5s' }} />
      <text x="44" y="49" textAnchor="middle"
        fill={color} fontSize="14" fontWeight="700"
        fontFamily="DM Mono, monospace">
        {mins}:{secs}
      </text>
    </svg>
  )
}

function ProgressDots({
  total, done, current,
}: { total: number; done: number; current: number }) {
  return (
    <div style={{ display: 'flex', gap: 5, alignItems: 'center' }}>
      {Array.from({ length: total }, (_, i) => {
        const isDone    = i + 1 < current
        const isCurrent = i + 1 === current
        return (
          <div key={i} style={{
            height: 6,
            width:  isDone ? 18 : isCurrent ? 26 : 8,
            borderRadius: 3,
            background: isDone    ? 'var(--green)'
              :         isCurrent ? 'var(--blue-core)'
              :                     'var(--bg-elevated)',
            transition: 'all 0.4s cubic-bezier(0.34,1.56,0.64,1)',
          }} />
        )
      })}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Main component
// ─────────────────────────────────────────────────────────────────────────────

export default function InterviewRoom() {
  const params    = useParams()
  const router    = useRouter()
  const sessionId = params.sessionId as string

  // Core state
  const [state, setState]           = useState<SessionState>('connecting')
  const [mode, setMode]             = useState<'audio' | 'text'>('audio')
  const [question, setQuestion]     = useState<Question | null>(null)
  const [evaluation, setEvaluation] = useState<Evaluation | null>(null)
  const [pendingQ, setPendingQ]     = useState<Question | null>(null)
  const [iriResult, setIriResult]   = useState<IRIResult | null>(null)
  const [error, setError]           = useState('')

  // UI state
  const [timerSec, setTimerSec]         = useState(120)
  const [totalSec, setTotalSec]         = useState(120)
  const [totalQ, setTotalQ]             = useState(5)
  const [doneQ, setDoneQ]               = useState(0)
  const [isLastQ, setIsLastQ]           = useState(false)
  const [statusMsg, setStatusMsg]       = useState('Connecting to AI interviewer...')
  const [textAnswer, setTextAnswer]     = useState('')
  const [liveTranscript, setLiveTranscript] = useState('')
  const [isPaused, setIsPaused]         = useState(false)
  const [showEndConfirm, setShowEndConfirm] = useState(false)
  const [isResuming, setIsResuming]     = useState(false)

  // Refs
  const answerStart    = useRef(Date.now())
  const currentQ       = useRef(1)
  const recordingStart = useRef(0)
  const recordingActive = useRef(false)
  const recognitionRef  = useRef<any>(null)
  const isFirstQ        = useRef(true)
  const pausedTimerRef  = useRef<number>(0)
  const transcriptRef   = useRef<HTMLDivElement>(null)

  const { enqueueAudio, stopAudio }                                       = useAudioPlayer()
  const { startRecording, stopRecording, requestPermission, isRecording } = useMicrophone()
  const token = typeof window !== 'undefined'
    ? localStorage.getItem('access_token') || '' : ''

  // ── Apply a question ──────────────────────────────────────────────────────
  const applyQuestion = useCallback((q: Question) => {
    setQuestion(q)
    setEvaluation(null)
    setPendingQ(null)
    setTextAnswer('')
    setLiveTranscript('')
    setTimerSec(q.time_limit_seconds)
    setTotalSec(q.time_limit_seconds)
    setState('interviewing')
    currentQ.current  = q.question_number
    answerStart.current = Date.now()
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      window.speechSynthesis.cancel()
      const u = new SpeechSynthesisUtterance(q.question)
      u.rate = 0.9
      window.speechSynthesis.speak(u)
    }
  }, [])

  // ── Message handler ───────────────────────────────────────────────────────
  const handleMessage = useCallback((msg: {
    type: string; data: Record<string, unknown>
  }) => {
    switch (msg.type) {

      case 'session_ready':
        setMode((msg.data.mode as 'audio' | 'text') || 'audio')
        setTotalQ((msg.data.total_questions as number) || 5)
        setStatusMsg((msg.data.message as string) || 'Interview starting...')
        setIsResuming(!!(msg.data.is_resuming))
        setState('interviewing')
        break

      case 'question': {
        const q = msg.data as unknown as Question
        if (isFirstQ.current) {
          isFirstQ.current = false
          applyQuestion(q)
        } else {
          setPendingQ(q)
        }
        break
      }

      case 'audio_response': {
        const d = (msg.data as { data: string }).data
        if (d) enqueueAudio(d)
        break
      }

      case 'timer':
        if (!isPaused)
          setTimerSec(msg.data.remaining_seconds as number)
        break

      case 'evaluation':
        setState('evaluating')
        if (msg.data.evaluation) setEvaluation(msg.data.evaluation as Evaluation)
        setDoneQ(msg.data.question_number as number)
        setIsLastQ(!!(msg.data.is_last_question))
        currentQ.current = (msg.data.question_number as number) + 1
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

      default: break
    }
  }, [enqueueAudio, stopAudio, applyQuestion, isPaused])

  const {
    connect, disconnect, sendAudioChunk, sendTextAnswer, endSession, isConnected,
  } = useInterviewSocket({
    sessionId, token, mode,
    onMessage:    handleMessage,
    onConnect:    () => setStatusMsg('Connected! Interview starting...'),
    onDisconnect: () => setState('error'),
    onError:      (err) => { setError(err); setState('error') },
  })

  useEffect(() => {
    if (token) connect()
    return () => {
      disconnect(); stopAudio(); stopRecording()
      if (recognitionRef.current) {
        try { recognitionRef.current.stop() } catch {}
      }
    }
  }, [])

  // ── Pause / resume ────────────────────────────────────────────────────────
  function handlePause() {
    if (isRecording) stopFullRecording()
    pausedTimerRef.current = timerSec
    setIsPaused(true)
  }

  function handleResume() {
    setIsPaused(false)
  }

  // ── Recording ─────────────────────────────────────────────────────────────
  async function handleStartRecording() {
    if (isPaused) return
    recordingActive.current = false
    recordingStart.current  = 0
    setLiveTranscript('')
    try {
      const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
      if (SR) {
        const rec      = new SR()
        rec.continuous = true; rec.interimResults = true; rec.lang = 'en-US'
        let acc = ''
        rec.onresult = (e: any) => {
          let interim = ''
          for (let i = 0; i < e.results.length; i++) {
            if (e.results[i].isFinal) acc += e.results[i][0].transcript + ' '
            else interim += e.results[i][0].transcript
          }
          setLiveTranscript((acc + interim).trim())
        }
        rec.onerror = () => {}
        rec.start()
        recognitionRef.current = rec
      }
      await requestPermission()
      recordingActive.current = true
      recordingStart.current  = Date.now()
      answerStart.current     = Date.now()
      const qNum = question?.question_number ?? currentQ.current
      await startRecording((chunk) => sendAudioChunk(chunk, qNum))
    } catch {
      recordingActive.current = false
      if (recognitionRef.current) {
        try { recognitionRef.current.stop() } catch {}
        recognitionRef.current = null
      }
    }
  }

  function stopFullRecording() {
    stopRecording()
    if (recognitionRef.current) {
      try { recognitionRef.current.stop() } catch {}
      recognitionRef.current = null
    }
    recordingActive.current = false
    setLiveTranscript('')
  }

  async function handleStopAndSubmit() {
    stopRecording()
    if (!recordingActive.current) { stopFullRecording(); return }
    recordingActive.current = false
    const duration = Date.now() - recordingStart.current
    if (duration < 1500) { stopFullRecording(); return }
    let spoken = ''
    if (recognitionRef.current) {
      try { recognitionRef.current.stop() } catch {}
      await new Promise(r => setTimeout(r, 300))
      spoken = liveTranscript.trim()
      recognitionRef.current = null
    }
    setLiveTranscript('')
    const qNum   = question?.question_number ?? currentQ.current
    const taken  = Math.floor((Date.now() - answerStart.current) / 1000)
    sendTextAnswer(spoken || '__audio_complete__', qNum, taken)
    setState('evaluating')
  }

  function handleSubmitText() {
    if (!textAnswer.trim() || !question) return
    const taken = Math.floor((Date.now() - answerStart.current) / 1000)
    sendTextAnswer(textAnswer, question.question_number, taken)
    setState('evaluating')
  }

  function handleEndSession() {
    setShowEndConfirm(false)
    endSession(); stopAudio(); stopFullRecording()
  }

  // ── Timer color ───────────────────────────────────────────────────────────
  const timerColor = timerSec > 60
    ? 'var(--green)'
    : timerSec > 30 ? 'var(--yellow)' : 'var(--red)'

  // ── Completed screen ───────────────────────────────────────────────────────
  if (state === 'completed' && iriResult) {
    return (
      <div style={{
        minHeight: '100vh', background: 'var(--bg-base)',
        display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24,
      }}>
        <style>{`
          @keyframes fadeUp {
            from { opacity: 0; transform: translateY(20px); }
            to   { opacity: 1; transform: translateY(0); }
          }
        `}</style>
        <div style={{
          maxWidth: 480, width: '100%', textAlign: 'center',
          animation: 'fadeUp 0.5s ease forwards',
        }}>
          <div style={{
            width: 64, height: 64, borderRadius: '50%',
            background: 'rgba(16,185,129,0.15)',
            border: '2px solid var(--green)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            margin: '0 auto 20px', fontSize: 28,
          }}>🎉</div>
          <p className="label-caps" style={{ marginBottom: 8, color: 'var(--green)' }}>
            Session complete
          </p>
          <h1 style={{ fontFamily: 'Outfit, sans-serif', fontSize: 28, fontWeight: 700, marginBottom: 6 }}>
            Your IRI Score
          </h1>
          <p style={{ fontSize: 14, color: 'var(--text-muted)', marginBottom: 32 }}>
            {iriResult.readiness_level}
          </p>

          <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 28 }}>
            <div style={{ position: 'relative' }}>
              <svg width="140" height="140" viewBox="0 0 140 140">
                <circle cx="70" cy="70" r="58" fill="none"
                  stroke="var(--bg-elevated)" strokeWidth="8" />
                <circle cx="70" cy="70" r="58" fill="none"
                  stroke="var(--blue-core)" strokeWidth="8"
                  strokeDasharray={2 * Math.PI * 58}
                  strokeDashoffset={2 * Math.PI * 58 * (1 - iriResult.overall_score / 100)}
                  strokeLinecap="round"
                  transform="rotate(-90 70 70)"
                  style={{ transition: 'stroke-dashoffset 1.5s ease' }} />
                <text x="70" y="66" textAnchor="middle"
                  fill="var(--text-primary)" fontSize="28" fontWeight="700"
                  fontFamily="DM Mono, monospace">
                  {Math.round(iriResult.overall_score)}
                </text>
                <text x="70" y="85" textAnchor="middle"
                  fill="var(--text-muted)" fontSize="11">
                  / 100
                </text>
              </svg>
            </div>
          </div>

          <div className="card" style={{ marginBottom: 16, textAlign: 'left' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 16 }}>
              {[
                ['Communication', iriResult.communication],
                ['Confidence',    iriResult.confidence],
                ['Technical',     iriResult.technical_accuracy],
                ['Structure',     iriResult.structure],
              ].map(([label, val]) => (
                <div key={label as string} style={{
                  background: 'var(--bg-elevated)', borderRadius: 10,
                  padding: '12px 14px', textAlign: 'center',
                }}>
                  <div style={{
                    fontFamily: 'DM Mono, monospace', fontSize: 22, fontWeight: 600,
                    color: 'var(--blue-bright)',
                  }}>
                    {Math.round(val as number)}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 3 }}>
                    {label}
                  </div>
                </div>
              ))}
            </div>
            <div style={{
              padding: '12px 14px',
              background: 'rgba(37,99,235,0.08)',
              borderRadius: 8, borderLeft: '3px solid var(--blue-mid)',
            }}>
              <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                {iriResult.next_step}
              </p>
            </div>
          </div>

          <button className="btn btn-primary btn-lg" style={{ width: '100%' }}
            onClick={() => router.push('/coaching')}>
            Back to coaching
          </button>
        </div>
      </div>
    )
  }

  // ── Error screen ───────────────────────────────────────────────────────────
  if (state === 'error') {
    return (
      <div style={{
        minHeight: '100vh', background: 'var(--bg-base)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <div style={{ textAlign: 'center', maxWidth: 380, padding: 24 }}>
          <div style={{
            width: 52, height: 52, borderRadius: '50%',
            background: 'var(--red-dim)', border: '1px solid rgba(239,68,68,0.3)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            margin: '0 auto 16px', fontSize: 22,
          }}>⚠️</div>
          <h2 style={{ fontFamily: 'Outfit, sans-serif', fontSize: 20, fontWeight: 600, marginBottom: 8 }}>
            Connection error
          </h2>
          <p style={{ fontSize: 14, color: 'var(--text-secondary)', marginBottom: 24, lineHeight: 1.6 }}>
            {error || 'Something went wrong with the interview connection.'}
          </p>
          <div style={{ display: 'flex', gap: 10, justifyContent: 'center' }}>
            <button className="btn btn-ghost" onClick={() => window.location.reload()}>
              Try again
            </button>
            <button className="btn btn-primary" onClick={() => router.push('/coaching')}>
              Back to coaching
            </button>
          </div>
        </div>
      </div>
    )
  }

  // ── Main interview UI ──────────────────────────────────────────────────────
  return (
    <div style={{
      minHeight: '100vh', background: 'var(--bg-base)',
      display: 'flex', flexDirection: 'column',
      position: 'relative',
    }}>

      {/* ── Keyframe styles ──────────────────────────────────────────────── */}
      <style>{`
        @keyframes waveBar {
          from { height: 5px; }
          to   { height: var(--wave-h, 40px); }
        }
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(12px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        @keyframes slideUp {
          from { opacity: 0; transform: translateY(24px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        @keyframes pulse {
          0%, 100% { box-shadow: 0 0 0 0 rgba(239,68,68,0.4); }
          50%       { box-shadow: 0 0 0 12px rgba(239,68,68,0); }
        }
        @keyframes glow {
          0%, 100% { box-shadow: 0 0 16px rgba(37,99,235,0.3); }
          50%       { box-shadow: 0 0 32px rgba(37,99,235,0.6); }
        }
        .interview-card {
          animation: fadeIn 0.35s ease forwards;
        }
        .eval-card {
          animation: slideUp 0.4s cubic-bezier(0.34,1.56,0.64,1) forwards;
        }
      `}</style>

      {/* ── Header ───────────────────────────────────────────────────────── */}
      <div style={{
        background: 'var(--bg-surface)',
        borderBottom: '1px solid var(--border-subtle)',
        padding: '0 20px', height: 56, flexShrink: 0,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        {/* Left */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontFamily: 'Outfit, sans-serif', fontSize: 15, fontWeight: 700 }}>
            AI Interview
          </span>
          <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            <div style={{
              width: 7, height: 7, borderRadius: '50%',
              background: isConnected ? 'var(--green)' : 'var(--red)',
              boxShadow: isConnected ? '0 0 6px var(--green)' : 'none',
            }} />
            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
              {isConnected ? 'Live' : 'Disconnected'}
            </span>
          </div>
        </div>

        {/* Center — progress */}
        {question && (
          <ProgressDots total={totalQ} done={doneQ} current={question.question_number} />
        )}

        {/* Right — controls */}
        <div style={{ display: 'flex', gap: 8 }}>
          {state !== 'connecting' && (
            <button
              onClick={isPaused ? handleResume : handlePause}
              className="btn btn-ghost btn-sm"
              title={isPaused ? 'Resume' : 'Pause session'}
              style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
              {isPaused
                ? <><Play size={13} /> Resume</>
                : <><Pause size={13} /> Pause</>}
            </button>
          )}
          <button
            onClick={() => setShowEndConfirm(v => !v)}
            className="btn btn-sm"
            style={{
              background: showEndConfirm ? 'var(--red)' : 'var(--red-dim)',
              border: '1px solid rgba(239,68,68,0.3)',
              color: showEndConfirm ? 'white' : 'var(--red)',
              display: 'flex', alignItems: 'center', gap: 5,
            }}>
            <PhoneOff size={13} />
            {showEndConfirm ? 'Confirm end?' : 'End'}
          </button>
          {showEndConfirm && (
            <button className="btn btn-ghost btn-sm"
              onClick={() => setShowEndConfirm(false)}>
              Cancel
            </button>
          )}
          {showEndConfirm && (
            <button className="btn btn-danger btn-sm" onClick={handleEndSession}>
              Yes, end session
            </button>
          )}
        </div>
      </div>

      {/* ── Body ─────────────────────────────────────────────────────────── */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>

        {/* Main column */}
        <div style={{
          flex: 1, display: 'flex', flexDirection: 'column',
          padding: '20px', gap: 14, overflowY: 'auto',
          maxWidth: 680, margin: '0 auto', width: '100%',
        }}>

          {/* Connecting / status */}
          {state === 'connecting' && (
            <div style={{
              display: 'flex', flexDirection: 'column',
              alignItems: 'center', justifyContent: 'center',
              flex: 1, gap: 16, paddingTop: 60,
            }}>
              <div style={{
                width: 64, height: 64, borderRadius: '50%',
                background: 'rgba(37,99,235,0.15)',
                border: '2px solid rgba(37,99,235,0.3)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                animation: 'glow 2s ease-in-out infinite',
              }}>
                <div className="spinner spinner-lg" />
              </div>
              <p style={{ fontSize: 14, color: 'var(--text-muted)' }}>{statusMsg}</p>
            </div>
          )}

          {/* Resume banner */}
          {isResuming && question && (
            <div style={{
              background: 'rgba(37,99,235,0.08)',
              border: '1px solid rgba(37,99,235,0.2)',
              borderRadius: 10, padding: '10px 16px',
              display: 'flex', alignItems: 'center', gap: 10,
              animation: 'fadeIn 0.3s ease',
            }}>
              <span style={{ fontSize: 18 }}>▶️</span>
              <p style={{ fontSize: 13, color: 'var(--blue-bright)' }}>
                Session resumed — continuing from question {question.question_number}
              </p>
            </div>
          )}

          {/* Question card */}
          {question && (
            <div className="card interview-card" style={{
              borderLeft: state === 'interviewing'
                ? '3px solid var(--blue-mid)'
                : '3px solid var(--border-subtle)',
              transition: 'border-color 0.3s',
            }}>
              <div style={{
                display: 'flex', alignItems: 'flex-start',
                justifyContent: 'space-between', gap: 16, marginBottom: 16,
              }}>
                {/* Question meta */}
                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 12 }}>
                    <span className="label-caps" style={{ color: 'var(--text-muted)' }}>
                      Question {question.question_number} of {totalQ}
                    </span>
                    <span className="badge badge-blue" style={{ textTransform: 'capitalize', fontSize: 10 }}>
                      {question.type}
                    </span>
                    {state === 'evaluating' && (
                      <span style={{
                        fontSize: 11, color: 'var(--yellow)',
                        background: 'rgba(245,158,11,0.1)',
                        border: '1px solid rgba(245,158,11,0.2)',
                        borderRadius: 10, padding: '2px 8px',
                      }}>
                        Analysing...
                      </span>
                    )}
                  </div>
                  <p style={{
                    fontSize: 16, color: 'var(--text-primary)',
                    lineHeight: 1.75, fontWeight: 500,
                  }}>
                    {question.question}
                  </p>
                </div>

                {/* Timer */}
                {state === 'interviewing' && !isPaused && (
                  <div style={{ flexShrink: 0 }}>
                    <CircularTimer
                      seconds={timerSec}
                      total={totalSec}
                      color={timerColor}
                    />
                  </div>
                )}
                {isPaused && (
                  <div style={{
                    width: 88, height: 88, borderRadius: '50%',
                    background: 'var(--bg-elevated)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    flexShrink: 0,
                  }}>
                    <Pause size={22} style={{ color: 'var(--text-muted)' }} />
                  </div>
                )}
              </div>

              {/* Hints */}
              {question.hints.length > 0 && state === 'interviewing' && (
                <div style={{
                  background: 'rgba(37,99,235,0.05)',
                  border: '1px solid rgba(37,99,235,0.12)',
                  borderRadius: 8, padding: '10px 14px',
                }}>
                  <p style={{
                    fontSize: 10, fontWeight: 700,
                    color: 'var(--blue-bright)', letterSpacing: '0.08em',
                    textTransform: 'uppercase', marginBottom: 6,
                  }}>
                    Hints
                  </p>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                    {question.hints.map((h, i) => (
                      <span key={i} style={{
                        fontSize: 12, color: 'var(--text-secondary)',
                        background: 'var(--bg-elevated)',
                        borderRadius: 6, padding: '3px 10px',
                      }}>
                        {h}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Answer controls — audio mode */}
          {state === 'interviewing' && mode === 'audio' && !isPaused && (
            <div className="card" style={{
              textAlign: 'center', padding: '28px 24px',
              background: isRecording
                ? 'rgba(239,68,68,0.04)'
                : 'var(--bg-surface)',
              border: isRecording
                ? '1px solid rgba(239,68,68,0.2)'
                : '1px solid var(--border-default)',
              transition: 'all 0.3s',
            }}>
              <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 20 }}>
                {isRecording
                  ? 'Recording your answer — click again to submit'
                  : 'Click the mic and speak your answer clearly'}
              </p>

              {/* Wave bars */}
              <div style={{ marginBottom: 20, minHeight: 56 }}>
                <WaveBars active={isRecording} color="var(--blue-bright)" />
              </div>

              {/* Live transcript */}
              {(isRecording || liveTranscript) && (
                <div style={{
                  background: 'var(--bg-elevated)',
                  border: '1px solid var(--border-default)',
                  borderRadius: 8, padding: '10px 14px',
                  marginBottom: 20, textAlign: 'left', minHeight: 44,
                  animation: 'fadeIn 0.2s ease',
                }}>
                  <p style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 4 }}>
                    {isRecording ? '🔴 Transcribing...' : 'Your answer:'}
                  </p>
                  <p style={{ fontSize: 13, color: 'var(--text-primary)', lineHeight: 1.5 }}>
                    {liveTranscript || (
                      <span style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>
                        Listening...
                      </span>
                    )}
                  </p>
                </div>
              )}

              {/* Mic button */}
              <button
                onClick={isRecording ? handleStopAndSubmit : handleStartRecording}
                style={{
                  width: 76, height: 76, borderRadius: '50%',
                  border: 'none', cursor: 'pointer', margin: '0 auto',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  background: isRecording
                    ? 'var(--red)'
                    : 'linear-gradient(135deg, var(--blue-mid), var(--blue-core))',
                  boxShadow: isRecording
                    ? '0 0 0 0 rgba(239,68,68,0.4)'
                    : '0 4px 20px rgba(37,99,235,0.35)',
                  animation: isRecording ? 'pulse 1.5s ease-in-out infinite' : 'none',
                  transition: 'all 0.2s cubic-bezier(0.34,1.56,0.64,1)',
                  transform: isRecording ? 'scale(1.05)' : 'scale(1)',
                }}>
                {isRecording
                  ? <MicOff size={30} color="white" />
                  : <Mic size={30} color="white" />}
              </button>

              <button className="btn btn-ghost btn-sm"
                style={{ marginTop: 16, fontSize: 11 }}
                onClick={() => setMode('text')}>
                Switch to text mode
              </button>
            </div>
          )}

          {/* Answer controls — text mode */}
          {state === 'interviewing' && mode === 'text' && question && !isPaused && (
            <div className="card" style={{ animation: 'fadeIn 0.3s ease' }}>
              <textarea className="input" rows={4}
                placeholder="Type your answer here..."
                value={textAnswer}
                onChange={e => setTextAnswer(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter' && e.ctrlKey) handleSubmitText() }}
                style={{ resize: 'none', marginBottom: 12 }} />
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ display: 'flex', gap: 8 }}>
                  <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                    Ctrl + Enter to submit
                  </span>
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                  <button className="btn btn-ghost btn-sm"
                    onClick={() => setMode('audio')}>
                    <Mic size={12} /> Voice mode
                  </button>
                  <button className="btn btn-primary"
                    onClick={handleSubmitText}
                    disabled={!textAnswer.trim()}>
                    <Send size={13} /> Submit
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Evaluation feedback */}
          {evaluation && state === 'evaluating' && (
            <div className="card eval-card" style={{
              borderLeft: '3px solid var(--green)',
            }}>
              {/* Score header */}
              <div style={{
                display: 'flex', alignItems: 'center',
                justifyContent: 'space-between', marginBottom: 18,
              }}>
                <div>
                  <h3 style={{
                    fontFamily: 'Outfit, sans-serif',
                    fontSize: 15, fontWeight: 700, marginBottom: 2,
                  }}>
                    Feedback
                  </h3>
                  <p style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                    Question {doneQ} of {totalQ}
                  </p>
                </div>
                <div style={{
                  fontFamily: 'DM Mono, monospace', fontSize: 26, fontWeight: 700,
                  color: evaluation.overall_score >= 70 ? 'var(--green)' : 'var(--yellow)',
                  background: evaluation.overall_score >= 70
                    ? 'rgba(16,185,129,0.08)' : 'rgba(245,158,11,0.08)',
                  border: `1px solid ${evaluation.overall_score >= 70 ? 'rgba(16,185,129,0.2)' : 'rgba(245,158,11,0.2)'}`,
                  borderRadius: 10, padding: '6px 14px',
                }}>
                  {evaluation.overall_score}
                  <span style={{ fontSize: 14, opacity: 0.6 }}>/100</span>
                </div>
              </div>

              {/* Score bars */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 16 }}>
                {Object.entries(evaluation.scores).map(([k, v]) => (
                  <ProgressBar key={k} label={k.replace('_', ' ')} value={v as number} />
                ))}
              </div>

              {/* Strengths */}
              {evaluation.strengths.length > 0 && (
                <div style={{ marginBottom: 10 }}>
                  {evaluation.strengths.map((s, i) => (
                    <div key={i} style={{
                      display: 'flex', alignItems: 'flex-start', gap: 8,
                      marginBottom: 4,
                    }}>
                      <span style={{ color: 'var(--green)', fontSize: 14, lineHeight: '20px' }}>✓</span>
                      <p style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5 }}>{s}</p>
                    </div>
                  ))}
                </div>
              )}

              {/* Improvements */}
              {evaluation.improvements.length > 0 && (
                <div style={{ marginBottom: 12 }}>
                  {evaluation.improvements.map((s, i) => (
                    <div key={i} style={{
                      display: 'flex', alignItems: 'flex-start', gap: 8,
                      marginBottom: 4,
                    }}>
                      <span style={{ color: 'var(--yellow)', fontSize: 14, lineHeight: '20px' }}>→</span>
                      <p style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5 }}>{s}</p>
                    </div>
                  ))}
                </div>
              )}

              {/* Encouragement */}
              <div style={{
                padding: '10px 14px',
                background: 'rgba(37,99,235,0.06)',
                borderRadius: 8, marginBottom: 18,
              }}>
                <p style={{ fontSize: 13, color: 'var(--text-secondary)', fontStyle: 'italic', lineHeight: 1.55 }}>
                  {evaluation.encouragement}
                </p>
              </div>

              {/* Action button */}
              {isLastQ ? (
                <button className="btn btn-primary" style={{ width: '100%' }}
                  onClick={() => setShowEndConfirm(true)}>
                  View your IRI score →
                </button>
              ) : pendingQ ? (
                <button className="btn btn-primary" style={{ width: '100%' }}
                  onClick={() => applyQuestion(pendingQ)}>
                  Continue to question {pendingQ.question_number}
                  <ChevronRight size={15} />
                </button>
              ) : (
                <div style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10,
                }}>
                  <div className="spinner spinner-sm" />
                  <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                    Loading next question...
                  </span>
                </div>
              )}

              {showEndConfirm && isLastQ && (
                <div style={{
                  marginTop: 12, padding: '12px 14px',
                  background: 'rgba(239,68,68,0.06)',
                  border: '1px solid rgba(239,68,68,0.2)',
                  borderRadius: 8,
                  display: 'flex', alignItems: 'center',
                  justifyContent: 'space-between', gap: 10,
                }}>
                  <p style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                    End session and calculate your IRI score?
                  </p>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <button className="btn btn-ghost btn-sm"
                      onClick={() => setShowEndConfirm(false)}>Cancel</button>
                    <button className="btn btn-danger btn-sm"
                      onClick={handleEndSession}>Confirm</button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Transcript sidebar */}
        <div style={{
          width: 240, background: 'var(--bg-surface)',
          borderLeft: '1px solid var(--border-subtle)',
          display: 'flex', flexDirection: 'column', flexShrink: 0,
        }}>
          <div style={{
            padding: '14px 16px',
            borderBottom: '1px solid var(--border-subtle)',
          }}>
            <p className="label-caps">Conversation</p>
          </div>
          <div ref={transcriptRef} style={{
            flex: 1, overflowY: 'auto', padding: 10,
            display: 'flex', flexDirection: 'column', gap: 6,
          }}>
            {question && (
              <div style={{
                padding: '8px 10px', borderRadius: 8, fontSize: 12,
                background: 'rgba(37,99,235,0.08)',
                border: '1px solid rgba(37,99,235,0.15)',
                animation: 'fadeIn 0.3s ease',
              }}>
                <span style={{
                  fontSize: 10, fontWeight: 700, color: 'var(--blue-bright)',
                  textTransform: 'uppercase', letterSpacing: '0.05em',
                  display: 'block', marginBottom: 4,
                }}>
                  Q{question.question_number}
                </span>
                <span style={{ color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                  {question.question}
                </span>
              </div>
            )}
            {liveTranscript && isRecording && (
              <div style={{
                padding: '8px 10px', borderRadius: 8, fontSize: 12,
                background: 'rgba(239,68,68,0.06)',
                border: '1px solid rgba(239,68,68,0.15)',
              }}>
                <span style={{
                  fontSize: 10, fontWeight: 700, color: 'var(--red)',
                  textTransform: 'uppercase', letterSpacing: '0.05em',
                  display: 'block', marginBottom: 4,
                }}>
                  🔴 You
                </span>
                <span style={{ color: 'var(--text-secondary)' }}>{liveTranscript}</span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── Pause overlay ─────────────────────────────────────────────────── */}
      {isPaused && (
        <div style={{
          position: 'fixed', inset: 0,
          background: 'rgba(0,0,0,0.75)',
          backdropFilter: 'blur(8px)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          zIndex: 100,
          animation: 'fadeIn 0.25s ease',
        }}>
          <div style={{
            background: 'var(--bg-surface)',
            border: '1px solid var(--border-default)',
            borderRadius: 16, padding: '36px 40px',
            textAlign: 'center', maxWidth: 340, width: '100%',
          }}>
            <div style={{
              width: 56, height: 56, borderRadius: '50%',
              background: 'rgba(37,99,235,0.1)',
              border: '1px solid rgba(37,99,235,0.2)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              margin: '0 auto 16px',
            }}>
              <Pause size={22} style={{ color: 'var(--blue-bright)' }} />
            </div>
            <h2 style={{
              fontFamily: 'Outfit, sans-serif', fontSize: 20,
              fontWeight: 700, marginBottom: 6,
            }}>
              Session paused
            </h2>
            <p style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 24, lineHeight: 1.6 }}>
              Take your time. Your progress is saved. Resume whenever you are ready.
            </p>
            <button className="btn btn-primary" style={{ width: '100%', marginBottom: 10 }}
              onClick={handleResume}>
              <Play size={14} /> Resume interview
            </button>
            <button className="btn btn-ghost" style={{ width: '100%' }}
              onClick={() => { setIsPaused(false); setShowEndConfirm(true) }}>
              End session
            </button>
          </div>
        </div>
      )}
    </div>
  )
}