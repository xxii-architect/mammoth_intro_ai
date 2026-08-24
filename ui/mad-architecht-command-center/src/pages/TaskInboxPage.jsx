import { useEffect, useMemo, useState } from 'react'
import { CheckCircle2, Clock3, ListTodo, Sparkles } from 'lucide-react'

const STORAGE_KEY = 'mammoth_chat_task_cards_v1'

const STATUS_LABELS = {
  queued: 'Queued',
  in_progress: 'In progress',
  complete: 'Complete',
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

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(cards))
  }, [cards])

  const sorted = useMemo(
    () => [...cards].sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0)),
    [cards],
  )

  const bumpStatus = (id, currentStatus) => {
    const nextStatus = currentStatus === 'queued' ? 'in_progress' : currentStatus === 'in_progress' ? 'complete' : 'queued'
    setCards((prev) => prev.map((card) => (card.id === id ? { ...card, status: nextStatus } : card)))
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
        </div>
      </div>

      {sorted.length === 0 ? (
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
            const status = card.status || 'queued'
            const statusTone = status === 'complete' ? '#16a34a' : status === 'in_progress' ? '#f59e0b' : '#60a5fa'

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
                    onClick={() => bumpStatus(card.id, status)}
                    style={{ display: 'inline-flex', alignItems: 'center', gap: 8, padding: '8px 12px', borderRadius: 10, border: '1px solid rgba(255,255,255,0.08)', background: 'rgba(255,255,255,0.03)', color: 'var(--txt-pri)', cursor: 'pointer' }}
                  >
                    {status === 'complete' ? <CheckCircle2 size={14} color={statusTone} /> : <Clock3 size={14} color={statusTone} />}
                    {STATUS_LABELS[status] || 'Queued'}
                  </button>
                </div>

                <div style={{ marginTop: 12, fontSize: '0.8rem', color: 'var(--txt-sec)', lineHeight: 1.7 }}>
                  {card.prompt || card.reply || 'No task detail was attached.'}
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
