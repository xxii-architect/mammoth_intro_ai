import { useState } from 'react'

function MammothLogo({ size = 84, style = {} }) {
  const [errored, setErrored] = useState(false)

  if (errored) {
    return (
      <div
        style={{
          width: size,
          height: size,
          display: 'grid',
          placeItems: 'center',
          borderRadius: 22,
          background: 'linear-gradient(135deg, rgba(77,166,255,0.18), rgba(180,124,255,0.18))',
          border: '1px solid rgba(255,255,255,0.1)',
          fontSize: Math.max(24, size * 0.46),
          ...style,
        }}
      >
        🐘
      </div>
    )
  }

  return (
    <img
      src="/branding/mammoth-logo.png"
      alt="MammothOS logo"
      width={size}
      height={size}
      onError={() => setErrored(true)}
      style={{
        width: size,
        height: size,
        objectFit: 'contain',
        borderRadius: 20,
        display: 'block',
        ...style,
      }}
    />
  )
}

const FEATURE_COLUMNS = [
  {
    title: 'Adaptive tutoring engine',
    items: [
      'ATLAS adjusts pacing, difficulty, and coaching depth from your real performance.',
      'Learner memory tracks confidence, weak concepts, and recovery patterns.',
      'Every lesson can resume with recap, flashcards, quiz, and next steps.',
    ],
  },
  {
    title: 'Multi-agent execution layer',
    items: [
      'Planner, tutor, coding, research, and safety agents can coordinate around one objective.',
      'Plan + Execute runs stay visible through traceable steps and runtime notices.',
      'Fallback model routing keeps workflows moving during provider outages or quota issues.',
    ],
  },
  {
    title: 'Trust-first operator controls',
    items: [
      'Approval-gated actions help keep powerful automations reviewable.',
      'Audit export, observability runs, and active project context are built in.',
      'Workspace account isolation prevents one learner profile from leaking into another.',
    ],
  },
]

const TRUST_POINTS = [
  'Local-first session support',
  'No-cheat tutoring guardrails',
  'Approval-gated code actions',
  'Runtime fallback notices',
  'Workspace multi-account onboarding',
  'Audit + observability surfaces',
]

const WORKFLOW_STEPS = [
  {
    label: '01',
    title: 'Set up a workspace account',
    text: 'Create a learner or operator identity for this workspace so progress, entitlements, and session state stay scoped correctly.',
  },
  {
    label: '02',
    title: 'Start an adaptive lesson',
    text: 'ATLAS builds a lesson from your topic, learner context, and module track instead of dropping you into a generic chat.',
  },
  {
    label: '03',
    title: 'Review the agent plan',
    text: 'Planner, tutor, and support agents produce visible checkpoints and safe next actions before execution.',
  },
  {
    label: '04',
    title: 'Ship with confidence',
    text: 'Use audit trails, runtime status, and approval gates to keep product work explainable and operationally safe.',
  },
]

