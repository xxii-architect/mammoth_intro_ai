import { useEffect, useMemo, useState } from 'react'
import { Copy, FileText, FolderOpen, Sparkles, Trash2 } from 'lucide-react'
import { api } from '../api/client'

const STORAGE_KEY = 'mammoth_artifact_library_v1'

function loadArtifacts() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function formatStamp(value) {
  if (!value) return 'just now'
  try {
    return new Date(value).toLocaleString([], {
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
    })
  } catch {
    return 'just now'
  }
}

export default function ArtifactLibraryPage() {
  const [items, setItems] = useState(() => loadArtifacts())
  const [source, setSource] = useState('local')

  const sorted = useMemo(
    () => [...items].sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0)),
    [items],
  )

  useEffect(() => {
    const load = async () => {
      try {
        const data = await api('/workspace/artifacts')
        if (Array.isArray(data?.artifacts)) {
          setItems(data.artifacts)
          setSource('backend')
          localStorage.setItem(STORAGE_KEY, JSON.stringify(data.artifacts))
          return
        }
      } catch {
        // keep local fallback
      }
      setSource('local')
      setItems(loadArtifacts())
    }
    load()
  }, [])

  const removeItem = (id) => {
    const applyLocalRemove = () => setItems((prev) => {
      const next = prev.filter((item) => item.id !== id)
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
      return next
    })
    if (source !== 'backend') {
      applyLocalRemove()
      return
    }
    api(`/workspace/artifacts/${encodeURIComponent(id)}`, { method: 'DELETE' })
      .then(() => applyLocalRemove())
      .catch(() => {
        setSource('local')
        applyLocalRemove()
      })
  }

  const copySnippet = async (text) => {
    if (!text) return
    try {
      await navigator.clipboard.writeText(text)
    } catch {
      // no-op: clipboard fallback is optional for this surface
    }
  }

  return (
    <div className="page-enter" style={{ padding: '24px', maxWidth: 1280, margin: '0 auto', width: '100%' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap', marginBottom: 20 }}>
        <div>
          <div style={{ fontSize: '0.72rem', letterSpacing: '0.14em', textTransform: 'uppercase', color: 'var(--txt-mut)', marginBottom: 8 }}>
            Artifact Index
          </div>
          <h1 style={{ margin: 0, fontSize: '1.5rem', color: 'var(--txt-pri)' }}>Saved reports & outputs</h1>
          <p style={{ margin: '8px 0 0', fontSize: '0.72rem', color: 'var(--txt-mut)' }}>
            Source: {source}
          </p>
        </div>
        <button
        type="button"
        onClick={() => {
          setItems([])
          localStorage.setItem(STORAGE_KEY, JSON.stringify([]))
          if (source === 'backend') {
            api('/workspace/artifacts', { method: 'DELETE' }).catch(() => {})
          }
        }}
          style={{ display: 'inline-flex', alignItems: 'center', gap: 8, padding: '8px 12px', borderRadius: 10, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.04)', color: 'var(--txt-sec)', cursor: 'pointer' }}
        >
          <Trash2 size={14} /> Clear library
        </button>
      </div>

      {sorted.length === 0 ? (
        <div className="glass-card-solid" style={{ padding: 28, textAlign: 'center', maxWidth: 760, margin: '0 auto' }}>
          <Sparkles size={32} color="var(--photon)" style={{ marginBottom: 12 }} />
          <h2 style={{ margin: '0 0 10px', color: 'var(--txt-pri)' }}>No saved artifacts yet</h2>
          <p style={{ margin: 0, color: 'var(--txt-sec)', lineHeight: 1.7 }}>
            Save a research brief, coding report, or lesson summary to build a proper artifact library that stays with your workspace.
          </p>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: 16 }}>
          {sorted.map((item) => (
            <div key={item.id} className="glass-card-solid" style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 12 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <FileText size={16} color="var(--cyan)" />
                  <span style={{ fontWeight: 700, color: 'var(--txt-pri)', fontSize: '0.9rem' }}>{item.title || 'Saved artifact'}</span>
                </div>
                <span style={{ fontSize: '0.66rem', color: 'var(--txt-mut)', background: 'rgba(255,255,255,0.04)', border: '1px solid var(--border)', borderRadius: 999, padding: '4px 8px' }}>
                  {item.format || 'txt'}
                </span>
              </div>

              <div style={{ color: 'var(--txt-sec)', fontSize: '0.76rem', lineHeight: 1.6 }}>
                {item.summary || item.body?.slice(0, 140) || 'No summary provided.'}
              </div>

              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', color: 'var(--txt-mut)', fontSize: '0.68rem' }}>
                <span>{item.source || 'workspace'}</span>
                <span>•</span>
                <span>{formatStamp(item.created_at)}</span>
              </div>

              {item.path && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--txt-sec)', fontSize: '0.72rem', overflowWrap: 'anywhere' }}>
                  <FolderOpen size={14} />
                  <span>{item.path}</span>
                </div>
              )}

              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 'auto' }}>
                {item.body && (
                  <button
                    type="button"
                    onClick={() => copySnippet(item.body)}
                    style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '6px 10px', borderRadius: 8, border: '1px solid rgba(255,255,255,0.08)', background: 'rgba(255,255,255,0.03)', color: 'var(--txt-sec)', cursor: 'pointer', fontSize: '0.7rem' }}
                  >
                    <Copy size={12} /> Copy
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => removeItem(item.id)}
                  style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '6px 10px', borderRadius: 8, border: '1px solid rgba(248,113,113,0.25)', background: 'rgba(248,113,113,0.06)', color: '#fca5a5', cursor: 'pointer', fontSize: '0.7rem' }}
                >
                  Remove
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
