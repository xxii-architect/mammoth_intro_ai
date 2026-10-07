import { useCallback, useEffect, useState } from 'react'
import { ChevronDown, ChevronRight, FolderGit2, GitBranch, Check, Plus, X, RefreshCw, Lock } from 'lucide-react'
import { api } from '../api/client'

const ACTIVE_KEY = (userId) => `mammoth_active_repo_source:${userId}`

export function readActive(userId) {
  try { return window.localStorage.getItem(ACTIVE_KEY(userId)) || '' } catch { return '' }
}

export function writeActive(userId, value) {
  try {
    if (value) window.localStorage.setItem(ACTIVE_KEY(userId), value)
    else window.localStorage.removeItem(ACTIVE_KEY(userId))
  } catch { /* storage may be blocked */ }
}

const SLUG_RE = /^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})\/[A-Za-z0-9._-]{1,100}$/

function normalizeSlug(raw) {
  return String(raw || '').trim().replace(/^https?:\/\/(www\.)?github\.com\//i, '').replace(/\.git$/, '').replace(/\/+$/, '')
}

/**
 * Backend-driven repo source picker.
 * - Default selection is "No repository" (no repo context is sent).
 * - Options come from /api/mammoth/repo-sources; the platform repo only appears for the owner/admin.
 * - Users connect public GitHub repos by owner/repo; the backend clones them into a per-user sandbox.
 */
export default function RepoSourcesPanel({ userId, value, onChange, compact = false }) {
  const [open, setOpen] = useState(false)
  const [options, setOptions] = useState([])
  const [sources, setSources] = useState([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')

  const refresh = useCallback(async () => {
    try {
      const data = await api('/mammoth/repo-sources')
      const nextOptions = Array.isArray(data?.options) ? data.options : []
      setOptions(nextOptions)
      setSources(Array.isArray(data?.sources) ? data.sources : [])
      const stored = readActive(userId)
      const stillValid = nextOptions.some((opt) => opt.value === stored)
      onChange?.(stillValid ? stored : '')
      if (!stillValid && stored) writeActive(userId, '')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load repo sources')
    }
  }, [userId, onChange])

  useEffect(() => { refresh() }, [refresh])

  const select = (next) => {
    writeActive(userId, next)
    onChange?.(next)
  }

  const connect = async () => {
    const slug = normalizeSlug(input)
    if (!SLUG_RE.test(slug)) {
      setError('Use a GitHub repository in owner/repo form.')
      return
    }
    setBusy('connect')
    setError('')
    try {
      const data = await api('/mammoth/repo-sources', { method: 'POST', body: { repo: slug } })
      if (data?.status !== 'ok') {
        setError(data?.error || 'Could not connect repository.')
      } else {
        setInput('')
        await refresh()
        if (data?.source?.id) select(data.source.id)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not connect repository.')
    } finally {
      setBusy('')
    }
  }

  const sync = async (id) => {
    setBusy(`sync:${id}`)
    try {
      const data = await api(`/mammoth/repo-sources/${encodeURIComponent(id)}/sync`, { method: 'POST' })
      if (data?.status !== 'ok') setError(data?.error || 'Sync failed.')
      await refresh()
    } finally {
      setBusy('')
    }
  }

  const remove = async (id) => {
    setBusy(`remove:${id}`)
    try {
      await api(`/mammoth/repo-sources/${encodeURIComponent(id)}`, { method: 'DELETE' })
      if (value === id) select('')
      await refresh()
    } finally {
      setBusy('')
    }
  }

  const active = options.find((opt) => opt.value === value)
  const sourceById = Object.fromEntries(sources.map((s) => [s.id, s]))

  const rowStyle = (selected) => ({
    display: 'flex', alignItems: 'center', gap: 6, padding: '8px 10px', borderRadius: 9,
    border: `1px solid ${selected ? 'rgba(77,166,255,0.35)' : 'var(--border)'}`,
    background: selected ? 'rgba(77,166,255,0.08)' : 'rgba(255,255,255,0.025)', cursor: 'pointer',
  })
  const iconBtn = { background: 'none', border: 'none', cursor: 'pointer', color: 'var(--txt-mut)', padding: 2, display: 'flex' }

  return (
    <div className="glass-card-solid" style={{ padding: compact ? 14 : 16, borderLeft: '3px solid var(--mm-color-system-default)' }}>
      <button
        type="button"
        onClick={() => setOpen((p) => !p)}
        aria-expanded={open}
        style={{ width: '100%', textAlign: 'left', background: 'none', border: 'none', cursor: 'pointer', color: 'var(--txt-pri)' }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <FolderGit2 size={14} color="var(--mm-color-system-default)" />
            <p style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.14em', color: 'var(--txt-sec)', fontWeight: 700, margin: 0 }}>Repo Context</p>
          </div>
          {open ? <ChevronDown size={13} color="var(--txt-mut)" /> : <ChevronRight size={13} color="var(--txt-mut)" />}
        </div>
      </button>
      <div style={{ marginTop: 8, fontSize: '0.76rem', color: 'var(--txt-sec)' }}>
        Active: <span style={{ color: active ? 'var(--mm-color-system-default)' : 'var(--txt-mut)', fontFamily: 'JetBrains Mono,monospace', fontWeight: 700 }}>
          {active?.label || 'No repository'}
        </span>
      </div>

      {open && (
        <div style={{ marginTop: 12, display: 'grid', gap: 10 }}>
          <div style={{ display: 'flex', gap: 6 }}>
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') connect() }}
              placeholder="owner/repo (public GitHub)"
              aria-label="Connect a GitHub repository"
              style={{ flex: 1, background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, color: 'var(--txt-pri)', fontSize: '0.76rem', padding: '7px 10px', outline: 'none', fontFamily: 'JetBrains Mono,monospace' }}
            />
            <button
              type="button"
              onClick={connect}
              disabled={!input.trim() || busy === 'connect'}
              style={{ display: 'inline-flex', alignItems: 'center', gap: 4, padding: '7px 10px', borderRadius: 8, border: '1px solid rgba(77,166,255,0.3)', background: 'rgba(77,166,255,0.12)', color: 'var(--photon)', fontSize: '0.74rem', cursor: input.trim() ? 'pointer' : 'not-allowed', opacity: input.trim() ? 1 : 0.5 }}
            >
              <Plus size={13} /> {busy === 'connect' ? 'Cloning…' : 'Connect'}
            </button>
          </div>
          <p style={{ fontSize: '0.7rem', color: 'var(--txt-mut)', margin: 0, lineHeight: 1.5 }}>
            Repos are cloned into your private sandbox. Edits are proposals (branch + patch); MammothOS never pushes.
          </p>
          {error && <p role="alert" style={{ fontSize: '0.72rem', color: 'var(--red, #f87171)', margin: 0 }}>{error}</p>}

          <div style={{ display: 'grid', gap: 6 }}>
            <div style={rowStyle(!value)} onClick={() => select('')}>
              <X size={12} color={!value ? 'var(--mm-color-system-default)' : 'var(--txt-mut)'} />
              <span style={{ flex: 1, fontSize: '0.74rem', color: !value ? 'var(--photon)' : 'var(--txt-sec)' }}>No repository (no repo context)</span>
              {!value && <Check size={12} color="var(--mm-color-system-default)" />}
            </div>
            {options.map((opt) => {
              const selected = value === opt.value
              const source = sourceById[opt.value]
              const ready = opt.scope === 'platform' || source?.status === 'ready'
              return (
                <div key={opt.id} style={rowStyle(selected)} onClick={() => ready && select(opt.value)} title={ready ? '' : (source?.error || 'Not synced yet')}>
                  {opt.scope === 'platform' ? <Lock size={12} color="var(--amber, #f59e0b)" /> : <GitBranch size={12} color={selected ? 'var(--mm-color-system-default)' : 'var(--txt-mut)'} />}
                  <span style={{ flex: 1, fontSize: '0.74rem', fontFamily: 'JetBrains Mono,monospace', color: selected ? 'var(--photon)' : 'var(--txt-sec)', overflowWrap: 'anywhere', opacity: ready ? 1 : 0.6 }}>
                    {opt.label}{!ready && source?.status ? ` · ${source.status}` : ''}
                  </span>
                  {selected && <Check size={12} color="var(--mm-color-system-default)" />}
                  {opt.scope === 'tenant' && (
                    <>
                      <button type="button" aria-label={`Sync ${opt.label}`} onClick={(e) => { e.stopPropagation(); sync(opt.value) }} style={iconBtn} disabled={busy === `sync:${opt.value}`}>
                        <RefreshCw size={12} />
                      </button>
                      <button type="button" aria-label={`Remove ${opt.label}`} onClick={(e) => { e.stopPropagation(); remove(opt.value) }} style={iconBtn} disabled={busy === `remove:${opt.value}`}>
                        <X size={12} />
                      </button>
                    </>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
