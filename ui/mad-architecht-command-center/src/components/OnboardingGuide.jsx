import { useEffect, useMemo, useState } from 'react'
import { ArrowRight, Bot, BookOpen, CheckCircle2, Sparkles, Terminal } from 'lucide-react'

const STORAGE_KEY = 'mammoth_onboarding_v1'

export const ONBOARDING_STEPS = [
  {
    id: 'manual',
    label: 'Read the Manual page',
    detail: 'Learn prompt shape, terminal patterns, and approval-safe workflow.',
    page: 'manual',
    Icon: BookOpen,
    color: 'var(--cyan)',
  },
  {
    id: 'terminal',
    label: 'Run one Terminal command',
    detail: 'Use the in-app Terminal playbook so command usage stays in one place.',
    page: 'terminal',
    Icon: Terminal,
    color: 'var(--photon)',
  },
  {
    id: 'agent',
    label: 'Run one Agent template',
    detail: 'Use source-aware templates with scope and constraints for sharper output.',
    page: 'agent',
    Icon: Bot,
    color: 'var(--violet)',
  },
]

function loadOnboardingState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return { dismissed: false, completed: {} }
    const parsed = JSON.parse(raw)
    return {
      dismissed: Boolean(parsed?.dismissed),
      completed: parsed?.completed && typeof parsed.completed === 'object' ? parsed.completed : {},
    }
  } catch {
    return { dismissed: false, completed: {} }
  }
}

export function useOnboardingState() {
  const [state, setState] = useState(loadOnboardingState)

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
  }, [state])

  const actions = useMemo(() => ({
    markStepComplete(stepId) {
      setState((prev) => ({
        ...prev,
        dismissed: false,
        completed: { ...(prev.completed || {}), [stepId]: true },
      }))
    },
    dismiss() {
      setState((prev) => ({ ...prev, dismissed: true }))
    },
    reset() {
      setState({ dismissed: false, completed: {} })
    },
  }), [])

  return [state, actions]
}

