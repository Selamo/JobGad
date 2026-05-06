'use client'
import { useEffect, useState } from 'react'
import { AppShell } from '@/components/layout/AppShell'
import { ProgressBar, Modal, Spinner, EmptyState, toast, ToastContainer } from '@/components/ui'
import { profile, type Profile, type Skill, type Document, type SkillGap } from '@/lib/api'
import { Plus, Trash2, Upload, RefreshCw, Link as LinkIcon, Globe, CheckCircle2, ChevronDown, ChevronUp, X } from 'lucide-react'

const PROFICIENCY = ['beginner', 'intermediate', 'advanced', 'expert']
const CATEGORIES  = ['technical', 'soft', 'tool', 'domain']
const EDU_LEVELS  = ['BSc', 'MSc', 'PhD', 'HND', 'BEng', 'MEng', 'Diploma', 'Other']

export default function ProfilePage() {
  const [prof, setProf]           = useState<Profile | null>(null)
  const [completeness, setComp]   = useState(0)
  const [skills, setSkills]       = useState<Skill[]>([])
  const [docs, setDocs]           = useState<Document[]>([])
  const [skillGap, setSkillGap]   = useState<SkillGap | null>(null)
  const [loading, setLoading]     = useState(true)
  const [saving, setSaving]       = useState(false)
  const [analyzing, setAnalyzing] = useState(false)
  const [uploadingCV, setUploadingCV] = useState(false)
  const [showSkillModal, setShowSkillModal] = useState(false)
  const [showGapModal, setShowGapModal]     = useState(false)
  const [expandSocials, setExpandSocials]   = useState(false)
  const [newSkill, setNewSkill]   = useState({ name: '', category: 'technical', proficiency: 'intermediate' })
  const [form, setForm]           = useState<Partial<Profile>>({})

  useEffect(() => { loadAll() }, [])

  async function loadAll() {
    setLoading(true)
    try {
      const [p, c, s, d] = await Promise.allSettled([
        profile.get(),
        profile.completeness(),
        profile.getSkills(),
        profile.getDocuments(),
      ])
      if (p.status === 'fulfilled') { setProf(p.value); setForm(p.value) }
      if (c.status === 'fulfilled') setComp(c.value.profile_completeness)
      if (s.status === 'fulfilled') setSkills(s.value)
      if (d.status === 'fulfilled') setDocs(d.value)
    } finally {
      setLoading(false)
    }
  }

  async function handleSave() {
    setSaving(true)
    try {
      if (prof) await profile.update(form)
      else await profile.create(form)
      toast('Profile saved successfully', 'success')
      await loadAll()
    } catch (e: any) {
      toast(e.message || 'Failed to save profile', 'error')
    } finally {
      setSaving(false)
    }
  }

  async function handleAddSkill() {
    if (!newSkill.name.trim()) return
    try {
      await profile.addSkill(newSkill)
      toast('Skill added', 'success')
      setShowSkillModal(false)
      setNewSkill({ name: '', category: 'technical', proficiency: 'intermediate' })
      const s = await profile.getSkills()
      setSkills(s)
    } catch (e: any) {
      toast(e.message || 'Failed to add skill', 'error')
    }
  }

  async function handleDeleteSkill(id: string) {
    try {
      await profile.deleteSkill(id)
      setSkills(s => s.filter(x => x.id !== id))
      toast('Skill removed', 'info')
    } catch (e: any) {
      toast(e.message || 'Failed to remove skill', 'error')
    }
  }

  async function handleUploadCV(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    setUploadingCV(true)
    try {
      await profile.uploadDocument(file, 'cv')
      toast('CV uploaded — skills being extracted', 'success')
      const [d, s] = await Promise.all([profile.getDocuments(), profile.getSkills()])
      setDocs(d); setSkills(s)
      await loadAll()
    } catch (e: any) {
      toast(e.message || 'Upload failed', 'error')
    } finally {
      setUploadingCV(false)
      e.target.value = ''
    }
  }

  async function handleAnalyzeSocials() {
    setAnalyzing(true)
    try {
      const res: any = await profile.analyzeSocials()
      toast(`${res.total_new_skills_added} new skills added from your social profiles`, 'success')
      const s = await profile.getSkills()
      setSkills(s)
    } catch (e: any) {
      toast(e.message || 'Analysis failed', 'error')
    } finally {
      setAnalyzing(false)
    }
  }

  async function handleSkillGap() {
    try {
      const gap = await profile.skillGap()
      setSkillGap(gap)
      setShowGapModal(true)
    } catch (e: any) {
      toast(e.message || 'Could not load skill gap', 'error')
    }
  }

  const update = (k: string, v: string | number) => setForm(p => ({ ...p, [k]: v }))

  const profColors: Record<string, string> = {
    beginner: 'var(--yellow)', intermediate: 'var(--blue-core)',
    advanced: 'var(--cyan-core)', expert: 'var(--green)',
  }

  if (loading) {
    return (
      <AppShell title="Profile">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 300 }}>
          <Spinner size="lg" />
        </div>
      </AppShell>
    )
  }

  return (
    <AppShell
      title="Profile"
      subtitle="Manage your career profile and skills"
      actions={
        <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
          {saving ? <Spinner size="sm" /> : 'Save changes'}
        </button>
      }
    >
      <ToastContainer />

      {/* Completeness bar */}
      <div className="card" style={{ marginBottom: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
          <span style={{ fontSize: 13, fontWeight: 500 }}>Profile completeness</span>
          <span style={{ fontFamily: 'DM Mono, monospace', fontSize: 13, color: 'var(--blue-bright)' }}>
            {Math.round(completeness)}%
          </span>
        </div>
        <ProgressBar value={completeness} />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>

        {/* LEFT */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div className="card">
            <h3 style={{ fontFamily: 'Outfit, sans-serif', fontSize: 15, fontWeight: 600, marginBottom: 16 }}>Basic Information</h3>
            <div className="form-group">
              <label className="label">Headline</label>
              <input className="input" placeholder="e.g. Software Engineering Graduate"
                value={form.headline || ''} onChange={e => update('headline', e.target.value)} />
            </div>
            <div className="form-group">
              <label className="label">Bio</label>
              <textarea className="input" rows={3} placeholder="A short bio about yourself..."
                value={form.bio || ''} onChange={e => update('bio', e.target.value)} />
            </div>
            <div className="form-group" style={{ marginBottom: 0 }}>
              <label className="label">Target Role</label>
              <input className="input" placeholder="e.g. Backend Developer"
                value={form.target_role || ''} onChange={e => update('target_role', e.target.value)} />
            </div>
          </div>

          <div className="card">
            <h3 style={{ fontFamily: 'Outfit, sans-serif', fontSize: 15, fontWeight: 600, marginBottom: 16 }}>Education</h3>
            <div className="form-group">
              <label className="label">Education Level</label>
              <select className="input" value={form.education_level || ''} onChange={e => update('education_level', e.target.value)}>
                <option value="">Select level</option>
                {EDU_LEVELS.map(l => <option key={l} value={l}>{l}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label className="label">Field of Study</label>
              <input className="input" placeholder="e.g. Computer Engineering"
                value={form.field_of_study || ''} onChange={e => update('field_of_study', e.target.value)} />
            </div>
            <div className="form-group">
              <label className="label">Institution</label>
              <input className="input" placeholder="e.g. University of Bamenda"
                value={form.institution || ''} onChange={e => update('institution', e.target.value)} />
            </div>
            <div className="form-group" style={{ marginBottom: 0 }}>
              <label className="label">Graduation Year</label>
              <input className="input" type="number" placeholder="e.g. 2025" min={2000} max={2030}
                value={form.graduation_year || ''} onChange={e => update('graduation_year', Number(e.target.value))} />
            </div>
          </div>

          <div className="card">
            <button onClick={() => setExpandSocials(p => !p)}
              style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}>
              <h3 style={{ fontFamily: 'Outfit, sans-serif', fontSize: 15, fontWeight: 600 }}>Social Links</h3>
              {expandSocials ? <ChevronUp size={16} color="var(--text-muted)" /> : <ChevronDown size={16} color="var(--text-muted)" />}
            </button>
            {expandSocials && (
              <div style={{ marginTop: 16, display: 'flex', flexDirection: 'column', gap: 12 }}>
                {[
                  { key: 'github_url',    icon: <LinkIcon size={14} />, label: 'GitHub URL',    ph: 'https://github.com/username' },
                  { key: 'linkedin_url',  icon: <LinkIcon size={14} />, label: 'LinkedIn URL',  ph: 'https://linkedin.com/in/username' },
                  { key: 'portfolio_url', icon: <Globe size={14} />,    label: 'Portfolio URL', ph: 'https://yourportfolio.com' },
                ].map(f => (
                  <div key={f.key}>
                    <label className="label" style={{ display: 'flex', alignItems: 'center', gap: 5 }}>{f.icon} {f.label}</label>
                    <input className="input" placeholder={f.ph}
                      value={(form as any)[f.key] || ''} onChange={e => update(f.key, e.target.value)} />
                  </div>
                ))}
                <button className="btn btn-secondary btn-sm" onClick={handleAnalyzeSocials} disabled={analyzing} style={{ alignSelf: 'flex-start' }}>
                  {analyzing ? <Spinner size="sm" /> : <RefreshCw size={13} />}
                  {analyzing ? 'Analyzing...' : 'Extract skills from profiles'}
                </button>
              </div>
            )}
          </div>
        </div>

        {/* RIGHT */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div className="card">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
              <h3 style={{ fontFamily: 'Outfit, sans-serif', fontSize: 15, fontWeight: 600 }}>Documents</h3>
              <label className="btn btn-secondary btn-sm" style={{ cursor: 'pointer' }}>
                {uploadingCV ? <Spinner size="sm" /> : <Upload size={13} />}
                {uploadingCV ? 'Uploading...' : 'Upload CV'}
                <input type="file" accept=".pdf,.docx" onChange={handleUploadCV} style={{ display: 'none' }} disabled={uploadingCV} />
              </label>
            </div>
            {docs.length === 0 ? (
              <EmptyState title="No documents yet" description="Upload your CV to auto-extract skills." />
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {docs.map(doc => (
                  <div key={doc.id} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 12px', background: 'var(--bg-elevated)', borderRadius: 8 }}>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 13, fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{doc.file_name}</div>
                      <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2, textTransform: 'capitalize' }}>{doc.doc_type} · {doc.processing_status}</div>
                    </div>
                    {doc.processing_status === 'completed' && <CheckCircle2 size={14} style={{ color: 'var(--green)', flexShrink: 0 }} />}
                    <button onClick={() => profile.deleteDocument(doc.id).then(loadAll)}
                      style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', display: 'flex', padding: 4 }}>
                      <Trash2 size={13} />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="card">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
              <div>
                <h3 style={{ fontFamily: 'Outfit, sans-serif', fontSize: 15, fontWeight: 600 }}>Skills</h3>
                <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>{skills.length} total</p>
              </div>
              <button className="btn btn-primary btn-sm" onClick={() => setShowSkillModal(true)}>
                <Plus size={13} /> Add skill
              </button>
            </div>
            {skills.length === 0 ? (
              <EmptyState title="No skills yet" description="Add skills manually or upload your CV." />
            ) : (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                {skills.map(sk => (
                  <div key={sk.id} style={{ display: 'inline-flex', alignItems: 'center', gap: 7, background: 'var(--bg-elevated)', borderRadius: 6, padding: '5px 10px', border: '1px solid var(--border-default)' }}>
                    <span style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-primary)' }}>{sk.name}</span>
                    <span style={{ width: 6, height: 6, borderRadius: '50%', background: profColors[sk.proficiency] || 'var(--text-muted)', flexShrink: 0 }} />
                    <button onClick={() => handleDeleteSkill(sk.id)}
                      style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', display: 'flex', padding: 0, marginLeft: 2 }}>
                      <X size={11} />
                    </button>
                  </div>
                ))}
              </div>
            )}
            {skills.length > 0 && (
              <button className="btn btn-ghost btn-sm" style={{ marginTop: 14, width: '100%' }} onClick={handleSkillGap}>
                View skill gap analysis
              </button>
            )}
          </div>

          <div className="card" style={{ padding: '14px 16px' }}>
            <p className="label-caps" style={{ marginBottom: 10 }}>Skill proficiency legend</p>
            <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap' }}>
              {PROFICIENCY.map(p => (
                <div key={p} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ width: 7, height: 7, borderRadius: '50%', background: profColors[p], display: 'inline-block' }} />
                  <span style={{ fontSize: 12, color: 'var(--text-secondary)', textTransform: 'capitalize' }}>{p}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Add Skill Modal */}
      <Modal open={showSkillModal} onClose={() => setShowSkillModal(false)} title="Add a skill">
        <div className="modal-body">
          <div className="form-group">
            <label className="label">Skill name</label>
            <input className="input" placeholder="e.g. Python, Docker, Communication"
              value={newSkill.name} onChange={e => setNewSkill(p => ({ ...p, name: e.target.value }))}
              onKeyDown={e => e.key === 'Enter' && handleAddSkill()} autoFocus />
          </div>
          <div className="form-group">
            <label className="label">Category</label>
            <select className="input" value={newSkill.category} onChange={e => setNewSkill(p => ({ ...p, category: e.target.value }))}>
              {CATEGORIES.map(c => <option key={c} value={c} style={{ textTransform: 'capitalize' }}>{c}</option>)}
            </select>
          </div>
          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="label">Proficiency</label>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8 }}>
              {PROFICIENCY.map(p => (
                <button key={p} type="button" onClick={() => setNewSkill(prev => ({ ...prev, proficiency: p }))}
                  style={{ padding: '8px 4px', borderRadius: 7, border: `1px solid ${newSkill.proficiency === p ? profColors[p] : 'var(--border-default)'}`, background: newSkill.proficiency === p ? `${profColors[p]}18` : 'var(--bg-elevated)', color: newSkill.proficiency === p ? profColors[p] : 'var(--text-secondary)', fontSize: 11, fontWeight: 600, cursor: 'pointer', textTransform: 'capitalize', transition: 'all 0.15s' }}>
                  {p}
                </button>
              ))}
            </div>
          </div>
        </div>
        <div className="modal-footer">
          <button className="btn btn-ghost" onClick={() => setShowSkillModal(false)}>Cancel</button>
          <button className="btn btn-primary" onClick={handleAddSkill} disabled={!newSkill.name.trim()}>Add skill</button>
        </div>
      </Modal>

      {/* Skill Gap Modal */}
      <Modal open={showGapModal} onClose={() => setShowGapModal(false)} title="Skill Gap Analysis" maxWidth={520}>
        <div className="modal-body">
          {skillGap && (
            <>
              <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 20, padding: '14px 16px', background: 'var(--bg-elevated)', borderRadius: 10 }}>
                <div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>Readiness Score</div>
                  <div style={{ fontFamily: 'DM Mono, monospace', fontSize: 32, fontWeight: 500, color: skillGap.readiness_score >= 70 ? 'var(--green)' : skillGap.readiness_score >= 50 ? 'var(--blue-bright)' : 'var(--yellow)', lineHeight: 1 }}>
                    {skillGap.readiness_score}<span style={{ fontSize: 16, color: 'var(--text-muted)' }}>/100</span>
                  </div>
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 6 }}>Target: {skillGap.target_role}</div>
                  <ProgressBar value={skillGap.readiness_score} />
                </div>
              </div>
              {skillGap.matching_skills.length > 0 && (
                <div style={{ marginBottom: 16 }}>
                  <p className="label-caps" style={{ marginBottom: 8 }}>Matching skills ({skillGap.matching_skills.length})</p>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                    {skillGap.matching_skills.map(s => (
                      <span key={s} style={{ background: 'var(--green-dim)', color: 'var(--green)', fontSize: 12, padding: '3px 9px', borderRadius: 5, fontWeight: 500 }}>{s}</span>
                    ))}
                  </div>
                </div>
              )}
              {skillGap.missing_skills.length > 0 && (
                <div style={{ marginBottom: 16 }}>
                  <p className="label-caps" style={{ marginBottom: 8 }}>Missing skills ({skillGap.missing_skills.length})</p>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                    {skillGap.missing_skills.map(s => (
                      <span key={s} style={{ background: 'var(--red-dim)', color: 'var(--red)', fontSize: 12, padding: '3px 9px', borderRadius: 5, fontWeight: 500 }}>{s}</span>
                    ))}
                  </div>
                </div>
              )}
              {skillGap.recommendations.length > 0 && (
                <div>
                  <p className="label-caps" style={{ marginBottom: 8 }}>Recommendations</p>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {skillGap.recommendations.map((r, i) => (
                      <div key={i} style={{ display: 'flex', gap: 10, fontSize: 13, color: 'var(--text-secondary)', padding: '8px 12px', background: 'var(--bg-elevated)', borderRadius: 7 }}>
                        <span style={{ color: 'var(--blue-mid)', fontWeight: 600, flexShrink: 0 }}>{i + 1}.</span>
                        {r}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
        <div className="modal-footer">
          <button className="btn btn-ghost" onClick={() => setShowGapModal(false)}>Close</button>
        </div>
      </Modal>
    </AppShell>
  )
}