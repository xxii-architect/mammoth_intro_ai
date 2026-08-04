import { useState } from 'react'

const TABS = ['Terms of Use', 'Privacy Policy', 'Acceptable Use', 'Disclaimer']

const CONTENT = {
  'Terms of Use': [
    'MammothOS is an AI-assisted educational platform. The software is provided for personal and educational use.',
    'The AI tutor (ATLAS) is a learning aid and does not constitute professional instruction, therapy, or certified education.',
    'You may not use MammothOS to cheat on exams, pass off AI-generated work as your own, or circumvent academic integrity policies.',
    'Users retain ownership of their own submitted code and notes. MammothOS retains no claim over student work.',
    'The platform may be modified, expanded, or discontinued at any time. Features are subject to change without notice.',
    'By using MammothOS you agree to these terms.',
  ],
  'Privacy Policy': [
    'We collect only what is necessary to operate the tutor: your lesson history, onboarding profile, learner model state, and submitted code.',
    'All data is stored locally in your browser session and in your local Supabase instance. No data is sent to third-party analytics or ad networks.',
    'AI model providers (OpenAI, Ollama) may process your prompts per their own terms. We recommend not including personal, sensitive, or identifying information in prompts.',
    'We do not sell, rent, or share your personal data.',
    'You may request deletion of your data at any time by resetting your session from the Settings page.',
  ],
  'Acceptable Use': [
    'ATLAS is designed to coach, not complete. Do not use it to generate complete answers to submit as your own work.',
    'Do not attempt to jailbreak or circumvent the no-cheat guard through prompt engineering.',
    'Do not use MammothOS for harmful, abusive, or illegal content generation.',
    'Respect the spirit of the platform: it exists to make you a better developer, not to do your job for you.',
    'Violations may result in restriction of access to advanced features.',
  ],
  'Disclaimer': [
    'MammothOS is experimental AI software in active development. Features may be incomplete or change without notice.',
    'AI-generated coaching, code, and lesson plans are not guaranteed to be accurate, complete, or free from error. Always verify code before using it in production.',
    'ATLAS is a tutoring assistant — not a replacement for real mentors, documentation, or professional advice.',
    '"Patents pending on adaptive tutor and memory graph methodologies" is forward-looking language. No formal patents have been filed as of this version.',
    'The creators of MammothOS are not liable for any outcomes resulting from use of the platform.',
  ],
}

export default function CompliancePage({ setPage }) {
  const [activeTab, setActiveTab] = useState('Terms of Use')

  return (
    <div className="page-enter" style={{ padding: '32px 28px 80px', maxWidth: 860, margin: '0 auto' }}>

      <div style={{ marginBottom: 28 }}>
        <button
          onClick={() => setPage('landing')}
          style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--photon)', fontSize: '0.88rem', padding: 0, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6 }}
        >
          ← Back
        </button>
      </div>

      <h1 style={{ fontSize: '1.7rem', fontWeight: 800, color: 'var(--txt-pri)', marginBottom: 6 }}>Legal & Compliance</h1>
      <p style={{ color: 'var(--txt-sec)', fontSize: '0.88rem', marginBottom: 28 }}>
        MammothOS is an educational AI platform. Please read these policies carefully.
      </p>

      {/* Tab bar */}
      <div style={{ display: 'flex', gap: 4, borderBottom: '1px solid var(--border)', marginBottom: 28, flexWrap: 'wrap' }}>
        {TABS.map(tab => (
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
              transition: 'all 0.15s',
              whiteSpace: 'nowrap',
            }}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="glass-card-solid" style={{ padding: '28px 32px' }}>
        <h2 style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--photon)', marginBottom: 20 }}>{activeTab}</h2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          {CONTENT[activeTab].map((para, i) => (
            <p key={i} style={{ margin: 0, fontSize: '0.9rem', color: 'var(--txt-sec)', lineHeight: 1.7, paddingLeft: 12, borderLeft: '2px solid rgba(77,166,255,0.2)' }}>
              {para}
            </p>
          ))}
        </div>
        <p style={{ marginTop: 28, marginBottom: 0, fontSize: '0.72rem', color: 'var(--txt-mut)', fontStyle: 'italic' }}>
          Last updated: August 2026
        </p>
      </div>

    </div>
  )
}
