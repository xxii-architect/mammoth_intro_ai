import { useEffect, useState } from 'react'
import { api } from '../api/client'

const TIERS = [
  {
    key: 'explorer',
    name: 'Explorer',
    badge: 'Live now',
    badgeColor: '#22c55e',
    badgeBg: 'rgba(34,197,94,0.12)',
    badgeBorder: 'rgba(34,197,94,0.3)',
    price: '$0',
    period: '/ month',
    subtitle: 'For individual learners getting started with ATLAS.',
    priceColor: 'var(--photon)',
    features: [
      'Adaptive tutor chat across lesson types',
      'Lesson resume, recap, quiz, and flashcards',
      'Learner model and memory graph basics',
      'Local-first session persistence',
      'Core eval and progress surfaces',
    ],
    cta: 'Start free',
  },
  {
    key: 'pro',
    name: 'Pro',
    badge: 'Planned',
    badgeColor: 'var(--cyan)',
    badgeBg: 'rgba(0,245,212,0.1)',
    badgeBorder: 'rgba(0,245,212,0.35)',
    price: '$12',
    period: '/ month (target)',
    subtitle: 'For serious builders who want deeper orchestration and exports.',
    priceColor: 'var(--cyan)',
    cardBorder: '1px solid rgba(0,245,212,0.35)',
    features: [
      'Everything in Explorer',
      'Full Plan + Execute across supported profiles',
      'Supabase sync and progress export',
      'Audit log export and richer observability',
      'Priority model routing and coding approvals',
    ],
    cta: 'Join waitlist',
  },
  {
    key: 'enterprise',
    name: 'Team / Enterprise',
    badge: 'Roadmap',
    badgeColor: 'var(--violet)',
    badgeBg: 'rgba(180,124,255,0.1)',
    badgeBorder: 'rgba(180,124,255,0.35)',
    price: 'Contact us',
    period: '',
    subtitle: 'For schools, teams, and multi-operator deployments.',
    priceColor: 'var(--violet)',
    cardBorder: '1px solid rgba(180,124,255,0.24)',
    features: [
      'Everything in Pro',
      'Team dashboards and cohort analytics',
      'Custom curriculum and onboarding paths',
      'Enterprise support posture and rollout planning',
      'White-label and LMS integration direction',
    ],
    cta: 'Talk to us',
  },
]

const FAQS = [
  { q: 'Can I use MammothOS without paying?', a: 'Yes. Explorer is the default path and includes the core ATLAS tutoring experience.' },
  { q: 'What is the difference between product pricing and operator toggles?', a: 'Pricing describes the intended customer packaging. Operator toggles below are workspace-local controls for testing and development.' },
  { q: 'Do I need cloud auth to get started?', a: 'No. The current onboarding model is workspace-local. You can create separate workspace accounts before adding hosted auth later.' },
  { q: 'Will Pro include cloud sync?', a: 'That is the intended direction. Pro is planned to package Supabase sync, exports, and deeper orchestration controls.' },
  { q: 'Can teams use this today?', a: 'Early operator and observability surfaces exist now. Full enterprise posture is still being productized.' },
]

const TRUST_BADGES = [
  'Audit event capture + export',
  'Runtime fallback transparency',
  'Guarded tutoring over answer leakage',
  'Workspace-scoped account onboarding',
]