export default function LandingPage({ setPage }) {
  return (
    <div className="page-enter" style={{ padding: '32px 20px 70px', maxWidth: 1180, margin: '0 auto' }}>
      <div
        style={{
          position: 'relative',
          overflow: 'hidden',
          padding: '36px 30px 44px',
          borderRadius: 30,
          border: '1px solid rgba(255,255,255,0.08)',
          background: 'radial-gradient(circle at top left, rgba(77,166,255,0.18), transparent 28%), radial-gradient(circle at top right, rgba(180,124,255,0.18), transparent 30%), rgba(13,17,23,0.94)',
          boxShadow: '0 20px 60px rgba(0,0,0,0.35)',
        }}
      >
        <div
          style={{
            position: 'absolute',
            inset: 0,
            background: 'linear-gradient(135deg, rgba(255,255,255,0.02), transparent 52%, rgba(0,245,212,0.03))',
            pointerEvents: 'none',
          }}
        />

        <div style={{ position: 'relative', zIndex: 1 }}>
          <div style={{ textAlign: 'center', marginBottom: 30 }}>
            <div
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: 110,
                height: 110,
                borderRadius: 28,
                background: 'linear-gradient(135deg, rgba(77,166,255,0.18), rgba(180,124,255,0.16))',
                border: '1px solid rgba(255,255,255,0.1)',
                boxShadow: '0 0 30px rgba(77,166,255,0.18)',
                marginBottom: 18,
              }}
            >
              <MammothLogo size={80} />
            </div>

            <div
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 8,
                border: '1px solid rgba(255,255,255,0.08)',
                background: 'rgba(255,255,255,0.03)',
                borderRadius: 999,
                padding: '7px 12px',
                marginBottom: 18,
                color: 'var(--txt-sec)',
                fontSize: '0.72rem',
                letterSpacing: '0.12em',
                textTransform: 'uppercase',
              }}
            >
              <span style={{ color: 'var(--cyan)' }}>MammothOS</span>
              <span>•</span>
              <span>Adaptive tutor + agent workspace</span>
            </div>

            <h1
              style={{
                margin: '0 0 12px',
                fontSize: 'clamp(2.5rem, 5vw, 4.2rem)',
                fontWeight: 800,
                letterSpacing: '-0.045em',
                background: 'linear-gradient(90deg, var(--photon), var(--cyan), var(--violet))',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
                backgroundClip: 'text',
                lineHeight: 1.02,
              }}
            >
              Learn, build, and operate with a real cognitive system.
            </h1>

            <p style={{ fontSize: '1.04rem', color: 'var(--txt-sec)', maxWidth: 780, margin: '0 auto 26px', lineHeight: 1.72 }}>
              ATLAS gives you structured tutoring, memory-backed progression, and visible multi-agent execution so you can grow real skill instead of chasing answer-shaped shortcuts.
            </p>

            <div style={{ display: 'flex', gap: 14, justifyContent: 'center', flexWrap: 'wrap', marginBottom: 18 }}>
              <button
                onClick={() => setPage('atlas')}
                style={{
                  padding: '13px 28px',
                  borderRadius: 12,
                  border: 'none',
                  background: 'linear-gradient(90deg, var(--photon), var(--cyan))',
                  color: '#050608',
                  fontWeight: 800,
                  fontSize: '0.96rem',
                  cursor: 'pointer',
                  boxShadow: '0 12px 30px rgba(77,166,255,0.28)',
                }}
              >
                Open ATLAS Tutor
              </button>
              <button
                onClick={() => setPage('settings')}
                style={{
                  padding: '13px 28px',
                  borderRadius: 12,
                  border: '1px solid rgba(255,255,255,0.08)',
                  background: 'rgba(255,255,255,0.02)',
                  color: 'var(--txt-pri)',
                  fontWeight: 700,
                  fontSize: '0.96rem',
                  cursor: 'pointer',
                }}
              >
                Set Up Workspace Accounts
              </button>
            </div>

            <div style={{ display: 'flex', justifyContent: 'center', gap: 10, flexWrap: 'wrap' }}>
              {['Structured lessons', 'Visible agent steps', 'Safe plan execution', 'Local-first onboarding'].map((pill) => (
                <span key={pill} style={{ padding: '6px 10px', borderRadius: 999, border: '1px solid rgba(255,255,255,0.08)', background: 'rgba(255,255,255,0.03)', color: 'var(--txt-sec)', fontSize: '0.76rem' }}>
                  {pill}
                </span>
              ))}
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 14 }}>
            {[
              { label: 'Primary mode', value: 'Adaptive tutoring' },
              { label: 'Execution model', value: 'Multi-agent, traceable' },
              { label: 'Account model', value: 'Workspace multi-account' },
              { label: 'Trust posture', value: 'Guardrails + approvals' },
            ].map((item) => (
              <div key={item.label} className="glass-card-solid" style={{ padding: '14px 16px', borderRadius: 16 }}>
                <div style={{ fontSize: '0.72rem', color: 'var(--txt-mut)', textTransform: 'uppercase', letterSpacing: '0.12em', marginBottom: 6 }}>{item.label}</div>
                <div style={{ fontSize: '0.92rem', color: 'var(--txt-pri)', fontWeight: 700 }}>{item.value}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div style={{ padding: '54px 0 26px' }}>
        <div style={{ textAlign: 'center', marginBottom: 28 }}>
          <p style={{ fontSize: '0.72rem', letterSpacing: '0.18em', textTransform: 'uppercase', color: 'var(--txt-mut)', marginBottom: 8 }}>
            Why teams and learners stick with it
          </p>
          <h2 style={{ fontSize: '1.8rem', fontWeight: 700, color: 'var(--txt-pri)', margin: 0 }}>
            Built for durable progress, not disposable prompts.
          </h2>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 18 }}>
          {FEATURE_COLUMNS.map((column) => (
            <div key={column.title} className="glass-card-solid" style={{ padding: '22px 22px 18px', borderRadius: 18 }}>
              <h3 style={{ margin: '0 0 12px', fontSize: '0.98rem', fontWeight: 700, color: 'var(--photon)' }}>{column.title}</h3>
              <div style={{ display: 'grid', gap: 10 }}>
                {column.items.map((item) => (
                  <div key={item} style={{ fontSize: '0.85rem', color: 'var(--txt-sec)', lineHeight: 1.6, display: 'flex', gap: 8 }}>
                    <span style={{ color: 'var(--cyan)' }}>✓</span>
                    <span>{item}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div style={{ borderTop: '1px solid var(--border)', padding: '42px 0 24px' }}>
        <div style={{ textAlign: 'center', marginBottom: 26 }}>
          <p style={{ fontSize: '0.72rem', letterSpacing: '0.18em', textTransform: 'uppercase', color: 'var(--txt-mut)', marginBottom: 8 }}>
            How the experience flows
          </p>
          <h2 style={{ fontSize: '1.7rem', fontWeight: 700, color: 'var(--txt-pri)', margin: 0 }}>
            From onboarding to execution in four steps.
          </h2>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 16 }}>
          {WORKFLOW_STEPS.map((step) => (
            <div key={step.label} className="glass-card-solid" style={{ padding: '20px 18px', borderRadius: 18 }}>
              <div style={{ fontSize: '0.78rem', color: 'var(--cyan)', fontWeight: 800, letterSpacing: '0.12em', marginBottom: 10 }}>{step.label}</div>
              <h3 style={{ margin: '0 0 8px', fontSize: '0.95rem', color: 'var(--txt-pri)' }}>{step.title}</h3>
              <p style={{ margin: 0, fontSize: '0.84rem', color: 'var(--txt-sec)', lineHeight: 1.6 }}>{step.text}</p>
            </div>
          ))}
        </div>
      </div>

      <div style={{ borderTop: '1px solid var(--border)', padding: '42px 0 18px' }}>
        <div className="glass-card-solid" style={{ padding: '24px 24px 18px', borderRadius: 20 }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 18, flexWrap: 'wrap' }}>
            <div style={{ flex: '1 1 360px' }}>
              <p style={{ fontSize: '0.72rem', letterSpacing: '0.18em', textTransform: 'uppercase', color: 'var(--txt-mut)', marginBottom: 8 }}>
                Trust signals
              </p>
              <h2 style={{ margin: '0 0 10px', fontSize: '1.45rem', color: 'var(--txt-pri)' }}>
                Product polish matters, but trust posture is what makes the system usable.
              </h2>
              <p style={{ margin: 0, fontSize: '0.88rem', color: 'var(--txt-sec)', lineHeight: 1.68 }}>
                MammothOS is being shaped as a serious learning and operator environment: guarded tutoring, workspace-scoped onboarding, explainable execution, and upgrade paths toward stronger compliance and team delivery.
              </p>
            </div>
            <div style={{ flex: '1 1 320px', display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 10 }}>
              {TRUST_POINTS.map((point) => (
                <div key={point} style={{ padding: '10px 12px', borderRadius: 10, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)', fontSize: '0.8rem', color: 'var(--txt-sec)' }}>
                  {point}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div style={{ borderTop: '1px solid var(--border)', paddingTop: 24, marginTop: 36, textAlign: 'center' }}>
        <p style={{ fontSize: '0.78rem', color: 'var(--txt-mut)', marginBottom: 12 }}>
          © 2026 MammothOS. Educational AI software with safety, progress, and operator clarity at the center.
        </p>
        <div style={{ display: 'flex', gap: 16, justifyContent: 'center', marginBottom: 8, flexWrap: 'wrap' }}>
          <button onClick={() => setPage('pricing')} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--txt-mut)', fontSize: '0.78rem', padding: 0, textDecoration: 'underline' }}>
            Pricing
          </button>
          <button onClick={() => setPage('compliance')} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--txt-mut)', fontSize: '0.78rem', padding: 0, textDecoration: 'underline' }}>
            Legal & Compliance
          </button>
          <button onClick={() => setPage('settings')} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--txt-mut)', fontSize: '0.78rem', padding: 0, textDecoration: 'underline' }}>
            Workspace Setup
          </button>
        </div>
      </div>
    </div>
  )
}
