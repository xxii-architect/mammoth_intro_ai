import { useState } from 'react'

const TABS = ['Terms of Use', 'Privacy Policy', 'Acceptable Use', 'AI Safety', 'Enterprise Posture']

const CONTENT = {
  'Terms of Use': [
    'MammothOS is an AI-assisted educational and operator platform intended for learning, planning, and supervised execution workflows.',
    'ATLAS is a tutoring and coaching system, not a licensed teacher, therapist, lawyer, accountant, or substitute for human professional judgment.',
    'You are responsible for reviewing generated code, plans, and outputs before using them in real environments.',
    'You may not use MammothOS to cheat on exams, submit generated work as your own without disclosure where required, or bypass academic integrity policies.',
    'Product surfaces, packaging, and feature availability may change as MammothOS evolves from prototype to production system.',
  ],
  'Privacy Policy': [
    'The current workspace model is local-first: account identity, lesson state, learner context, and operator settings are primarily stored in your local workspace state.',
    'When external model providers are configured, prompts may be processed by those providers under their own terms. Do not submit sensitive personal, legal, medical, or regulated data unless you have approved controls in place.',
    'MammothOS is designed to minimize unnecessary collection and to avoid ad-tech style data sharing.',
    'We do not position the current build as a broad consumer data platform; it is an evolving product and should be treated accordingly.',
    'You can reset active learning sessions and maintain separate workspace accounts to reduce state leakage between users in the same environment.',
  ],
  'Acceptable Use': [
    'Use MammothOS to learn, reason, build, and review responsibly.',
    'Do not use the platform to generate abusive, illegal, harmful, or exploitative content.',
    'Do not attempt to defeat tutoring guardrails or extract full answer keys from active exercises.',
    'Do not use shared workspace accounts in a way that misrepresents identity, authorship, or learner progress.',
    'Advanced features may be restricted where misuse, unsafe automation, or policy abuse is detected.',
  ],
  'AI Safety': [
    'ATLAS is intentionally designed to coach instead of simply completing assignments.',
    'Riskier actions can be routed through approval workflows so operators keep a human checkpoint before execution.',
    'Runtime fallback behavior should degrade safely when providers fail, rather than dead-ending the learning or build flow.',
    'Observability, audit trails, and trace IDs exist to make agent behavior reviewable instead of opaque.',
    'Generated outputs can still be wrong. Safety features reduce risk; they do not eliminate the need for review.',
  ],
  'Enterprise Posture': [
    'MammothOS is moving toward a stronger enterprise posture through audit capture, observability, workspace account isolation, and safer runtime contracts.',
    'The current build should be treated as an advancing product, not as fully certified compliance infrastructure.',
    'Organizations should validate data handling, model routing, and operational controls against their own requirements before broader deployment.',
    'Future readiness areas include clearer hosted auth, billing controls, policy versioning, and documented administrative workflows.',
    'If you need strict regulatory assurances, use a controlled pilot and document the boundaries of the current system.',
  ],
}

const POSTURE_POINTS = [
  'Workspace account switching now scopes learner identity and entitlement state per account.',
  'Audit logging, export surfaces, and observability runs support post-action review.',
  'Guarded tutoring aims to reduce answer leakage and over-automation.',
  'Provider fallback routing is designed to fail softer instead of crashing learner flows.',
]

export default function CompliancePage({ setPage }) {
  const [activeTab, setActiveTab] = useState('Terms of Use')

  return (
    <div className="page-enter" style={{ padding: '32px 28px 80px', maxWidth: 920, margin: '0 auto' }}>
      <div style={{ marginBottom: 28 }}>
        <button
          onClick={() => setPage('landing')}
          style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--photon)', fontSize: '0.88rem', padding: 0, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6 }}
        >
          ← Back
        </button>
      </div>

      <h1 style={{ fontSize: '1.8rem', fontWeight: 800, color: 'var(--txt-pri)', marginBottom: 8 }}>Trust, Legal & Compliance</h1>
      <p style={{ color: 'var(--txt-sec)', fontSize: '0.9rem', marginBottom: 28, lineHeight: 1.65 }}>
        MammothOS is growing into a serious tutoring and operator platform. This page clarifies the current boundaries, safeguards, and trust posture of the product.
      </p>

      <div className="glass-card-solid" style={{ marginBottom: 20, padding: '18px 20px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 10 }}>
          <div style={{ padding: '10px 12px', borderRadius: 10, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)' }}>
            <div style={{ fontSize: '0.72rem', color: 'var(--txt-mut)', textTransform: 'uppercase', letterSpacing: '0.12em', marginBottom: 6 }}>Current account model</div>
            <div style={{ fontSize: '0.86rem', color: 'var(--txt-pri)', fontWeight: 700 }}>Workspace multi-account</div>
          </div>
          <div style={{ padding: '10px 12px', borderRadius: 10, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)' }}>
            <div style={{ fontSize: '0.72rem', color: 'var(--txt-mut)', textTransform: 'uppercase', letterSpacing: '0.12em', marginBottom: 6 }}>Primary safety stance</div>
            <div style={{ fontSize: '0.86rem', color: 'var(--txt-pri)', fontWeight: 700 }}>Coach, do not cheat</div>
          </div>
          <div style={{ padding: '10px 12px', borderRadius: 10, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)' }}>
            <div style={{ fontSize: '0.72rem', color: 'var(--txt-mut)', textTransform: 'uppercase', letterSpacing: '0.12em', marginBottom: 6 }}>Operational controls</div>
            <div style={{ fontSize: '0.86rem', color: 'var(--txt-pri)', fontWeight: 700 }}>Audit, approvals, observability</div>
          </div>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 4, borderBottom: '1px solid var(--border)', marginBottom: 28, flexWrap: 'wrap' }}>
        {TABS.map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            style={{
              padding: '9px 16px',
              border: 'none',
              borderBottom: `2px solid ${activeTab === tab ? 'var(--photon)' : 'transparent'}`,
              background: 'none',
              cursor: 'pointer',
              fontSize: '0.86rem',
              fontWeight: activeTab === tab ? 700 : 400,
              color: activeTab === tab ? 'var(--photon)' : 'var(--txt-sec)',
              whiteSpace: 'nowrap',
            }}
          >
            {tab}
          </button>
        ))}
      </div>

      <div className="glass-card-solid" style={{ padding: '28px 32px' }}>
        <h2 style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--photon)', marginBottom: 20 }}>{activeTab}</h2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          {CONTENT[activeTab].map((para) => (
            <p key={para} style={{ margin: 0, fontSize: '0.9rem', color: 'var(--txt-sec)', lineHeight: 1.7, paddingLeft: 12, borderLeft: '2px solid rgba(77,166,255,0.2)' }}>
              {para}
            </p>
          ))}
        </div>
        <p style={{ marginTop: 28, marginBottom: 0, fontSize: '0.72rem', color: 'var(--txt-mut)', fontStyle: 'italic' }}>
          Last updated: August 2026
        </p>
      </div>

      <div className="glass-card-solid" style={{ marginTop: 18, padding: '20px 24px' }}>
        <h3 style={{ margin: '0 0 10px', fontSize: '1rem', color: 'var(--txt-pri)' }}>Current posture snapshot</h3>
        <div style={{ display: 'grid', gap: 8 }}>
          {POSTURE_POINTS.map((line) => (
            <div key={line} style={{ fontSize: '0.82rem', color: 'var(--txt-sec)', padding: '8px 10px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)' }}>
              {line}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