export default function PricingPage({ setPage }) {
  const [openFaq, setOpenFaq] = useState(null)
  const [entitlements, setEntitlements] = useState(null)
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState('')
  const adminControlsEnabled = entitlements?.admin_controls_enabled !== false

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
      setMsg(`Workspace testing tier switched to ${tier}.`)
    } catch (e) {
      setMsg('Tier update failed: ' + e.message)
    }
    setSaving(false)
    window.setTimeout(() => setMsg(''), 2400)
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
    window.setTimeout(() => setMsg(''), 2400)
  }

  return (
    <div className="page-enter" style={{ padding: '40px 28px 80px', maxWidth: 1120, margin: '0 auto' }}>
      <div style={{ textAlign: 'center', marginBottom: 42 }}>
        <h1 style={{ fontSize: '2rem', fontWeight: 800, color: 'var(--txt-pri)', marginBottom: 10 }}>Plans & Packaging</h1>
        <p style={{ fontSize: '0.95rem', color: 'var(--txt-sec)', maxWidth: 640, margin: '0 auto', lineHeight: 1.65 }}>
          MammothOS is being packaged in layers: a free learner path, a deeper operator plan, and a future team posture that keeps governance and trust visible.
        </p>
      </div>

      <div className="glass-card-solid" style={{ padding: '18px 20px', marginBottom: 28 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
          <div>
            <div style={{ fontSize: '0.74rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-mut)' }}>Current workspace access</div>
            <div style={{ fontSize: '1rem', color: 'var(--cyan)', fontWeight: 700, textTransform: 'capitalize' }}>
              {entitlements?.effective_tier || entitlements?.tier || 'explorer'}
            </div>
            <div style={{ fontSize: '0.76rem', color: 'var(--txt-mut)', marginTop: 4 }}>
              Active account: <span style={{ fontFamily: 'JetBrains Mono,monospace' }}>{entitlements?.active_account_id || 'default'}</span>
            </div>
          </div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <button
              onClick={() => setPage('settings')}
              style={{ padding: '8px 12px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.05)', color: 'var(--txt-sec)', cursor: 'pointer', fontSize: '0.78rem' }}
            >
              Manage accounts
            </button>
            <button
              onClick={() => setPage('compliance')}
              style={{ padding: '8px 12px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.05)', color: 'var(--txt-sec)', cursor: 'pointer', fontSize: '0.78rem' }}
            >
              Review trust posture
            </button>
          </div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 24, marginBottom: 54 }}>
        {TIERS.map((tier) => (
          <div
            key={tier.key}
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
              {tier.features.map((f) => (
                <li key={f} style={{ fontSize: '0.85rem', color: 'var(--txt-sec)', display: 'flex', gap: 8 }}>
                  <span style={{ color: 'var(--cyan)' }}>✓</span>
                  {f}
                </li>
              ))}
            </ul>
            <button
              onClick={() => (tier.key === 'explorer' ? setPage('atlas') : setPage('settings'))}
              style={{ width: '100%', padding: '11px 0', borderRadius: 8, fontSize: '0.9rem', fontWeight: 600, cursor: 'pointer', border: tier.key === 'explorer' ? 'none' : '1px solid var(--border)', background: tier.key === 'explorer' ? 'linear-gradient(90deg, var(--photon), var(--cyan))' : 'rgba(255,255,255,0.04)', color: tier.key === 'explorer' ? '#050608' : 'var(--txt-pri)' }}
            >
              {tier.cta}
            </button>
          </div>
        ))}
      </div>

      <div className="glass-card-solid" style={{ padding: '20px 24px', marginBottom: 42 }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 18, flexWrap: 'wrap' }}>
          <div style={{ flex: '1 1 360px' }}>
            <h2 style={{ margin: '0 0 8px', fontSize: '1.1rem', color: 'var(--txt-pri)' }}>Operator controls stay separate from customer-facing pricing.</h2>
            <p style={{ margin: 0, fontSize: '0.84rem', color: 'var(--txt-sec)', lineHeight: 1.65 }}>
              These workspace-local toggles exist so you can test entitlements and developer access during recovery and productization work without confusing the public packaging story.
            </p>
            {!adminControlsEnabled && (
              <p style={{ margin: '8px 0 0', fontSize: '0.76rem', color: 'var(--txt-mut)' }}>
                You are not an admin for this workspace, so entitlement controls are read-only.
              </p>
            )}
          </div>
          <div style={{ flex: '1 1 320px', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: 8 }}>
            {['explorer', 'pro', 'enterprise'].map((tier) => (
              <button
                key={tier}
                onClick={() => changeTier(tier)}
                disabled={saving || !adminControlsEnabled}
                style={{ padding: '9px 12px', borderRadius: 8, border: `1.5px solid ${entitlements?.tier === tier ? 'var(--cyan)' : 'var(--border)'}`, background: entitlements?.tier === tier ? 'rgba(0,245,212,0.12)' : 'rgba(255,255,255,0.04)', color: entitlements?.tier === tier ? 'var(--cyan)' : 'var(--txt-sec)', cursor: 'pointer', textTransform: 'capitalize', fontSize: '0.78rem', fontWeight: 600 }}
              >
                Set {tier}
              </button>
            ))}
            <button
              onClick={toggleDeveloperAccess}
              disabled={saving || !adminControlsEnabled}
              style={{ padding: '9px 12px', borderRadius: 8, border: '1px solid rgba(34,197,94,0.4)', background: 'rgba(34,197,94,0.1)', color: '#22c55e', cursor: 'pointer', fontSize: '0.78rem', fontWeight: 600, gridColumn: '1 / -1' }}
            >
              {entitlements?.developer_access ? 'Disable Dev Full Access' : 'Enable Dev Full Access'}
            </button>
          </div>
        </div>
        {msg && <p style={{ margin: '12px 0 0', fontSize: '0.78rem', color: msg.includes('failed') ? '#f87171' : '#22c55e' }}>{msg}</p>}
      </div>

      <div style={{ maxWidth: 860, margin: '0 auto 48px' }}>
        <h2 style={{ fontSize: '1.3rem', fontWeight: 700, color: 'var(--txt-pri)', marginBottom: 20, textAlign: 'center' }}>
          Trust & launch readiness
        </h2>
        <div className="glass-card-solid" style={{ padding: '20px 24px', marginBottom: 18 }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 10 }}>
            {TRUST_BADGES.map((badge) => (
              <div key={badge} style={{ padding: '10px 12px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)', fontSize: '0.8rem', color: 'var(--txt-sec)' }}>
                ✓ {badge}
              </div>
            ))}
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {FAQS.map((faq, i) => (
            <div key={faq.q} className="glass-card-solid" style={{ padding: '14px 20px', cursor: 'pointer' }} onClick={() => setOpenFaq(openFaq === i ? null : i)}>
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
    </div>
  )
}
