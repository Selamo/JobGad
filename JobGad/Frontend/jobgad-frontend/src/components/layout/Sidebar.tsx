'use client'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useAuth } from '@/context/AuthContext'
import {
  LayoutDashboard, User, Briefcase, FileText, Mic,
  FileEdit, Bell, LogOut, ChevronRight, ShieldCheck, X
} from 'lucide-react'

interface NavItem {
  label: string
  href: string
  icon: React.ReactNode
}

const gradNav: NavItem[] = [
  { label: 'Dashboard',    href: '/dashboard',    icon: <LayoutDashboard size={16} /> },
  { label: 'Profile',      href: '/profile',      icon: <User size={16} /> },
  { label: 'Jobs',         href: '/jobs',         icon: <Briefcase size={16} /> },
  { label: 'Applications', href: '/applications', icon: <FileText size={16} /> },
  { label: 'Coaching',     href: '/coaching',     icon: <Mic size={16} /> },
  { label: 'CV Generator', href: '/cv',           icon: <FileEdit size={16} /> },
]

const hrNav: NavItem[] = [
  { label: 'Dashboard',    href: '/dashboard', icon: <LayoutDashboard size={16} /> },
  { label: 'HR Panel',     href: '/hr',        icon: <Briefcase size={16} /> },
]

const adminNav: NavItem[] = [
  { label: 'Dashboard',   href: '/dashboard', icon: <LayoutDashboard size={16} /> },
  { label: 'Admin Panel', href: '/admin',     icon: <ShieldCheck size={16} /> },
]

interface SidebarProps {
  unreadCount?: number
  isOpen?: boolean
  onClose?: () => void
}

export function Sidebar({ unreadCount = 0, isOpen = false, onClose }: SidebarProps) {
  const pathname = usePathname()
  const { user, logout } = useAuth()

  const navItems =
    user?.role === 'hr' ? hrNav :
    user?.role === 'admin' || user?.role === 'superadmin' ? adminNav :
    gradNav

  const initials = user?.full_name
    ? user.full_name.split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase()
    : 'JG'

  return (
    <>
      {/* Mobile backdrop */}
      {isOpen && (
        <div
          onClick={onClose}
          style={{
            position: 'fixed', inset: 0,
            background: 'rgba(0,0,0,0.6)',
            backdropFilter: 'blur(2px)',
            zIndex: 99,
            display: 'none',
          }}
          className="mobile-backdrop"
        />
      )}

      <aside className={`app-sidebar ${isOpen ? 'open' : ''}`}>
        {/* Logo */}
        <div style={{ padding: '18px 16px 14px', borderBottom: '1px solid var(--border-subtle)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Link href="/dashboard" style={{ textDecoration: 'none' }} onClick={onClose}>
            <div style={{ fontFamily: 'Outfit, sans-serif', fontSize: 20, fontWeight: 700, color: 'var(--text-primary)', letterSpacing: '-0.02em' }}>
              Job<span style={{ color: 'var(--blue-core)' }}>Gad</span>
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 1 }}>Graduate Career Platform</div>
          </Link>
          {/* Close button — mobile only */}
          <button
            onClick={onClose}
            className="mobile-only"
            style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: 4, display: 'flex', alignItems: 'center' }}>
            <X size={18} />
          </button>
        </div>

        {/* Nav */}
        <nav style={{ flex: 1, padding: '12px 8px', overflowY: 'auto' }}>
          <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.07em', textTransform: 'uppercase', color: 'var(--text-muted)', padding: '4px 12px 8px' }}>
            Menu
          </div>
          {navItems.map(item => {
            const active = pathname === item.href || (item.href !== '/dashboard' && pathname.startsWith(item.href))
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`nav-item ${active ? 'active' : ''}`}
                style={{ textDecoration: 'none' }}
                onClick={onClose}
              >
                <span style={{ opacity: active ? 1 : 0.7 }}>{item.icon}</span>
                <span>{item.label}</span>
                {active && <ChevronRight size={12} style={{ marginLeft: 'auto', opacity: 0.6 }} />}
              </Link>
            )
          })}

          <div style={{ height: 1, background: 'var(--border-subtle)', margin: '12px 0' }} />

          <Link
            href="/notifications"
            className={`nav-item ${pathname === '/notifications' ? 'active' : ''}`}
            style={{ textDecoration: 'none' }}
            onClick={onClose}
          >
            <Bell size={16} style={{ opacity: 0.7 }} />
            <span>Notifications</span>
            {unreadCount > 0 && (
              <span style={{ marginLeft: 'auto', background: 'var(--red)', color: '#fff', fontSize: 10, fontWeight: 700, padding: '1px 6px', borderRadius: 10 }}>
                {unreadCount > 9 ? '9+' : unreadCount}
              </span>
            )}
          </Link>
        </nav>

        {/* User */}
        <div style={{ padding: '12px 8px', borderTop: '1px solid var(--border-subtle)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 10px', borderRadius: 8 }}>
            <div style={{ width: 32, height: 32, borderRadius: '50%', background: 'var(--blue-dim)', color: 'var(--blue-bright)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, fontWeight: 600, flexShrink: 0 }}>
              {initials}
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {user?.full_name}
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'capitalize' }}>
                {user?.role}
              </div>
            </div>
            <button
              onClick={logout}
              title="Sign out"
              style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: 4, borderRadius: 4, display: 'flex', alignItems: 'center' }}
              onMouseEnter={e => (e.currentTarget.style.color = 'var(--red)')}
              onMouseLeave={e => (e.currentTarget.style.color = 'var(--text-muted)')}
            >
              <LogOut size={15} />
            </button>
          </div>
        </div>
      </aside>
    </>
  )
}