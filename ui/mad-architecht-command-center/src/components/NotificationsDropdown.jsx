import { useEffect, useRef, useState } from 'react'
import { Bell, BellDot, CheckCheck, X, ExternalLink } from 'lucide-react'
import { api } from '../api/client'

const TYPE_COLORS = {
  system: 'var(--photon)',
  billing: '#f59e0b',
  agent: 'var(--cyan)',
  security: '#f87171',
  info: 'var(--txt-sec)',
  warning: '#f59e0b',
}

const TYPE_ICONS = {
  system: '⚙️',
  billing: '💳',
  agent: '🤖',
  security: '🔒',
  info: 'ℹ️',
  warning: '⚠️',
}

function timeAgo(isoString) {
  if (!isoString) return ''
  const diff = Date.now() - new Date(isoString).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.floor(hours / 24)}d ago`
}

export default function NotificationsDropdown() {
  const [open, setOpen] = useState(false)
  const [notifications, setNotifications] = useState([])
  const [unreadCount, setUnreadCount] = useState(0)
  const [loading, setLoading] = useState(false)
  const ref = useRef(null)

  // Poll unread count every 60 seconds
  useEffect(() => {
    let mounted = true
    const poll = async () => {
      try {
        const data = await api('/notifications/unread-count')
        if (mounted) setUnreadCount(data?.unread_count ?? 0)
      } catch {
        // ignore — auth may not be set up in all environments
      }
    }
    poll()
    const interval = setInterval(poll, 60_000)
    return () => {
      mounted = false
      clearInterval(interval)
    }
  }, [])

  // Load full list when opened
  useEffect(() => {
    if (!open) return
    setLoading(true)
    api('/notifications?limit=30')
      .then((data) => {
        setNotifications(data?.notifications ?? [])
        setUnreadCount(data?.unread_count ?? 0)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [open])

  // Close on outside click
  useEffect(() => {
    if (!open) return
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  const markRead = async (id) => {
    try {
      await api(`/notifications/${id}/read`, { method: 'PATCH' })
      setNotifications((prev) => prev.map((n) => n.id === id ? { ...n, read: true } : n))
      setUnreadCount((c) => Math.max(0, c - 1))
    } catch { /* ignore */ }
  }

  const dismiss = async (id) => {
    const was = notifications.find((n) => n.id === id)
    try {
      await api(`/notifications/${id}`, { method: 'DELETE' })
      setNotifications((prev) => prev.filter((n) => n.id !== id))
      setUnreadCount((c) => (was && !was.read) ? Math.max(0, c - 1) : c)
    } catch { /* ignore */ }
  }

  const markAllRead = async () => {
    try {
      await api('/notifications/mark-all-read', { method: 'POST', body: {} })
      setNotifications((prev) => prev.map((n) => ({ ...n, read: true })))
      setUnreadCount(0)
    } catch { /* ignore */ }
  }

  return (
    <div ref={ref} style={{ position: 'relative' }}>
      <button
        onClick={() => setOpen((v) => !v)}
        title="Notifications"
        style={{
          position: 'relative',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: 'none',
          border: '1px solid var(--border)',
          borderRadius: 8,
          color: 'var(--txt-sec)',
          padding: '6px 8px',
          cursor: 'pointer',
          flexShrink: 0,
        }}
      >
        {unreadCount > 0 ? <BellDot size={16} color="var(--photon)" /> : <Bell size={16} />}
        {unreadCount > 0 && (
          <span
            style={{
              position: 'absolute',
              top: -5,
              right: -5,
              background: 'var(--photon)',
              color: '#000',
              fontSize: '0.6rem',
              fontWeight: 800,
              borderRadius: 999,
              minWidth: 16,
              height: 16,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '0 3px',
            }}
          >
            {unreadCount > 99 ? '99+' : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div
          style={{
            position: 'absolute',
            top: 'calc(100% + 8px)',
            right: 0,
            width: 360,
            maxWidth: 'calc(100vw - 24px)',
            background: 'var(--card)',
            border: '1px solid var(--border)',
            borderRadius: 12,
            boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
            zIndex: 9999,
            overflow: 'hidden',
          }}
        >
          {/* Header */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '12px 14px 10px',
              borderBottom: '1px solid var(--border)',
            }}
          >
            <span style={{ fontWeight: 700, fontSize: '0.82rem', color: 'var(--txt-pri)' }}>
              Notifications{unreadCount > 0 && <span style={{ color: 'var(--photon)', marginLeft: 6 }}>({unreadCount} new)</span>}
            </span>
            {unreadCount > 0 && (
              <button
                onClick={markAllRead}
                title="Mark all read"
                style={{
                  background: 'none',
                  border: 'none',
                  color: 'var(--txt-sec)',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 4,
                  fontSize: '0.72rem',
                }}
              >
                <CheckCheck size={13} /> All read
              </button>
            )}
          </div>

          {/* List */}
          <div style={{ maxHeight: 380, overflowY: 'auto' }}>
            {loading && (
              <div style={{ padding: '24px 0', textAlign: 'center', color: 'var(--txt-sec)', fontSize: '0.78rem' }}>
                Loading…
              </div>
            )}
            {!loading && notifications.length === 0 && (
              <div style={{ padding: '32px 0', textAlign: 'center', color: 'var(--txt-sec)', fontSize: '0.78rem' }}>
                <Bell size={22} style={{ opacity: 0.4, marginBottom: 8, display: 'block', margin: '0 auto 8px' }} />
                You're all caught up
              </div>
            )}
            {!loading && notifications.map((n) => (
              <div
                key={n.id}
                onClick={() => !n.read && markRead(n.id)}
                style={{
                  display: 'flex',
                  gap: 10,
                  padding: '11px 14px',
                  borderBottom: '1px solid var(--border)',
                  background: n.read ? 'transparent' : 'rgba(0,149,255, 0.05)',
                  cursor: n.read ? 'default' : 'pointer',
                  transition: 'background 0.15s',
                }}
              >
                <span style={{ fontSize: '1rem', lineHeight: 1, flexShrink: 0, marginTop: 1 }}>
                  {TYPE_ICONS[n.type] || 'ℹ️'}
                </span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 6 }}>
                    <p
                      style={{
                        margin: 0,
                        fontSize: '0.78rem',
                        fontWeight: n.read ? 500 : 700,
                        color: n.read ? 'var(--txt-sec)' : 'var(--txt-pri)',
                        lineHeight: 1.35,
                      }}
                    >
                      {n.title}
                    </p>
                    <button
                      onClick={(e) => { e.stopPropagation(); dismiss(n.id) }}
                      style={{ background: 'none', border: 'none', color: 'var(--txt-mut)', cursor: 'pointer', padding: 0, flexShrink: 0, lineHeight: 1 }}
                      title="Dismiss"
                    >
                      <X size={12} />
                    </button>
                  </div>
                  <p style={{ margin: '3px 0 4px', fontSize: '0.73rem', color: 'var(--txt-sec)', lineHeight: 1.45 }}>
                    {n.body}
                  </p>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span
                      style={{
                        fontSize: '0.66rem',
                        color: TYPE_COLORS[n.type] || 'var(--txt-mut)',
                        fontWeight: 600,
                        textTransform: 'uppercase',
                        letterSpacing: '0.08em',
                      }}
                    >
                      {n.type}
                    </span>
                    <span style={{ fontSize: '0.66rem', color: 'var(--txt-mut)' }}>{timeAgo(n.created_at)}</span>
                    {n.action_url && (
                      <a
                        href={n.action_url}
                        style={{ marginLeft: 'auto', color: 'var(--photon)', fontSize: '0.68rem', display: 'flex', alignItems: 'center', gap: 2, textDecoration: 'none' }}
                        onClick={(e) => e.stopPropagation()}
                      >
                        View <ExternalLink size={10} />
                      </a>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
