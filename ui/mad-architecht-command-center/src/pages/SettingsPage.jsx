import { useState, useEffect } from 'react'
import { Settings, Eye, EyeOff, RotateCcw } from 'lucide-react'
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
      <h1 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: 20, display: 'flex', alignItems: 'center', gap: 8 }}>
        <Settings size={20} color="var(--txt-sec)" /> Settings
      </h1>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(320px,1fr))', gap: 20 }}>
        {/* System Info */}
        <div className="glass-card-solid" style={{ padding: 20 }}>
          <p style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.14em', color: 'var(--txt-sec)', marginBottom: 12, fontWeight: 600 }}>System Info</p>
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
        <div className="glass-card-solid" style={{ padding: 20 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
            <p style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.14em', color: 'var(--txt-sec)', fontWeight: 600 }}>.env Variables</p>
            <button onClick={() => setMasked(m => !m)}
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--txt-sec)', display: 'flex', alignItems: 'center', gap: 4, fontSize: '0.75rem' }}>
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
            <p style={{ color: 'var(--txt-mut)', fontSize: '0.85rem' }}>
              {health ? 'No .env keys found.' : 'Connecting to backend…'}
            </p>
          )}
        </div>

        {/* ATLAS */}
        <div className="glass-card-solid" style={{ padding: 20 }}>
          <p style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.14em', color: 'var(--txt-sec)', marginBottom: 12, fontWeight: 600 }}>ATLAS Session</p>
          <p style={{ fontSize: '0.85rem', color: 'var(--txt-sec)', marginBottom: 16, lineHeight: 1.5 }}>
            Resets the current ATLAS learning session stored in <code style={{ fontFamily: 'JetBrains Mono,monospace', fontSize: '0.8rem', color: 'var(--photon)' }}>.mammoth/atlas_cli_session.json</code>.
          </p>
          <button onClick={resetAtlas} disabled={resetting}
            style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 16px', borderRadius: 8, border: '1px solid rgba(239,68,68,0.3)', background: 'rgba(239,68,68,0.08)', color: '#f87171', fontSize: '0.85rem', cursor: 'pointer', opacity: resetting ? 0.7 : 1 }}>
            <RotateCcw size={14} /> {resetting ? 'Resetting…' : 'Reset ATLAS Session'}
          </button>
          {resetMsg && (
            <p style={{ marginTop: 10, fontSize: '0.78rem', color: resetMsg.includes('success') ? '#22c55e' : '#f87171' }}>{resetMsg}</p>
          )}
        </div>

        {/* Theme */}
        <div className="glass-card-solid" style={{ padding: 20 }}>
          <p style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.14em', color: 'var(--txt-sec)', marginBottom: 12, fontWeight: 600 }}>Theme</p>
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
            {THEME_OPTIONS.map(t => {
              const active = theme === t.id
              return (
                <div key={t.id} onClick={() => setTheme && setTheme(t.id)}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 8,
                    padding: '10px 16px', borderRadius: 10, cursor: 'pointer',
                    background: t.bg,
                    border: `2px solid ${active ? 'var(--photon)' : 'rgba(255,255,255,0.08)'}`,
                    boxShadow: active ? '0 0 12px rgba(77,166,255,0.35)' : 'none',
                    transition: 'all 0.15s',
                  }}>
                  <div style={{ width: 16, height: 16, borderRadius: '50%', background: t.bg, border: `2px solid ${active ? 'var(--photon)' : 'rgba(255,255,255,0.2)'}` }} />
                  <span style={{ fontSize: '0.82rem', color: active ? 'var(--photon)' : 'var(--txt-pri)', fontWeight: active ? 600 : 400 }}>{t.label}</span>
                </div>
              )
            })}
          </div>
          <p style={{ marginTop: 10, fontSize: '0.72rem', color: 'var(--txt-mut)' }}>
            Active: <span style={{ color: 'var(--photon)', fontFamily: 'JetBrains Mono,monospace' }}>{theme || 'darker'}</span>
          </p>
        </div>

        {/* AI Runtime */}
        <div className="glass-card-solid" style={{ padding: 20 }}>
          <p style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.14em', color: 'var(--txt-sec)', marginBottom: 12, fontWeight: 600 }}>
            AI Runtime Integration
          </p>
          <div style={{ display: 'grid', gap: 0, marginBottom: 12 }}>
            {[
              { label: 'Active Adapter', value: models?.active_adapter || '–' },
              { label: 'Active Model', value: models?.active_model || '–' },
              { label: 'Ollama Running', value: models?.ollama_running ? 'Yes' : 'No' },
              { label: 'OpenAI Key', value: models?.openai_key_present ? 'Present' : 'Missing' },
            ].map(({ label, value }, i) => (
              <div key={label} style={{ display: 'flex', justifyContent: 'space-between', padding: '10px 0', borderTop: i ? '1px solid var(--border)' : 'none' }}>
                <span style={{ fontSize: '0.8rem', color: 'var(--txt-mut)' }}>{label}</span>
                <span style={{ fontSize: '0.82rem', fontFamily: 'JetBrains Mono,monospace', color: 'var(--txt-pri)' }}>{value}</span>
              </div>
            ))}
          </div>
          <p style={{ fontSize: '0.72rem', color: 'var(--txt-sec)', marginBottom: 8 }}>Discovered local models</p>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {(models?.models || []).filter((m) => m.provider === 'ollama').map((m) => (
              <span key={m.id} style={{
                padding: '4px 10px', borderRadius: 999,
                border: '1px solid var(--border)',
                fontSize: '0.72rem', fontFamily: 'JetBrains Mono,monospace',
                color: m.installed ? '#22c55e' : 'var(--txt-mut)',
                background: 'rgba(255,255,255,0.03)',
              }}>
                {m.id}
              </span>
            ))}
          </div>
        </div>

        {/* Account & Access */}
        <div className="glass-card-solid" style={{ padding: 20 }}>
          <p style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.14em', color: 'var(--txt-sec)', marginBottom: 12, fontWeight: 600 }}>
            Account & Access
          </p>
          <div style={{ display: 'grid', gap: 10, marginBottom: 14 }}>
            <input
              value={profile.display_name || ''}
              onChange={(e) => setProfile((p) => ({ ...p, display_name: e.target.value }))}
              placeholder="Display name"
              style={{ width: '100%', padding: '8px 10px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.04)', color: 'var(--txt-pri)', fontSize: '0.82rem' }}
            />
            <input
              value={profile.email || ''}
              onChange={(e) => setProfile((p) => ({ ...p, email: e.target.value }))}
              placeholder="Email"
              style={{ width: '100%', padding: '8px 10px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.04)', color: 'var(--txt-pri)', fontSize: '0.82rem' }}
            />
            <input
              value={profile.organization || ''}
              onChange={(e) => setProfile((p) => ({ ...p, organization: e.target.value }))}
              placeholder="Organization"
              style={{ width: '100%', padding: '8px 10px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.04)', color: 'var(--txt-pri)', fontSize: '0.82rem' }}
            />
            <button
              onClick={saveProfile}
              disabled={savingProfile}
              style={{ padding: '8px 12px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.06)', color: 'var(--txt-pri)', fontSize: '0.8rem', cursor: 'pointer' }}
            >
              {savingProfile ? 'Saving profile…' : 'Save profile'}
            </button>
          </div>
          <div style={{ display: 'grid', gap: 8 }}>
            <div style={{ display: 'grid', gap: 6, padding: '10px 12px', borderRadius: 10, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)' }}>
              <div style={{ fontSize: '0.76rem', color: 'var(--txt-sec)' }}>
                Session mode: <span style={{ color: 'var(--cyan)', fontFamily: 'JetBrains Mono,monospace' }}>{profileMeta.auth_mode || entitlements?.auth_mode || 'local_operator'}</span>
              </div>
              <div style={{ fontSize: '0.76rem', color: 'var(--txt-sec)' }}>
                Profile readiness: <span style={{ color: profileComplete ? '#22c55e' : '#eab308', fontWeight: 700 }}>{profileComplete ? 'complete' : 'needs identity fields'}</span>
              </div>
              <div style={{ fontSize: '0.72rem', color: 'var(--txt-mut)' }}>
                Workspace session scope: {profileMeta.session_scope || entitlements?.session_scope || 'workspace_local'}
              </div>
              {(profileMeta.updated_at || entitlements?.developer_access_updated_at || entitlements?.tier_updated_at) && (
                <div style={{ fontSize: '0.72rem', color: 'var(--txt-mut)' }}>
                  {profileMeta.updated_at ? `Profile updated ${new Date(profileMeta.updated_at).toLocaleString()}` : 'Profile not saved yet'}
                  {entitlements?.tier_updated_at ? ` • Tier ${new Date(entitlements.tier_updated_at).toLocaleString()}` : ''}
                  {entitlements?.developer_access_updated_at ? ` • Dev access ${new Date(entitlements.developer_access_updated_at).toLocaleString()}` : ''}
                </div>
              )}
            </div>
            <div style={{ fontSize: '0.76rem', color: 'var(--txt-sec)' }}>
              Tier: <span style={{ color: 'var(--cyan)', textTransform: 'capitalize', fontWeight: 700 }}>{entitlements?.effective_tier || currentTier}</span>
            </div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {['explorer', 'pro', 'enterprise'].map((tier) => (
                <button
                  key={tier}
                  onClick={() => changeTier(tier)}
                  disabled={tierSaving}
                  style={{
                    padding: '6px 10px',
                    borderRadius: 8,
                    border: `1px solid ${currentTier === tier ? 'var(--cyan)' : 'var(--border)'}`,
                    background: currentTier === tier ? 'rgba(0,245,212,0.12)' : 'rgba(255,255,255,0.04)',
                    color: currentTier === tier ? 'var(--cyan)' : 'var(--txt-sec)',
                    fontSize: '0.75rem',
                    textTransform: 'capitalize',
                    cursor: 'pointer',
                  }}
                >
                  {tier}
                </button>
              ))}
              <button
                onClick={toggleDeveloperAccess}
                disabled={tierSaving}
                style={{
                  padding: '6px 10px',
                  borderRadius: 8,
                  border: `1px solid ${developerAccess ? '#22c55e' : 'var(--border)'}`,
                  background: developerAccess ? 'rgba(34,197,94,0.12)' : 'rgba(255,255,255,0.04)',
                  color: developerAccess ? '#22c55e' : 'var(--txt-sec)',
                  fontSize: '0.75rem',
                  cursor: 'pointer',
                }}
              >
                {developerAccess ? 'Disable Dev Full Access' : 'Enable Dev Full Access'}
              </button>
            </div>
            {profileMsg && <p style={{ margin: 0, fontSize: '0.76rem', color: profileMsg.includes('failed') ? '#f87171' : '#22c55e' }}>{profileMsg}</p>}
            {tierMsg && <p style={{ margin: 0, fontSize: '0.76rem', color: tierMsg.includes('failed') ? '#f87171' : '#22c55e' }}>{tierMsg}</p>}
          </div>
        </div>
      </div>
    </div>
  )
}