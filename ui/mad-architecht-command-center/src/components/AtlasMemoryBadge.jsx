import { useEffect, useState } from 'react'
import { Brain } from 'lucide-react'
import { api } from '../api/client'

// Derive a session estimate from local chat history length
function estimateSessions() {
  try {
    const hist = JSON.parse(window.localStorage.getItem('mammoth_chat_history') || '[]')
    const turns = hist.filter((h) => h.role === 'assistant').length
    return Math.max(1, Math.ceil(turns / 4))
  } catch {
    return 1
  }
}

export default function AtlasMemoryBadge({ compact = false }) {
  const [learner, setLearner] = useState(null)
  const [sessions, setSessions] = useState(0)
  const [ping, setPing] = useState(true)

  useEffect(() => {
    setSessions(estimateSessions())
    api('/atlas/learner')
      .then((data) => setLearner(data))
      .catch(() => {})
    const t = setTimeout(() => setPing(false), 2200)
    return () => clearTimeout(t)
  }, [])

  const lm = learner?.learner_model || {}
  const focusAreas = Array.isArray(lm.onboarding?.focus_areas)
    ? lm.onboarding.focus_areas.slice(0, 2)
    : []
  const hasData = sessions > 0 || lm.version

  if (!hasData) return null

  return (
    <div
      className={ping ? 'atlas-memory-badge atlas-memory-badge--ping' : 'atlas-memory-badge'}
      title="ATLAS has persistent memory across your sessions"
    >
      <Brain size={compact ? 11 : 13} color="var(--violet)" />
      <span style={{ fontSize: compact ? '0.64rem' : '0.72rem', fontWeight: 700, color: 'var(--violet)' }}>
        ATLAS remembers you
      </span>
      {sessions > 0 && (
        <span style={{ fontSize: '0.62rem', color: 'rgba(180,124,255,0.7)', fontWeight: 600 }}>
          &nbsp;·&nbsp;{sessions} session{sessions !== 1 ? 's' : ''}
        </span>
      )}
      {focusAreas.length > 0 && !compact && (
        <span style={{ fontSize: '0.62rem', color: 'rgba(180,124,255,0.6)' }}>
          &nbsp;·&nbsp;{focusAreas.join(', ')}
        </span>
      )}
    </div>
  )
}
