'use client'
import { useEffect, useState } from 'react'
import { AppShell } from '@/components/layout/AppShell'
import { Modal, Spinner, EmptyState, toast, ToastContainer } from '@/components/ui'
import { cv, jobs, type GeneratedCV, type Job } from '@/lib/api'
import { FileText, Download, Plus, Wand2, Calendar, CheckCircle2, AlertCircle } from 'lucide-react'

type Format = 'pdf' | 'docx'

export default function CVPage() {
  const [cvList, setCVList]           = useState<GeneratedCV[]>([])
  const [jobList, setJobList]         = useState<Job[]>([])
  const [loading, setLoading]         = useState(true)
  const [generating, setGenerating]   = useState(false)
  const [downloading, setDownloading] = useState<string | null>(null)
  const [showModal, setShowModal]     = useState(false)
  const [selectedJob, setSelectedJob] = useState('')
  const [format, setFormat]           = useState<Format>('pdf')
  const [missingQ, setMissingQ]       = useState<string[]>([])
  const [answers, setAnswers]         = useState<Record<string, string>>({})
  const [step, setStep]               = useState<'config' | 'questions'>('config')

  useEffect(() => { loadAll() }, [])

  async function loadAll() {
    setLoading(true)
    try {
      const [cvs, jbs] = await Promise.allSettled([cv.list(), jobs.list({ page_size: 50 })])
      if (cvs.status === 'fulfilled') setCVList(Array.isArray(cvs.value) ? cvs.value : [])
      if (jbs.status === 'fulfilled') setJobList(jbs.value.jobs ?? [])
    } finally { setLoading(false) }
  }

  async function handleGenerate() {
    if (!selectedJob) { toast('Please select a job first', 'error'); return }
    setGenerating(true)
    try {
      const res: any = await cv.generate(selectedJob, format)
      if (res.missing_info_questions?.length > 0) {
        setMissingQ(res.missing_info_questions)
        setStep('questions')
      } else {
        toast('CV generated successfully', 'success')
        setShowModal(false)
        setStep('config')
        await loadAll()
      }
    } catch (e: any) {
      toast(e.message || 'Failed to generate CV', 'error')
    } finally { setGenerating(false) }
  }

  async function handleGenerateWithAnswers() {
    if (!selectedJob) return
    setGenerating(true)
    try {
      await cv.generateWithAnswers({ job_id: selectedJob, file_format: format, answers })
      toast('CV generated successfully', 'success')
      setShowModal(false)
      setStep('config')
      setAnswers({})
      setMissingQ([])
      await loadAll()
    } catch (e: any) {
      toast(e.message || 'Failed to generate CV', 'error')
    } finally { setGenerating(false) }
  }

  async function handleDownload(item: GeneratedCV) {
    setDownloading(item.cv_id)
    try {
      await cv.download(item.cv_id, item.file_name)
      toast('Download started', 'success')
    } catch (e: any) {
      toast(e.message || 'Download failed', 'error')
    } finally { setDownloading(null) }
  }

  function openModal() {
    setSelectedJob('')
    setFormat('pdf')
    setStep('config')
    setMissingQ([])
    setAnswers({})
    setShowModal(true)
  }

  function formatDate(iso: string) {
    return new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
  }

  const selectedJobObj = jobList.find(j => j.id === selectedJob)

  return (
    <AppShell
      title="CV Generator"
      subtitle="Generate tailored CVs powered by Gemini AI"
      actions={
        <button className="btn btn-primary" onClick={openModal}>
          <Plus size={14} /> Generate CV
        </button>
      }
    >
      <ToastContainer />

      {/* Info banner */}
      <div style={{ background: 'rgba(6,182,212,0.06)', border: '1px solid rgba(6,182,212,0.15)', borderRadius: 10, padding: '13px 18px', marginBottom: 24, display: 'flex', alignItems: 'flex-start', gap: 12 }}>
        <Wand2 size={16} style={{ color: 'var(--cyan-bright)', flexShrink: 0, marginTop: 1 }} />
        <div>
          <p style={{ fontSize: 13, color: 'var(--text-primary)', fontWeight: 500, marginBottom: 2 }}>AI-tailored CVs for every job</p>
          <p style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
            Select a target job and Gemini AI will generate a CV that highlights your most relevant skills and experience for that specific role.
          </p>
        </div>
      </div>

      {loading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: 60 }}><Spinner size="lg" /></div>
      ) : cvList.length === 0 ? (
        <EmptyState icon={<FileText size={32} />} title="No CVs generated yet"
          description="Generate your first tailored CV by clicking the button above."
          action={<button className="btn btn-primary" onClick={openModal}><Plus size={14} /> Generate your first CV</button>}
        />
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 14 }}>
          {cvList.map(item => (
            <div key={item.cv_id} className="card card-interactive">
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: 14, marginBottom: 14 }}>
                <div style={{ width: 44, height: 52, borderRadius: 8, flexShrink: 0, background: item.file_format === 'pdf' ? 'rgba(239,68,68,0.12)' : 'rgba(37,99,235,0.12)', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 2 }}>
                  <FileText size={18} style={{ color: item.file_format === 'pdf' ? 'var(--red)' : 'var(--blue-bright)' }} />
                  <span style={{ fontSize: 9, fontWeight: 700, color: item.file_format === 'pdf' ? 'var(--red)' : 'var(--blue-bright)', letterSpacing: '0.05em' }}>
                    {item.file_format.toUpperCase()}
                  </span>
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <h3 style={{ fontSize: 13, fontWeight: 600, marginBottom: 4, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{item.file_name}</h3>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, color: 'var(--text-muted)' }}>
                    <Calendar size={10} /> {formatDate(item.generated_at)}
                  </div>
                </div>
                <CheckCircle2 size={16} style={{ color: 'var(--green)', flexShrink: 0 }} />
              </div>
              <button className="btn btn-primary btn-sm" style={{ width: '100%' }}
                onClick={() => handleDownload(item)} disabled={downloading === item.cv_id}>
                {downloading === item.cv_id ? <Spinner size="sm" /> : <Download size={13} />}
                {downloading === item.cv_id ? 'Downloading...' : 'Download'}
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Generate CV Modal */}
      <Modal open={showModal} onClose={() => { if (!generating) setShowModal(false) }}
        title={step === 'questions' ? 'Additional Information' : 'Generate Tailored CV'} maxWidth={520}>
        {step === 'config' && (
          <>
            <div className="modal-body">
              <div className="form-group">
                <label className="label">Target job</label>
                <select className="input" value={selectedJob} onChange={e => setSelectedJob(e.target.value)}>
                  <option value="">Select a job...</option>
                  {jobList.map(j => <option key={j.id} value={j.id}>{j.title} — {j.company}</option>)}
                </select>
                {selectedJobObj && (
                  <div style={{ marginTop: 8, padding: '8px 12px', background: 'var(--bg-elevated)', borderRadius: 7 }}>
                    <p style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                      {selectedJobObj.location} · <span style={{ textTransform: 'capitalize' }}>{selectedJobObj.employment_type}</span>
                    </p>
                  </div>
                )}
              </div>
              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="label">Output format</label>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                  {(['pdf', 'docx'] as Format[]).map(f => (
                    <button key={f} type="button" onClick={() => setFormat(f)}
                      style={{ padding: 14, borderRadius: 8, cursor: 'pointer', textAlign: 'center', border: `1px solid ${format === f ? (f === 'pdf' ? 'var(--red)' : 'var(--blue-mid)') : 'var(--border-default)'}`, background: format === f ? (f === 'pdf' ? 'rgba(239,68,68,0.08)' : 'rgba(37,99,235,0.08)') : 'var(--bg-elevated)', transition: 'all 0.15s' }}>
                      <FileText size={22} style={{ margin: '0 auto 4px', color: format === f ? (f === 'pdf' ? 'var(--red)' : 'var(--blue-bright)') : 'var(--text-muted)' }} />
                      <div style={{ fontSize: 13, fontWeight: 600, textTransform: 'uppercase', color: format === f ? (f === 'pdf' ? 'var(--red)' : 'var(--blue-bright)') : 'var(--text-secondary)' }}>{f}</div>
                      <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>{f === 'pdf' ? 'Best for sharing' : 'Best for editing'}</div>
                    </button>
                  ))}
                </div>
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-ghost" onClick={() => setShowModal(false)} disabled={generating}>Cancel</button>
              <button className="btn btn-primary" onClick={handleGenerate} disabled={generating || !selectedJob}>
                {generating ? <Spinner size="sm" /> : <Wand2 size={14} />}
                {generating ? 'Generating...' : 'Generate CV'}
              </button>
            </div>
          </>
        )}
        {step === 'questions' && (
          <>
            <div className="modal-body">
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10, padding: '10px 14px', background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.2)', borderRadius: 8, marginBottom: 20 }}>
                <AlertCircle size={15} style={{ color: 'var(--yellow)', flexShrink: 0, marginTop: 1 }} />
                <p style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                  The AI needs a bit more information to complete your CV. Please answer the questions below.
                </p>
              </div>
              {missingQ.map((q, i) => (
                <div key={i} className="form-group">
                  <label className="label">{q}</label>
                  <textarea className="input" rows={3} placeholder="Your answer..."
                    value={answers[q] || ''} onChange={e => setAnswers(p => ({ ...p, [q]: e.target.value }))} />
                </div>
              ))}
            </div>
            <div className="modal-footer">
              <button className="btn btn-ghost" onClick={() => setStep('config')} disabled={generating}>Back</button>
              <button className="btn btn-primary" onClick={handleGenerateWithAnswers} disabled={generating}>
                {generating ? <Spinner size="sm" /> : <Wand2 size={14} />}
                {generating ? 'Generating...' : 'Generate CV'}
              </button>
            </div>
          </>
        )}
      </Modal>
    </AppShell>
  )
}