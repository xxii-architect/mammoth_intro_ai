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

const LIVE_SIGNAL_CARDS = [
  {
    label: 'Mammoth Mind',
    value: 'Multi-thread, repo-aware, file-attachable',
  },
  {
    label: 'ATLAS Tutor',
    value: 'Adaptive lanes + Monaco lesson workspace',
  },
  {
    label: 'Trust posture',
    value: 'Guide steps, approvals, fallback-aware runtime',
  },
  {
    label: 'Learning context',
    value: 'Materials library, recap, quiz, review, flashcards',
  },
]

const DIFFERENTIATORS = [
  {
    title: 'Context before charisma',
    body: 'MammothOS is designed to attach the right page, lesson, repo, and workflow context before asking the model to speak.',
  },
  {
    title: 'Agent surfaces, not just a chat box',
    body: 'Guide, Tutor, Build, Agent, and Terminal each serve a different job so users are not forced into one overloaded UI pattern.',
  },
  {
    title: 'Learning loops with memory',
    body: 'ATLAS is built to coach through recap, practice, feedback, weak-concept recovery, and next-step pacing instead of one-shot answers.',
  },
  {
    title: 'Operator-grade trust controls',
    body: 'Approval gates, runtime notices, observability, and artifact capture make the system safer to use in real workflows.',
  },
]

const CURRENT_HIGHLIGHTS = [
  'Expandable guide steps are wired in Mammoth Mind and ATLAS Assistant.',
  'Repo-aware guidance now pairs with multi-thread chat and attachment support.',
  'ATLAS lessons use Monaco-based editing and structured exercise support.',
  'Learning materials and generated artifacts now have cleaner homes inside the app.',
]

const ROLE_PATHS = [
  {
    title: 'For learners',
    subtitle: 'Start with a real lesson loop, not a blank prompt.',
    page: 'lessons',
    accent: 'var(--cyan)',
    action: 'Open Lessons',
  },
  {
    title: 'For builders',
    subtitle: 'Ground your work in repo context and execution flow.',
    page: 'chat',
    accent: 'var(--photon)',
    action: 'Open Mammoth Mind',
  },
  {
    title: 'For operators',
    subtitle: 'Stay audit-ready with status, approvals, and artifacts.',
    page: 'agent',
    accent: 'var(--violet)',
    action: 'Open Agent',
  },
]

const JOURNEYS = [
  {
    audience: 'For learners',
    headline: 'Start with a topic, not a prompt recipe.',
    body: 'ATLAS builds a lesson, adapts pacing, tracks weak concepts, and gives recap, quiz, review, and flashcard follow-through.',
    primaryLabel: 'Open Lessons',
    primaryPage: 'lessons',
    secondaryLabel: 'Open ATLAS Tutor',
    secondaryPage: 'atlas',
  },
  {
    audience: 'For builders',
    headline: 'Inspect, guide, and ship from one workspace.',
    body: 'Use Mammoth Mind for repo-aware /guide flows, the Agent page for plan/execute, and the Command Library for high-signal prompts.',
    primaryLabel: 'Open Mammoth Mind',
    primaryPage: 'chat',
    secondaryLabel: 'Open Command Library',
    secondaryPage: 'commandlib',
  },
  {
    audience: 'For operators',
    headline: 'Keep power visible and reviewable.',
    body: 'Use runtime banners, approvals, artifacts, and task tracking to keep advanced automation explainable instead of magical.',
    primaryLabel: 'Open Agent',
    primaryPage: 'agent',
    secondaryLabel: 'Open Manual',
    secondaryPage: 'manual',
  },
]

const FLOW = [
  {
    step: '01',
    title: 'Ground the session',
    text: 'Pick the right surface, the right lane, and the correct repo path for the backend you are actually using.',
  },
  {
    step: '02',
    title: 'Ask with intent',
    text: 'Name the file, symbol, concept, or lesson outcome you want instead of relying on generic open-ended phrasing.',
  },
  {
    step: '03',
    title: 'Review the structured output',
    text: 'Use guide steps, adaptive feedback, artifacts, and visible run status to understand what the system is actually doing.',
  },
  {
    step: '04',
    title: 'Verify and keep momentum',
    text: 'Build, test, save artifacts, or move the work into a thread or task so it stays durable after the chat scrolls away.',
  },
]

