import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from 'react'
import { MessageSquare, Plus, Trash2, Pencil, Check, X } from 'lucide-react'
import { api, authorizedFetch } from '../api/client'

function formatRelativeTime(iso) {
  if (!iso) return ''
  const diff = Date.now() - new Date(iso).getTime()
  const m = Math.floor(diff / 60000)
  if (m < 1) return 'just now'
  if (m < 60) return `${m}m ago`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}h ago`
  const d = Math.floor(h / 24)
  return `${d}d ago`
}

const ChatThreadSidebar = forwardRef(function ChatThreadSidebar({ activeThreadId, onSelectThread, onNewThread, scopeUserId }, ref) {
  const [threads, setThreads] = useState([])

  useImperativeHandle(ref, () => ({
    reload: loadThreads,
  }))
  const [loading, setLoading] = useState(true)
  const [editingId, setEditingId] = useState(null)
  const [editTitle, setEditTitle] = useState('')
  const editRef = useRef(null)

  const loadThreads = async () => {
    try {
      const data = await api('/mammoth/chat/threads')
      setThreads(Array.isArray(data?.threads) ? data.threads : [])
    } catch {
      setThreads([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadThreads()
  }, [scopeUserId])

  useEffect(() => {
    if (editingId && editRef.current) editRef.current.focus()
  }, [editingId])

  const handleDelete = async (e, threadId) => {
    e.stopPropagation()
    try {
      await authorizedFetch(`/mammoth/chat/threads/${threadId}`, { method: 'DELETE' })
      setThreads(prev => prev.filter(t => t.id !== threadId))
      if (activeThreadId === threadId) onSelectThread(null)
    } catch { /* no-op */ }
  }

  const startEdit = (e, thread) => {
    e.stopPropagation()
    setEditingId(thread.id)
    setEditTitle(thread.title || '')
  }

  const commitEdit = async (threadId) => {
    if (!editTitle.trim()) { setEditingId(null); return }
    try {
      await authorizedFetch(`/mammoth/chat/threads/${threadId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: editTitle.trim() }),
      })
      setThreads(prev => prev.map(t => t.id === threadId ? { ...t, title: editTitle.trim() } : t))
    } catch { /* no-op */ }
    setEditingId(null)
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: 'rgba(0,0,0,0.18)', borderRight: '1px solid var(--border)' }}>
      {/* Header */}
      <div style={{ padding: '14px 14px 10px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.14em', color: 'var(--txt-mut)', fontWeight: 700 }}>Chats</span>
        <button
          onClick={onNewThread}
          title="New chat"
          style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '5px 9px', borderRadius: 7, border: '1px solid rgba(99,102,241,0.35)', background: 'rgba(99,102,241,0.12)', color: 'var(--photon)', cursor: 'pointer', fontSize: '0.72rem', fontWeight: 600 }}
        >
          <Plus size={12} /> New
        </button>
      </div>

      {/* Thread list */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '6px 6px' }}>
        {loading && (
          <p style={{ fontSize: '0.76rem', color: 'var(--txt-mut)', padding: '12px 8px', margin: 0 }}>Loading…</p>
        )}
        {!loading && threads.length === 0 && (
          <p style={{ fontSize: '0.76rem', color: 'var(--txt-mut)', padding: '12px 8px', margin: 0, lineHeight: 1.6 }}>
            No chats yet. Hit New to start your first conversation.
          </p>
        )}
        {threads.map((thread) => {
          const isActive = thread.id === activeThreadId
          return (
            <div
              key={thread.id}
              onClick={() => onSelectThread(thread.id)}
              style={{
                padding: '9px 10px',
                borderRadius: 9,
                marginBottom: 3,
                background: isActive ? 'rgba(77,166,255,0.1)' : 'transparent',
                border: `1px solid ${isActive ? 'rgba(77,166,255,0.22)' : 'transparent'}`,
                cursor: 'pointer',
                position: 'relative',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
                <MessageSquare size={13} color={isActive ? 'var(--photon)' : 'var(--txt-mut)'} style={{ marginTop: 2, flexShrink: 0 }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  {editingId === thread.id ? (
                    <div style={{ display: 'flex', gap: 4 }} onClick={e => e.stopPropagation()}>
                      <input
                        ref={editRef}
                        value={editTitle}
                        onChange={e => setEditTitle(e.target.value)}
                        onKeyDown={e => { if (e.key === 'Enter') commitEdit(thread.id); if (e.key === 'Escape') setEditingId(null) }}
                        style={{ flex: 1, fontSize: '0.78rem', background: 'rgba(255,255,255,0.08)', border: '1px solid rgba(255,255,255,0.18)', borderRadius: 5, color: 'var(--txt-pri)', padding: '2px 6px', outline: 'none' }}
                      />
                      <button onClick={() => commitEdit(thread.id)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#22c55e', padding: 2 }}><Check size={12} /></button>
                      <button onClick={() => setEditingId(null)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--txt-mut)', padding: 2 }}><X size={12} /></button>
                    </div>
                  ) : (
                    <div style={{ fontSize: '0.78rem', color: isActive ? 'var(--txt-pri)' : 'var(--txt-sec)', fontWeight: isActive ? 600 : 400, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', lineHeight: 1.4 }}>
                      {thread.title || 'Conversation'}
                    </div>
                  )}
                  <div style={{ fontSize: '0.64rem', color: 'var(--txt-mut)', marginTop: 2, display: 'flex', gap: 6 }}>
                    <span>{formatRelativeTime(thread.updated_at)}</span>
                    {thread.message_count > 0 && <span>· {thread.message_count} msg{thread.message_count !== 1 ? 's' : ''}</span>}
                  </div>
                </div>
              </div>

              {/* Hover actions */}
              {!editingId && (
                <div style={{ position: 'absolute', right: 6, top: '50%', transform: 'translateY(-50%)', display: 'flex', gap: 3, opacity: 0 }}
                  className="thread-actions"
                  onMouseEnter={e => { e.currentTarget.style.opacity = 1 }}
                >
                  <button onClick={e => startEdit(e, thread)} title="Rename" style={{ background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 5, cursor: 'pointer', color: 'var(--txt-mut)', padding: '3px 4px', display: 'flex', alignItems: 'center' }}>
                    <Pencil size={10} />
                  </button>
                  <button onClick={e => handleDelete(e, thread.id)} title="Delete" style={{ background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.18)', borderRadius: 5, cursor: 'pointer', color: '#f87171', padding: '3px 4px', display: 'flex', alignItems: 'center' }}>
                    <Trash2 size={10} />
                  </button>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
)

export default ChatThreadSidebar
