'use client'
import { useEffect, useState, ReactNode } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/context/AuthContext'
import { Sidebar } from './Sidebar'
import { ToastContainer, LoadingPage } from '@/components/ui'
import { notifications } from '@/lib/api'
import { Menu } from 'lucide-react'

interface AppShellProps {
  children: ReactNode
  title?: string
  subtitle?: string
  actions?: ReactNode
}

export function AppShell({ children, title, subtitle, actions }: AppShellProps) {
  const { user, loading } = useAuth()
  const router = useRouter()
  const [unread, setUnread]         = useState(0)
  const [sidebarOpen, setSidebarOpen] = useState(false)

  useEffect(() => {
    if (!loading && !user) router.push('/login')
  }, [loading, user, router])

  useEffect(() => {
    if (!user) return
    notifications.list()
      .then(d => setUnread(d.unread))
      .catch(() => {})
    const interval = setInterval(() => {
      notifications.list().then(d => setUnread(d.unread)).catch(() => {})
    }, 60000)
    return () => clearInterval(interval)
  }, [user])

  // Close sidebar when route changes on mobile
  useEffect(() => {
    setSidebarOpen(false)
  }, [])

  if (loading) return <LoadingPage />
  if (!user)   return null

  return (
    <div className="app-shell">
      <Sidebar
        unreadCount={unread}
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />

      {/* Mobile backdrop */}
      {sidebarOpen && (
        <div
          onClick={() => setSidebarOpen(false)}
          style={{
            position: 'fixed', inset: 0,
            background: 'rgba(0,0,0,0.6)',
            backdropFilter: 'blur(2px)',
            zIndex: 98,
          }}
        />
      )}

      <main className="app-main">
        {/* Topbar */}
        <div className="app-topbar">
          {/* Hamburger — mobile only */}
          <button
            onClick={() => setSidebarOpen(p => !p)}
            style={{
              display: 'none',
              background: 'none', border: 'none',
              color: 'var(--text-secondary)',
              cursor: 'pointer', padding: 6,
              borderRadius: 6, alignItems: 'center',
            }}
            className="mobile-menu-btn"
          >
            <Menu size={20} />
          </button>

          {title && (
            <div style={{ flex: 1 }}>
              <h1 style={{ fontFamily: 'Outfit, sans-serif', fontSize: 17, fontWeight: 600, color: 'var(--text-primary)', lineHeight: 1.2 }}>
                {title}
              </h1>
              {subtitle && (
                <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 1 }}>{subtitle}</p>
              )}
            </div>
          )}
          {!title && <div style={{ flex: 1 }} />}

          {actions && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              {actions}
            </div>
          )}
        </div>

        {/* Page content */}
        <div className="app-content">
          {children}
        </div>
      </main>

      <ToastContainer />
    </div>
  )
}