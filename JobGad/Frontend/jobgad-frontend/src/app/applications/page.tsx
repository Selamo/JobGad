'use client'
import { useEffect, useState } from 'react'
import { AppShell } from '@/components/layout/AppShell'
import { Badge, Modal, Spinner, EmptyState, toast, ToastContainer } from '@/components/ui'
import { applications, type Application, type ApplicationStats } from '@/lib/api'
import { FileText, MapPin, Clock, Trash2, ChevronRight } from 'lucide-react'

const STATUSES = ['all', 'pending', 'reviewed', 'shortlisted', 'accepted', 'rejected']

const STATUS_COLORS: Record<string, { bg: string; border: string; dot: string }> = {
  pending:     { bg: 'rgba(245,158,11,0.06)',  border: 'rgba(245,158,11,0.15)',  dot: 'var(--yellow)' },
  reviewed:    { bg: 'rgba(59,130,246,0.06)',   border: 'rgba(59,130,246,0.15)',  dot: 'var(--blue-core)' },
  shortlisted: { bg: 'rgba(16,185,129,0.06)',   border: 'rgba(16,185,129,0.15)', dot: 'var(--green)' },
  accepted:    { bg: 'rgba(16,185,129,0.08)',   border: 'rgba(16,185,129,0.2)',  dot: 'var(--green)' },
  rejected:    { bg: 'rgba(239,68,68,0.06)',    border: 'rgba(239,68,68,0.15)',  dot: 'var(--red)' },
}

