import { useRef, useState } from 'react'
import { Paperclip, X, FileText, Code, FileJson, Loader, Upload } from 'lucide-react'
import { authorizedFetch } from '../api/client'

const EXT_ICONS = {
  '.py': Code, '.js': Code, '.jsx': Code, '.ts': Code, '.tsx': Code,
  '.json': FileJson, '.md': FileText, '.txt': FileText,
}

function fileIcon(name) {
  const ext = name.includes('.') ? '.' + name.split('.').pop().toLowerCase() : ''
  const Icon = EXT_ICONS[ext] || FileText
  return <Icon size={13} />
}

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes}B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`
}

/**
 * FileAttachmentPanel — attach files to chat messages for context.
 * Props:
 *   attached: [{ file_id, name, size }]   — currently attached files
 *   onAttach(file): adds a file to attached list
 *   onRemove(file_id): removes from attached list
 */
export default function FileAttachmentPanel({ attached = [], onAttach, onRemove }) {
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')
  const inputRef = useRef(null)

  const handleFileChange = async (e) => {
    const files = Array.from(e.target.files || [])
    if (!files.length) return
    e.target.value = ''
    setError('')
    setUploading(true)
    for (const file of files.slice(0, 4)) {
      try {
        const form = new FormData()
        form.append('file', file)
        const resp = await authorizedFetch('/mammoth/files/upload', { method: 'POST', body: form })
        const data = await resp.json()
        if (data.status === 'ok') {
          onAttach({ file_id: data.file_id, name: data.name, size: data.size })
        } else {
          setError(data.error || 'Upload failed')
        }
      } catch {
        setError('Upload failed')
      }
    }
    setUploading(false)
  }

  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 6, padding: '4px 0' }}>
      {/* Attached file chips */}
      {attached.map(f => (
        <div
          key={f.file_id}
          style={{ display: 'inline-flex', alignItems: 'center', gap: 5, padding: '3px 8px 3px 7px', borderRadius: 20, border: '1px solid rgba(77,166,255,0.3)', background: 'rgba(77,166,255,0.07)', fontSize: '0.72rem', color: 'var(--txt-sec)', maxWidth: 200 }}
        >
          {fileIcon(f.name)}
          <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>{f.name}</span>
          <span style={{ color: 'var(--txt-mut)', flexShrink: 0 }}>{formatSize(f.size)}</span>
          <button onClick={() => onRemove(f.file_id)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--txt-mut)', padding: '0 1px', display: 'flex', lineHeight: 1 }}>
            <X size={11} />
          </button>
        </div>
      ))}

      {/* Upload trigger */}
      <button
        type="button"
        title="Attach a file for context (.py, .ts, .md, .txt, .json, .pdf…)"
        onClick={() => inputRef.current?.click()}
        disabled={uploading}
        style={{ display: 'inline-flex', alignItems: 'center', gap: 5, padding: '4px 9px', borderRadius: 20, border: '1px solid rgba(255,255,255,0.12)', background: 'rgba(255,255,255,0.04)', color: uploading ? 'var(--txt-mut)' : 'var(--txt-sec)', cursor: uploading ? 'default' : 'pointer', fontSize: '0.72rem' }}
      >
        {uploading ? <Loader size={12} style={{ animation: 'spin 1s linear infinite' }} /> : <Paperclip size={12} />}
        {uploading ? 'Uploading…' : 'Attach'}
      </button>

      {error && (
        <span style={{ fontSize: '0.68rem', color: '#f87171' }}>{error}</span>
      )}

      <input
        ref={inputRef}
        type="file"
        style={{ display: 'none' }}
        accept=".py,.ts,.tsx,.js,.jsx,.md,.txt,.json,.toml,.yaml,.yml,.csv,.html,.css,.sh,.sql,.pdf"
        multiple
        onChange={handleFileChange}
      />
    </div>
  )
}