const DOCS = [
  {
    title: 'Manual',
    body: 'The clean operator and tester map for current surfaces, repo context, and validation habits.',
    page: 'manual',
  },
  {
    title: 'Command Library',
    body: 'Rich prompt recipes for Guide, ATLAS lanes, attachments, research, and operator execution.',
    page: 'commandlib',
  },
  {
    title: 'Pricing & Packaging',
    body: 'The buyer-facing story for the platform, the SDK, and the embeddable ATLAS FAB.',
    page: 'pricing',
  },
]

export default function LandingPage({ setPage }) {
  return (
    <div className="page-enter" style={{ padding: '32px 20px 72px', maxWidth: 1180, margin: '0 auto' }}>
      <div
        style={{
          position: 'relative',
          overflow: 'hidden',
          padding: '38px 30px 44px',
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
          <div style={{ textAlign: 'center', marginBottom: 28 }}>
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
              <span>Adaptive agent workspace + tutoring engine</span>
            </div>

            <h1
              style={{
                margin: '0 0 12px',
                fontSize: 'clamp(2.45rem, 5vw, 4.25rem)',
                fontWeight: 800,
                letterSpacing: '-0.045em',
                background: 'linear-gradient(90deg, var(--photon), var(--cyan), var(--violet))',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
                backgroundClip: 'text',
                lineHeight: 1.02,
              }}
            >
              The learning OS where guidance, execution, and trust finally live in one place.
            </h1>

            <p style={{ fontSize: '1.04rem', color: 'var(--txt-sec)', maxWidth: 820, margin: '0 auto 26px', lineHeight: 1.72 }}>
              MammothOS combines Mammoth Mind, ATLAS Tutor, agent orchestration, materials-aware learning, and buyer-ready packaging into one coherent system instead of a pile of disconnected AI demos.
            </p>

            <div style={{ display: 'flex', gap: 14, justifyContent: 'center', flexWrap: 'wrap', marginBottom: 18 }}>
              <button
                onClick={() => setPage('chat')}
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
                Open Mammoth Mind
              </button>
              <button
                onClick={() => setPage('atlas')}
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
                Open ATLAS Tutor
              </button>
            </div>

            <div style={{ display: 'flex', justifyContent: 'center', gap: 10, flexWrap: 'wrap' }}>
              {['Guide steps', 'ATLAS lanes', 'Repo-aware context', 'Materials library', 'Artifacts + tasks'].map((pill) => (
                <span key={pill} style={{ padding: '6px 10px', borderRadius: 999, border: '1px solid rgba(255,255,255,0.08)', background: 'rgba(255,255,255,0.03)', color: 'var(--txt-sec)', fontSize: '0.76rem' }}>
                  {pill}
                </span>
              ))}
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 14 }}>
            {LIVE_SIGNAL_CARDS.map((item) => (
              <div key={item.label} className="glass-card-solid" style={{ padding: '14px 16px', borderRadius: 16 }}>
                <div style={{ fontSize: '0.72rem', color: 'var(--txt-mut)', textTransform: 'uppercase', letterSpacing: '0.12em', marginBottom: 6 }}>{item.label}</div>
                <div style={{ fontSize: '0.92rem', color: 'var(--txt-pri)', fontWeight: 700, lineHeight: 1.45 }}>{item.value}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div style={{ padding: '52px 0 24px' }}>
        <div className="glass-card-solid" style={{ padding: '18px 20px', borderRadius: 18, marginBottom: 24, border: '1px solid rgba(0,245,212,0.35)' }}>
          <div style={{ fontSize: '0.72rem', letterSpacing: '0.14em', textTransform: 'uppercase', color: 'var(--cyan)', marginBottom: 10 }}>
            Current status
          </div>
          <div style={{ display: 'grid', gap: 8 }}>
            {CURRENT_HIGHLIGHTS.map((line) => (
              <div key={line} style={{ fontSize: '0.83rem', color: 'var(--txt-sec)', lineHeight: 1.6, display: 'flex', gap: 8 }}>
                <span style={{ color: 'var(--cyan)' }}>✓</span>
                <span>{line}</span>
              </div>
            ))}
          </div>
        </div>

        <div style={{ marginBottom: 26 }}>
          <div style={{ textAlign: 'center', marginBottom: 18 }}>
            <p style={{ fontSize: '0.72rem', letterSpacing: '0.18em', textTransform: 'uppercase', color: 'var(--txt-mut)', marginBottom: 8 }}>
              Start in the right lane
            </p>
            <h2 style={{ fontSize: '1.8rem', fontWeight: 700, color: 'var(--txt-pri)', margin: 0 }}>
              Pick the path that matches the work in front of you.
            </h2>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 16 }}>
            {ROLE_PATHS.map((role) => (
              <button
                key={role.title}
                onClick={() => setPage(role.page)}
                style={{
                  textAlign: 'left',
                  borderRadius: 18,
                  padding: '18px 18px 16px',
                  border: `1px solid ${role.accent}33`,
                  background: 'rgba(255,255,255,0.02)',
                  cursor: 'pointer',
                  color: 'var(--txt-pri)',
                  boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.03)',
                }}
              >
                <div style={{ color: role.accent, fontSize: '0.7rem', letterSpacing: '0.14em', textTransform: 'uppercase', fontWeight: 700, marginBottom: 6 }}>
                  {role.title}
                </div>
                <div style={{ fontSize: '0.96rem', fontWeight: 700, marginBottom: 8 }}>{role.subtitle}</div>
                <div style={{ display: 'inline-flex', alignItems: 'center', gap: 8, color: 'var(--txt-sec)', fontSize: '0.76rem', fontWeight: 700 }}>
                  {role.action}
                  <span aria-hidden="true">→</span>
                </div>
              </button>
            ))}
          </div>
        </div>

        <div style={{ textAlign: 'center', marginBottom: 28 }}>
          <p style={{ fontSize: '0.72rem', letterSpacing: '0.18em', textTransform: 'uppercase', color: 'var(--txt-mut)', marginBottom: 8 }}>
            Why MammothOS feels different
          </p>
          <h2 style={{ fontSize: '1.8rem', fontWeight: 700, color: 'var(--txt-pri)', margin: 0 }}>
            It is built around context, journeys, and verification instead of prompt theater.
          </h2>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: 18 }}>
          {DIFFERENTIATORS.map((item) => (
            <div key={item.title} className="glass-card-solid" style={{ padding: '22px 22px 18px', borderRadius: 18 }}>
              <h3 style={{ margin: '0 0 12px', fontSize: '1rem', fontWeight: 700, color: 'var(--photon)' }}>{item.title}</h3>
              <div style={{ fontSize: '0.85rem', color: 'var(--txt-sec)', lineHeight: 1.65 }}>{item.body}</div>
            </div>
          ))}
        </div>
      </div>

      <div style={{ borderTop: '1px solid var(--border)', padding: '42px 0 24px' }}>
        <div style={{ textAlign: 'center', marginBottom: 28 }}>
          <p style={{ fontSize: '0.72rem', letterSpacing: '0.18em', textTransform: 'uppercase', color: 'var(--txt-mut)', marginBottom: 8 }}>
            Choose your entry point
          </p>
          <h2 style={{ fontSize: '1.8rem', fontWeight: 700, color: 'var(--txt-pri)', margin: 0 }}>
            Three strong journeys, one MammothOS system.
          </h2>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 20 }}>
          {JOURNEYS.map((journey) => (
            <div key={journey.audience} className="glass-card-solid" style={{ padding: '24px 22px', borderRadius: 20, display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div>
                <div style={{ fontSize: '0.72rem', letterSpacing: '0.14em', textTransform: 'uppercase', color: 'var(--cyan)', marginBottom: 8 }}>
                  {journey.audience}
                </div>
                <h3 style={{ margin: '0 0 10px', fontSize: '1.2rem', color: 'var(--txt-pri)' }}>{journey.headline}</h3>
                <p style={{ margin: 0, fontSize: '0.84rem', color: 'var(--txt-sec)', lineHeight: 1.68 }}>
                  {journey.body}
                </p>
              </div>

              <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginTop: 'auto' }}>
                <button
                  onClick={() => setPage(journey.primaryPage)}
                  style={{
                    padding: '11px 16px',
                    borderRadius: 10,
                    border: 'none',
                    background: 'linear-gradient(90deg, var(--photon), var(--cyan))',
                    color: '#050608',
                    fontWeight: 800,
                    fontSize: '0.85rem',
                    cursor: 'pointer',
                  }}
                >
                  {journey.primaryLabel}
                </button>
                <button
                  onClick={() => setPage(journey.secondaryPage)}
                  style={{
                    padding: '11px 16px',
                    borderRadius: 10,
                    border: '1px solid rgba(255,255,255,0.08)',
                    background: 'rgba(255,255,255,0.02)',
                    color: 'var(--txt-pri)',
                    fontWeight: 700,
                    fontSize: '0.85rem',
                    cursor: 'pointer',
                  }}
                >
                  {journey.secondaryLabel}
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div style={{ borderTop: '1px solid var(--border)', padding: '42px 0 24px' }}>
        <div style={{ textAlign: 'center', marginBottom: 26 }}>
          <p style={{ fontSize: '0.72rem', letterSpacing: '0.18em', textTransform: 'uppercase', color: 'var(--txt-mut)', marginBottom: 8 }}>
            How the product works
          </p>
          <h2 style={{ fontSize: '1.7rem', fontWeight: 700, color: 'var(--txt-pri)', margin: 0 }}>
            From context to confidence in four steps.
          </h2>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 16 }}>
          {FLOW.map((item) => (
            <div key={item.step} className="glass-card-solid" style={{ padding: '20px 18px', borderRadius: 18 }}>
              <div style={{ fontSize: '0.78rem', color: 'var(--cyan)', fontWeight: 800, letterSpacing: '0.12em', marginBottom: 10 }}>{item.step}</div>
              <h3 style={{ margin: '0 0 8px', fontSize: '0.95rem', color: 'var(--txt-pri)' }}>{item.title}</h3>
              <p style={{ margin: 0, fontSize: '0.84rem', color: 'var(--txt-sec)', lineHeight: 1.6 }}>{item.text}</p>
            </div>
          ))}
        </div>
      </div>

      <div style={{ borderTop: '1px solid var(--border)', padding: '42px 0 18px' }}>
        <div className="glass-card-solid" style={{ padding: '24px 24px 18px', borderRadius: 20 }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 18, flexWrap: 'wrap' }}>
            <div style={{ flex: '1 1 360px' }}>
              <p style={{ fontSize: '0.72rem', letterSpacing: '0.18em', textTransform: 'uppercase', color: 'var(--txt-mut)', marginBottom: 8 }}>
                Explore deeper
              </p>
              <h2 style={{ margin: '0 0 10px', fontSize: '1.45rem', color: 'var(--txt-pri)' }}>
                The docs and in-app pages now tell a tighter, cleaner story.
              </h2>
              <p style={{ margin: 0, fontSize: '0.88rem', color: 'var(--txt-sec)', lineHeight: 1.68 }}>
                Use the pages below when you want the operational map, the best prompt recipes, or the buyer-facing packaging layer.
              </p>
            </div>
            <div style={{ flex: '1 1 320px', display: 'grid', gap: 10 }}>
              {DOCS.map((item) => (
                <button
                  key={item.title}
                  onClick={() => setPage(item.page)}
                  style={{ padding: '12px 14px', borderRadius: 12, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)', textAlign: 'left', cursor: 'pointer' }}
                >
                  <div style={{ color: 'var(--txt-pri)', fontSize: '0.84rem', fontWeight: 700, marginBottom: 4 }}>{item.title}</div>
                  <div style={{ color: 'var(--txt-sec)', fontSize: '0.77rem', lineHeight: 1.55 }}>{item.body}</div>
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div style={{ borderTop: '1px solid var(--border)', paddingTop: 24, marginTop: 36, textAlign: 'center' }}>
        <p style={{ fontSize: '0.78rem', color: 'var(--txt-mut)', marginBottom: 12 }}>
          © 2026 MammothOS. Adaptive tutoring, agent execution, and trust-first product design in one ecosystem.
        </p>
        <div style={{ display: 'flex', gap: 16, justifyContent: 'center', marginBottom: 8, flexWrap: 'wrap' }}>
          <button onClick={() => setPage('manual')} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--txt-mut)', fontSize: '0.78rem', padding: 0, textDecoration: 'underline' }}>
            Manual
          </button>
          <button onClick={() => setPage('commandlib')} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--txt-mut)', fontSize: '0.78rem', padding: 0, textDecoration: 'underline' }}>
            Command Library
          </button>
          <button onClick={() => setPage('pricing')} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--txt-mut)', fontSize: '0.78rem', padding: 0, textDecoration: 'underline' }}>
            Pricing
          </button>
        </div>
      </div>
    </div>
  )
}
