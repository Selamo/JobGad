'use client'
import { useEffect, useState, ReactNode } from 'react'
import { X } from 'lucide-react'

export function Spinner({ size = 'md' }: { size?: 'sm' | 'md' | 'lg' }) {
  const cls = size === 'sm' ? 'spinner spinner-sm' : size === 'lg' ? 'spinner spinner-lg' : 'spinner'
  return <span className={cls} />
}

export function LoadingPage() {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '100vh', background: 'var(--bg-base)' }}>
      <div style={{ textAlign: 'center' }}>
        <Spinner size="lg" />
        <p style={{ color: 'var(--text-muted)', fontSize: 13, marginTop: 14 }}>Loading...</p>
      </div>
    </div>
  )
}

const badgeMap: Record<string, string> = {
  pending: 'badge-yellow', reviewed: 'badge-blue', shortlisted: 'badge-green',
  accepted: 'badge-green', rejected: 'badge-red', withdrawn: 'badge-gray',
  suggested: 'badge-blue', saved: 'badge-purple', applied: 'badge-cyan',
  active: 'badge-green', closed: 'badge-gray', approved: 'badge-green',
  'full-time': 'badge-blue', 'part-time': 'badge-purple',
  contract: 'badge-yellow', internship: 'badge-cyan',
  behavioral: 'badge-blue', technical: 'badge-purple', mixed: 'badge-cyan',
  completed: 'badge-green', draft: 'badge-gray',
}

export function Badge({ label, variant }: { label: string; variant?: string }) {
  const cls = variant ? `badge badge-${variant}` : badgeMap[label.toLowerCase()] || 'badge badge-gray'
  return <span className={cls}>{label}</span>
}

export function ProgressBar({ value, max = 100, label }: { value: number; max?: number; label?: string }) {
  const pct = Math.min(100, Math.round((value / max) * 100))
  return (
    <div>
      {label && (
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 5 }}>
          <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{label}</span>
          <span style={{ fontSize: 12, fontFamily: 'DM Mono, monospace', color: 'var(--text-secondary)' }}>{pct}%</span>
        </div>
      )}
      <div className="progress-track">
        <div className="progress-fill" style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

export function ScoreRing({ score, size = 80 }: { score: number; size?: number }) {
  const r = (size - 10) / 2
  const circ = 2 * Math.PI * r
  const offset = circ - (score / 100) * circ
  const color = score >= 70 ? 'var(--green)' : score >= 50 ? 'var(--blue-core)' : 'var(--yellow)'
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ flexShrink: 0 }}>
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="var(--bg-elevated)" strokeWidth={5} />
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={color} strokeWidth={5}
        strokeDasharray={circ} strokeDashoffset={offset}
        strokeLinecap="round" transform={`rotate(-90 ${size/2} ${size/2})`}
        style={{ transition: 'stroke-dashoffset 0.8s ease' }}
      />
      <text x={size/2} y={size/2+1} textAnchor="middle" dominantBaseline="middle"
        style={{ fontFamily: 'DM Mono, monospace', fontSize: size * 0.22, fontWeight: 500, fill: color }}>
        {Math.round(score)}
      </text>
    </svg>
  )
}

interface ModalProps {
  open: boolean
  onClose: () => void
  title?: string
  children: ReactNode
  maxWidth?: number
}

export function Modal({ open, onClose, title, children, maxWidth = 480 }: ModalProps) {
  useEffect(() => {
    if (open) document.body.style.overflow = 'hidden'
    else document.body.style.overflow = ''
    return () => { document.body.style.overflow = '' }
  }, [open])
  if (!open) return null
  return (
    <div className="modal-backdrop" onClick={(e) => { if (e.target === e.currentTarget) onClose() }}>
      <div className="modal" style={{ maxWidth }}>
        {title && (
          <div className="modal-header">
            <h2 style={{ fontFamily: 'Outfit, sans-serif', fontSize: 18, fontWeight: 600 }}>{title}</h2>
            <button onClick={onClose} className="btn btn-ghost btn-sm" style={{ padding: '0 8px' }}>
              <X size={16} />
            </button>
          </div>
        )}
        {children}
      </div>
    </div>
  )
}

export type ToastType = 'success' | 'error' | 'info'
interface ToastMsg { id: number; message: string; type: ToastType }

let addToastFn: ((msg: string, type: ToastType) => void) | null = null
export function toast(message: string, type: ToastType = 'info') {
  addToastFn?.(message, type)
}

export function ToastContainer() {
  const [toasts, setToasts] = useState<ToastMsg[]>([])
  addToastFn = (message, type) => {
    const id = Date.now()
    setToasts(p => [...p, { id, message, type }])
    setTimeout(() => setToasts(p => p.filter(t => t.id !== id)), 3500)
  }
  const icons: Record<ToastType, string> = { success: '✓', error: '✗', info: 'i' }
  const colors: Record<ToastType, string> = { success: 'var(--green)', error: 'var(--red)', info: 'var(--blue-core)' }
  return (
    <div className="toast-container">
      {toasts.map(t => (
        <div key={t.id} className={`toast toast-${t.type}`}>
          <span style={{ color: colors[t.type], fontSize: 14, fontWeight: 700, flexShrink: 0 }}>{icons[t.type]}</span>
          <span style={{ fontSize: 13, color: 'var(--text-primary)', lineHeight: 1.4 }}>{t.message}</span>
          <button onClick={() => setToasts(p => p.filter(x => x.id !== t.id))}
            style={{ marginLeft: 'auto', background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', flexShrink: 0 }}>
            <X size={14} />
          </button>
        </div>
      ))}
    </div>
  )
}

export function EmptyState({ icon, title, description, action }: {
  icon?: ReactNode; title: string; description?: string; action?: ReactNode
}) {
  return (
    <div style={{ textAlign: 'center', padding: '48px 24px' }}>
      {icon && <div style={{ marginBottom: 12, color: 'var(--text-muted)' }}>{icon}</div>}
      <h3 style={{ fontFamily: 'Outfit, sans-serif', fontSize: 16, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 6 }}>{title}</h3>
      {description && <p style={{ fontSize: 13, color: 'var(--text-muted)', maxWidth: 320, margin: '0 auto 20px' }}>{description}</p>}
      {action}
    </div>
  )
}

export function SkeletonCard({ rows = 3 }: { rows?: number }) {
  return (
    <div className="card">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="skeleton" style={{ height: 14, marginBottom: i < rows - 1 ? 10 : 0, width: i === 0 ? '60%' : i === rows - 1 ? '40%' : '85%' }} />
      ))}
    </div>
  )
}

export function StatCard({ label, value, sub, color }: { label: string; value: string | number; sub?: string; color?: string }) {
  return (
    <div className="stat-card">
      <div className="label-caps" style={{ marginBottom: 8 }}>{label}</div>
      <div className="stat-value" style={{ color: color || 'var(--text-primary)' }}>{value}</div>
      {sub && <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 4 }}>{sub}</div>}
    </div>
  )
}