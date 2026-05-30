'use client'
import { useState } from 'react'
import Link from 'next/link'
import { auth } from '@/lib/api'
import { Spinner } from '@/components/ui'

export default function ForgotPasswordPage() {
  const [email, setEmail]       = useState('')
  const [loading, setLoading]   = useState(false)
  const [sent, setSent]         = useState(false)
  const [error, setError]       = useState('')

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!email.trim()) return
    setLoading(true)
    setError('')
    try {
      await auth.forgotPassword(email)
      setSent(true)
    } catch (e: any) {
      setError(e.message || 'Something went wrong. Please try again.')
    } finally { setLoading(false) }
  }

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg-base)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24 }}>
      <div style={{ width: '100%', maxWidth: 400 }}>
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <h1 style={{ fontFamily: 'Outfit, sans-serif', fontSize: 28, fontWeight: 700, marginBottom: 8 }}>
            JobGad
          </h1>
          <p style={{ fontSize: 14, color: 'var(--text-muted)' }}>
            {sent ? 'Check your email' : 'Reset your password'}
          </p>
        </div>

        <div className="card" style={{ padding: 32 }}>
          {sent ? (
            <div style={{ textAlign: 'center' }}>
              <div style={{ width: 56, height: 56, borderRadius: '50%', background: 'rgba(22,163,74,0.12)', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 16px' }}>
                <span style={{ fontSize: 24 }}>✉️</span>
              </div>
              <h2 style={{ fontFamily: 'Outfit, sans-serif', fontSize: 18, fontWeight: 600, marginBottom: 10 }}>
                Reset link sent
              </h2>
              <p style={{ fontSize: 14, color: 'var(--text-secondary)', lineHeight: 1.7, marginBottom: 24 }}>
                If an account exists for <strong>{email}</strong>, you will receive a password reset link shortly. Check your spam folder if you do not see it.
              </p>
              <Link href="/login" className="btn btn-primary" style={{ textDecoration: 'none', display: 'inline-flex' }}>
                Back to login
              </Link>
            </div>
          ) : (
            <>
              <p style={{ fontSize: 14, color: 'var(--text-secondary)', marginBottom: 24, lineHeight: 1.6 }}>
                Enter your email address and we will send you a link to reset your password.
              </p>
              <form onSubmit={handleSubmit}>
                <div className="form-group">
                  <label className="label">Email address</label>
                  <input
                    className="input"
                    type="email"
                    placeholder="you@example.com"
                    value={email}
                    onChange={e => setEmail(e.target.value)}
                    autoFocus
                    required
                  />
                </div>
                {error && (
                  <div style={{ padding: '10px 14px', background: 'var(--red-dim)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: 8, marginBottom: 16 }}>
                    <p style={{ fontSize: 13, color: 'var(--red)' }}>{error}</p>
                  </div>
                )}
                <button className="btn btn-primary" type="submit" disabled={loading || !email.trim()} style={{ width: '100%', justifyContent: 'center' }}>
                  {loading ? <Spinner size="sm" /> : null}
                  {loading ? 'Sending...' : 'Send reset link'}
                </button>
              </form>
              <div style={{ textAlign: 'center', marginTop: 20 }}>
                <Link href="/login" style={{ fontSize: 13, color: 'var(--text-muted)', textDecoration: 'none' }}>
                  ← Back to login
                </Link>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}