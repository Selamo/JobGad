'use client'
import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { auth, admin, saveTokens } from '@/lib/api'
import { Spinner } from '@/components/ui'
import { Eye, EyeOff, GraduationCap, Building2, ArrowRight, ChevronLeft } from 'lucide-react'

type Step = 'role' | 'details' | 'company'

export default function RegisterPage() {
  const router = useRouter()
  const [step, setStep]         = useState<Step>('role')
  const [form, setForm]         = useState({ full_name: '', email: '', password: '', role: 'graduate' })
  const [company, setCompany]   = useState({ name: '', industry: '', city: '', country: '', website: '' })
  const [hrTitle, setHrTitle]   = useState('')
  const [showPw, setShowPw]     = useState(false)
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState('')

  const update        = (k: string, v: string) => setForm(p => ({ ...p, [k]: v }))
  const updateCompany = (k: string, v: string) => setCompany(p => ({ ...p, [k]: v }))

  const handleDetailsNext = (e: React.FormEvent) => {
    e.preventDefault()
    if (form.password.length < 8) { setError('Password must be at least 8 characters.'); return }
    setError('')
    if (form.role === 'hr') setStep('company')
    else handleSubmitGraduate()
  }

  async function handleSubmitGraduate() {
    setLoading(true)
    try {
      await auth.register(form)
      const tokens = await auth.login(form.email, form.password)
      saveTokens(tokens.access_token, tokens.refresh_token)
      router.push('/dashboard')
    } catch (err: any) {
      setError(err.message || 'Registration failed. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  async function handleSubmitHR(e: React.FormEvent) {
    e.preventDefault()
    if (!company.name || !company.industry || !company.city || !company.country) {
      setError('Please fill in all company fields.')
      return
    }
    setLoading(true)
    setError('')
    try {
      // 1. Register user account
      await auth.register(form)

      // 2. Login to get tokens
      const tokens = await auth.login(form.email, form.password)
      saveTokens(tokens.access_token, tokens.refresh_token)

      // 3. Register company
      const companyRes: any = await admin.registerCompany({
        name:        company.name,
        industry:    company.industry,
        city:        company.city,
        country:     company.country,
        website:     company.website || undefined,
        description: `${company.name} — ${company.industry}`,
      })

      // 4. Register HR profile linked to company
      await admin.registerHRProfile({
        company_id: companyRes.id,
        job_title:  hrTitle || 'HR Manager',
        is_company_admin: true,
      })

      router.push('/dashboard')
    } catch (err: any) {
      setError(err.message || 'Registration failed. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg-base)', display: 'flex', flexDirection: 'column' }}>

      {/* Navbar */}
      <nav style={{ height: 56, display: 'flex', alignItems: 'center', padding: '0 24px', borderBottom: '1px solid var(--border-subtle)', flexShrink: 0 }}>
        <Link href="/" style={{ textDecoration: 'none', fontFamily: 'Outfit, sans-serif', fontSize: 18, fontWeight: 700, color: 'var(--text-primary)' }}>
          Job<span style={{ color: 'var(--blue-core)' }}>Gad</span>
        </Link>
        <div style={{ marginLeft: 'auto', fontSize: 13, color: 'var(--text-muted)' }}>
          Have an account?{' '}
          <Link href="/login" style={{ color: 'var(--blue-bright)', textDecoration: 'none', fontWeight: 500 }}>Sign in</Link>
        </div>
      </nav>

      {/* Main */}
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '24px 16px' }}>
        <div style={{ width: '100%', maxWidth: 460 }}>

          {/* Step indicator */}
          {form.role === 'hr' && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 24, justifyContent: 'center' }}>
              {(['role', 'details', 'company'] as Step[]).map((s, i) => (
                <div key={s} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <div style={{
                    width: 28, height: 28, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 12, fontWeight: 600,
                    background: step === s ? 'var(--blue-mid)' : (['role', 'details', 'company'].indexOf(step) > i) ? 'var(--green)' : 'var(--bg-elevated)',
                    color: step === s || (['role', 'details', 'company'].indexOf(step) > i) ? 'white' : 'var(--text-muted)',
                    border: `1px solid ${step === s ? 'var(--blue-mid)' : 'var(--border-default)'}`,
                  }}>
                    {['role', 'details', 'company'].indexOf(step) > i ? '✓' : i + 1}
                  </div>
                  <span style={{ fontSize: 12, color: step === s ? 'var(--text-primary)' : 'var(--text-muted)', textTransform: 'capitalize' }}>{s}</span>
                  {i < 2 && <div style={{ width: 24, height: 1, background: 'var(--border-default)' }} />}
                </div>
              ))}
            </div>
          )}

          {/* STEP 1 — Role selection */}
          {step === 'role' && (
            <div className="animate-fade-up">
              <div style={{ textAlign: 'center', marginBottom: 28 }}>
                <h1 style={{ fontFamily: 'Outfit, sans-serif', fontSize: 28, fontWeight: 700, letterSpacing: '-0.02em', marginBottom: 8 }}>
                  Create your account
                </h1>
                <p style={{ fontSize: 14, color: 'var(--text-secondary)' }}>Free forever. No credit card required.</p>
              </div>
              <div className="card" style={{ padding: 24 }}>
                <label className="label" style={{ marginBottom: 12 }}>I am a</label>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 20 }}>
                  {[
                    { value: 'graduate', label: 'Graduate',  sub: 'Looking for jobs',  icon: <GraduationCap size={22} /> },
                    { value: 'hr',       label: 'Recruiter', sub: 'Hiring graduates',  icon: <Building2 size={22} /> },
                  ].map(r => {
                    const active = form.role === r.value
                    return (
                      <button key={r.value} type="button" onClick={() => update('role', r.value)}
                        style={{ background: active ? 'rgba(37,99,235,0.12)' : 'var(--bg-elevated)', border: `1px solid ${active ? 'var(--blue-mid)' : 'var(--border-default)'}`, borderRadius: 10, padding: '16px 14px', cursor: 'pointer', textAlign: 'left', transition: 'all 0.15s' }}>
                        <div style={{ color: active ? 'var(--blue-bright)' : 'var(--text-secondary)', marginBottom: 8 }}>{r.icon}</div>
                        <div style={{ fontSize: 15, fontWeight: 600, color: active ? 'var(--blue-bright)' : 'var(--text-primary)', marginBottom: 3 }}>{r.label}</div>
                        <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>{r.sub}</div>
                      </button>
                    )
                  })}
                </div>
                <button className="btn btn-primary" style={{ width: '100%', height: 44 }} onClick={() => setStep('details')}>
                  Continue <ArrowRight size={15} />
                </button>
              </div>
            </div>
          )}

          {/* STEP 2 — Account details */}
          {step === 'details' && (
            <div className="animate-fade-up">
              <div style={{ textAlign: 'center', marginBottom: 24 }}>
                <h1 style={{ fontFamily: 'Outfit, sans-serif', fontSize: 26, fontWeight: 700, letterSpacing: '-0.02em', marginBottom: 6 }}>
                  Your details
                </h1>
                <p style={{ fontSize: 14, color: 'var(--text-secondary)' }}>
                  {form.role === 'hr' ? 'Set up your recruiter account' : 'Set up your graduate account'}
                </p>
              </div>
              <div className="card" style={{ padding: 24 }}>
                <form onSubmit={handleDetailsNext}>
                  <div className="form-group">
                    <label className="label">Full name</label>
                    <input className="input" type="text" placeholder="Allen Leinyuy"
                      value={form.full_name} onChange={e => update('full_name', e.target.value)} required autoComplete="name" />
                  </div>
                  <div className="form-group">
                    <label className="label">Email address</label>
                    <input className="input" type="email" placeholder="you@example.com"
                      value={form.email} onChange={e => update('email', e.target.value)} required autoComplete="email" />
                  </div>
                  {form.role === 'hr' && (
                    <div className="form-group">
                      <label className="label">Job title</label>
                      <input className="input" type="text" placeholder="e.g. HR Manager, Talent Acquisition"
                        value={hrTitle} onChange={e => setHrTitle(e.target.value)} />
                    </div>
                  )}
                  <div className="form-group">
                    <label className="label">Password</label>
                    <div style={{ position: 'relative' }}>
                      <input className="input" type={showPw ? 'text' : 'password'} placeholder="Min. 8 characters"
                        value={form.password} onChange={e => update('password', e.target.value)}
                        required minLength={8} autoComplete="new-password" style={{ paddingRight: 44 }} />
                      <button type="button" onClick={() => setShowPw(p => !p)}
                        style={{ position: 'absolute', right: 13, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', display: 'flex', alignItems: 'center' }}>
                        {showPw ? <EyeOff size={16} /> : <Eye size={16} />}
                      </button>
                    </div>
                    {form.password && (
                      <div style={{ marginTop: 8, display: 'flex', gap: 4 }}>
                        {[1,2,3,4].map(i => (
                          <div key={i} style={{ flex: 1, height: 3, borderRadius: 2, transition: 'background 0.3s',
                            background: form.password.length >= i * 3 ? i <= 1 ? 'var(--red)' : i === 2 ? 'var(--yellow)' : 'var(--green)' : 'var(--bg-elevated)' }} />
                        ))}
                      </div>
                    )}
                  </div>

                  {error && (
                    <div style={{ background: 'var(--red-dim)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: 8, padding: '10px 13px', marginBottom: 16, fontSize: 13, color: 'var(--red)' }}>
                      {error}
                    </div>
                  )}

                  <div style={{ display: 'flex', gap: 10 }}>
                    <button type="button" className="btn btn-ghost" style={{ height: 44 }} onClick={() => { setStep('role'); setError('') }}>
                      <ChevronLeft size={15} /> Back
                    </button>
                    <button type="submit" className="btn btn-primary" disabled={loading} style={{ flex: 1, height: 44 }}>
                      {loading ? <Spinner size="sm" /> : form.role === 'hr' ? <>Next <ArrowRight size={15} /></> : <>Create account <ArrowRight size={15} /></>}
                    </button>
                  </div>
                </form>
              </div>
            </div>
          )}

          {/* STEP 3 — Company details (HR only) */}
          {step === 'company' && (
            <div className="animate-fade-up">
              <div style={{ textAlign: 'center', marginBottom: 24 }}>
                <h1 style={{ fontFamily: 'Outfit, sans-serif', fontSize: 26, fontWeight: 700, letterSpacing: '-0.02em', marginBottom: 6 }}>
                  Company details
                </h1>
                <p style={{ fontSize: 14, color: 'var(--text-secondary)' }}>
                  This will be reviewed and approved by an admin
                </p>
              </div>

              <div style={{ background: 'rgba(245,158,11,0.07)', border: '1px solid rgba(245,158,11,0.2)', borderRadius: 10, padding: '12px 16px', marginBottom: 20, fontSize: 13, color: 'var(--text-secondary)' }}>
                Your company and HR account will be reviewed by our admin team before you can post jobs.
              </div>

              <div className="card" style={{ padding: 24 }}>
                <form onSubmit={handleSubmitHR}>
                  <div className="form-group">
                    <label className="label">Company name</label>
                    <input className="input" placeholder="e.g. TechCorp Africa"
                      value={company.name} onChange={e => updateCompany('name', e.target.value)} required />
                  </div>
                  <div className="form-group">
                    <label className="label">Industry</label>
                    <input className="input" placeholder="e.g. Technology, Finance, Healthcare"
                      value={company.industry} onChange={e => updateCompany('industry', e.target.value)} required />
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                    <div className="form-group">
                      <label className="label">City</label>
                      <input className="input" placeholder="e.g. Douala"
                        value={company.city} onChange={e => updateCompany('city', e.target.value)} required />
                    </div>
                    <div className="form-group">
                      <label className="label">Country</label>
                      <input className="input" placeholder="e.g. Cameroon"
                        value={company.country} onChange={e => updateCompany('country', e.target.value)} required />
                    </div>
                  </div>
                  <div className="form-group">
                    <label className="label">Website <span style={{ color: 'var(--text-muted)', fontWeight: 400 }}>(optional)</span></label>
                    <input className="input" placeholder="https://yourcompany.com"
                      value={company.website} onChange={e => updateCompany('website', e.target.value)} />
                  </div>

                  {error && (
                    <div style={{ background: 'var(--red-dim)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: 8, padding: '10px 13px', marginBottom: 16, fontSize: 13, color: 'var(--red)' }}>
                      {error}
                    </div>
                  )}

                  <div style={{ display: 'flex', gap: 10 }}>
                    <button type="button" className="btn btn-ghost" style={{ height: 44 }} onClick={() => { setStep('details'); setError('') }}>
                      <ChevronLeft size={15} /> Back
                    </button>
                    <button type="submit" className="btn btn-primary" disabled={loading} style={{ flex: 1, height: 44 }}>
                      {loading ? <Spinner size="sm" /> : <>Submit for approval <ArrowRight size={15} /></>}
                    </button>
                  </div>
                </form>
              </div>

              <p style={{ fontSize: 11, color: 'var(--text-muted)', textAlign: 'center', marginTop: 14, lineHeight: 1.6 }}>
                By registering you agree to our Terms of Service and Privacy Policy.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}