export default function OnboardingGuide({ currentPage, setPage, variant = 'panel', className = '' }) {
  const [state, actions] = useOnboardingState()
  const completedCount = ONBOARDING_STEPS.filter((step) => state.completed?.[step.id]).length
  const nextStep = ONBOARDING_STEPS.find((step) => !state.completed?.[step.id]) || ONBOARDING_STEPS[0]
  const currentStep = ONBOARDING_STEPS.find((step) => step.page === currentPage)
  const currentStepDone = currentStep ? Boolean(state.completed?.[currentStep.id]) : false
  const percent = Math.round((completedCount / ONBOARDING_STEPS.length) * 100)

  const goToStep = (step) => {
    if (!step) return
    setPage?.(step.page)
  }

  if (state.dismissed && variant === 'banner') {
    return null
  }

  if (state.dismissed && variant === 'panel') {
    return (
      <div className={`glass-card-solid ${className}`.trim()} style={{ padding: 14, marginBottom: 16, borderLeft: '2px solid var(--photon)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
              <CheckCircle2 size={16} color="#22c55e" />
              <span style={{ fontSize: '0.82rem', fontWeight: 700, color: 'var(--txt-pri)' }}>
                {completedCount >= ONBOARDING_STEPS.length ? 'Onboarding complete' : 'Onboarding hidden'}
              </span>
            </div>
            <p style={{ margin: 0, color: 'var(--txt-sec)', fontSize: '0.78rem' }}>
              {completedCount >= ONBOARDING_STEPS.length
                ? 'You can reopen the tutorial flow at any time from Home.'
                : 'The tutorial is hidden. Restart it if you want the guided flow back.'}
            </p>
          </div>
          <button
            onClick={actions.reset}
            style={{ border: '1px solid var(--border)', background: 'rgba(255,255,255,0.04)', color: 'var(--txt-sec)', borderRadius: 8, padding: '6px 10px', fontSize: '0.74rem', cursor: 'pointer' }}
          >
            Restart tutorial
          </button>
        </div>
      </div>
    )
  }

  if (variant === 'banner') {
    return (
      <div
        className={`glass-card-solid ${className}`.trim()}
        style={{ padding: 14, marginBottom: 16, borderLeft: '2px solid var(--photon)' }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
          <div style={{ minWidth: 220 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
              <Sparkles size={16} color="var(--photon)" />
              <span style={{ fontSize: '0.82rem', fontWeight: 700, color: 'var(--txt-pri)' }}>First-run tutorial</span>
            </div>
            <p style={{ margin: 0, color: 'var(--txt-sec)', fontSize: '0.78rem', lineHeight: 1.6 }}>
              {currentStep
                ? `Step ${completedCount + (currentStepDone ? 0 : 1)} of ${ONBOARDING_STEPS.length}: ${currentStep.label}.`
                : `Finish the onboarding flow by opening ${nextStep.label}.`}
            </p>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <span style={{ fontSize: '0.7rem', color: 'var(--txt-mut)', fontFamily: 'JetBrains Mono,monospace' }}>
              {completedCount}/{ONBOARDING_STEPS.length} complete
            </span>
            {currentStep && !currentStepDone && (
              <button
                onClick={() => actions.markStepComplete(currentStep.id)}
                style={{ border: '1px solid var(--border)', background: 'rgba(255,255,255,0.04)', color: 'var(--txt-pri)', borderRadius: 8, padding: '6px 10px', fontSize: '0.74rem', cursor: 'pointer' }}
              >
                Mark step complete
              </button>
            )}
            {nextStep && nextStep.page !== currentPage && (
              <button
                onClick={() => goToStep(nextStep)}
                style={{ border: 'none', background: 'linear-gradient(90deg, var(--photon), var(--cyan))', color: '#050608', borderRadius: 8, padding: '6px 10px', fontSize: '0.74rem', fontWeight: 700, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6 }}
              >
                Next: {nextStep.label}
                <ArrowRight size={14} />
              </button>
            )}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className={`glass-card-solid ${className}`.trim()} style={{ padding: 18, marginBottom: 16, borderLeft: '2px solid var(--photon)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center', flexWrap: 'wrap', marginBottom: 10 }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
            <Sparkles size={16} color="var(--photon)" />
            <span style={{ fontSize: '0.82rem', fontWeight: 700, color: 'var(--txt-pri)' }}>First-run workflow</span>
          </div>
          <p style={{ fontSize: '0.8rem', color: 'var(--txt-sec)', margin: 0, lineHeight: 1.6, maxWidth: 720 }}>
            Follow this once to lock in agent prompting, terminal usage, and safe execution defaults.
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          <div style={{ fontSize: '0.72rem', fontFamily: 'JetBrains Mono,monospace', color: 'var(--txt-mut)' }}>
            {completedCount}/{ONBOARDING_STEPS.length} complete
          </div>
          <div style={{ minWidth: 100, height: 8, borderRadius: 999, background: 'rgba(255,255,255,0.06)', overflow: 'hidden' }}>
            <div style={{ width: `${percent}%`, height: '100%', background: 'linear-gradient(90deg, var(--photon), var(--cyan))' }} />
          </div>
          <button
            onClick={actions.dismiss}
            style={{ border: '1px solid var(--border)', background: 'rgba(255,255,255,0.04)', color: 'var(--txt-sec)', borderRadius: 8, padding: '6px 10px', fontSize: '0.74rem', cursor: 'pointer' }}
          >
            Hide onboarding
          </button>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(220px,1fr))', gap: 10 }}>
        {ONBOARDING_STEPS.map((step) => {
          const done = Boolean(state.completed?.[step.id])
          const Icon = step.Icon
          return (
            <button
              key={step.id}
              onClick={() => {
                actions.markStepComplete(step.id)
                goToStep(step)
              }}
              style={{
                textAlign: 'left',
                padding: '10px 12px',
                borderRadius: 10,
                border: `1px solid ${done ? 'rgba(34,197,94,0.35)' : 'var(--border)'}`,
                background: done ? 'rgba(34,197,94,0.06)' : 'rgba(255,255,255,0.03)',
                cursor: 'pointer',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                {done ? <CheckCircle2 size={14} color="#22c55e" /> : <Icon size={14} color={step.color} />}
                <span style={{ fontSize: '0.76rem', color: 'var(--txt-pri)', fontWeight: 600 }}>{step.label}</span>
              </div>
              <div style={{ fontSize: '0.72rem', color: 'var(--txt-sec)', lineHeight: 1.5 }}>{step.detail}</div>
            </button>
          )
        })}
      </div>
    </div>
  )
}
