import { useEffect, useState } from 'react'
import { api } from '../api/client'

const TIERS = [
  {
    name: 'Explorer',
    badge: 'Active',
    badgeColor: '#22c55e',
    badgeBg: 'rgba(34,197,94,0.12)',
    badgeBorder: 'rgba(34,197,94,0.3)',
    price: '$0',
    period: '/ month',
    subtitle: 'Forever free for individual learners',
    priceColor: 'var(--photon)',
    features: [
      'ATLAS tutor chat (all lesson types)',
      'Adaptive pacing and learner model',
      'Lesson resume and memory graph',
      'Flashcards, quiz, and recap tools',
      'Basic eval harness',
      'Local session storage',
    ],
    cta: "You're on this plan",
    ctaDisabled: true,
    ctaStyle: { background: 'rgba(255,255,255,0.06)', color: 'var(--txt-mut)', border: '1px solid var(--border)', cursor: 'not-allowed' },
  },
  {
    name: 'Pro',
    badge: 'Coming Soon',
    badgeColor: 'var(--cyan)',
    badgeBg: 'rgba(0,245,212,0.1)',
    badgeBorder: 'rgba(0,245,212,0.35)',
    price: '$12',
    period: '/ month (est.)',
    subtitle: 'For serious learners and power users',
    priceColor: 'var(--cyan)',
    cardBorder: '1px solid rgba(0,245,212,0.35)',
    features: [
      'Everything in Explorer, plus:',
      'Multi-agent tutor orchestration',
      'Full Plan + Execute with all profiles',
      'Supabase sync and progress export',
      'Eval history dashboard',
      'Priority model routing',
      'Audit log export',
      'Coding agent with approval workflow',
    ],
    cta: 'Join Waitlist',
    ctaStyle: { background: 'linear-gradient(90deg, var(--photon), var(--cyan))', color: '#050608', fontWeight: 700, border: 'none', cursor: 'pointer' },
  },
  {
    name: 'Team / Enterprise',
    badge: 'Future',
    badgeColor: 'var(--violet)',
    badgeBg: 'rgba(180,124,255,0.1)',
    badgeBorder: 'rgba(180,124,255,0.35)',
    price: 'Contact us',
    period: '',
    subtitle: 'For teams, schools, and cohorts',
    priceColor: 'var(--violet)',
    cardBorder: '1px solid rgba(180,124,255,0.2)',
    features: [
      'Everything in Pro, plus:',
      'Team dashboards and cohort analytics',
      'Custom curriculum authoring',
      'LMS integration',
      'White-label ATLAS deployment',
      'Custom model fine-tuning',
      'SLA and dedicated support',
    ],
    cta: 'Get in Touch',
    ctaStyle: { background: 'rgba(255,255,255,0.04)', color: 'var(--txt-sec)', border: '1px solid var(--border)', cursor: 'pointer' },
  },
]

const FAQS = [
  { q: 'Is ATLAS really free?', a: 'Yes, the core tutor is free. Pro features (advanced orchestration, sync, export) will be paid when they launch.' },
  { q: 'Do I need an account?', a: 'Not today. MammothOS stores your progress locally. Cloud sync requires Supabase configuration.' },
  { q: 'Will my data be safe on Pro?', a: 'Yes. We never sell your data. Pro adds cloud sync — you control what syncs.' },
  { q: 'Do you have a refund policy?', a: 'Yes. Pro plans will offer a 14-day full refund window.' },
  { q: 'Is this FERPA/COPPA compliant?', a: 'MammothOS is not a covered educational institution and does not collect data from minors under 13. Do not use with students under 13.' },
]

const TRUST_BADGES = [
  'No-cheat tutoring guardrails',
  'Approval-gated coding actions',
  'Audit log stream + CSV export',
  'Local-first learner state support',
]

