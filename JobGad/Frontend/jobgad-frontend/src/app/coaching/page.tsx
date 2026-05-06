'use client'
import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { AppShell } from '@/components/layout/AppShell'
import { ScoreRing, ProgressBar, Badge, Modal, Spinner, EmptyState, toast, ToastContainer } from '@/components/ui'
import { coaching, jobs, type CoachingSession, type IRIData, type Job } from '@/lib/api'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'
import { Mic, Plus, ChevronRight, Calendar, TrendingUp } from 'lucide-react'

const SESSION_TYPES = [
  { value: 'mixed',      label: 'Mixed',      desc: 'Behavioral and technical questions combined' },
  { value: 'behavioral', label: 'Behavioral', desc: 'Focus on soft skills and situational questions' },
  { value: 'technical',  label: 'Technical',  desc: 'Focus on technical and domain knowledge' },
]

export default function CoachingPage() {
  const router = useRouter()
  const [iriData, setIriData]     = useState<IRIData | null>(null)
  const [sessions, setSessions]   = useState<CoachingSession[]>([])
  const [jobList, setJobList]     = useState<Job[]>([])
  const [loading, setLoading]     = useState(true)
  const [starting, setStarting]   = useState(false)
  const [showModal, setShowModal] = useState(false)
  const [selectedJob, setSelectedJob]   = useState('')
  const [sessionType, setSessionType]   = useState<'mixed' | 'behavioral' | 'technical'>('mixed')

  useEffect(() => { loadAll() }, [])

  async function loadAll() {
    setLoading(true)
    try {
      const [iri, sess, jbs] = await Promise.allSettled([
        coaching.getIRI(),
        coaching.getSessions(),
        jobs.list({ page_size: 50 }),
      ])
      if (iri.status  === 'fulfilled') setIriData(iri.value)
      if (sess.status === 'fulfilled') setSessions(Array.isArray(sess.value) ? sess.value : [])
      if (jbs.status  === 'fulfilled') setJobList(jbs.value.jobs ?? [])
    } finally { setLoading(false) }
  }

  async function handleStart() {
    if (!selectedJob) { toast('Please select a job to practice for', 'error'); return }
    setStarting(true)
    try {
      const session = await coaching.createSession(selectedJob, sessionType)
      router.push(`/coaching/interview/${session.session_id}`)
    } catch (e: any) {
      toast(e.message || 'Failed to start session', 'error')
      setStarting(false)
    }
  }

  function formatDate(iso: string) {
    return new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
  }

  const iri = iriData?.current_iri ?? 0

  const readinessColor =
    iri >= 80 ? 'var(--green)'       :
    iri >= 60 ? 'var(--blue-bright)' :
    iri >= 40 ? 'var(--yellow)'      : 'var(--red)'

  const chartData = (iriData?.history ?? []).map((h, i) => ({
    session: `S${i + 1}`,
    score: Math.round(h.score),
    date: formatDate(h.date),
  }))

  const CustomTooltip = ({ active, payload }: any) => {
    if (!active || !payload?.length) return null
    return (
      <div style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border-default)', borderRadius: 8, padding: '8px 12px' }}>
        <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 2 }}>{payload[0]?.payload?.date}</p>
        <p style={{ fontFamily: 'DM Mono, monospace', fontSize: 16, fontWeight: 600, color: 'var(--blue-bright)' }}>{payload[0]?.value}</p>
      </div>
    )
  }

  return (
    <AppShell
      title="Interview Coaching"
      subtitle="Practice with AI and track your readiness"
      actions={
        <button className="btn btn-primary" onClick={() => setShowModal(true)}>
          <Plus size={14} /> New session
        </button>
      }
    >
      <ToastContainer />

      {loading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: 60 }}><Spinner size="lg" /></div>
      ) : (
        <>
          {/* Top grid */}
          <div style={{ display: 'grid', gridTemplateColumns: '280px 1fr', gap: 16, marginBottom: 16 }}>

            {/* IRI score card */}
            <div className="card" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', textAlign: 'center', padding: 28 }}>
              <p className="label-caps" style={{ marginBottom: 16 }}>Interview Readiness Index</p>
              <ScoreRing score={iri} size={100} />
              <div style={{ marginTop: 16, marginBottom: 8 }}>
                <p style={{ fontFamily: 'Outfit, sans-serif', fontSize: 15, fontWeight: 600, color: readinessColor }}>
                  {iriData?.readiness_level ?? 'Not started'}
                </p>
              </div>
              <p style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                {iriData?.total_sessions ?? 0} session{(iriData?.total_sessions ?? 0) !== 1 ? 's' : ''} completed
              </p>
              <button className="btn btn-primary" style={{ marginTop: 20, width: '100%' }} onClick={() => setShowModal(true)}>
                <Mic size={14} /> Start session
              </button>
            </div>

            {/* IRI chart */}
            <div className="card">
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 20 }}>
                <TrendingUp size={15} style={{ color: 'var(--blue-bright)' }} />
                <h3 style={{ fontFamily: 'Outfit, sans-serif', fontSize: 15, fontWeight: 600 }}>IRI Progress Over Time</h3>
              </div>
              {chartData.length < 2 ? (
                <EmptyState title="Not enough data yet" description="Complete at least 2 sessions to see your progress chart." />
              ) : (
                <ResponsiveContainer width="100%" height={200}>
                  <LineChart data={chartData} margin={{ top: 4, right: 16, left: -20, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                    <XAxis dataKey="session" tick={{ fontSize: 11, fill: 'var(--text-muted)' }} axisLine={false} tickLine={false} />
                    <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: 'var(--text-muted)' }} axisLine={false} tickLine={false} />
                    <Tooltip content={<CustomTooltip />} />
                    <Line type="monotone" dataKey="score" stroke="var(--blue-core)" strokeWidth={2.5}
                      dot={{ fill: 'var(--blue-bright)', r: 4, strokeWidth: 0 }}
                      activeDot={{ r: 6, fill: 'var(--blue-bright)' }} />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>

          {/* Breakdown bars */}
          {iri > 0 && iriData && (
            <div className="card" style={{ marginBottom: 16 }}>
              <h3 style={{ fontFamily: 'Outfit, sans-serif', fontSize: 15, fontWeight: 600, marginBottom: 16 }}>Score Breakdown</h3>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
                {[
                  { label: 'Communication',      value: iriData.breakdown.communication },
                  { label: 'Technical Accuracy', value: iriData.breakdown.technical_accuracy },
                  { label: 'Confidence',         value: iriData.breakdown.confidence },
                  { label: 'Structure',          value: iriData.breakdown.structure },
                ].map(item => (
                  <ProgressBar key={item.label} label={item.label} value={item.value} />
                ))}
              </div>
            </div>
          )}

          {/* Session history */}
          <div className="card">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
              <h3 style={{ fontFamily: 'Outfit, sans-serif', fontSize: 15, fontWeight: 600 }}>Session History</h3>
              <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{sessions.length} total</span>
            </div>
            {sessions.length === 0 ? (
              <EmptyState icon={<Mic size={28} />} title="No sessions yet"
                description="Start your first AI interview session to begin building your IRI score."
                action={
                  <button className="btn btn-primary" onClick={() => setShowModal(true)}>
                    <Plus size={14} /> Start first session
                  </button>
                }
              />
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {sessions.map(s => {
                  const score = s.iri_score?.overall_score ?? 0
                  const isCompleted = s.status === 'completed'
                  return (
                    <div key={s.session_id} style={{ display: 'flex', alignItems: 'center', gap: 14, padding: '13px 16px', background: 'var(--bg-elevated)', borderRadius: 10, border: '1px solid var(--border-subtle)' }}>
                      <div style={{ width: 44, height: 44, borderRadius: 8, flexShrink: 0, background: isCompleted ? 'rgba(59,130,246,0.12)' : 'var(--bg-overlay)', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
                        {isCompleted ? (
                          <>
                            <span style={{ fontFamily: 'DM Mono, monospace', fontSize: 13, fontWeight: 600, color: 'var(--blue-bright)', lineHeight: 1 }}>{Math.round(score)}</span>
                            <span style={{ fontSize: 9, color: 'var(--text-muted)', marginTop: 1 }}>IRI</span>
                          </>
                        ) : (
                          <Mic size={16} style={{ color: 'var(--text-muted)' }} />
                        )}
                      </div>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontSize: 13, fontWeight: 500, marginBottom: 3, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {s.job_title ?? 'General Practice'}
                        </div>
                        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
                          <Badge label={s.session_type} />
                        </div>
                      </div>
                      <Badge label={s.status} />
                      {s.status === 'active' && (
                        <button className="btn btn-primary btn-sm" onClick={() => router.push(`/coaching/interview/${s.session_id}`)}>
                          Resume <ChevronRight size={12} />
                        </button>
                      )}
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </>
      )}

      {/* New Session Modal */}
      <Modal open={showModal} onClose={() => { if (!starting) setShowModal(false) }} title="Start Interview Session" maxWidth={500}>
        <div className="modal-body">
          <div className="form-group">
            <label className="label">Practice for which job?</label>
            <select className="input" value={selectedJob} onChange={e => setSelectedJob(e.target.value)}>
              <option value="">Select a job...</option>
              {jobList.map(j => (
                <option key={j.id} value={j.id}>{j.title} — {j.company}</option>
              ))}
            </select>
            <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 5 }}>
              The AI will tailor questions to this specific role and company.
            </p>
          </div>
          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="label">Session type</label>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {SESSION_TYPES.map(t => (
                <button key={t.value} type="button" onClick={() => setSessionType(t.value as any)}
                  style={{ padding: '12px 14px', borderRadius: 8, textAlign: 'left', cursor: 'pointer', border: `1px solid ${sessionType === t.value ? 'var(--blue-mid)' : 'var(--border-default)'}`, background: sessionType === t.value ? 'rgba(37,99,235,0.1)' : 'var(--bg-elevated)', transition: 'all 0.15s' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <span style={{ fontSize: 14, fontWeight: 500, color: sessionType === t.value ? 'var(--blue-bright)' : 'var(--text-primary)' }}>{t.label}</span>
                    {sessionType === t.value && <div style={{ width: 7, height: 7, borderRadius: '50%', background: 'var(--blue-core)' }} />}
                  </div>
                  <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 3 }}>{t.desc}</p>
                </button>
              ))}
            </div>
          </div>
        </div>
        <div className="modal-footer">
          <button className="btn btn-ghost" onClick={() => setShowModal(false)} disabled={starting}>Cancel</button>
          <button className="btn btn-primary" onClick={handleStart} disabled={starting || !selectedJob}>
            {starting ? <Spinner size="sm" /> : <Mic size={14} />}
            {starting ? 'Starting...' : 'Begin session'}
          </button>
        </div>
      </Modal>
    </AppShell>
  )
}