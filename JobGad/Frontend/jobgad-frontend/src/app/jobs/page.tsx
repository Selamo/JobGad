'use client'
import { useEffect, useState } from 'react'
import { AppShell } from '@/components/layout/AppShell'
import { Badge, Modal, Spinner, EmptyState, toast, ToastContainer } from '@/components/ui'
import { jobs, applications, type Job, type JobMatch, type MatchExplanation } from '@/lib/api'
import { Search, Zap, MapPin, Briefcase, ChevronRight, X, CheckCircle2 } from 'lucide-react'

type Tab = 'matches' | 'browse'
const EMPLOYMENT_TYPES = ['full-time', 'part-time', 'contract', 'internship']

export default function JobsPage() {
  const [tab, setTab]                 = useState<Tab>('matches')
  const [matches, setMatches]         = useState<JobMatch[]>([])
  const [browseJobs, setBrowseJobs]   = useState<Job[]>([])
  const [total, setTotal]             = useState(0)
  const [loading, setLoading]         = useState(true)
  const [running, setRunning]         = useState(false)
  const [applying, setApplying]       = useState(false)
  const [searchQ, setSearchQ]         = useState('')
  const [filterType, setFilterType]   = useState('')
  const [filterLoc, setFilterLoc]     = useState('')
  const [page, setPage]               = useState(1)
  const [explanation, setExplanation] = useState<MatchExplanation | null>(null)
  const [showExplain, setShowExplain] = useState(false)
  const [coverLetter, setCoverLetter] = useState('')
  const [showApplyModal, setShowApplyModal] = useState(false)
  const [applyTarget, setApplyTarget] = useState<Job | null>(null)

  useEffect(() => {
    if (tab === 'matches') loadMatches()
    else loadBrowse()
  }, [tab])

  useEffect(() => {
    if (tab === 'browse') {
      const t = setTimeout(() => loadBrowse(), 400)
      return () => clearTimeout(t)
    }
  }, [searchQ, filterType, filterLoc, page])

  async function loadMatches() {
    setLoading(true)
    try {
      const data = await jobs.getMatches()
      setMatches(Array.isArray(data) ? data : [])
    } catch { setMatches([]) }
    finally { setLoading(false) }
  }

  async function loadBrowse() {
    setLoading(true)
    try {
      const res = await jobs.list({ search: searchQ || undefined, employment_type: filterType || undefined, location: filterLoc || undefined, page, page_size: 15 })
      setBrowseJobs(res.jobs ?? [])
      setTotal(res.total ?? 0)
    } catch { setBrowseJobs([]) }
    finally { setLoading(false) }
  }

  async function handleRunMatches() {
    setRunning(true)
    try {
      await jobs.runMatches(10)
      toast('Job matching complete', 'success')
      await loadMatches()
    } catch (e: any) {
      toast(e.message || 'Matching failed', 'error')
    } finally { setRunning(false) }
  }

  async function handleUpdateStatus(matchId: string, status: string) {
    try {
      await jobs.updateMatchStatus(matchId, status)
      setMatches(m => m.map(x => x.id === matchId ? { ...x, status } : x))
      toast(`Match marked as ${status}`, 'success')
    } catch (e: any) { toast(e.message || 'Failed to update', 'error') }
  }

  async function handleExplain(jobId: string) {
    try {
      const exp = await jobs.explainMatch(jobId)
      setExplanation(exp)
      setShowExplain(true)
    } catch (e: any) { toast(e.message || 'Could not load explanation', 'error') }
  }

  async function handleApply() {
    if (!applyTarget) return
    setApplying(true)
    try {
      await applications.apply(applyTarget.id, coverLetter || undefined)
      toast('Application submitted successfully', 'success')
      setShowApplyModal(false)
      setCoverLetter('')
      setApplyTarget(null)
    } catch (e: any) {
      toast(e.message || 'Application failed', 'error')
    } finally { setApplying(false) }
  }

  function openApply(job: Job) { setApplyTarget(job); setShowApplyModal(true) }

  const scoreColor = (s: number) => s >= 0.8 ? 'var(--green)' : s >= 0.6 ? 'var(--blue-bright)' : 'var(--yellow)'
  const totalPages = Math.ceil(total / 15)

  return (
    <AppShell
      title="Jobs"
      subtitle="Matches and job listings"
      actions={
        tab === 'matches' ? (
          <button className="btn btn-primary" onClick={handleRunMatches} disabled={running}>
            {running ? <Spinner size="sm" /> : <Zap size={14} />}
            {running ? 'Matching...' : 'Run AI matching'}
          </button>
        ) : undefined
      }
    >
      <ToastContainer />

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 20, borderBottom: '1px solid var(--border-subtle)' }}>
        {(['matches', 'browse'] as Tab[]).map(t => (
          <button key={t} onClick={() => setTab(t)}
            style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '8px 16px', fontSize: 14, fontWeight: 500, color: tab === t ? 'var(--text-primary)' : 'var(--text-muted)', borderBottom: `2px solid ${tab === t ? 'var(--blue-core)' : 'transparent'}`, marginBottom: -1, transition: 'all 0.15s', textTransform: 'capitalize' }}>
            {t === 'matches' ? `AI Matches${matches.length > 0 ? ` (${matches.length})` : ''}` : 'Browse All Jobs'}
          </button>
        ))}
      </div>

      {/* Browse filters */}
      {tab === 'browse' && (
        <div style={{ display: 'flex', gap: 10, marginBottom: 18, flexWrap: 'wrap' }}>
          <div style={{ position: 'relative', flex: 1, minWidth: 200 }}>
            <Search size={14} style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
            <input className="input" placeholder="Search jobs..." value={searchQ}
              onChange={e => { setSearchQ(e.target.value); setPage(1) }} style={{ paddingLeft: 36 }} />
          </div>
          <select className="input" style={{ width: 160 }} value={filterType} onChange={e => { setFilterType(e.target.value); setPage(1) }}>
            <option value="">All types</option>
            {EMPLOYMENT_TYPES.map(t => <option key={t} value={t} style={{ textTransform: 'capitalize' }}>{t}</option>)}
          </select>
          <div style={{ position: 'relative', width: 160 }}>
            <MapPin size={13} style={{ position: 'absolute', left: 11, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
            <input className="input" placeholder="Location" value={filterLoc}
              onChange={e => { setFilterLoc(e.target.value); setPage(1) }} style={{ paddingLeft: 32 }} />
          </div>
          {(searchQ || filterType || filterLoc) && (
            <button className="btn btn-ghost btn-sm" onClick={() => { setSearchQ(''); setFilterType(''); setFilterLoc(''); setPage(1) }}>
              <X size={13} /> Clear
            </button>
          )}
        </div>
      )}

      {loading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: 60 }}><Spinner size="lg" /></div>
      ) : tab === 'matches' ? (
        matches.length === 0 ? (
          <div className="card" style={{ padding: 48, textAlign: 'center' }}>
            <Zap size={28} style={{ color: 'var(--text-muted)', margin: '0 auto 12px' }} />
            <h3 style={{ fontFamily: 'Outfit, sans-serif', fontSize: 16, fontWeight: 600, marginBottom: 6 }}>No matches yet</h3>
            <p style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 20 }}>Click &quot;Run AI matching&quot; to find jobs that match your profile.</p>
            <button className="btn btn-primary" onClick={handleRunMatches} disabled={running}>
              {running ? <Spinner size="sm" /> : <Zap size={14} />} {running ? 'Running...' : 'Run AI matching'}
            </button>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {matches.map(match => (
              <div key={match.id} className="card card-interactive" style={{ display: 'flex', gap: 16, alignItems: 'flex-start' }}>
                <div style={{ width: 52, height: 52, borderRadius: 10, flexShrink: 0, background: `${scoreColor(match.similarity_score)}18`, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
                  <span style={{ fontFamily: 'DM Mono, monospace', fontSize: 14, fontWeight: 600, color: scoreColor(match.similarity_score), lineHeight: 1 }}>
                    {Math.round(match.similarity_score * 100)}
                  </span>
                  <span style={{ fontSize: 9, color: 'var(--text-muted)', marginTop: 1 }}>match</span>
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 10, marginBottom: 4 }}>
                    <div>
                      <h3 style={{ fontFamily: 'Outfit, sans-serif', fontSize: 15, fontWeight: 600, marginBottom: 2 }}>{match.job.title}</h3>
                      <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{match.job.company}</span>
                    </div>
                    <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexShrink: 0 }}>
                      <Badge label={match.status} />
                      <Badge label={match.job.employment_type} />
                    </div>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
                    <span style={{ fontSize: 12, color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 4 }}>
                      <MapPin size={11} /> {match.job.location}
                    </span>
                    {match.job.salary_range && <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{match.job.salary_range}</span>}
                  </div>
                  {match.match_reason && (
                    <p style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.55, marginBottom: 12, fontStyle: 'italic' }}>{match.match_reason}</p>
                  )}
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                    <button className="btn btn-primary btn-sm" onClick={() => openApply(match.job)}>Apply now</button>
                    <button className="btn btn-ghost btn-sm" onClick={() => handleExplain(match.job.id)}>Explain match <ChevronRight size={12} /></button>
                    {match.status === 'suggested' && (
                      <button className="btn btn-ghost btn-sm" onClick={() => handleUpdateStatus(match.id, 'saved')}>Save</button>
                    )}
                    {match.status !== 'rejected' && (
                      <button className="btn btn-ghost btn-sm" onClick={() => handleUpdateStatus(match.id, 'rejected')} style={{ color: 'var(--text-muted)' }}>Dismiss</button>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )
      ) : (
        browseJobs.length === 0 ? (
          <EmptyState icon={<Briefcase size={28} />} title="No jobs found" description="Try adjusting your search or filters." />
        ) : (
          <>
            <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 12 }}>{total} job{total !== 1 ? 's' : ''} found</p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {browseJobs.map(job => (
                <div key={job.id} className="card card-interactive" style={{ display: 'flex', gap: 14, alignItems: 'flex-start' }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 10, marginBottom: 4 }}>
                      <h3 style={{ fontFamily: 'Outfit, sans-serif', fontSize: 15, fontWeight: 600 }}>{job.title}</h3>
                      <Badge label={job.employment_type} />
                    </div>
                    <div style={{ display: 'flex', gap: 16, marginBottom: 8 }}>
                      <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{job.company}</span>
                      <span style={{ fontSize: 12, color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 4 }}>
                        <MapPin size={11} /> {job.location}
                      </span>
                    </div>
                    {job.salary_range && <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 8 }}>{job.salary_range}</p>}
                    <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.55, marginBottom: 12, overflow: 'hidden', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' }}>
                      {job.description}
                    </p>
                    <button className="btn btn-primary btn-sm" onClick={() => openApply(job)}>Apply now</button>
                  </div>
                </div>
              ))}
            </div>
            {totalPages > 1 && (
              <div style={{ display: 'flex', justifyContent: 'center', gap: 8, marginTop: 24 }}>
                <button className="btn btn-ghost btn-sm" disabled={page === 1} onClick={() => setPage(p => p - 1)}>Previous</button>
                <span style={{ display: 'flex', alignItems: 'center', fontSize: 13, color: 'var(--text-muted)', padding: '0 12px' }}>Page {page} of {totalPages}</span>
                <button className="btn btn-ghost btn-sm" disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}>Next</button>
              </div>
            )}
          </>
        )
      )}

      {/* Apply Modal */}
      <Modal open={showApplyModal} onClose={() => { setShowApplyModal(false); setCoverLetter('') }} title="Apply for position" maxWidth={500}>
        <div className="modal-body">
          {applyTarget && (
            <>
              <div style={{ background: 'var(--bg-elevated)', borderRadius: 8, padding: '12px 14px', marginBottom: 20 }}>
                <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 2 }}>{applyTarget.title}</div>
                <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>{applyTarget.company} · {applyTarget.location}</div>
              </div>
              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="label">Cover letter <span style={{ color: 'var(--text-muted)', fontWeight: 400 }}>(optional)</span></label>
                <textarea className="input" rows={5} placeholder="Tell the recruiter why you are a great fit..."
                  value={coverLetter} onChange={e => setCoverLetter(e.target.value)} />
              </div>
            </>
          )}
        </div>
        <div className="modal-footer">
          <button className="btn btn-ghost" onClick={() => setShowApplyModal(false)}>Cancel</button>
          <button className="btn btn-primary" onClick={handleApply} disabled={applying}>
            {applying ? <Spinner size="sm" /> : <CheckCircle2 size={14} />}
            {applying ? 'Submitting...' : 'Submit application'}
          </button>
        </div>
      </Modal>

      {/* Explain Modal */}
      <Modal open={showExplain} onClose={() => setShowExplain(false)} title="Match Explanation" maxWidth={520}>
        <div className="modal-body">
          {explanation && (
            <>
              <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 20, padding: '12px 14px', background: 'var(--bg-elevated)', borderRadius: 8 }}>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontFamily: 'DM Mono, monospace', fontSize: 28, fontWeight: 600, color: scoreColor(explanation.similarity_score), lineHeight: 1 }}>
                    {Math.round(explanation.similarity_score * 100)}
                  </div>
                  <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>score</div>
                </div>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 2 }}>{explanation.tier}</div>
                  <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5 }}>{explanation.match_reason}</div>
                </div>
              </div>
              {explanation.skill_overlap?.matched?.length > 0 && (
                <div style={{ marginBottom: 14 }}>
                  <p className="label-caps" style={{ marginBottom: 8 }}>Skills you have ({explanation.skill_overlap.matched.length})</p>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                    {explanation.skill_overlap.matched.map(s => (
                      <span key={s} style={{ background: 'var(--green-dim)', color: 'var(--green)', fontSize: 12, padding: '3px 9px', borderRadius: 5, fontWeight: 500 }}>{s}</span>
                    ))}
                  </div>
                </div>
              )}
              {explanation.skill_overlap?.missing?.length > 0 && (
                <div>
                  <p className="label-caps" style={{ marginBottom: 8 }}>Skills to develop ({explanation.skill_overlap.missing.length})</p>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                    {explanation.skill_overlap.missing.map(s => (
                      <span key={s} style={{ background: 'var(--red-dim)', color: 'var(--red)', fontSize: 12, padding: '3px 9px', borderRadius: 5, fontWeight: 500 }}>{s}</span>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
        <div className="modal-footer">
          <button className="btn btn-ghost" onClick={() => setShowExplain(false)}>Close</button>
          {explanation && (
            <button className="btn btn-primary" onClick={() => { setShowExplain(false); openApply(explanation.job) }}>
              Apply for this job
            </button>
          )}
        </div>
      </Modal>
    </AppShell>
  )
}