export default function PricingPage({ setPage }) {
  const [openFaq, setOpenFaq] = useState(null)
  const [entitlements, setEntitlements] = useState(null)
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState('')

  const refreshEntitlements = async () => {
    try {
      const data = await api('/entitlements')
      setEntitlements(data)
    } catch (_) {}
  }

  useEffect(() => {
    refreshEntitlements()
  }, [])

  const changeTier = async (tier) => {
    setSaving(true)
    try {
      await api('/entitlements/tier', { method: 'POST', body: { tier } })
      await refreshEntitlements()
      setMsg(`Tier switched to ${tier}.`)
    } catch (e) {
      setMsg('Tier update failed: ' + e.message)
    }
    setSaving(false)
    setTimeout(() => setMsg(''), 2400)
  }

  const toggleDeveloperAccess = async () => {
    setSaving(true)
    try {
      await api('/account/developer-access', { method: 'POST', body: { enabled: !Boolean(entitlements?.developer_access) } })
      await refreshEntitlements()
      setMsg(Boolean(entitlements?.developer_access) ? 'Developer full access disabled.' : 'Developer full access enabled.')
    } catch (e) {
      setMsg('Developer access update failed: ' + e.message)
    }
    setSaving(false)
    setTimeout(() => setMsg(''), 2400)
  }

  return (
    <div className="page-enter" style={{ padding: '40px 28px 80px', maxWidth: 1100, margin: '0 auto' }}>

      {/* Header */}
      <div style={{ textAlign: 'center', marginBottom: 48 }}>
        <h1 style={{ fontSize: '2rem', fontWeight: 800, color: 'var(--txt-pri)', marginBottom: 10 }}>Plans & Pricing</h1>
        <p style={{ fontSize: '0.95rem', color: 'var(--txt-sec)', maxWidth: 520, margin: '0 auto' }}>
          ATLAS is free to explore. Pro features unlock the full cognitive tutor stack.
        </p>
      </div>

      <div className="glass-card-solid" style={{ padding: '16px 18px', marginBottom: 28 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
          <div>
            <div style={{ fontSize: '0.74rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-mut)' }}>Current access</div>
            <div style={{ fontSize: '1rem', color: 'var(--cyan)', fontWeight: 700, textTransform: 'capitalize' }}>
              {entitlements?.effective_tier || entitlements?.tier || 'explorer'}
            </div>
          </div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {['explorer', 'pro', 'enterprise'].map((tier) => (
              <button
                key={tier}
                onClick={() => changeTier(tier)}
                disabled={saving}
                style={{ padding: '8px 12px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.05)', color: 'var(--txt-sec)', cursor: 'pointer', textTransform: 'capitalize', fontSize: '0.78rem' }}
              >
                Set {tier}
              </button>
            ))}
            <button
              onClick={toggleDeveloperAccess}
              disabled={saving}
              style={{ padding: '8px 12px', borderRadius: 8, border: '1px solid rgba(34,197,94,0.4)', background: 'rgba(34,197,94,0.1)', color: '#22c55e', cursor: 'pointer', fontSize: '0.78rem' }}
            >
              {entitlements?.developer_access ? 'Disable Dev Full Access' : 'Enable Dev Full Access'}
            </button>
          </div>
        </div>
        {msg && <p style={{ margin: '10px 0 0', fontSize: '0.78rem', color: msg.includes('failed') ? '#f87171' : '#22c55e' }}>{msg}</p>}
      </div>

      {/* Tier grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 24, marginBottom: 60 }}>
        {TIERS.map(tier => (
          <div
            key={tier.name}
            className="glass-card-solid"
            style={{ padding: '28px 26px 26px', border: tier.cardBorder, display: 'flex', flexDirection: 'column' }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
              <span style={{ fontWeight: 700, fontSize: '1rem', color: 'var(--txt-pri)' }}>{tier.name}</span>
              <span style={{ fontSize: '0.7rem', fontWeight: 700, color: tier.badgeColor, background: tier.badgeBg, borderRadius: 20, padding: '3px 10px', border: `1px solid ${tier.badgeBorder}` }}>
                {tier.badge}
              </span>
            </div>
            <div style={{ marginBottom: 4 }}>
              <span style={{ fontSize: '1.6rem', fontWeight: 800, color: tier.priceColor }}>{tier.price}</span>
              {tier.period && <span style={{ fontSize: '0.82rem', color: 'var(--txt-mut)', marginLeft: 4 }}>{tier.period}</span>}
            </div>
            <p style={{ fontSize: '0.8rem', color: 'var(--txt-mut)', marginBottom: 20 }}>{tier.subtitle}</p>
            <ul style={{ listStyle: 'none', padding: 0, margin: '0 0 24px', flex: 1, display: 'flex', flexDirection: 'column', gap: 8 }}>
              {tier.features.map((f, i) => (
                <li key={i} style={{ fontSize: '0.85rem', color: i === 0 && f.endsWith(':') ? 'var(--txt-mut)' : 'var(--txt-sec)', display: 'flex', gap: 8, fontStyle: i === 0 && f.endsWith(':') ? 'italic' : 'normal' }}>
                  {!(i === 0 && f.endsWith(':')) && <span style={{ color: 'var(--cyan)' }}>✓</span>}
                  {i === 0 && f.endsWith(':') && <span style={{ color: 'var(--txt-mut)' }}>›</span>}
                  {f}
                </li>
              ))}
            </ul>
            <button
              disabled={tier.ctaDisabled}
              onClick={tier.ctaDisabled ? undefined : () => setPage('landing')}
              style={{ width: '100%', padding: '11px 0', borderRadius: 8, fontSize: '0.9rem', fontWeight: 600, transition: 'opacity 0.15s', ...tier.ctaStyle }}
            >
              {tier.cta}
            </button>
          </div>
        ))}
      </div>

      {/* FAQ */}
      <div style={{ maxWidth: 680, margin: '0 auto 48px' }}>
        <h2 style={{ fontSize: '1.3rem', fontWeight: 700, color: 'var(--txt-pri)', marginBottom: 20, textAlign: 'center' }}>
          Frequently Asked Questions
        </h2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {FAQS.map((faq, i) => (
            <div key={i} className="glass-card-solid" style={{ padding: '14px 20px', cursor: 'pointer' }} onClick={() => setOpenFaq(openFaq === i ? null : i)}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
                <span style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--txt-pri)' }}>{faq.q}</span>
                <span style={{ color: 'var(--txt-mut)', fontSize: '0.85rem', flexShrink: 0 }}>{openFaq === i ? '▲' : '▼'}</span>
              </div>
              {openFaq === i && (
                <p style={{ margin: '10px 0 0', fontSize: '0.86rem', color: 'var(--txt-sec)', lineHeight: 1.65 }}>
                  {faq.a}
                </p>
              )}
            </div>
          ))}
        </div>
      </div>

      <div className="glass-card-solid" style={{ maxWidth: 860, margin: '0 auto 52px', padding: '20px 24px' }}>
        <h3 style={{ margin: '0 0 10px', fontSize: '1rem', color: 'var(--txt-pri)' }}>Enterprise readiness snapshot</h3>
        <p style={{ margin: '0 0 14px', fontSize: '0.84rem', color: 'var(--txt-sec)', lineHeight: 1.6 }}>
          We are intentionally sequencing monetization after core reliability. Current builds already include governance primitives teams ask for first.
        </p>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 10 }}>
          {TRUST_BADGES.map((badge) => (
            <div key={badge} style={{ padding: '10px 12px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)', fontSize: '0.8rem', color: 'var(--txt-sec)' }}>
              ✓ {badge}
            </div>
          ))}
        </div>
      </div>

      {/* Footer */}
      <div style={{ textAlign: 'center', borderTop: '1px solid var(--border)', paddingTop: 24 }}>
        <div style={{ display: 'flex', justifyContent: 'center', gap: 14, flexWrap: 'wrap', marginBottom: 8 }}>
          <button
            onClick={() => setPage('compliance')}
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--txt-mut)', fontSize: '0.8rem', textDecoration: 'underline' }}
          >
            Legal & Compliance
          </button>
          <button
            onClick={() => setPage('landing')}
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--txt-mut)', fontSize: '0.8rem', textDecoration: 'underline' }}
          >
            Back to Landing
          </button>
        </div>
        <p style={{ fontSize: '0.75rem', color: 'var(--txt-mut)' }}>© 2026 MammothOS</p>
      </div>

    </div>
  )
}
