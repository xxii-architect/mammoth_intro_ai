import { useEffect, useState } from 'react'
import { FolderGit2 } from 'lucide-react'
import { api } from '../../api/client'
import { readActive, writeActive } from '../RepoSourcesPanel'

/**
 * Compact repository selector for the Agent page. Options come from the backend repo policy
 * (the platform repo only appears for the owner), and the selection is shared with Mammoth Mind.
 * Only an option id is ever sent to the server, never a filesystem path.
 */
export default function RepoPicker({ userId, value, onChange }) {
  const [options, setOptions] = useState([])
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    let cancelled = false
    api('/mammoth/repo-sources')
      .then((data) => {
        if (cancelled) return
        const next = Array.isArray(data?.options) ? data.options : []
        setOptions(next)
        const stored = readActive(userId)
        const match = next.find((opt) => opt.value === stored)
        if (!match && stored) writeActive(userId, '')
        onChange(match ? stored : '', match?.label || '')
      })
      .catch(() => { if (!cancelled) onChange('', '') })
      .finally(() => { if (!cancelled) setLoaded(true) })
    return () => { cancelled = true }
  }, [userId])

  const select = (next) => {
    writeActive(userId, next)
    onChange(next, options.find((opt) => opt.value === next)?.label || '')
  }

  if (loaded && options.length === 0) {
    return (
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: '0.68rem', color: 'var(--txt-mut)' }}
        title="Connect a GitHub repository from Mammoth Mind's Repo Context panel">
        <FolderGit2 size={12} /> No repo connected
      </span>
    )
  }

  return (
    <label style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: '0.7rem', color: 'var(--txt-mut)', minWidth: 0 }}>
      <FolderGit2 size={12} aria-hidden="true" />
      <select value={value} onChange={(event) => select(event.target.value)} disabled={!loaded} aria-label="Repository context"
        style={{ maxWidth: 220, minWidth: 0, background: 'var(--mm-color-surface-sunken, #080a0e)', color: 'var(--txt-sec)', border: '1px solid var(--border)', borderRadius: 6, padding: '3px 6px', fontSize: '0.72rem' }}>
        <option value="">No repository</option>
        {options.map((opt) => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
      </select>
    </label>
  )
}
