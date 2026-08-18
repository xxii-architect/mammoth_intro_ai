import { useState, useEffect } from 'react'
import { Settings, Eye, EyeOff, RotateCcw, User, Mail, Building2, Lock, Code2, Palette, Zap, CheckCircle, AlertCircle } from 'lucide-react'
import { api } from '../api/client'

const THEME_OPTIONS = [
  { id: 'darker',   label: 'Darker',   bg: '#050608' },
  { id: 'dark',     label: 'Dark',     bg: '#0d1117' },
  { id: 'midnight', label: 'Midnight', bg: '#080c14' },
]

export default function SettingsPage({ theme, setTheme }) {
  const [status, setStatus]   = useState(null)
  const [health, setHealth]   = useState(null)
  const [models, setModels]   = useState(null)
  const [entitlements, setEntitlements] = useState(null)
  const [profile, setProfile] = useState({ display_name: '', email: '', organization: '' })
  const [profileMeta, setProfileMeta] = useState({ auth_mode: '', session_scope: '', updated_at: '', profile_complete: false })
  const [masked, setMasked]   = useState(true)
  const [resetting, setResetting] = useState(false)
  const [resetMsg, setResetMsg]   = useState('')
  const [savingProfile, setSavingProfile] = useState(false)
  const [tierSaving, setTierSaving] = useState(false)
  const [profileMsg, setProfileMsg] = useState('')
  const [tierMsg, setTierMsg] = useState('')

  useEffect(() => {
    Promise.all([api('/status'), api('/health'), api('/models'), api('/entitlements'), api('/account/profile')]).then(([s, h, m, e, p]) => {
      setStatus(s)
      setHealth(h)
      setModels(m)
      setEntitlements(e)
      if (p?.profile) setProfile(p.profile)
      setProfileMeta({
        auth_mode: p?.auth_mode || '',
        session_scope: p?.session_scope || '',
        updated_at: p?.updated_at || '',
        profile_complete: Boolean(p?.profile_complete),
      })
    }).catch(() => {})
  }, [])

  const resetAtlas = async () => {
    setResetting(true)
    try {
      await api('/atlas/reset', { method: 'POST', body: {} })
      setResetMsg('ATLAS session reset successfully.')
    } catch (e) {
      setResetMsg('Reset failed: ' + e.message)
    }
    setResetting(false)
    setTimeout(() => setResetMsg(''), 3000)
  }

  const envKeys = health?.env_keys || []
  const currentTier = entitlements?.tier || 'explorer'
  const developerAccess = Boolean(entitlements?.developer_access)
  const profileComplete = profileMeta.profile_complete || Boolean(profile?.display_name && profile?.email && profile?.organization)

  const saveProfile = async () => {
    setSavingProfile(true)
    try {
      const saved = await api('/account/profile', { method: 'POST', body: profile })
      if (saved?.profile) setProfile(saved.profile)
      setProfileMeta({
        auth_mode: profileMeta.auth_mode,
        session_scope: profileMeta.session_scope || 'workspace_local',
        updated_at: saved?.updated_at || '',
        profile_complete: Boolean(saved?.profile_complete),
      })
      setProfileMsg('Profile saved.')
      const e = await api('/entitlements')
      setEntitlements(e)
    } catch (e) {
      setProfileMsg('Profile save failed: ' + e.message)
    }
    setSavingProfile(false)
    setTimeout(() => setProfileMsg(''), 2500)
  }

  const changeTier = async (nextTier) => {
    setTierSaving(true)
    try {
      await api('/entitlements/tier', { method: 'POST', body: { tier: nextTier } })
      const e = await api('/entitlements')
      setEntitlements(e)
      setTierMsg(`Tier set to ${nextTier}.`)
    } catch (e) {
      setTierMsg('Tier update failed: ' + e.message)
    }
    setTierSaving(false)
    setTimeout(() => setTierMsg(''), 2500)
  }

  const toggleDeveloperAccess = async () => {
    setTierSaving(true)
    try {
      await api('/account/developer-access', { method: 'POST', body: { enabled: !developerAccess } })
      const e = await api('/entitlements')
      setEntitlements(e)
      setTierMsg(!developerAccess ? 'Developer full-access enabled.' : 'Developer full-access disabled.')
    } catch (e) {
      setTierMsg('Developer access update failed: ' + e.message)
    }
    setTierSaving(false)
    setTimeout(() => setTierMsg(''), 2500)
  }

  return (
    <div className="page-enter" style={{ padding: 24 }}>
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: 8, display: 'flex', alignItems: 'center', gap: 8 }}>
          <Settings size={20} color="var(--photon)" /> Settings
        </h1>
        <p style={{ fontSize: '0.82rem', color: 'var(--txt-sec)', margin: 0 }}>
          Configure your operator identity, runtime, and preferences
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(320px,1fr))', gap: 20 }}>
        {/* System Info */}
        <div className="glass-card-solid" style={{ padding: 20, borderLeft: '3px solid var(--photon)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
            <Zap size={16} color="var(--photon)" />
            <p style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.14em', color: 'var(--txt-sec)', margin: 0, fontWeight: 600 }}>System Info</p>
          </div>
          <div style={{ display: 'grid', gap: 0 }}>
            {[
              { label: 'Python Version', value: status?.python_version?.split(' ')[0] || '–' },
              { label: 'API Uptime',     value: status?.uptime || '–' },
              { label: 'Engine Count',  value: String(status?.engine_count ?? '–') },
              { label: 'Agent Count',   value: String(status?.agent_count ?? '–') },
              { label: 'UI Project',    value: 'mad-architecht-command-center' },
              { label: 'Port',          value: ':8000 / :5173' },
            ].map(({ label, value }, i) => (
              <div key={label} style={{ display: 'flex', justifyContent: 'space-between', padding: '10px 0', borderTop: i ? '1px solid var(--border)' : 'none' }}>
                <span style={{ fontSize: '0.8rem', color: 'var(--txt-mut)' }}>{label}</span>
                <span style={{ fontSize: '0.82rem', fontFamily: 'JetBrains Mono,monospace', color: 'var(--txt-pri)' }}>{value}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Environment */}
        <div className="glass-card-solid" style={{ padding: 20, borderLeft: '3px solid var(--cyan)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <Lock size={16} color="var(--cyan)" />
              <p style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.14em', color: 'var(--txt-sec)', fontWeight: 600, margin: 0 }}>.env Variables</p>
            </div>
            <button onClick={() => setMasked(m => !m)}
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--txt-sec)', display: 'flex', alignItems: 'center', gap: 4, fontSize: '0.75rem', transition: 'color 0.15s' }}>
              {masked ? <Eye size={14} /> : <EyeOff size={14} />}
              {masked ? 'Show keys' : 'Hide keys'}
            </button>
          </div>
          {envKeys.length > 0 ? envKeys.map((k, i) => (
            <div key={k} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0', borderTop: i ? '1px solid var(--border)' : 'none' }}>
              <span style={{ fontSize: '0.82rem', fontFamily: 'JetBrains Mono,monospace', color: 'var(--txt-pri)' }}>{k}</span>
              <span style={{ fontSize: '0.72rem', fontFamily: 'JetBrains Mono,monospace', color: 'var(--txt-mut)' }}>
                {masked ? '••••••••' : '(set)'}
              </span>
            </div>
          )) : (
            <p style={{ color: 'var(--txt-mut)', fontSize: '0.85rem', margin: 0 }}>
              {health ? 'No .env keys found.' : 'Connecting to backend…'}
            </p>
          )}
        </div>

        {/* ATLAS */}
        <div className="glass-card-solid" style={{ padding: 20, borderLeft: '3px solid var(--photon)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
            <RotateCcw size={16} color="var(--photon)" />
            <p style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.14em', color: 'var(--txt-sec)', fontWeight: 600, margin: 0 }}>ATLAS Session</p>
          </div>
          <p style={{ fontSize: '0.85rem', color: 'var(--txt-sec)', marginBottom: 16, lineHeight: 1.5 }}>
            Clear the current learning session stored in <code style={{ fontFamily: 'JetBrains Mono,monospace', fontSize: '0.8rem', color: 'var(--photon)', background: 'rgba(77,166,255,0.1)', padding: '2px 6px', borderRadius: 4 }}>.mammoth/atlas_cli_session.json</code>.
          </p>
          <button onClick={resetAtlas} disabled={resetting}
            style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '9px 14px', borderRadius: 8, border: '1px solid rgba(239,68,68,0.3)', background: 'rgba(239,68,68,0.08)', color: '#f87171', fontSize: '0.85rem', fontWeight: 600, cursor: 'pointer', opacity: resetting ? 0.7 : 1, transition: 'all 0.15s' }}>
            <RotateCcw size={14} /> {resetting ? 'Resetting…' : 'Reset ATLAS Session'}
          </button>
          {resetMsg && (
            <p style={{ marginTop: 10, fontSize: '0.78rem', color: resetMsg.includes('success') ? '#22c55e' : '#f87171', margin: 0 }}>{resetMsg}</p>
          )}
        </div>

        {/* Theme */}
        <div className="glass-card-solid" style={{ padding: 20, borderLeft: '3px solid var(--violet)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
            <Palette size={16} color="var(--violet)" />
            <p style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.14em', color: 'var(--txt-sec)', fontWeight: 600, margin: 0 }}>Theme</p>
          </div>
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 12 }}>
            {THEME_OPTIONS.map(t => {
              const active = theme === t.id
              return (
                <div key={t.id} onClick={() => setTheme && setTheme(t.id)}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 8,
                    padding: '10px 16px', borderRadius: 10, cursor: 'pointer',
                    background: t.bg,
                    border: `2px solid ${active ? 'var(--violet)' : 'rgba(255,255,255,0.08)'}`,
                    boxShadow: active ? '0 0 12px rgba(168,85,247,0.35)' : 'none',
                    transition: 'all 0.15s',
                  }}>
                  <div style={{ width: 16, height: 16, borderRadius: '50%', background: t.bg, border: `2px solid ${active ? 'var(--violet)' : 'rgba(255,255,255,0.2)'}` }} />
                  <span style={{ fontSize: '0.82rem', color: active ? 'var(--violet)' : 'var(--txt-pri)', fontWeight: active ? 600 : 400 }}>{t.label}</span>
                </div>
              )
            })}
          </div>
          <p style={{ marginBottom: 0, fontSize: '0.72rem', color: 'var(--txt-mut)' }}>
            Active: <span style={{ color: 'var(--violet)', fontFamily: 'JetBrains Mono,monospace', fontWeight: 600 }}>{theme || 'darker'}</span>
          </p>
        </div>

        {/* AI Runtime */}
        <div className="glass-card-solid" style={{ padding: 20, borderLeft: '3px solid var(--cyan)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
            <Zap size={16} color="var(--cyan)" />
            <p style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.14em', color: 'var(--txt-sec)', fontWeight: 600, margin: 0 }}>
              AI Runtime Integration
            </p>
          </div>
          <div style={{ display: 'grid', gap: 0, marginBottom: 14 }}>
            {[
              { label: 'Active Adapter', value: models?.active_adapter || '–' },
              { label: 'Active Model', value: models?.active_model || '–' },
              { label: 'Ollama Running', value: models?.ollama_running ? '✓ Yes' : '✗ No', color: models?.ollama_running ? '#22c55e' : '#f87171' },
              { label: 'OpenAI Key', value: models?.openai_key_present ? '✓ Present' : '✗ Missing', color: models?.openai_key_present ? '#22c55e' : '#f87171' },
            ].map(({ label, value, color }, i) => (
              <div key={label} style={{ display: 'flex', justifyContent: 'space-between', padding: '10px 0', borderTop: i ? '1px solid var(--border)' : 'none' }}>
                <span style={{ fontSize: '0.8rem', color: 'var(--txt-mut)' }}>{label}</span>
                <span style={{ fontSize: '0.82rem', fontFamily: 'JetBrains Mono,monospace', color: color || 'var(--txt-pri)', fontWeight: color ? 600 : 400 }}>{value}</span>
              </div>
            ))}
          </div>
          <p style={{ fontSize: '0.72rem', color: 'var(--txt-sec)', marginBottom: 10, margin: '12px 0 10px' }}>Discovered local models</p>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {(models?.models || []).filter((m) => m.provider === 'ollama').map((m) => (
              <span key={m.id} style={{
                padding: '5px 10px', borderRadius: 6,
                border: `1px solid ${m.installed ? '#22c55e' : 'var(--border)'}`,
                fontSize: '0.72rem', fontFamily: 'JetBrains Mono,monospace',
                color: m.installed ? '#22c55e' : 'var(--txt-mut)',
                background: m.installed ? 'rgba(34,197,94,0.08)' : 'rgba(255,255,255,0.03)',
                transition: 'all 0.15s'
              }}>
                {m.id}
              </span>
            ))}
          </div>
        </div>

        {/* Account & Access */}
        <div className="glass-card-solid" style={{ padding: 20, borderLeft: '3px solid var(--photon)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 18 }}>
            <User size={16} color="var(--photon)" />
            <p style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.14em', color: 'var(--txt-sec)', fontWeight: 600, margin: 0 }}>
              Account & Access
            </p>
          </div>

          {/* Profile form */}
          <div style={{ marginBottom: 18, paddingBottom: 16, borderBottom: '1px solid var(--border)' }}>
            <div style={{ fontSize: '0.76rem', fontWeight: 600, color: 'var(--txt-pri)', marginBottom: 10, display: 'flex', alignItems: 'center', gap: 8 }}>
              <User size={14} color="var(--photon)" />
              Operator Identity
            </div>
            <div style={{ display: 'grid', gap: 10 }}>
              <input
                value={profile.display_name || ''}
                onChange={(e) => setProfile((p) => ({ ...p, display_name: e.target.value }))}
                placeholder="Display name"
                style={{ width: '100%', padding: '9px 12px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(0,245,212,0.04)', color: 'var(--txt-pri)', fontSize: '0.82rem', outline: 'none', transition: 'border-color 0.15s' }}
              />
              <input
                value={profile.email || ''}
                onChange={(e) => setProfile((p) => ({ ...p, email: e.target.value }))}
                placeholder="Email"
                style={{ width: '100%', padding: '9px 12px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(0,245,212,0.04)', color: 'var(--txt-pri)', fontSize: '0.82rem', outline: 'none', transition: 'border-color 0.15s' }}
              />
              <input
                value={profile.organization || ''}
                onChange={(e) => setProfile((p) => ({ ...p, organization: e.target.value }))}
                placeholder="Organization"
                style={{ width: '100%', padding: '9px 12px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(0,245,212,0.04)', color: 'var(--txt-pri)', fontSize: '0.82rem', outline: 'none', transition: 'border-color 0.15s' }}
              />
              <button
                onClick={saveProfile}
                disabled={savingProfile}
                style={{ padding: '9px 12px', borderRadius: 8, border: 'none', background: 'linear-gradient(90deg, var(--photon), var(--cyan))', color: '#050608', fontSize: '0.8rem', fontWeight: 700, cursor: 'pointer', opacity: savingProfile ? 0.7 : 1, transition: 'opacity 0.15s' }}
              >
                {savingProfile ? 'Saving profile…' : 'Save profile'}
              </button>
            </div>
            {profileMsg && <p style={{ marginTop: 10, fontSize: '0.76rem', color: profileMsg.includes('failed') ? '#f87171' : '#22c55e', margin: 0 }}>{profileMsg}</p>}
          </div>

          {/* Session & readiness */}
          <div style={{ marginBottom: 16, display: 'grid', gap: 8 }}>
            <div style={{ display: 'grid', gap: 6, padding: '10px 12px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)' }}>
              <div style={{ fontSize: '0.75rem', color: 'var(--txt-sec)', display: 'flex', alignItems: 'center', gap: 6 }}>
                <Lock size={12} color="var(--photon)" />
                Session mode: <span style={{ color: 'var(--photon)', fontFamily: 'JetBrains Mono,monospace', fontWeight: 600 }}>{profileMeta.auth_mode || entitlements?.auth_mode || 'local_operator'}</span>
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--txt-sec)', display: 'flex', alignItems: 'center', gap: 6 }}>
                {profileComplete ? <CheckCircle size={12} color="#22c55e" /> : <AlertCircle size={12} color="#eab308" />}
                Profile readiness: <span style={{ color: profileComplete ? '#22c55e' : '#eab308', fontWeight: 700 }}>{profileComplete ? 'complete' : 'needs identity'}</span>
              </div>
              <div style={{ fontSize: '0.72rem', color: 'var(--txt-mut)' }}>
                Scope: {profileMeta.session_scope || entitlements?.session_scope || 'workspace_local'}
              </div>
              {(profileMeta.updated_at || entitlements?.tier_updated_at || entitlements?.developer_access_updated_at) && (
                <div style={{ fontSize: '0.7rem', color: 'var(--txt-mut)' }}>
                  {profileMeta.updated_at ? `Updated ${new Date(profileMeta.updated_at).toLocaleString()}` : ''}
                  {entitlements?.tier_updated_at ? ` • Tier ${new Date(entitlements.tier_updated_at).toLocaleString()}` : ''}
                  {entitlements?.developer_access_updated_at ? ` • Dev ${new Date(entitlements.developer_access_updated_at).toLocaleString()}` : ''}
                </div>
              )}
            </div>
          </div>

          {/* Tier & access controls */}
          <div style={{ marginBottom: 14 }}>
            <div style={{ fontSize: '0.76rem', fontWeight: 600, color: 'var(--txt-pri)', marginBottom: 10, display: 'flex', alignItems: 'center', gap: 8 }}>
              <Zap size={14} color="var(--cyan)" />
              Access Tier: <span style={{ color: 'var(--cyan)', fontFamily: 'JetBrains Mono,monospace' }}>{entitlements?.effective_tier || currentTier}</span>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(100px,1fr))', gap: 8, marginBottom: 12 }}>
              {['explorer', 'pro', 'enterprise'].map((tier) => (
                <button
                  key={tier}
                  onClick={() => changeTier(tier)}
                  disabled={tierSaving}
                  style={{
                    padding: '8px 12px',
                    borderRadius: 8,
                    border: `1.5px solid ${currentTier === tier ? 'var(--cyan)' : 'var(--border)'}`,
                    background: currentTier === tier ? 'rgba(0,245,212,0.12)' : 'rgba(255,255,255,0.04)',
                    color: currentTier === tier ? 'var(--cyan)' : 'var(--txt-sec)',
                    fontSize: '0.75rem',
                    fontWeight: 600,
                    textTransform: 'capitalize',
                    cursor: 'pointer',
                    transition: 'all 0.15s',
                  }}
                >
                  {tier}
                </button>
              ))}
            </div>
            <button
              onClick={toggleDeveloperAccess}
              disabled={tierSaving}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                padding: '9px 12px',
                borderRadius: 8,
                border: `1.5px solid ${developerAccess ? '#22c55e' : 'var(--border)'}`,
                background: developerAccess ? 'rgba(34,197,94,0.12)' : 'rgba(255,255,255,0.04)',
                color: developerAccess ? '#22c55e' : 'var(--txt-sec)',
                fontSize: '0.75rem',
                fontWeight: 600,
                cursor: 'pointer',
                transition: 'all 0.15s',
              }}
            >
              <Code2 size={14} />
              {developerAccess ? 'Disable Dev Full Access' : 'Enable Dev Full Access'}
            </button>
            {tierMsg && <p style={{ marginTop: 10, fontSize: '0.76rem', color: tierMsg.includes('failed') ? '#f87171' : '#22c55e', margin: 0 }}>{tierMsg}</p>}
          </div>
        </div>
      </div>
    </div>
  )
}