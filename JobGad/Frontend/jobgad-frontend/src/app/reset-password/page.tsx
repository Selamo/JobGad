'use client'
import { useState, useEffect, Suspense } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import Link from 'next/link'
import { auth } from '@/lib/api'
import { Spinner } from '@/components/ui'

function ResetPasswordForm() {
  const router       = useRouter()
  const searchParams = useSearchParams()
  const token        = searchParams.get('token') || ''

  const [password, setPassword]   = useState('')
  const [confirm, setConfirm]     = useState('')
  const [loading, setLoading]     = useState(false)
  const [success, setSuccess]     = useState(false)
  const [error, setError]         = useState('')
  const [showPass, setShowPass]   = useState(false)

  useEffect(() => {
    if (!token) setError('Invalid or missing reset token. Please request a new link.')
  }, [token])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (password.length < 8) { setError('Password must be at least 8 characters.'); return }
    if (password !== confirm) { setError('Passwords do not match.'); return }
    setLoading(true)
    setError('')
    try {
      await auth.resetPassword(token, password)
      setSuccess(true)
      setTimeout(() => router.push('/login'), 3000)
    } catch (e: any) {
      setError(e.message || 'Failed to reset password. The link may have expired.')
    } finally { setLoading(false) }
  }

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg-base)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24 }}>
      <div style={{ width: '100%', maxWidth: 400 }}>
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <h1 style={{ fontFamily: 'Outfit, sans-serif', fontSize: 28, fontWeight: 700, marginBottom: 8 }}>JobGad</h1>
          <p style={{ fontSize: 14, color: 'var(--text-muted)' }}>Set a new password</p>
        </div>

        <div className="card" style={{ padding: 32 }}>
          {success ? (
            <div style={{ textAlign: 'center' }}>
              <div style={{ width: 56, height: 56, borderRadius: '50%', background: 'rgba(22,163,74,0.12)', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 16px' }}>
                <span style={{ fontSize: 24 }}>✅</span>
              </div>
              <h2 style={{ fontFamily: 'Outfit, sans-serif', fontSize: 18, fontWeight: 600, marginBottom: 10 }}>Password reset!</h2>
              <p style={{ fontSize: 14, color: 'var(--text-secondary)', lineHeight: 1.7, marginBottom: 8 }}>
                Your password has been updated successfully.
              </p>
              <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 24 }}>Redirecting to login...</p>
              <Link href="/login" className="btn btn-primary" style={{ textDecoration: 'none', display: 'inline-flex' }}>
                Go to login
              </Link>
            </div>
          ) : (
            <>
              <p style={{ fontSize: 14, color: 'var(--text-secondary)', marginBottom: 24, lineHeight: 1.6 }}>
                Choose a strong password of at least 8 characters.
              </p>
              <form onSubmit={handleSubmit}>
                <div className="form-group">
                  <label className="label">New password</label>
                  <div style={{ position: 'relative' }}>
                    <input
                      className="input"
                      type={showPass ? 'text' : 'password'}
                      placeholder="Min 8 characters"
                      value={password}
                      onChange={e => setPassword(e.target.value)}
                      autoFocus
                      required
                    />
                    <button type="button" onClick={() => setShowPass(p => !p)}
                      style={{ position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', fontSize: 12 }}>
                      {showPass ? 'Hide' : 'Show'}
                    </button>
                  </div>
                </div>
                <div className="form-group">
                  <label className="label">Confirm password</label>
                  <input
                    className="input"
                    type={showPass ? 'text' : 'password'}
                    placeholder="Repeat your password"
                    value={confirm}
                    onChange={e => setConfirm(e.target.value)}
                    required
                  />
                </div>
                {error && (
                  <div style={{ padding: '10px 14px', background: 'var(--red-dim)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: 8, marginBottom: 16 }}>
                    <p style={{ fontSize: 13, color: 'var(--red)' }}>{error}</p>
                  </div>
                )}
                <button className="btn btn-primary" type="submit"
                  disabled={loading || !password || !confirm || !token}
                  style={{ width: '100%', justifyContent: 'center' }}>
                  {loading ? <Spinner size="sm" /> : null}
                  {loading ? 'Resetting...' : 'Reset password'}
                </button>
              </form>
              <div style={{ textAlign: 'center', marginTop: 20 }}>
                <Link href="/forgot-password" style={{ fontSize: 13, color: 'var(--text-muted)', textDecoration: 'none' }}>
                  Request a new link
                </Link>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={<div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}><Spinner size="lg" /></div>}>
      <ResetPasswordForm />
    </Suspense>
  )
}