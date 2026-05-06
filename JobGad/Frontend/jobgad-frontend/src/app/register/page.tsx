'use client'
import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { auth, saveTokens } from '@/lib/api'
import { Spinner } from '@/components/ui'
import { Eye, EyeOff, GraduationCap, Building2, ArrowRight } from 'lucide-react'

export default function RegisterPage() {
  const router = useRouter()
  const [form, setForm]       = useState({ full_name: '', email: '', password: '', role: 'graduate' })
  const [showPw, setShowPw]   = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState('')

  const update = (k: string, v: string) => setForm(p => ({ ...p, [k]: v }))

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (form.password.length < 8) { setError('Password must be at least 8 characters.'); return }
    setError('')
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

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg-base)', display: 'flex' }}>

      {/* Left panel */}
      <div className="dot-grid" style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center', padding: '48px', position: 'relative', overflow: 'hidden' }}>
        <div style={{ position: 'absolute', inset: 0, background: 'radial-gradient(ellipse at 30% 40%, rgba(6,182,212,0.08) 0%, transparent 60%)', pointerEvents: 'none' }} />
        <div style={{ position: 'relative', maxWidth: 400 }}>
          <Link href="/" style={{ textDecoration: 'none' }}>
            <div style={{ fontFamily: 'Outfit, sans-serif', fontSize: 24, fontWeight: 700, letterSpacing: '-0.02em', marginBottom: 48 }}>
              Job<span style={{ color: 'var(--blue-core)' }}>Gad</span>
            </div>
          </Link>
          <h1 style={{ fontFamily: 'Outfit, sans-serif', fontSize: 36, fontWeight: 800, letterSpacing: '-0.025em', lineHeight: 1.15, marginBottom: 16 }}>
            Start your journey
          </h1>
          <p style={{ fontSize: 15, color: 'var(--text-secondary)', lineHeight: 1.7 }}>
            Create your free account and let AI match you to your first job — no experience required.
          </p>
        </div>
      </div>

      {/* Right panel */}
      <div style={{ width: '100%', maxWidth: 480, display: 'flex', flexDirection: 'column', justifyContent: 'center', padding: '48px 40px', background: 'var(--bg-surface)', borderLeft: '1px solid var(--border-subtle)', overflowY: 'auto' }}>
        <div className="animate-fade-up">
          <h2 style={{ fontFamily: 'Outfit, sans-serif', fontSize: 24, fontWeight: 700, marginBottom: 6 }}>Create account</h2>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 28 }}>
            Already have one?{' '}
            <Link href="/login" style={{ color: 'var(--blue-bright)', textDecoration: 'none', fontWeight: 500 }}>Sign in</Link>
          </p>

          {/* Role picker */}
          <div style={{ marginBottom: 24 }}>
            <label className="label">I am a</label>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              {[
                { value: 'graduate', label: 'Graduate',  sub: 'Looking for jobs',   icon: <GraduationCap size={18} /> },
                { value: 'hr',       label: 'Recruiter', sub: 'Hiring graduates',   icon: <Building2 size={18} /> },
              ].map(r => {
                const active = form.role === r.value
                return (
                  <button key={r.value} type="button" onClick={() => update('role', r.value)}
                    style={{
                      background: active ? 'rgba(37,99,235,0.12)' : 'var(--bg-elevated)',
                      border: `1px solid ${active ? 'var(--blue-mid)' : 'var(--border-default)'}`,
                      borderRadius: 10, padding: '12px 14px', cursor: 'pointer',
                      textAlign: 'left', transition: 'all 0.15s',
                    }}>
                    <div style={{ color: active ? 'var(--blue-bright)' : 'var(--text-secondary)', marginBottom: 4 }}>{r.icon}</div>
                    <div style={{ fontSize: 14, fontWeight: 600, color: active ? 'var(--blue-bright)' : 'var(--text-primary)' }}>{r.label}</div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{r.sub}</div>
                  </button>
                )
              })}
            </div>
          </div>

          <form onSubmit={handleSubmit}>
            <div className="form-group">
              <label className="label">Full name</label>
              <input className="input" type="text" placeholder="Allen Leinyuy"
                value={form.full_name} onChange={e => update('full_name', e.target.value)}
                required autoComplete="name" />
            </div>

            <div className="form-group">
              <label className="label">Email address</label>
              <input className="input" type="email" placeholder="you@example.com"
                value={form.email} onChange={e => update('email', e.target.value)}
                required autoComplete="email" />
            </div>

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
                <div style={{ marginTop: 6, display: 'flex', gap: 4 }}>
                  {[1,2,3,4].map(i => (
                    <div key={i} style={{ flex: 1, height: 3, borderRadius: 2, transition: 'background 0.3s',
                      background: form.password.length >= i * 3
                        ? i <= 1 ? 'var(--red)' : i === 2 ? 'var(--yellow)' : 'var(--green)'
                        : 'var(--bg-elevated)' }} />
                  ))}
                </div>
              )}
            </div>

            {error && (
              <div style={{ background: 'var(--red-dim)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: 8, padding: '10px 13px', marginBottom: 16, fontSize: 13, color: 'var(--red)' }}>
                {error}
              </div>
            )}

            <button type="submit" className="btn btn-primary" disabled={loading}
              style={{ width: '100%', height: 44, fontSize: 15 }}>
              {loading ? <Spinner size="sm" /> : <>Create account <ArrowRight size={15} /></>}
            </button>

            <p style={{ fontSize: 11, color: 'var(--text-muted)', textAlign: 'center', marginTop: 16, lineHeight: 1.6 }}>
              By creating an account you agree to our Terms of Service and Privacy Policy.
            </p>
          </form>
        </div>
      </div>
    </div>
  )
}