import { useEffect, useState } from 'react'
import { CheckCircle2, Circle, ChevronDown, ChevronUp, Sparkles, X } from 'lucide-react'
import { api } from '../api/client'

const DISMISS_KEY = 'mammoth.onboarding.dismissed.v1'

export default function OnboardingChecklist({ setPage }) {
  const [state, setState] = useState(null)
  const [expanded, setExpanded] = useState(true)
  const [dismissed, setDismissed] = useState(() => {
    try { return window.localStorage.getItem(DISMISS_KEY) === '1' } catch { return false }
  })
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (dismissed) return
    api('/onboarding/state')
      .then((data) => {
        if (data?.status === 'ok') setState(data)
      })
      .catch(() => {})
  }, [dismissed])

  const completeStep = async (stepId) => {
    setLoading(true)
    try {
      await api('/onboarding/complete-step', { method: 'POST', body: { step_id: stepId } })
      const data = await api('/onboarding/state')
      if (data?.status === 'ok') setState(data)
    } catch { /* ignore */ } finally { setLoading(false) }
  }

  const dismiss = () => {
    setDismissed(true)
    try { window.localStorage.setItem(DISMISS_KEY, '1') } catch { /* ignore */ }
  }

  if (dismissed || !state || state.onboarding_complete) return null

  const steps = state.steps || []
  const percent = state.percent || 0

  return (
    <div
      style={{
        background: 'var(--card)',
        border: '1px solid rgba(var(--photon-raw, 0,149,255),0.3)',
        borderLeft: '3px solid var(--photon)',
        borderRadius: 10,
        marginBottom: 16,
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          padding: '10px 14px',
          cursor: 'pointer',
        }}
        onClick={() => setExpanded((v) => !v)}
      >
        <Sparkles size={14} color="var(--photon)" />
        <div style={{ flex: 1 }}>
          <span style={{ fontSize: '0.78rem', fontWeight: 700, color: 'var(--txt-pri)' }}>
            Get started with MammothOS
          </span>
          <span style={{ fontSize: '0.7rem', color: 'var(--txt-sec)', marginLeft: 8 }}>
            {state.completed}/{state.total} steps
          </span>
        </div>
        {/* Progress bar */}
        <div style={{ width: 80, height: 5, borderRadius: 99, background: 'var(--border)', overflow: 'hidden' }}>
          <div style={{ width: `${percent}%`, height: '100%', background: 'var(--photon)', borderRadius: 99, transition: 'width 0.4s' }} />
        </div>
        <span style={{ fontSize: '0.68rem', color: 'var(--photon)', fontWeight: 700 }}>{percent}%</span>
        {expanded ? <ChevronUp size={13} color="var(--txt-sec)" /> : <ChevronDown size={13} color="var(--txt-sec)" />}
        <button
          onClick={(e) => { e.stopPropagation(); dismiss() }}
          style={{ background: 'none', border: 'none', color: 'var(--txt-mut)', cursor: 'pointer', padding: 0, lineHeight: 1 }}
          title="Dismiss onboarding"
        >
          <X size={13} />
        </button>
      </div>

      {expanded && (
        <div style={{ padding: '0 14px 12px', borderTop: '1px solid var(--border)' }}>
          {steps.map((step) => (
            <div
              key={step.id}
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: 10,
                padding: '8px 0',
                borderBottom: '1px solid rgba(255,255,255,0.04)',
                opacity: step.completed ? 0.5 : 1,
              }}
            >
              <button
                onClick={() => !step.completed && !loading && completeStep(step.id)}
                style={{
                  background: 'none',
                  border: 'none',
                  padding: 0,
                  cursor: step.completed ? 'default' : 'pointer',
                  color: step.completed ? 'var(--cyan)' : 'var(--txt-mut)',
                  flexShrink: 0,
                  marginTop: 1,
                }}
                title={step.completed ? 'Completed' : 'Mark complete'}
              >
                {step.completed ? <CheckCircle2 size={15} /> : <Circle size={15} />}
              </button>
              <div style={{ flex: 1 }}>
                <p
                  style={{
                    margin: 0,
                    fontSize: '0.77rem',
                    fontWeight: 600,
                    color: 'var(--txt-pri)',
                    textDecoration: step.completed ? 'line-through' : 'none',
                  }}
                >
                  {step.label}
                </p>
                <p style={{ margin: '2px 0 0', fontSize: '0.7rem', color: 'var(--txt-sec)', lineHeight: 1.4 }}>
                  {step.description}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