export default function ApplicationsPage() {
  const [apps, setApps]         = useState<Application[]>([])
  const [stats, setStats]       = useState<ApplicationStats | null>(null)
  const [filter, setFilter]     = useState('all')
  const [loading, setLoading]   = useState(true)
  const [selected, setSelected] = useState<Application | null>(null)
  const [showDetail, setShowDetail]   = useState(false)
  const [withdrawing, setWithdrawing] = useState<string | null>(null)

  useEffect(() => { loadAll() }, [])

  async function loadAll() {
    setLoading(true)
    try {
      const [a, s] = await Promise.all([applications.list(), applications.stats()])
      setApps(Array.isArray(a) ? a : [])
      setStats(s)
    } catch { setApps([]) }
    finally { setLoading(false) }
  }

  async function handleWithdraw(id: string) {
    setWithdrawing(id)
    try {
      await applications.withdraw(id)
      toast('Application withdrawn', 'info')
      setShowDetail(false)
      await loadAll()
    } catch (e: any) {
      toast(e.message || 'Cannot withdraw this application', 'error')
    } finally { setWithdrawing(null) }
  }

  function openDetail(app: Application) { setSelected(app); setShowDetail(true) }

  const filtered = filter === 'all' ? apps : apps.filter(a => a.status === filter)

  function formatDate(iso: string) {
    return new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
  }

  const canWithdraw = (status: string) => status === 'pending' || status === 'reviewed'

  return (
    <AppShell title="Applications" subtitle="Track all your job applications">
      <ToastContainer />

      {/* Stats bar */}
      {stats && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(100px, 1fr))', gap: 10, marginBottom: 24 }}>
          {[
            { label: 'Total',       value: stats.total_applications, color: 'var(--text-primary)' },
            { label: 'Pending',     value: stats.pending,            color: 'var(--yellow)' },
            { label: 'Reviewed',    value: stats.reviewed,           color: 'var(--blue-bright)' },
            { label: 'Shortlisted', value: stats.shortlisted,        color: 'var(--green)' },
            { label: 'Accepted',    value: stats.accepted,           color: 'var(--green)' },
            { label: 'Rejected',    value: stats.rejected,           color: 'var(--red)' },
          ].map(s => (
            <div key={s.label} style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-default)', borderRadius: 10, padding: '14px 16px', textAlign: 'center' }}>
              <div style={{ fontFamily: 'DM Mono, monospace', fontSize: 22, fontWeight: 500, color: s.color, lineHeight: 1 }}>{s.value}</div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 5 }}>{s.label}</div>
            </div>
          ))}
        </div>
      )}

      {/* Filter tabs */}
      <div style={{ display: 'flex', gap: 6, marginBottom: 18, flexWrap: 'wrap' }}>
        {STATUSES.map(s => (
          <button key={s} onClick={() => setFilter(s)}
            style={{ padding: '5px 14px', borderRadius: 20, fontSize: 12, fontWeight: 500, cursor: 'pointer', border: '1px solid', borderColor: filter === s ? 'var(--blue-mid)' : 'var(--border-default)', background: filter === s ? 'rgba(37,99,235,0.12)' : 'transparent', color: filter === s ? 'var(--blue-bright)' : 'var(--text-secondary)', textTransform: 'capitalize', transition: 'all 0.15s' }}>
            {s}
          </button>
        ))}
      </div>

      {loading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: 60 }}><Spinner size="lg" /></div>
      ) : filtered.length === 0 ? (
        <EmptyState icon={<FileText size={28} />} title={filter === 'all' ? 'No applications yet' : `No ${filter} applications`}
          description={filter === 'all' ? 'Apply to jobs from the Jobs page to see them here.' : `You have no applications with status "${filter}".`} />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {filtered.map(app => {
            const style = STATUS_COLORS[app.status] || STATUS_COLORS['pending']
            return (
              <div key={app.id} onClick={() => openDetail(app)}
                style={{ background: style.bg, border: `1px solid ${style.border}`, borderRadius: 12, padding: '16px 18px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 16, transition: 'all 0.15s' }}
                onMouseEnter={e => (e.currentTarget.style.transform = 'translateY(-1px)')}
                onMouseLeave={e => (e.currentTarget.style.transform = 'translateY(0)')}>
                <div style={{ width: 8, height: 8, borderRadius: '50%', background: style.dot, flexShrink: 0, boxShadow: `0 0 6px ${style.dot}` }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 10 }}>
                    <div>
                      <h3 style={{ fontFamily: 'Outfit, sans-serif', fontSize: 14, fontWeight: 600, marginBottom: 3 }}>{app.job?.title}</h3>
                      <div style={{ display: 'flex', gap: 14, alignItems: 'center', flexWrap: 'wrap' }}>
                        <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{app.job?.company}</span>
                        {app.job?.location && (
                          <span style={{ fontSize: 12, color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 3 }}>
                            <MapPin size={11} /> {app.job.location}
                          </span>
                        )}
                        <span style={{ fontSize: 12, color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 3 }}>
                          <Clock size={11} /> {formatDate(app.created_at)}
                        </span>
                      </div>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
                      <Badge label={app.status} />
                      <ChevronRight size={14} style={{ color: 'var(--text-muted)' }} />
                    </div>
                  </div>
                  {app.hr_notes && (
                    <div style={{ marginTop: 10, padding: '8px 12px', background: 'rgba(255,255,255,0.04)', borderRadius: 6, borderLeft: '2px solid var(--blue-mid)' }}>
                      <p style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5, fontStyle: 'italic' }}>{app.hr_notes}</p>
                    </div>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Detail Modal */}
      <Modal open={showDetail} onClose={() => setShowDetail(false)} title="Application Details" maxWidth={520}>
        {selected && (
          <>
            <div className="modal-body">
              <div style={{ background: 'var(--bg-elevated)', borderRadius: 10, padding: '14px 16px', marginBottom: 20 }}>
                <h3 style={{ fontFamily: 'Outfit, sans-serif', fontSize: 16, fontWeight: 600, marginBottom: 4 }}>{selected.job?.title}</h3>
                <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap' }}>
                  <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{selected.job?.company}</span>
                  {selected.job?.location && (
                    <span style={{ fontSize: 12, color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 4 }}>
                      <MapPin size={11} /> {selected.job.location}
                    </span>
                  )}
                </div>
              </div>

              <div style={{ marginBottom: 20 }}>
                <p className="label-caps" style={{ marginBottom: 8 }}>Current status</p>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <Badge label={selected.status} />
                  <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Applied {formatDate(selected.created_at)}</span>
                </div>
              </div>

              {/* Progress timeline */}
              <div style={{ marginBottom: 20 }}>
                <p className="label-caps" style={{ marginBottom: 10 }}>Progress</p>
                <div style={{ display: 'flex', alignItems: 'center' }}>
                  {['pending', 'reviewed', 'shortlisted', 'accepted'].map((s, i, arr) => {
                    const allStatuses = ['pending', 'reviewed', 'shortlisted', 'accepted', 'rejected']
                    const currentIdx = allStatuses.indexOf(selected.status)
                    const stepIdx    = allStatuses.indexOf(s)
                    const done       = selected.status === 'rejected' ? false : currentIdx >= stepIdx
                    const current    = currentIdx === stepIdx
                    return (
                      <div key={s} style={{ display: 'flex', alignItems: 'center', flex: i < arr.length - 1 ? 1 : 0 }}>
                        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
                          <div style={{ width: 28, height: 28, borderRadius: '50%', background: done ? 'var(--green)' : current ? 'var(--blue-mid)' : 'var(--bg-overlay)', border: `2px solid ${done ? 'var(--green)' : current ? 'var(--blue-mid)' : 'var(--border-default)'}`, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11, color: done || current ? 'white' : 'var(--text-muted)', fontWeight: 600, flexShrink: 0, transition: 'all 0.3s' }}>
                            {done ? '✓' : i + 1}
                          </div>
                          <span style={{ fontSize: 10, color: done || current ? 'var(--text-primary)' : 'var(--text-muted)', textTransform: 'capitalize', whiteSpace: 'nowrap' }}>{s}</span>
                        </div>
                        {i < arr.length - 1 && (
                          <div style={{ flex: 1, height: 2, background: done ? 'var(--green)' : 'var(--bg-overlay)', margin: '0 4px', marginBottom: 18, transition: 'background 0.3s' }} />
                        )}
                      </div>
                    )
                  })}
                </div>
                {selected.status === 'rejected' && (
                  <div style={{ marginTop: 12, padding: '8px 12px', background: 'var(--red-dim)', borderRadius: 6, fontSize: 12, color: 'var(--red)' }}>
                    This application was not successful.
                  </div>
                )}
              </div>

              {selected.hr_notes && (
                <div style={{ marginBottom: 20 }}>
                  <p className="label-caps" style={{ marginBottom: 8 }}>Recruiter notes</p>
                  <div style={{ padding: '12px 14px', background: 'var(--bg-elevated)', borderRadius: 8, borderLeft: '3px solid var(--blue-mid)' }}>
                    <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6, fontStyle: 'italic' }}>{selected.hr_notes}</p>
                  </div>
                </div>
              )}

              {selected.cover_letter && (
                <div>
                  <p className="label-caps" style={{ marginBottom: 8 }}>Your cover letter</p>
                  <div style={{ padding: '12px 14px', background: 'var(--bg-elevated)', borderRadius: 8, maxHeight: 160, overflowY: 'auto' }}>
                    <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.65, whiteSpace: 'pre-wrap' }}>{selected.cover_letter}</p>
                  </div>
                </div>
              )}
            </div>
            <div className="modal-footer">
              <button className="btn btn-ghost" onClick={() => setShowDetail(false)}>Close</button>
              {canWithdraw(selected.status) && (
                <button className="btn btn-danger" onClick={() => handleWithdraw(selected.id)} disabled={withdrawing === selected.id}>
                  {withdrawing === selected.id ? <Spinner size="sm" /> : <Trash2 size={13} />}
                  Withdraw application
                </button>
              )}
            </div>
          </>
        )}
      </Modal>
    </AppShell>
  )
}