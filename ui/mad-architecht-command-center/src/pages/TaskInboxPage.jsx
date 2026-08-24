import { useEffect, useMemo, useState } from 'react'
import { CheckCircle2, Clock3, ListTodo, RefreshCw, Sparkles } from 'lucide-react'
import { api } from '../api/client'

const STORAGE_KEY = 'mammoth_chat_task_cards_v1'

const STATUS_LABELS = {
  queued: 'Queued',
  in_progress: 'In progress',
  complete: 'Complete',
  active: 'Active',
  pending_approval: 'Pending approval',
  completed: 'Completed',
  failed: 'Failed',
}

function normalizeStatus(value) {
  const raw = String(value || '').trim().toLowerCase()
  if (['active', 'running', 'queued', 'in_progress', 'complete', 'completed', 'pending_approval', 'failed'].includes(raw)) {
    return raw === 'running' ? 'active' : raw === 'completed' ? 'complete' : raw
  }
  return 'queued'
}

function loadCards() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

export default function TaskInboxPage() {
  const [cards, setCards] = useState(() => loadCards())
  const [source, setSource] = useState('local')
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(cards))
  }, [cards])

  const loadRemoteCards = async ({ background = false } = {}) => {
    if (!background) setLoading(true)
    setRefreshing(background)
    try {
      const remote = await api('/tasks')
      if (Array.isArray(remote)) {
        setCards(remote)
        setSource('backend')
        localStorage.setItem(STORAGE_KEY, JSON.stringify(remote))
        return
      }
      throw new Error('tasks response was not an array')
    } catch {
      setCards(loadCards())
      setSource('local')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  useEffect(() => {
    loadRemoteCards()
  }, [])

  const sorted = useMemo(
    () => [...cards].sort((a, b) => new Date(b.updated_at || b.created_at || 0) - new Date(a.updated_at || a.created_at || 0)),
    [cards],
  )

  const persistCard = async (card, nextStatus) => {
    const nextCard = { ...card, status: nextStatus, updated_at: new Date().toISOString() }
    if (source === 'backend') {
      const saved = await api('/tasks', {
        method: 'POST',
        body: {
          id: card.id,
          title: card.title || 'Untitled task',
          status: nextStatus,
          agent_id: card.agent_id || '',
          description: card.description || card.prompt || card.reply || '',
          details: {
            ...(card.details || {}),
            prompt: card.prompt || '',
            reply: card.reply || '',
            task_id: card.task_id || '',
          },
        },
      })
      return saved && typeof saved === 'object' ? saved : nextCard
    }
    return nextCard
  }

  const bumpStatus = async (card, currentStatus) => {
    const current = normalizeStatus(currentStatus)
    const nextStatus = current === 'queued' ? 'in_progress' : current === 'in_progress' ? 'complete' : 'queued'
    const optimistic = { ...card, status: nextStatus, updated_at: new Date().toISOString() }
    setCards((prev) => prev.map((item) => (item.id === card.id ? optimistic : item)))
    try {
      const saved = await persistCard(card, nextStatus)
      setCards((prev) => prev.map((item) => (item.id === card.id ? { ...item, ...saved } : item)))
    } catch {
      setSource('local')
      setCards((prev) => {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(prev))
        return prev
      })
    }
  }

  return (
    <div className="page-enter" style={{ padding: '24px', maxWidth: 1200, margin: '0 auto', width: '100%' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap', marginBottom: 20 }}>
        <div>
          <div style={{ fontSize: '0.72rem', letterSpacing: '0.14em', textTransform: 'uppercase', color: 'var(--txt-mut)', marginBottom: 8 }}>
            Operations Queue
          </div>
          <h1 style={{ margin: 0, fontSize: '1.5rem', color: 'var(--txt-pri)' }}>Task inbox</h1>
        </div>
        <div style={{ display: 'inline-flex', alignItems: 'center', gap: 8, padding: '8px 12px', borderRadius: 999, background: 'rgba(37, 99, 235, 0.1)', border: '1px solid rgba(96, 165, 250, 0.2)', color: 'var(--photon)', fontSize: '0.72rem', fontWeight: 700 }}>
          <ListTodo size={14} />
          {sorted.length} queued
          <span style={{ color: 'var(--txt-mut)', fontWeight: 600 }}>{source}</span>
          <button
            type="button"
            onClick={() => loadRemoteCards({ background: true })}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 6, background: 'transparent', border: 'none', color: 'var(--photon)', cursor: 'pointer', fontSize: '0.68rem', padding: 0 }}
          >
            <RefreshCw size={12} style={{ opacity: refreshing ? 0.6 : 1 }} />
            {refreshing ? 'Syncing' : 'Sync'}
          </button>
        </div>
      </div>

      {loading ? (
        <div style={{ color: 'var(--txt-mut)', fontSize: '0.9rem' }}>Loading task inbox…</div>
      ) : sorted.length === 0 ? (
        <div className="glass-card-solid" style={{ padding: 28, textAlign: 'center', maxWidth: 760, margin: '0 auto' }}>
          <Sparkles size={28} color="var(--cyan)" style={{ marginBottom: 12 }} />
          <h2 style={{ margin: '0 0 10px', color: 'var(--txt-pri)' }}>No active tasks yet</h2>
          <p style={{ margin: 0, color: 'var(--txt-sec)', lineHeight: 1.7 }}>
            Save a task card from Mammoth Mind or create a plan from the chat surface to populate this task inbox.
          </p>
        </div>
      ) : (
        <div style={{ display: 'grid', gap: 14 }}>
          {sorted.map((card) => {
            const status = normalizeStatus(card.status)
            const statusTone = status === 'complete' ? '#16a34a' : status === 'pending_approval' ? '#f59e0b' : status === 'failed' ? '#f87171' : '#60a5fa'
            const taskDetails = card.details && typeof card.details === 'object' ? card.details : {}

            return (
              <div key={card.id} className="glass-card-solid" style={{ padding: 16 }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 14, flexWrap: 'wrap' }}>
                  <div style={{ flex: 1, minWidth: 220 }}>
                    <div style={{ fontSize: '0.82rem', color: 'var(--txt-mut)', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.12em' }}>
                      {card.agent_id || 'agent'}
                    </div>
                    <h3 style={{ margin: 0, fontSize: '1rem', color: 'var(--txt-pri)' }}>{card.title || 'Untitled task'}</h3>
                  </div>
                  <button
                    type="button"
                    onClick={() => bumpStatus(card, status)}
                    style={{ display: 'inline-flex', alignItems: 'center', gap: 8, padding: '8px 12px', borderRadius: 10, border: '1px solid rgba(255,255,255,0.08)', background: 'rgba(255,255,255,0.03)', color: 'var(--txt-pri)', cursor: 'pointer' }}
                  >
                    {status === 'complete' ? <CheckCircle2 size={14} color={statusTone} /> : <Clock3 size={14} color={statusTone} />}
                    {STATUS_LABELS[status] || 'Queued'}
                  </button>
                </div>

                <div style={{ marginTop: 12, fontSize: '0.8rem', color: 'var(--txt-sec)', lineHeight: 1.7 }}>
                  {card.prompt || card.reply || 'No task detail was attached.'}
                </div>

                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 10 }}>
                  {card.trace_id && <span style={{ fontSize: '0.64rem', color: 'var(--txt-mut)', fontFamily: 'JetBrains Mono,monospace' }}>trace {card.trace_id}</span>}
                  {card.task_id && <span style={{ fontSize: '0.64rem', color: 'var(--txt-mut)', fontFamily: 'JetBrains Mono,monospace' }}>task {card.task_id}</span>}
                  {taskDetails.source && <span style={{ fontSize: '0.64rem', color: 'var(--txt-mut)', fontFamily: 'JetBrains Mono,monospace' }}>source {taskDetails.source}</span>}
                </div>

                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10, marginTop: 12, flexWrap: 'wrap' }}>
                  <div style={{ fontSize: '0.68rem', color: 'var(--txt-mut)' }}>
                    {card.task_id ? `task: ${card.task_id}` : 'local task'}
                  </div>
                  <div style={{ fontSize: '0.68rem', color: statusTone, fontWeight: 700 }}>
                    {status === 'complete' ? 'Done' : status === 'in_progress' ? 'Actively moving' : 'Waiting'}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
