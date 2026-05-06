'use client'
import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { AppShell } from '@/components/layout/AppShell'
import { Spinner, EmptyState, toast, ToastContainer } from '@/components/ui'
import { notifications, type Notification } from '@/lib/api'
import { Bell, CheckCheck, Briefcase, FileText, Mic, Star, Info } from 'lucide-react'

const TYPE_ICONS: Record<string, React.ReactNode> = {
  status_changed:   <FileText size={15} />,
  new_match:        <Briefcase size={15} />,
  session_complete: <Mic size={15} />,
  cv_ready:         <Star size={15} />,
  welcome:          <Bell size={15} />,
}

const TYPE_COLORS: Record<string, string> = {
  status_changed:   'var(--blue-core)',
  new_match:        'var(--green)',
  session_complete: 'var(--cyan-core)',
  cv_ready:         'var(--purple)',
  welcome:          'var(--yellow)',
}

export default function NotificationsPage() {
  const router = useRouter()
  const [items, setItems]     = useState<Notification[]>([])
  const [unread, setUnread]   = useState(0)
  const [loading, setLoading] = useState(true)
  const [marking, setMarking] = useState(false)

  useEffect(() => { loadAll() }, [])

  async function loadAll() {
    setLoading(true)
    try {
      const res = await notifications.list()
      setItems(res.notifications ?? [])
      setUnread(res.unread ?? 0)
    } catch { setItems([]) }
    finally { setLoading(false) }
  }

  async function handleMarkRead(id: string) {
    try {
      await notifications.markRead(id)
      setItems(p => p.map(n => n.id === id ? { ...n, is_read: true } : n))
      setUnread(p => Math.max(0, p - 1))
    } catch (e: any) {
      toast(e.message || 'Failed to mark as read', 'error')
    }
  }

  async function handleMarkAllRead() {
    if (unread === 0) return
    setMarking(true)
    try {
      await notifications.markAllRead()
      setItems(p => p.map(n => ({ ...n, is_read: true })))
      setUnread(0)
      toast('All notifications marked as read', 'success')
    } catch (e: any) {
      toast(e.message || 'Failed to mark all as read', 'error')
    } finally { setMarking(false) }
  }

  function handleClick(notif: Notification) {
    if (!notif.is_read) handleMarkRead(notif.id)
    if (notif.related_application_id) router.push('/applications')
    else if (notif.related_job_id) router.push('/jobs')
  }

  function formatTime(iso: string) {
    const date = new Date(iso)
    const now  = new Date()
    const diff = Math.floor((now.getTime() - date.getTime()) / 1000)
    if (diff < 60)    return 'Just now'
    if (diff < 3600)  return `${Math.floor(diff / 60)}m ago`
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
    return date.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })
  }

  const iconColor = (type: string) => TYPE_COLORS[type] || 'var(--text-muted)'
  const icon      = (type: string) => TYPE_ICONS[type]  || <Info size={15} />

  return (
    <AppShell
      title="Notifications"
      subtitle={unread > 0 ? `${unread} unread` : 'All caught up'}
      actions={
        unread > 0 ? (
          <button className="btn btn-ghost btn-sm" onClick={handleMarkAllRead} disabled={marking}>
            {marking ? <Spinner size="sm" /> : <CheckCheck size={14} />}
            Mark all read
          </button>
        ) : undefined
      }
    >
      <ToastContainer />

      {loading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: 60 }}><Spinner size="lg" /></div>
      ) : items.length === 0 ? (
        <EmptyState icon={<Bell size={32} />} title="No notifications yet"
          description="You will be notified when your application status changes, new job matches are found, or your coaching session is complete." />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          {items.map(notif => {
            const color    = iconColor(notif.type)
            const isUnread = !notif.is_read
            return (
              <div key={notif.id} onClick={() => handleClick(notif)}
                style={{ display: 'flex', alignItems: 'flex-start', gap: 14, padding: '14px 16px', borderRadius: 10, cursor: 'pointer', background: isUnread ? 'rgba(37,99,235,0.05)' : 'transparent', border: `1px solid ${isUnread ? 'rgba(37,99,235,0.12)' : 'transparent'}`, transition: 'all 0.15s' }}
                onMouseEnter={e => { e.currentTarget.style.background = isUnread ? 'rgba(37,99,235,0.08)' : 'var(--bg-surface)' }}
                onMouseLeave={e => { e.currentTarget.style.background = isUnread ? 'rgba(37,99,235,0.05)' : 'transparent' }}>
                <div style={{ width: 36, height: 36, borderRadius: 8, background: `${color}18`, display: 'flex', alignItems: 'center', justifyContent: 'center', color, flexShrink: 0 }}>
                  {icon(notif.type)}
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8 }}>
                    <p style={{ fontSize: 13, fontWeight: isUnread ? 600 : 400, color: 'var(--text-primary)', marginBottom: 3, lineHeight: 1.4 }}>
                      {notif.title}
                    </p>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
                      <span style={{ fontSize: 11, color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>{formatTime(notif.created_at)}</span>
                      {isUnread && <div style={{ width: 7, height: 7, borderRadius: '50%', background: 'var(--blue-core)', flexShrink: 0 }} />}
                    </div>
                  </div>
                  <p style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.55 }}>{notif.message}</p>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </AppShell>
  )
}