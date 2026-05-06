'use client'
import { useEffect, useState } from 'react'
import { AppShell } from '@/components/layout/AppShell'
import { Badge, Modal, Spinner, EmptyState, toast, ToastContainer } from '@/components/ui'
import { hr, type Job, type Application } from '@/lib/api'
import { Plus, Briefcase, Users, CheckCircle2, MapPin, Calendar, ChevronRight, X } from 'lucide-react'

const EMPLOYMENT_TYPES = ['full-time', 'part-time', 'contract', 'internship']
const APP_STATUSES     = ['pending', 'reviewed', 'shortlisted', 'rejected', 'accepted']

type HRTab = 'jobs' | 'applications'

export default function HRPage() {
  const [tab, setTab]             = useState<HRTab>('jobs')
  const [jobs, setJobs]           = useState<Job[]>([])
  const [apps, setApps]           = useState<Application[]>([])
  const [loading, setLoading]     = useState(true)
  const [showJobModal, setShowJobModal] = useState(false)
  const [showAppModal, setShowAppModal] = useState(false)
  const [selectedApp, setSelectedApp]   = useState<Application | null>(null)
  const [saving, setSaving]       = useState(false)
  const [statusNote, setStatusNote] = useState('')
  const [newStatus, setNewStatus]   = useState('')
  const [form, setForm] = useState({
    title: '', location: '', description: '',
    requirements: '', salary_range: '', employment_type: 'full-time',
  })

  useEffect(() => { loadAll() }, [])

  async function loadAll() {
    setLoading(true)
    try {
      const [j, a] = await Promise.allSettled([hr.getJobs(), hr.getApplications()])
      if (j.status === 'fulfilled') setJobs(Array.isArray(j.value) ? j.value : [])
      if (a.status === 'fulfilled') setApps(Array.isArray(a.value) ? a.value : [])
    } finally { setLoading(false) }
  }

  async function handlePostJob() {
    if (!form.title || !form.description || !form.location) {
      toast('Please fill in title, location and description', 'error'); return
    }
    setSaving(true)
    try {
      await hr.postJob({ ...form, status: 'published' })
      toast('Job posted successfully', 'success')
      setShowJobModal(false)
      resetForm()
      await loadAll()
    } catch (e: any) {
      toast(e.message || 'Failed to post job', 'error')
    } finally { setSaving(false) }
  }

  async function handleCloseJob(id: string) {
    try {
      await hr.closeJob(id)
      toast('Job closed', 'info')
      await loadAll()
    } catch (e: any) { toast(e.message || 'Failed to close job', 'error') }
  }

  async function handleUpdateStatus() {
    if (!selectedApp || !newStatus) return
    setSaving(true)
    try {
      await hr.updateApplicationStatus(selectedApp.id, newStatus, statusNote)
      toast(`Application marked as ${newStatus}`, 'success')
      setShowAppModal(false)
      setSelectedApp(null)
      setStatusNote('')
      setNewStatus('')
      await loadAll()
    } catch (e: any) {
      toast(e.message || 'Failed to update status', 'error')
    } finally { setSaving(false) }
  }

  function openApp(app: Application) {
    setSelectedApp(app)
    setNewStatus(app.status)
    setStatusNote('')
    setShowAppModal(true)
  }

  function resetForm() {
    setForm({ title: '', location: '', description: '', requirements: '', salary_range: '', employment_type: 'full-time' })
  }

  function update(k: string, v: string) { setForm(p => ({ ...p, [k]: v })) }

  function formatDate(iso: string) {
    return new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
  }

  const pending     = apps.filter(a => a.status === 'pending').length
  const shortlisted = apps.filter(a => a.status === 'shortlisted').length
  const activeJobs  = jobs.filter(j => j.is_active).length

  return (
    <AppShell
      title="HR Dashboard"
      subtitle="Manage your job listings and applications"
      actions={
        tab === 'jobs' ? (
          <button className="btn btn-primary" onClick={() => setShowJobModal(true)}>
            <Plus size={14} /> Post a job
          </button>
        ) : undefined
      }
    >
      <ToastContainer />

      {/* Stats */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 12, marginBottom: 24 }}>
        {[
          { label: 'Active Jobs',  value: activeJobs,  color: 'var(--blue-bright)' },
          { label: 'Total Apps',   value: apps.length, color: 'var(--text-primary)' },
          { label: 'Pending',      value: pending,     color: 'var(--yellow)' },
          { label: 'Shortlisted',  value: shortlisted, color: 'var(--green)' },
        ].map(s => (
          <div key={s.label} style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-default)', borderRadius: 10, padding: '14px 16px', textAlign: 'center' }}>
            <div style={{ fontFamily: 'DM Mono, monospace', fontSize: 24, fontWeight: 500, color: s.color, lineHeight: 1 }}>{s.value}</div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 5 }}>{s.label}</div>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 20, borderBottom: '1px solid var(--border-subtle)' }}>
        {(['jobs', 'applications'] as HRTab[]).map(t => (
          <button key={t} onClick={() => setTab(t)}
            style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '8px 16px', fontSize: 14, fontWeight: 500, color: tab === t ? 'var(--text-primary)' : 'var(--text-muted)', borderBottom: `2px solid ${tab === t ? 'var(--blue-core)' : 'transparent'}`, marginBottom: -1, transition: 'all 0.15s', textTransform: 'capitalize' }}>
            {t === 'jobs' ? `Jobs (${jobs.length})` : `Applications (${apps.length})`}
          </button>
        ))}
      </div>

      {loading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: 60 }}><Spinner size="lg" /></div>
      ) : tab === 'jobs' ? (
        jobs.length === 0 ? (
          <EmptyState icon={<Briefcase size={28} />} title="No jobs posted yet"
            description="Post your first job listing to start receiving applications."
            action={<button className="btn btn-primary" onClick={() => setShowJobModal(true)}><Plus size={14} /> Post a job</button>} />
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {jobs.map(job => (
              <div key={job.id} className="card" style={{ display: 'flex', alignItems: 'flex-start', gap: 14 }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 10, marginBottom: 6 }}>
                    <div>
                      <h3 style={{ fontFamily: 'Outfit, sans-serif', fontSize: 15, fontWeight: 600, marginBottom: 3 }}>{job.title}</h3>
                      <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
                        <span style={{ fontSize: 12, color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 4 }}><MapPin size={11} /> {job.location}</span>
                        <span style={{ fontSize: 12, color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 4 }}><Calendar size={11} /> {formatDate(job.created_at)}</span>
                      </div>
                    </div>
                    <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexShrink: 0 }}>
                      <Badge label={job.employment_type} />
                      <Badge label={job.is_active ? 'active' : 'closed'} variant={job.is_active ? 'green' : 'gray'} />
                    </div>
                  </div>
                  <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.55, marginBottom: 12, overflow: 'hidden', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' }}>
                    {job.description}
                  </p>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <button className="btn btn-ghost btn-sm" onClick={() => setTab('applications')}>
                      <Users size={13} /> View applications
                    </button>
                    {job.is_active && (
                      <button className="btn btn-danger btn-sm" onClick={() => handleCloseJob(job.id)}>
                        <X size={13} /> Close job
                      </button>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )
      ) : (
        apps.length === 0 ? (
          <EmptyState icon={<Users size={28} />} title="No applications yet"
            description="Applications will appear here once graduates apply to your jobs." />
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {apps.map(app => (
              <div key={app.id} className="card card-interactive" onClick={() => openApp(app)}
                style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
                <div style={{ width: 38, height: 38, borderRadius: '50%', flexShrink: 0, background: 'var(--blue-dim)', color: 'var(--blue-bright)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13, fontWeight: 600 }}>
                  {(app as any).applicant_name?.charAt(0) || 'G'}
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10 }}>
                    <div>
                      <p style={{ fontSize: 13, fontWeight: 500, marginBottom: 2 }}>{(app as any).applicant_name || 'Graduate Applicant'}</p>
                      <p style={{ fontSize: 12, color: 'var(--text-muted)' }}>Applied for: <span style={{ color: 'var(--text-secondary)' }}>{app.job?.title}</span></p>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
                      <Badge label={app.status} />
                      <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{formatDate(app.created_at)}</span>
                      <ChevronRight size={14} style={{ color: 'var(--text-muted)' }} />
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )
      )}

      {/* Post Job Modal */}
      <Modal open={showJobModal} onClose={() => { if (!saving) { setShowJobModal(false); resetForm() } }} title="Post a New Job" maxWidth={560}>
        <div className="modal-body">
          <div className="form-group">
            <label className="label">Job title</label>
            <input className="input" placeholder="e.g. Backend Python Developer"
              value={form.title} onChange={e => update('title', e.target.value)} />
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <div className="form-group">
              <label className="label">Location</label>
              <input className="input" placeholder="e.g. Douala, Cameroon"
                value={form.location} onChange={e => update('location', e.target.value)} />
            </div>
            <div className="form-group">
              <label className="label">Employment type</label>
              <select className="input" value={form.employment_type} onChange={e => update('employment_type', e.target.value)}>
                {EMPLOYMENT_TYPES.map(t => <option key={t} value={t} style={{ textTransform: 'capitalize' }}>{t}</option>)}
              </select>
            </div>
          </div>
          <div className="form-group">
            <label className="label">Salary range <span style={{ color: 'var(--text-muted)', fontWeight: 400 }}>(optional)</span></label>
            <input className="input" placeholder="e.g. 500,000 - 800,000 FCFA/month"
              value={form.salary_range} onChange={e => update('salary_range', e.target.value)} />
          </div>
          <div className="form-group">
            <label className="label">Job description</label>
            <textarea className="input" rows={4} placeholder="Describe the role, responsibilities, and company..."
              value={form.description} onChange={e => update('description', e.target.value)} />
          </div>
          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="label">Requirements</label>
            <textarea className="input" rows={3} placeholder="List the skills and experience required..."
              value={form.requirements} onChange={e => update('requirements', e.target.value)} />
          </div>
        </div>
        <div className="modal-footer">
          <button className="btn btn-ghost" onClick={() => { setShowJobModal(false); resetForm() }} disabled={saving}>Cancel</button>
          <button className="btn btn-primary" onClick={handlePostJob} disabled={saving}>
            {saving ? <Spinner size="sm" /> : <CheckCircle2 size={14} />}
            {saving ? 'Posting...' : 'Post job'}
          </button>
        </div>
      </Modal>

      {/* Application Detail Modal */}
      <Modal open={showAppModal} onClose={() => { if (!saving) setShowAppModal(false) }} title="Review Application" maxWidth={500}>
        {selectedApp && (
          <>
            <div className="modal-body">
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '12px 14px', background: 'var(--bg-elevated)', borderRadius: 10, marginBottom: 20 }}>
                <div style={{ width: 40, height: 40, borderRadius: '50%', background: 'var(--blue-dim)', color: 'var(--blue-bright)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 14, fontWeight: 600, flexShrink: 0 }}>
                  {(selectedApp as any).applicant_name?.charAt(0) || 'G'}
                </div>
                <div>
                  <p style={{ fontSize: 14, fontWeight: 600 }}>{(selectedApp as any).applicant_name || 'Graduate Applicant'}</p>
                  <p style={{ fontSize: 12, color: 'var(--text-muted)' }}>Applied for: {selectedApp.job?.title} · {formatDate(selectedApp.created_at)}</p>
                </div>
              </div>
              {selectedApp.cover_letter && (
                <div style={{ marginBottom: 20 }}>
                  <p className="label-caps" style={{ marginBottom: 8 }}>Cover letter</p>
                  <div style={{ padding: '12px 14px', background: 'var(--bg-elevated)', borderRadius: 8, maxHeight: 140, overflowY: 'auto' }}>
                    <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.65, whiteSpace: 'pre-wrap' }}>{selectedApp.cover_letter}</p>
                  </div>
                </div>
              )}
              <div className="form-group">
                <label className="label">Update status</label>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8 }}>
                  {APP_STATUSES.map(s => (
                    <button key={s} type="button" onClick={() => setNewStatus(s)}
                      style={{ padding: '8px 4px', borderRadius: 7, fontSize: 11, fontWeight: 600, textTransform: 'capitalize', cursor: 'pointer', transition: 'all 0.15s', border: `1px solid ${newStatus === s ? 'var(--blue-mid)' : 'var(--border-default)'}`, background: newStatus === s ? 'rgba(37,99,235,0.12)' : 'var(--bg-elevated)', color: newStatus === s ? 'var(--blue-bright)' : 'var(--text-secondary)' }}>
                      {s}
                    </button>
                  ))}
                </div>
              </div>
              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="label">Notes for applicant <span style={{ color: 'var(--text-muted)', fontWeight: 400 }}>(optional)</span></label>
                <textarea className="input" rows={3} placeholder="e.g. Strong candidate, scheduling a technical interview..."
                  value={statusNote} onChange={e => setStatusNote(e.target.value)} />
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-ghost" onClick={() => setShowAppModal(false)} disabled={saving}>Cancel</button>
              <button className="btn btn-primary" onClick={handleUpdateStatus} disabled={saving || !newStatus}>
                {saving ? <Spinner size="sm" /> : <CheckCircle2 size={14} />}
                {saving ? 'Saving...' : 'Update status'}
              </button>
            </div>
          </>
        )}
      </Modal>
    </AppShell>
  )
}