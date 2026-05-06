'use client'
import { useEffect, useState } from 'react'
import { AppShell } from '@/components/layout/AppShell'
import { Badge, Modal, Spinner, EmptyState, toast, ToastContainer } from '@/components/ui'
import { admin } from '@/lib/api'
import { Building2, ShieldCheck, CheckCircle2, XCircle, ChevronRight, Globe, Users, LayoutDashboard } from 'lucide-react'

type AdminTab = 'overview' | 'companies' | 'hr'

interface Company {
  id: string; name: string; industry: string; city: string
  country: string; website?: string; status: string; created_at: string
}

interface HRProfile {
  id: string; job_title: string; status: string; created_at: string
  user?: { full_name: string; email: string }
  company?: { name: string }
}

interface DashboardStats {
  total_users?: number; total_companies?: number
  total_jobs?: number; total_applications?: number
  pending_companies?: number; pending_hr?: number
}

export default function AdminPage() {
  const [tab, setTab]               = useState<AdminTab>('overview')
  const [stats, setStats]           = useState<DashboardStats | null>(null)
  const [companies, setCompanies]   = useState<Company[]>([])
  const [hrProfiles, setHRProfiles] = useState<HRProfile[]>([])
  const [loading, setLoading]       = useState(true)
  const [actionId, setActionId]     = useState<string | null>(null)
  const [showReject, setShowReject] = useState(false)
  const [rejectTarget, setRejectTarget] = useState<{ id: string; type: 'company' | 'hr' } | null>(null)
  const [rejectReason, setRejectReason] = useState('')
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => { loadAll() }, [])

  async function loadAll() {
    setLoading(true)
    try {
      const [s, c, h] = await Promise.allSettled([admin.dashboard(), admin.getCompanies(), admin.getHRProfiles()])
      if (s.status === 'fulfilled') setStats(s.value as DashboardStats)
      if (c.status === 'fulfilled') setCompanies(Array.isArray(c.value) ? c.value as Company[] : [])
      if (h.status === 'fulfilled') setHRProfiles(Array.isArray(h.value) ? h.value as HRProfile[] : [])
    } finally { setLoading(false) }
  }

  async function handleApproveCompany(id: string) {
    setActionId(id)
    try {
      await admin.approveCompany(id)
      toast('Company approved', 'success')
      await loadAll()
    } catch (e: any) {
      toast(e.message || 'Failed to approve', 'error')
    } finally { setActionId(null) }
  }

  async function handleApproveHR(id: string) {
    setActionId(id)
    try {
      await admin.approveHR(id)
      toast('HR account approved', 'success')
      await loadAll()
    } catch (e: any) {
      toast(e.message || 'Failed to approve', 'error')
    } finally { setActionId(null) }
  }

  async function handleReject() {
    if (!rejectTarget || !rejectReason.trim()) { toast('Please provide a rejection reason', 'error'); return }
    setSubmitting(true)
    try {
      if (rejectTarget.type === 'company') await admin.rejectCompany(rejectTarget.id, rejectReason)
      else await admin.rejectHR(rejectTarget.id, rejectReason)
      toast('Rejected successfully', 'info')
      setShowReject(false)
      setRejectReason('')
      setRejectTarget(null)
      await loadAll()
    } catch (e: any) {
      toast(e.message || 'Failed to reject', 'error')
    } finally { setSubmitting(false) }
  }

  function openReject(id: string, type: 'company' | 'hr') {
    setRejectTarget({ id, type })
    setRejectReason('')
    setShowReject(true)
  }

  function formatDate(iso: string) {
    return new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
  }

  const pendingCompanies = companies.filter(c => c.status === 'pending')
  const pendingHR        = hrProfiles.filter(h => h.status === 'pending')

  return (
    <AppShell title="Admin Panel" subtitle="Manage companies, HR accounts and platform overview">
      <ToastContainer />

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 24, borderBottom: '1px solid var(--border-subtle)' }}>
        {([
          { key: 'overview',  label: 'Overview',  icon: <LayoutDashboard size={14} /> },
          { key: 'companies', label: `Companies${pendingCompanies.length > 0 ? ` (${pendingCompanies.length} pending)` : ''}`, icon: <Building2 size={14} /> },
          { key: 'hr',        label: `HR Accounts${pendingHR.length > 0 ? ` (${pendingHR.length} pending)` : ''}`, icon: <ShieldCheck size={14} /> },
        ] as { key: AdminTab; label: string; icon: React.ReactNode }[]).map(t => (
          <button key={t.key} onClick={() => setTab(t.key)}
            style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '8px 16px', fontSize: 13, fontWeight: 500, color: tab === t.key ? 'var(--text-primary)' : 'var(--text-muted)', borderBottom: `2px solid ${tab === t.key ? 'var(--blue-core)' : 'transparent'}`, marginBottom: -1, transition: 'all 0.15s', display: 'flex', alignItems: 'center', gap: 6 }}>
            {t.icon} {t.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: 60 }}><Spinner size="lg" /></div>
      ) : (
        <>
          {/* Overview */}
          {tab === 'overview' && (
            <div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 12, marginBottom: 24 }}>
                {[
                  { label: 'Total Users',        value: stats?.total_users        ?? '—', color: 'var(--blue-bright)' },
                  { label: 'Total Companies',    value: stats?.total_companies    ?? '—', color: 'var(--text-primary)' },
                  { label: 'Total Jobs',         value: stats?.total_jobs         ?? '—', color: 'var(--cyan-bright)' },
                  { label: 'Total Applications', value: stats?.total_applications ?? '—', color: 'var(--text-primary)' },
                  { label: 'Pending Companies',  value: pendingCompanies.length,          color: 'var(--yellow)' },
                  { label: 'Pending HR',         value: pendingHR.length,                 color: 'var(--yellow)' },
                ].map(s => (
                  <div key={s.label} style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-default)', borderRadius: 10, padding: 16, textAlign: 'center' }}>
                    <div style={{ fontFamily: 'DM Mono, monospace', fontSize: 26, fontWeight: 500, color: s.color, lineHeight: 1 }}>{s.value}</div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 6 }}>{s.label}</div>
                  </div>
                ))}
              </div>

              {(pendingCompanies.length > 0 || pendingHR.length > 0) ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                  {pendingCompanies.length > 0 && (
                    <div style={{ background: 'rgba(245,158,11,0.07)', border: '1px solid rgba(245,158,11,0.2)', borderRadius: 10, padding: '13px 18px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <Building2 size={15} style={{ color: 'var(--yellow)' }} />
                        <span style={{ fontSize: 13, color: 'var(--text-primary)' }}>
                          <strong>{pendingCompanies.length}</strong> company registration{pendingCompanies.length > 1 ? 's' : ''} awaiting approval
                        </span>
                      </div>
                      <button className="btn btn-ghost btn-sm" onClick={() => setTab('companies')}>
                        Review <ChevronRight size={13} />
                      </button>
                    </div>
                  )}
                  {pendingHR.length > 0 && (
                    <div style={{ background: 'rgba(245,158,11,0.07)', border: '1px solid rgba(245,158,11,0.2)', borderRadius: 10, padding: '13px 18px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <ShieldCheck size={15} style={{ color: 'var(--yellow)' }} />
                        <span style={{ fontSize: 13, color: 'var(--text-primary)' }}>
                          <strong>{pendingHR.length}</strong> HR account{pendingHR.length > 1 ? 's' : ''} awaiting approval
                        </span>
                      </div>
                      <button className="btn btn-ghost btn-sm" onClick={() => setTab('hr')}>
                        Review <ChevronRight size={13} />
                      </button>
                    </div>
                  )}
                </div>
              ) : (
                <div style={{ textAlign: 'center', padding: '40px 24px' }}>
                  <CheckCircle2 size={32} style={{ color: 'var(--green)', margin: '0 auto 12px' }} />
                  <p style={{ fontSize: 14, color: 'var(--text-muted)' }}>No pending approvals — everything is up to date.</p>
                </div>
              )}
            </div>
          )}

          {/* Companies */}
          {tab === 'companies' && (
            companies.length === 0 ? (
              <EmptyState icon={<Building2 size={28} />} title="No companies registered"
                description="Companies will appear here once they register on the platform." />
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {companies.map(company => (
                  <div key={company.id} className="card" style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
                    <div style={{ width: 42, height: 42, borderRadius: 10, background: 'var(--bg-elevated)', border: '1px solid var(--border-default)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                      <Building2 size={18} style={{ color: 'var(--text-muted)' }} />
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10 }}>
                        <div>
                          <h3 style={{ fontFamily: 'Outfit, sans-serif', fontSize: 14, fontWeight: 600, marginBottom: 3 }}>{company.name}</h3>
                          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
                            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{company.industry}</span>
                            <span style={{ fontSize: 12, color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 3 }}>
                              <Globe size={10} /> {company.city}, {company.country}
                            </span>
                            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Registered {formatDate(company.created_at)}</span>
                          </div>
                        </div>
                        <Badge label={company.status} />
                      </div>
                    </div>
                    {company.status === 'pending' && (
                      <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
                        <button className="btn btn-primary btn-sm" onClick={() => handleApproveCompany(company.id)} disabled={actionId === company.id}>
                          {actionId === company.id ? <Spinner size="sm" /> : <CheckCircle2 size={13} />} Approve
                        </button>
                        <button className="btn btn-danger btn-sm" onClick={() => openReject(company.id, 'company')}>
                          <XCircle size={13} /> Reject
                        </button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )
          )}

          {/* HR Accounts */}
          {tab === 'hr' && (
            hrProfiles.length === 0 ? (
              <EmptyState icon={<Users size={28} />} title="No HR accounts registered"
                description="HR accounts will appear here once recruiters register on the platform." />
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {hrProfiles.map(hrp => (
                  <div key={hrp.id} className="card" style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
                    <div style={{ width: 40, height: 40, borderRadius: '50%', background: 'var(--blue-dim)', color: 'var(--blue-bright)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 14, fontWeight: 600, flexShrink: 0 }}>
                      {hrp.user?.full_name?.charAt(0) || 'H'}
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10 }}>
                        <div>
                          <h3 style={{ fontFamily: 'Outfit, sans-serif', fontSize: 14, fontWeight: 600, marginBottom: 3 }}>{hrp.user?.full_name || 'HR User'}</h3>
                          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
                            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{hrp.user?.email}</span>
                            <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{hrp.job_title}</span>
                            {hrp.company && (
                              <span style={{ fontSize: 12, color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 3 }}>
                                <Building2 size={10} /> {hrp.company.name}
                              </span>
                            )}
                          </div>
                        </div>
                        <Badge label={hrp.status} />
                      </div>
                    </div>
                    {hrp.status === 'pending' && (
                      <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
                        <button className="btn btn-primary btn-sm" onClick={() => handleApproveHR(hrp.id)} disabled={actionId === hrp.id}>
                          {actionId === hrp.id ? <Spinner size="sm" /> : <CheckCircle2 size={13} />} Approve
                        </button>
                        <button className="btn btn-danger btn-sm" onClick={() => openReject(hrp.id, 'hr')}>
                          <XCircle size={13} /> Reject
                        </button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )
          )}
        </>
      )}

      {/* Reject Modal */}
      <Modal open={showReject} onClose={() => { if (!submitting) setShowReject(false) }}
        title={`Reject ${rejectTarget?.type === 'company' ? 'Company' : 'HR Account'}`} maxWidth={440}>
        <div className="modal-body">
          <div style={{ padding: '10px 14px', background: 'var(--red-dim)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: 8, marginBottom: 16 }}>
            <p style={{ fontSize: 12, color: 'var(--red)', lineHeight: 1.6 }}>
              The applicant will be notified by email with the reason you provide below.
            </p>
          </div>
          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="label">Rejection reason</label>
            <textarea className="input" rows={3}
              placeholder="e.g. Incomplete information provided, please resubmit with full company details."
              value={rejectReason} onChange={e => setRejectReason(e.target.value)} autoFocus />
          </div>
        </div>
        <div className="modal-footer">
          <button className="btn btn-ghost" onClick={() => setShowReject(false)} disabled={submitting}>Cancel</button>
          <button className="btn btn-danger" onClick={handleReject} disabled={submitting || !rejectReason.trim()}>
            {submitting ? <Spinner size="sm" /> : <XCircle size={14} />}
            {submitting ? 'Rejecting...' : 'Confirm rejection'}
          </button>
        </div>
      </Modal>
    </AppShell>
  )
}