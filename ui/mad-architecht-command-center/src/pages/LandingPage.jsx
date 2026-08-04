import { useState } from 'react'

export default function LandingPage({ setPage }) {
  const features = [
    { icon: '🧠', title: 'Adaptive Learning Engine', desc: 'ATLAS tracks your mastery, confidence, and error patterns to tune every lesson to your pace.' },
    { icon: '🎯', title: 'No-Cheat Coaching', desc: "ATLAS won't give you the answer. If you try, it generates a new exercise — keeping learning real." },
    { icon: '🗺️', title: 'Memory Graph', desc: 'ATLAS builds a live knowledge map of your concepts, goals, and progress across every session.' },
    { icon: '🤖', title: 'Multi-Agent Orchestration', desc: 'ATLAS coordinates a tutor, researcher, coding agent, and coach in real time to create your lesson plan.' },
    { icon: '💾', title: 'Lesson Resume', desc: 'Never lose your place. ATLAS reconstructs your prior notes, flashcards, and next actions when you return.' },
    { icon: '🚀', title: 'Plan + Execute', desc: 'Generate a full tutor plan from your exercise prompt, executed step-by-step with visible agent progress.' },
  ]

  return (
    <div className="page-enter" style={{ padding: '40px 32px 80px', maxWidth: 1100, margin: '0 auto' }}>

      {/* Hero */}
      <div style={{ textAlign: 'center', padding: '60px 0 56px', borderBottom: '1px solid var(--border)' }}>
        <div style={{
          fontSize: '4rem',
          animation: 'pulse-violet 2.5s infinite',
          display: 'inline-block',
          filter: 'drop-shadow(0 0 18px rgba(180,124,255,0.7))',
          marginBottom: 20,
        }}>
          🐘
        </div>
        <h1 style={{
          margin: '0 0 12px',
          fontSize: '2.8rem',
          fontWeight: 800,
          background: 'linear-gradient(90deg, var(--photon), var(--cyan))',
          WebkitBackgroundClip: 'text',
          WebkitTextFillColor: 'transparent',
          backgroundClip: 'text',
          lineHeight: 1.15,
        }}>
          MammothOS
        </h1>
        <p style={{ fontSize: '1.15rem', fontWeight: 600, color: 'var(--txt-pri)', margin: '0 0 14px' }}>
          ATLAS — The Adaptive Tutor Built for Real Learners
        </p>
        <p style={{ fontSize: '0.95rem', color: 'var(--txt-sec)', maxWidth: 620, margin: '0 auto 32px', lineHeight: 1.65 }}>
          A cognitive AI tutor system that meets you where you are, adapts to how you learn, and coaches you toward mastery — not just answers.
        </p>
        <div style={{ display: 'flex', gap: 14, justifyContent: 'center', flexWrap: 'wrap' }}>
          <button
            onClick={() => setPage('atlas')}
            style={{
              padding: '12px 28px',
              borderRadius: 10,
              border: 'none',
              background: 'linear-gradient(90deg, var(--photon), var(--cyan))',
              color: '#050608',
              fontWeight: 700,
              fontSize: '0.95rem',
              cursor: 'pointer',
              boxShadow: '0 0 20px rgba(77,166,255,0.3)',
            }}
          >
            Open ATLAS Tutor
          </button>
          <button
            onClick={() => setPage('pricing')}
            style={{
              padding: '12px 28px',
              borderRadius: 10,
              border: '1px solid var(--border)',
              background: 'rgba(255,255,255,0.04)',
              color: 'var(--txt-sec)',
              fontWeight: 600,
              fontSize: '0.95rem',
              cursor: 'pointer',
            }}
          >
            Learn More
          </button>
        </div>
      </div>

      {/* Features */}
      <div style={{ padding: '56px 0 40px' }}>
        <h2 style={{ textAlign: 'center', fontSize: '1.4rem', fontWeight: 700, color: 'var(--txt-pri)', marginBottom: 32 }}>
          What makes ATLAS different
        </h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(290px, 1fr))', gap: 20 }}>
          {features.map((f) => (
            <div key={f.title} className="glass-card-solid" style={{ padding: '22px 24px' }}>
              <div style={{ fontSize: '1.8rem', marginBottom: 10 }}>{f.icon}</div>
              <h3 style={{ margin: '0 0 8px', fontSize: '0.95rem', fontWeight: 700, color: 'var(--photon)' }}>{f.title}</h3>
              <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--txt-sec)', lineHeight: 1.6 }}>{f.desc}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Pricing tiers */}
      <div style={{ borderTop: '1px solid var(--border)', padding: '48px 0 40px' }}>
        <h2 style={{ textAlign: 'center', fontSize: '1.4rem', fontWeight: 700, color: 'var(--txt-pri)', marginBottom: 32 }}>
          Free to start. Built to grow.
        </h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 24, maxWidth: 760, margin: '0 auto' }}>

          {/* Explorer */}
          <div className="glass-card-solid" style={{ padding: '28px 28px 24px' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
              <span style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--txt-pri)' }}>Explorer</span>
              <span style={{ fontSize: '0.7rem', fontWeight: 700, color: '#22c55e', background: 'rgba(34,197,94,0.12)', borderRadius: 20, padding: '3px 10px', border: '1px solid rgba(34,197,94,0.3)' }}>Free</span>
            </div>
            <p style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--photon)', margin: '0 0 4px' }}>$0<span style={{ fontSize: '0.9rem', fontWeight: 400, color: 'var(--txt-sec)' }}> / month</span></p>
            <p style={{ fontSize: '0.8rem', color: 'var(--txt-mut)', marginBottom: 20 }}>Forever free for individual learners</p>
            <ul style={{ listStyle: 'none', padding: 0, margin: '0 0 24px', display: 'flex', flexDirection: 'column', gap: 7 }}>
              {['ATLAS tutor chat', 'Adaptive lesson pacing', 'Lesson resume', 'Basic eval checks'].map(f => (
                <li key={f} style={{ fontSize: '0.85rem', color: 'var(--txt-sec)', display: 'flex', gap: 8 }}>
                  <span style={{ color: 'var(--cyan)' }}>✓</span> {f}
                </li>
              ))}
            </ul>
            <button
              onClick={() => setPage('atlas')}
              style={{ width: '100%', padding: '10px 0', borderRadius: 8, border: 'none', background: 'linear-gradient(90deg, var(--photon), var(--cyan))', color: '#050608', fontWeight: 700, cursor: 'pointer', fontSize: '0.9rem' }}
            >
              Get Started
            </button>
          </div>

          {/* Pro */}
          <div className="glass-card-solid" style={{ padding: '28px 28px 24px', border: '1px solid rgba(0,245,212,0.35)' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
              <span style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--txt-pri)' }}>Pro</span>
              <span style={{ fontSize: '0.7rem', fontWeight: 700, color: 'var(--cyan)', background: 'rgba(0,245,212,0.1)', borderRadius: 20, padding: '3px 10px', border: '1px solid rgba(0,245,212,0.35)' }}>Early access</span>
            </div>
            <p style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--cyan)', margin: '0 0 4px' }}>Coming Soon</p>
            <p style={{ fontSize: '0.8rem', color: 'var(--txt-mut)', marginBottom: 20 }}>For serious learners and power users</p>
            <ul style={{ listStyle: 'none', padding: 0, margin: '0 0 24px', display: 'flex', flexDirection: 'column', gap: 7 }}>
              {['Everything in Explorer, plus:', 'Multi-agent plan execution', 'Team learning dashboards', 'Supabase progress sync', 'Audit export', 'Priority model routing'].map(f => (
                <li key={f} style={{ fontSize: '0.85rem', color: 'var(--txt-sec)', display: 'flex', gap: 8 }}>
                  <span style={{ color: 'var(--cyan)' }}>✓</span> {f}
                </li>
              ))}
            </ul>
            <button
              onClick={() => setPage('pricing')}
              style={{ width: '100%', padding: '10px 0', borderRadius: 8, border: '1px solid var(--cyan)', background: 'rgba(0,245,212,0.08)', color: 'var(--cyan)', fontWeight: 700, cursor: 'pointer', fontSize: '0.9rem' }}
            >
              Join Waitlist
            </button>
          </div>

        </div>
      </div>

      {/* Footer */}
      <div style={{ borderTop: '1px solid var(--border)', paddingTop: 28, textAlign: 'center' }}>
        <p style={{ fontSize: '0.78rem', color: 'var(--txt-mut)', marginBottom: 10 }}>
          © 2026 MammothOS. Educational AI software — not professional instruction.
        </p>
        <div style={{ display: 'flex', gap: 16, justifyContent: 'center', marginBottom: 10 }}>
          {['Terms of Use', 'Privacy Policy', 'Acceptable Use'].map(label => (
            <button
              key={label}
              onClick={() => setPage('compliance')}
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--txt-mut)', fontSize: '0.78rem', padding: 0, textDecoration: 'underline' }}
            >
              {label}
            </button>
          ))}
        </div>
        <p style={{ fontSize: '0.7rem', color: 'var(--txt-mut)', fontStyle: 'italic' }}>
          Product architecture, policy controls, and monetization surfaces are actively evolving.
        </p>
      </div>
    </div>
  )
}
