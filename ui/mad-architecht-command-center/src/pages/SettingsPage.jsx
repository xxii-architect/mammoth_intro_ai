import { useEffect, useState } from 'react'
import {
  Settings,
  Eye,
  EyeOff,
  RotateCcw,
  User,
  Lock,
  Code2,
  Palette,
  Zap,
  CheckCircle,
  AlertCircle,
  Users,
  PlusCircle,
  ArrowRightLeft,
  Trash2,
} from 'lucide-react'
import { api } from '../api/client'

const THEME_OPTIONS = [
  { id: 'darker', label: 'Darker', bg: '#050608' },
  { id: 'dark', label: 'Dark', bg: '#0d1117' },
  { id: 'midnight', label: 'Midnight', bg: '#080c14' },
]

const emptyProfile = { display_name: '', email: '', organization: '' }
const emptyWorkspaceAccount = { display_name: '', email: '', organization: '', account_id: '' }

export default function SettingsPage({ theme, setTheme }) {
  const [status, setStatus] = useState(null)
  const [health, setHealth] = useState(null)
  const [models, setModels] = useState(null)
  const [entitlements, setEntitlements] = useState(null)
  const [workspace, setWorkspace] = useState(null)
  const [profile, setProfile] = useState(emptyProfile)
  const [draftAccount, setDraftAccount] = useState(emptyWorkspaceAccount)
  const [profileMeta, setProfileMeta] = useState({
    auth_mode: '',
    session_scope: '',
    updated_at: '',
    profile_complete: false,
    active_account_id: '',
    user_id: '',
  })
  const [masked, setMasked] = useState(true)
  const [resetting, setResetting] = useState(false)
  const [resetMsg, setResetMsg] = useState('')
  const [savingProfile, setSavingProfile] = useState(false)
  const [tierSaving, setTierSaving] = useState(false)
  const [workspaceSaving, setWorkspaceSaving] = useState(false)
  const [profileMsg, setProfileMsg] = useState('')
  const [tierMsg, setTierMsg] = useState('')
  const [workspaceMsg, setWorkspaceMsg] = useState('')

  const refreshAll = async () => {
    const [s, h, m, e, p, w] = await Promise.all([
      api('/status'),
      api('/health'),
      api('/models'),
      api('/entitlements'),
      api('/account/profile'),
      api('/account/workspace'),
    ])
    setStatus(s)
    setHealth(h)
    setModels(m)
    setEntitlements(e)
    setWorkspace(w)
    if (p?.profile) {
      setProfile(p.profile)
    }
    setProfileMeta({
      auth_mode: p?.auth_mode || e?.auth_mode || '',
      session_scope: p?.session_scope || e?.session_scope || '',
      updated_at: p?.updated_at || '',
      profile_complete: Boolean(p?.profile_complete),
      active_account_id: p?.active_account_id || w?.active_account_id || '',
      user_id: p?.user_id || e?.user_id || '',
    })
  }

  useEffect(() => {
    refreshAll().catch(() => {})
  }, [])

  const flashMessage = (setter, value) => {
    setter(value)
    window.setTimeout(() => setter(''), 2500)
  }

  const resetAtlas = async () => {
    setResetting(true)
    try {
      await api('/atlas/reset', { method: 'POST', body: {} })
      await refreshAll()
      flashMessage(setResetMsg, 'ATLAS session reset successfully.')
    } catch (e) {
      flashMessage(setResetMsg, 'Reset failed: ' + e.message)
    }
    setResetting(false)
  }

  const saveProfile = async () => {
    setSavingProfile(true)
    try {
      await api('/account/profile', { method: 'POST', body: profile })
      await refreshAll()
      flashMessage(setProfileMsg, 'Profile saved.')
    } catch (e) {
      flashMessage(setProfileMsg, 'Profile save failed: ' + e.message)
    }
    setSavingProfile(false)
  }

  const changeTier = async (nextTier) => {
    setTierSaving(true)
    try {
      await api('/entitlements/tier', { method: 'POST', body: { tier: nextTier } })
      await refreshAll()
      flashMessage(setTierMsg, `Tier set to ${nextTier}.`)
    } catch (e) {
      flashMessage(setTierMsg, 'Tier update failed: ' + e.message)
    }
    setTierSaving(false)
  }

  const toggleDeveloperAccess = async () => {
    setTierSaving(true)
    try {
      await api('/account/developer-access', { method: 'POST', body: { enabled: !Boolean(entitlements?.developer_access) } })
      await refreshAll()
      flashMessage(setTierMsg, !Boolean(entitlements?.developer_access) ? 'Developer full-access enabled.' : 'Developer full-access disabled.')
    } catch (e) {
      flashMessage(setTierMsg, 'Developer access update failed: ' + e.message)
    }
    setTierSaving(false)
  }

  const createWorkspaceAccount = async () => {
    setWorkspaceSaving(true)
    try {
      const result = await api('/account/workspace', {
        method: 'POST',
        body: {
          action: 'create',
          activate: true,
          ...draftAccount,
        },
      })
      if (result?.status !== 'ok') {
        throw new Error(result?.error || 'Account creation failed')
      }
      setDraftAccount(emptyWorkspaceAccount)
      await refreshAll()
      flashMessage(setWorkspaceMsg, `Workspace account ${result.active_account_id} created.`)
    } catch (e) {
      flashMessage(setWorkspaceMsg, 'Workspace account creation failed: ' + e.message)
    }
    setWorkspaceSaving(false)
  }

  const switchWorkspaceAccount = async (accountId) => {
    setWorkspaceSaving(true)
    try {
      const result = await api('/account/workspace', { method: 'POST', body: { action: 'switch', account_id: accountId } })
      if (result?.status !== 'ok') {
        throw new Error(result?.error || 'Account switch failed')
      }
      await refreshAll()
      flashMessage(setWorkspaceMsg, `Switched to ${accountId}.`)
    } catch (e) {
      flashMessage(setWorkspaceMsg, 'Workspace account switch failed: ' + e.message)
    }
    setWorkspaceSaving(false)
  }

  const deleteWorkspaceAccount = async (accountId) => {
    setWorkspaceSaving(true)
    try {
      const result = await api('/account/workspace', { method: 'POST', body: { action: 'delete', account_id: accountId } })
      if (result?.status !== 'ok') {
        throw new Error(result?.error || 'Account deletion failed')
      }
      await refreshAll()
      flashMessage(setWorkspaceMsg, `Deleted ${accountId}.`)
    } catch (e) {
      flashMessage(setWorkspaceMsg, 'Workspace account deletion failed: ' + e.message)
    }
    setWorkspaceSaving(false)
  }

  const envKeys = health?.env_keys || []
  const currentTier = entitlements?.tier || 'explorer'
  const developerAccess = Boolean(entitlements?.developer_access)
  const adminControlsEnabled = entitlements?.admin_controls_enabled !== false
  const profileComplete = profileMeta.profile_complete || Boolean(profile?.display_name && profile?.email && profile?.organization)
  const activeAccountId = workspace?.active_account_id || profileMeta.active_account_id || 'default'

  return (
    <div className="page-enter" style={{ padding: 24 }}>
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: 8, display: 'flex', alignItems: 'center', gap: 8 }}>
          <Settings size={20} color="var(--photon)" /> Settings
        </h1>
        <p style={{ fontSize: '0.82rem', color: 'var(--txt-sec)', margin: 0 }}>
          Configure workspace accounts, runtime access, and operator preferences.
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(320px,1fr))', gap: 20 }}>
        <div className="glass-card-solid" style={{ padding: 20, borderLeft: '3px solid var(--photon)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
            <Zap size={16} color="var(--photon)" />
            <p style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.14em', color: 'var(--txt-sec)', margin: 0, fontWeight: 600 }}>System Info</p>
          </div>
          <div style={{ display: 'grid', gap: 0 }}>
            {[
              { label: 'Python Version', value: status?.python_version?.split(' ')[0] || '–' },
              { label: 'API Uptime', value: status?.uptime || '–' },
              { label: 'Engine Count', value: String(status?.engine_count ?? '–') },
              { label: 'Agent Count', value: String(status?.agent_count ?? '–') },
              { label: 'Workspace Scope', value: entitlements?.session_scope || 'workspace_multi_account' },
              { label: 'Active Account', value: activeAccountId },
            ].map(({ label, value }, i) => (
              <div key={label} style={{ display: 'flex', justifyContent: 'space-between', padding: '10px 0', borderTop: i ? '1px solid var(--border)' : 'none' }}>
                <span style={{ fontSize: '0.8rem', color: 'var(--txt-mut)' }}>{label}</span>
                <span style={{ fontSize: '0.82rem', fontFamily: 'JetBrains Mono,monospace', color: 'var(--txt-pri)' }}>{value}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="glass-card-solid" style={{ padding: 20, borderLeft: '3px solid var(--cyan)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <Lock size={16} color="var(--cyan)" />
              <p style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.14em', color: 'var(--txt-sec)', fontWeight: 600, margin: 0 }}>.env Variables</p>
            </div>
            <button
              onClick={() => setMasked((m) => !m)}
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--txt-sec)', display: 'flex', alignItems: 'center', gap: 4, fontSize: '0.75rem' }}
            >
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

        <div className="glass-card-solid" style={{ padding: 20, borderLeft: '3px solid var(--violet)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
            <Palette size={16} color="var(--violet)" />
            <p style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.14em', color: 'var(--txt-sec)', fontWeight: 600, margin: 0 }}>Theme</p>
          </div>
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 12 }}>
            {THEME_OPTIONS.map((t) => {
              const active = theme === t.id
              return (
                <div
                  key={t.id}
                  onClick={() => setTheme && setTheme(t.id)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    padding: '10px 16px',
                    borderRadius: 10,
                    cursor: 'pointer',
                    background: t.bg,
                    border: `2px solid ${active ? 'var(--violet)' : 'rgba(255,255,255,0.08)'}`,
                    boxShadow: active ? '0 0 12px rgba(168,85,247,0.35)' : 'none',
                  }}
                >
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

        <div className="glass-card-solid" style={{ padding: 20, borderLeft: '3px solid var(--photon)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
            <RotateCcw size={16} color="var(--photon)" />
            <p style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.14em', color: 'var(--txt-sec)', fontWeight: 600, margin: 0 }}>ATLAS Session</p>
          </div>
          <p style={{ fontSize: '0.85rem', color: 'var(--txt-sec)', marginBottom: 16, lineHeight: 1.5 }}>
            Reset the active account&apos;s learning session without affecting other workspace accounts.
          </p>
          <button
            onClick={resetAtlas}
            disabled={resetting}
            style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '9px 14px', borderRadius: 8, border: '1px solid rgba(239,68,68,0.3)', background: 'rgba(239,68,68,0.08)', color: '#f87171', fontSize: '0.85rem', fontWeight: 600, cursor: 'pointer', opacity: resetting ? 0.7 : 1 }}
          >
            <RotateCcw size={14} /> {resetting ? 'Resetting…' : 'Reset Active Session'}
          </button>
          {resetMsg && <p style={{ marginTop: 10, fontSize: '0.78rem', color: resetMsg.includes('failed') ? '#f87171' : '#22c55e', marginBottom: 0 }}>{resetMsg}</p>}
        </div>

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
              { label: 'Ollama Running', value: models?.ollama_running ? 'Yes' : 'No', color: models?.ollama_running ? '#22c55e' : '#f87171' },
              { label: 'OpenAI Key', value: models?.openai_key_present ? 'Present' : 'Missing', color: models?.openai_key_present ? '#22c55e' : '#f87171' },
            ].map(({ label, value, color }, i) => (
              <div key={label} style={{ display: 'flex', justifyContent: 'space-between', padding: '10px 0', borderTop: i ? '1px solid var(--border)' : 'none' }}>
                <span style={{ fontSize: '0.8rem', color: 'var(--txt-mut)' }}>{label}</span>
                <span style={{ fontSize: '0.82rem', fontFamily: 'JetBrains Mono,monospace', color: color || 'var(--txt-pri)', fontWeight: color ? 600 : 400 }}>{value}</span>
              </div>
            ))}
          </div>
          <p style={{ fontSize: '0.72rem', color: 'var(--txt-sec)', margin: '12px 0 10px' }}>Discovered local models</p>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {(models?.models || []).filter((m) => m.provider === 'ollama').map((m) => (
              <span
                key={m.id}
                style={{
                  padding: '5px 10px',
                  borderRadius: 6,
                  border: `1px solid ${m.installed ? '#22c55e' : 'var(--border)'}`,
                  fontSize: '0.72rem',
                  fontFamily: 'JetBrains Mono,monospace',
                  color: m.installed ? '#22c55e' : 'var(--txt-mut)',
                  background: m.installed ? 'rgba(34,197,94,0.08)' : 'rgba(255,255,255,0.03)',
                }}
              >
                {m.id}
              </span>
            ))}
          </div>
        </div>

        <div className="glass-card-solid" style={{ padding: 20, borderLeft: '3px solid var(--photon)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 18 }}>
            <Users size={16} color="var(--photon)" />
            <p style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.14em', color: 'var(--txt-sec)', fontWeight: 600, margin: 0 }}>Workspace Accounts</p>
          </div>

          <div style={{ display: 'grid', gap: 10, marginBottom: 18 }}>
            {(workspace?.accounts || []).map((account) => (
              <div key={account.account_id} style={{ padding: '12px 14px', borderRadius: 10, border: `1px solid ${account.is_active ? 'rgba(0,245,212,0.35)' : 'var(--border)'}`, background: account.is_active ? 'rgba(0,245,212,0.06)' : 'rgba(255,255,255,0.03)' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10, marginBottom: 8 }}>
                  <div>
                    <div style={{ fontSize: '0.84rem', fontWeight: 700, color: 'var(--txt-pri)' }}>{account.label}</div>
                    <div style={{ fontSize: '0.72rem', color: 'var(--txt-mut)', fontFamily: 'JetBrains Mono,monospace' }}>{account.user_id}</div>
                  </div>
                  <div style={{ fontSize: '0.68rem', color: account.is_active ? 'var(--cyan)' : 'var(--txt-mut)', textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 700 }}>
                    {account.is_active ? 'Active' : account.tier}
                  </div>
                </div>
                <div style={{ display: 'grid', gap: 6, marginBottom: 10 }}>
                  <div style={{ fontSize: '0.75rem', color: 'var(--txt-sec)' }}>Email: {account.profile?.email || 'not set'}</div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--txt-sec)' }}>Org: {account.profile?.organization || 'not set'}</div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--txt-sec)' }}>
                    Readiness: <span style={{ color: account.profile_complete ? '#22c55e' : '#eab308', fontWeight: 700 }}>{account.profile_complete ? 'complete' : 'needs onboarding'}</span>
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  {!account.is_active && (
                    <button
                      onClick={() => switchWorkspaceAccount(account.account_id)}
                      disabled={workspaceSaving}
                      style={{ padding: '8px 10px', borderRadius: 8, border: '1px solid rgba(77,166,255,0.3)', background: 'rgba(77,166,255,0.08)', color: 'var(--photon)', cursor: 'pointer', fontSize: '0.75rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6 }}
                    >
                      <ArrowRightLeft size={13} /> Switch
                    </button>
                  )}
                  {!account.is_active && (workspace?.accounts || []).length > 1 && (
                    <button
                      onClick={() => deleteWorkspaceAccount(account.account_id)}
                      disabled={workspaceSaving}
                      style={{ padding: '8px 10px', borderRadius: 8, border: '1px solid rgba(239,68,68,0.3)', background: 'rgba(239,68,68,0.08)', color: '#f87171', cursor: 'pointer', fontSize: '0.75rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6 }}
                    >
                      <Trash2 size={13} /> Delete
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>

          <div style={{ paddingTop: 16, borderTop: '1px solid var(--border)' }}>
            <div style={{ fontSize: '0.76rem', fontWeight: 600, color: 'var(--txt-pri)', marginBottom: 10, display: 'flex', alignItems: 'center', gap: 8 }}>
              <PlusCircle size={14} color="var(--cyan)" />
              Add workspace account
            </div>
            <div style={{ display: 'grid', gap: 10 }}>
              <input
                value={draftAccount.display_name}
                onChange={(e) => setDraftAccount((prev) => ({ ...prev, display_name: e.target.value }))}
                placeholder="Display name"
                style={{ width: '100%', padding: '9px 12px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(0,245,212,0.04)', color: 'var(--txt-pri)', fontSize: '0.82rem' }}
              />
              <input
                value={draftAccount.email}
                onChange={(e) => setDraftAccount((prev) => ({ ...prev, email: e.target.value }))}
                placeholder="Email"
                style={{ width: '100%', padding: '9px 12px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(0,245,212,0.04)', color: 'var(--txt-pri)', fontSize: '0.82rem' }}
              />
              <input
                value={draftAccount.organization}
                onChange={(e) => setDraftAccount((prev) => ({ ...prev, organization: e.target.value }))}
                placeholder="Organization"
                style={{ width: '100%', padding: '9px 12px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(0,245,212,0.04)', color: 'var(--txt-pri)', fontSize: '0.82rem' }}
              />
              <input
                value={draftAccount.account_id}
                onChange={(e) => setDraftAccount((prev) => ({ ...prev, account_id: e.target.value }))}
                placeholder="Optional account id (example: student-two)"
                style={{ width: '100%', padding: '9px 12px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(0,245,212,0.04)', color: 'var(--txt-pri)', fontSize: '0.82rem' }}
              />
              <button
                onClick={createWorkspaceAccount}
                disabled={workspaceSaving}
                style={{ padding: '9px 12px', borderRadius: 8, border: 'none', background: 'linear-gradient(90deg, var(--photon), var(--cyan))', color: '#050608', fontSize: '0.8rem', fontWeight: 700, cursor: 'pointer', opacity: workspaceSaving ? 0.7 : 1 }}
              >
                {workspaceSaving ? 'Saving account…' : 'Create and activate account'}
              </button>
            </div>
            {workspaceMsg && <p style={{ marginTop: 10, fontSize: '0.76rem', color: workspaceMsg.includes('failed') ? '#f87171' : '#22c55e', marginBottom: 0 }}>{workspaceMsg}</p>}
          </div>
        </div>

        <div className="glass-card-solid" style={{ padding: 20, borderLeft: '3px solid var(--cyan)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 18 }}>
            <User size={16} color="var(--cyan)" />
            <p style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.14em', color: 'var(--txt-sec)', fontWeight: 600, margin: 0 }}>Active Account Onboarding</p>
          </div>

          <div style={{ marginBottom: 18, paddingBottom: 16, borderBottom: '1px solid var(--border)' }}>
            <div style={{ fontSize: '0.76rem', fontWeight: 600, color: 'var(--txt-pri)', marginBottom: 10 }}>Profile for {activeAccountId}</div>
            <div style={{ display: 'grid', gap: 10 }}>
              <input
                value={profile.display_name || ''}
                onChange={(e) => setProfile((p) => ({ ...p, display_name: e.target.value }))}
                placeholder="Display name"
                style={{ width: '100%', padding: '9px 12px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(0,245,212,0.04)', color: 'var(--txt-pri)', fontSize: '0.82rem' }}
              />
              <input
                value={profile.email || ''}
                onChange={(e) => setProfile((p) => ({ ...p, email: e.target.value }))}
                placeholder="Email"
                style={{ width: '100%', padding: '9px 12px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(0,245,212,0.04)', color: 'var(--txt-pri)', fontSize: '0.82rem' }}
              />
              <input
                value={profile.organization || ''}
                onChange={(e) => setProfile((p) => ({ ...p, organization: e.target.value }))}
                placeholder="Organization"
                style={{ width: '100%', padding: '9px 12px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(0,245,212,0.04)', color: 'var(--txt-pri)', fontSize: '0.82rem' }}
              />
              <button
                onClick={saveProfile}
                disabled={savingProfile}
                style={{ padding: '9px 12px', borderRadius: 8, border: 'none', background: 'linear-gradient(90deg, var(--photon), var(--cyan))', color: '#050608', fontSize: '0.8rem', fontWeight: 700, cursor: 'pointer', opacity: savingProfile ? 0.7 : 1 }}
              >
                {savingProfile ? 'Saving profile…' : 'Save profile'}
              </button>
            </div>
            {profileMsg && <p style={{ marginTop: 10, fontSize: '0.76rem', color: profileMsg.includes('failed') ? '#f87171' : '#22c55e', marginBottom: 0 }}>{profileMsg}</p>}
          </div>

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
                Scope: {profileMeta.session_scope || entitlements?.session_scope || 'workspace_multi_account'}
              </div>
              <div style={{ fontSize: '0.72rem', color: 'var(--txt-mut)', fontFamily: 'JetBrains Mono,monospace' }}>
                Learner user id: {profileMeta.user_id || entitlements?.user_id || 'workspace:default'}
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

          <div>
            <div style={{ fontSize: '0.76rem', fontWeight: 600, color: 'var(--txt-pri)', marginBottom: 10, display: 'flex', alignItems: 'center', gap: 8 }}>
              <Code2 size={14} color="var(--cyan)" />
              Access Tier: <span style={{ color: 'var(--cyan)', fontFamily: 'JetBrains Mono,monospace' }}>{entitlements?.effective_tier || currentTier}</span>
            </div>
            {!adminControlsEnabled && (
              <p style={{ margin: '0 0 10px', fontSize: '0.74rem', color: 'var(--txt-mut)' }}>
                Tier and developer-access controls are restricted to workspace admins.
              </p>
            )}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(100px,1fr))', gap: 8, marginBottom: 12 }}>
              {['explorer', 'pro', 'enterprise'].map((tier) => (
                <button
                  key={tier}
                  onClick={() => changeTier(tier)}
                  disabled={tierSaving || !adminControlsEnabled}
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
                  }}
                >
                  {tier}
                </button>
              ))}
            </div>
            <button
              onClick={toggleDeveloperAccess}
              disabled={tierSaving || !adminControlsEnabled}
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
              }}
            >
              <Code2 size={14} />
              {developerAccess ? 'Disable Dev Full Access' : 'Enable Dev Full Access'}
            </button>
            {tierMsg && <p style={{ marginTop: 10, fontSize: '0.76rem', color: tierMsg.includes('failed') ? '#f87171' : '#22c55e', marginBottom: 0 }}>{tierMsg}</p>}
          </div>
        </div>
      </div>
    </div>
  )
}
