import { useEffect, useMemo, useState } from 'react'
import { CheckCircle2, Clock3, ListTodo, RefreshCw, Sparkles } from 'lucide-react'
import { api } from '../api/client'

const STATUS_LABELS = {
  queued: 'Queued',
  in_progress: 'In progress',
  complete: 'Complete',
  active: 'Active',
  pending_approval: 'Pending approval',
  completed: 'Completed',
  failed: 'Failed',
  planned: 'Planned',
  partial: 'Partial',
  unknown: 'Unknown',
}

function normalizeStatus(value) {
  const raw = String(value || '').trim().toLowerCase()
  if (raw === 'ok') return 'complete'
  if (raw === 'error') return 'failed'
  if (Object.hasOwn(STATUS_LABELS, raw) || raw === 'running') {
    return raw === 'running' ? 'active' : raw === 'completed' ? 'complete' : raw
  }
  return 'unknown'
}

function isClosedStatus(status) {
  return ['complete', 'completed', 'failed'].includes(normalizeStatus(status))
}

function canManuallyMove(card) {
  return card?.status_editable === true
}

export default function TaskInboxPage() {
  const [cards, setCards] = useState([])
  const [loadError, setLoadError] = useState('')
  const [updateError, setUpdateError] = useState('')
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [pendingIds, setPendingIds] = useState([])

  const loadRemoteCards = async ({ background = false } = {}) => {
    if (!background) setLoading(true)
    setLoadError('')
    setRefreshing(background)
    try {
      const remote = await api('/tasks')
      if (Array.isArray(remote)) {
        setCards(remote)
        return
      }
      throw new Error('tasks response was not an array')
    } catch (cause) {
      if (!background) setCards([])
      setLoadError(cause.message || 'Task inbox is unavailable right now.')
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
  const openCount = useMemo(() => sorted.filter(card => !isClosedStatus(card.status)).length, [sorted])

  const persistCard = async (card, nextStatus) => {
    const saved = await api('/tasks', {
      method: 'POST',
      body: {
        id: card.id,
        status: nextStatus,
      },
    })
    if (!saved || Array.isArray(saved) || saved.id !== card.id || saved.status !== nextStatus) {
      throw new Error('Task API did not confirm the status update. Sync to check the saved state.')
    }
    return saved
  }

  const bumpStatus = async (card, currentStatus) => {
    if (!canManuallyMove(card) || pendingIds.includes(card.id)) return
    setPendingIds(previous => [...previous, card.id])
    setUpdateError('')
    const current = normalizeStatus(currentStatus)
    const nextStatus = current === 'queued' ? 'in_progress' : current === 'in_progress' ? 'complete' : 'queued'
    const optimistic = { ...card, status: nextStatus, updated_at: new Date().toISOString() }
    const original = card
    setCards((prev) => prev.map((item) => (item.id === card.id ? optimistic : item)))
    try {
      const saved = await persistCard(card, nextStatus)
      setCards((prev) => prev.map((item) => (item.id === card.id ? { ...item, ...saved } : item)))
    } catch (cause) {
      setCards((prev) => prev.map((item) => (item.id === card.id ? original : item)))
      setUpdateError(cause.message || 'Task status update failed.')
    } finally {
      setPendingIds(previous => previous.filter(id => id !== card.id))
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
          {openCount} open
          <span style={{ color: 'var(--txt-mut)', fontWeight: 600 }}>backend</span>
          <button
            type="button"
            disabled={refreshing || loading || pendingIds.length > 0}
            onClick={() => loadRemoteCards({ background: true })}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 6, background: 'transparent', border: 'none', color: 'var(--photon)', cursor: 'pointer', fontSize: '0.68rem', padding: 0 }}
          >
            <RefreshCw size={12} style={{ opacity: refreshing ? 0.6 : 1 }} />
            {refreshing ? 'Syncing' : 'Sync'}
          </button>
        </div>
      </div>

      {loadError && (
        <div role="alert" style={{ marginBottom: 14, padding: '10px 12px', borderRadius: 10, border: '1px solid rgba(248,113,113,0.34)', background: 'rgba(248,113,113,0.1)', color: '#fca5a5', fontSize: '0.8rem' }}>
          {loadError}
        </div>
      )}
      {updateError && (
        <div role="alert" style={{ marginBottom: 14, padding: '10px 12px', borderRadius: 10, border: '1px solid rgba(245,185,66,0.34)', background: 'rgba(245,185,66,0.1)', color: '#fcd34d', fontSize: '0.8rem' }}>
          {updateError}
        </div>
      )}

      {loading ? (
        <div style={{ color: 'var(--txt-mut)', fontSize: '0.9rem' }}>Loading task inbox…</div>
      ) : sorted.length === 0 ? (
        <div className="glass-card-solid" style={{ padding: 28, textAlign: 'center', maxWidth: 760, margin: '0 auto' }}>
          <Sparkles size={28} color="var(--mm-color-system-default)" style={{ marginBottom: 12 }} />
          <h2 style={{ margin: '0 0 10px', color: 'var(--txt-pri)' }}>{loadError ? 'Task inbox unavailable' : 'No active tasks yet'}</h2>
          <p style={{ margin: 0, color: 'var(--txt-sec)', lineHeight: 1.7 }}>
            {loadError ? 'Use Sync to retry. Your saved tasks have not been removed.' : 'Save a task card from Mammoth Mind or create a plan from the chat surface to populate this task inbox.'}
          </p>
        </div>
      ) : (
        <div style={{ display: 'grid', gap: 14 }}>
          {sorted.map((card) => {
            const status = normalizeStatus(card.status)
            const statusTone = (status === 'complete' || status === 'completed') ? '#16a34a' : status === 'pending_approval' ? '#f59e0b' : status === 'failed' ? '#f87171' : '#60a5fa'
            const statusEditable = canManuallyMove(card)
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
                    disabled={!statusEditable || pendingIds.includes(card.id) || refreshing}
                    onClick={() => bumpStatus(card, status)}
                    title={statusEditable ? 'Cycle queued → in progress → complete.' : 'Run-backed task status is read-only.'}
                    style={{ display: 'inline-flex', alignItems: 'center', gap: 8, padding: '8px 12px', borderRadius: 10, border: '1px solid rgba(255,255,255,0.08)', background: 'rgba(255,255,255,0.03)', color: 'var(--txt-pri)', cursor: statusEditable ? 'pointer' : 'not-allowed', opacity: statusEditable ? 1 : 0.62 }}
                  >
                    {(status === 'complete' || status === 'completed') ? <CheckCircle2 size={14} color={statusTone} /> : <Clock3 size={14} color={statusTone} />}
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
                    {card.task_id ? `task: ${card.task_id}` : `task: ${card.id}`}
                  </div>
                  <div style={{ fontSize: '0.68rem', color: statusTone, fontWeight: 700 }}>
                    {statusEditable
                      ? `Manual card ${(STATUS_LABELS[status] || STATUS_LABELS.unknown).toLowerCase()}`
                      : 'Run-backed status'}
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
