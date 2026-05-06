'use client'
import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { useAuth } from '@/context/AuthContext'
import { Spinner } from '@/components/ui'
import { Eye, EyeOff, ArrowRight } from 'lucide-react'

export default function LoginPage() {
  const { login } = useAuth()
  const router = useRouter()
  const [email, setEmail]       = useState('')
  const [password, setPassword] = useState('')
  const [showPw, setShowPw]     = useState(false)
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(email, password)
      router.push('/dashboard')
    } catch (err: any) {
      setError(err.message || 'Invalid credentials. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg-base)', display: 'flex' }}>

      {/* Left panel */}
      <div className="dot-grid" style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center', padding: '48px', position: 'relative', overflow: 'hidden' }}>
        <div style={{ position: 'absolute', inset: 0, background: 'radial-gradient(ellipse at 30% 50%, rgba(37,99,235,0.1) 0%, transparent 65%)', pointerEvents: 'none' }} />
        <div style={{ position: 'relative', maxWidth: 400 }}>
          <Link href="/" style={{ textDecoration: 'none' }}>
            <div style={{ fontFamily: 'Outfit, sans-serif', fontSize: 24, fontWeight: 700, letterSpacing: '-0.02em', marginBottom: 48 }}>
              Job<span style={{ color: 'var(--blue-core)' }}>Gad</span>
            </div>
          </Link>
          <h1 style={{ fontFamily: 'Outfit, sans-serif', fontSize: 36, fontWeight: 800, letterSpacing: '-0.025em', lineHeight: 1.15, marginBottom: 16 }}>
            Welcome back
          </h1>
          <p style={{ fontSize: 15, color: 'var(--text-secondary)', lineHeight: 1.7, marginBottom: 40 }}>
            Sign in to access your job matches, coaching sessions, and generated CVs.
          </p>
          {[
            'AI-matched jobs based on your skills',
            'Live interview coaching with IRI scoring',
            'One-click tailored CV generation',
          ].map(f => (
            <div key={f} style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
              <div style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--blue-core)', flexShrink: 0 }} />
              <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{f}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Right panel */}
      <div style={{ width: '100%', maxWidth: 460, display: 'flex', flexDirection: 'column', justifyContent: 'center', padding: '48px 40px', background: 'var(--bg-surface)', borderLeft: '1px solid var(--border-subtle)' }}>
        <div className="animate-fade-up">
          <h2 style={{ fontFamily: 'Outfit, sans-serif', fontSize: 24, fontWeight: 700, marginBottom: 6 }}>Sign in</h2>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 32 }}>
            Don&apos;t have an account?{' '}
            <Link href="/register" style={{ color: 'var(--blue-bright)', textDecoration: 'none', fontWeight: 500 }}>Create one</Link>
          </p>

          <form onSubmit={handleSubmit}>
            <div className="form-group">
              <label className="label">Email address</label>
              <input className="input" type="email" placeholder="you@example.com"
                value={email} onChange={e => setEmail(e.target.value)} required autoComplete="email" />
            </div>

            <div className="form-group">
              <label className="label">Password</label>
              <div style={{ position: 'relative' }}>
                <input className="input" type={showPw ? 'text' : 'password'} placeholder="Your password"
                  value={password} onChange={e => setPassword(e.target.value)}
                  required autoComplete="current-password" style={{ paddingRight: 44 }} />
                <button type="button" onClick={() => setShowPw(p => !p)}
                  style={{ position: 'absolute', right: 13, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', display: 'flex', alignItems: 'center' }}>
                  {showPw ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            {error && (
              <div style={{ background: 'var(--red-dim)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: 8, padding: '10px 13px', marginBottom: 16, fontSize: 13, color: 'var(--red)' }}>
                {error}
              </div>
            )}

            <button type="submit" className="btn btn-primary" disabled={loading}
              style={{ width: '100%', height: 44, fontSize: 15, marginTop: 4 }}>
              {loading ? <Spinner size="sm" /> : <>Sign in <ArrowRight size={15} /></>}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}