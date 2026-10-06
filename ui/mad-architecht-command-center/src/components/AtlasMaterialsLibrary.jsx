import { useEffect, useRef, useState } from 'react'
import { Upload, Trash2, BookOpen, ClipboardList, FileText, Tag, Loader, GraduationCap, Check } from 'lucide-react'
import { api } from '../api/client'
import useDocumentUpload from './useDocumentUpload'
import DocumentUploadStatus from './DocumentUploadStatus'
import { useAuth } from '../lib/authContext'

const TAG_META = {
  textbook:  { label: 'Textbook',   icon: BookOpen,       color: '#60a5fa' },
  homework:  { label: 'Homework',   icon: ClipboardList,  color: '#f59e0b' },
  notes:     { label: 'Notes',      icon: FileText,       color: '#22c55e' },
  worksheet: { label: 'Worksheet',  icon: ClipboardList,  color: '#a78bfa' },
  practice:  { label: 'Practice',   icon: GraduationCap, color: '#f472b6' },
  other:     { label: 'Other',      icon: FileText,       color: 'var(--txt-mut)' },
}

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes}B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`
}

function TagBadge({ tag }) {
  const meta = TAG_META[tag] || TAG_META.other
  const Icon = meta.icon
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, padding: '1px 7px', borderRadius: 10, border: `1px solid ${meta.color}44`, background: `${meta.color}14`, fontSize: '0.66rem', color: meta.color, fontWeight: 600 }}>
      <Icon size={10} /> {meta.label}
    </span>
  )
}

/**
 * AtlasMaterialsLibrary — upload and manage school/lesson materials.
 * Props:
 *   attached: [file_id]            — file IDs attached to current session
 *   onToggleAttach(file, attach): toggle a file in the active session
 */
export default function AtlasMaterialsLibrary(props) {
  const auth = useAuth()
  return <MaterialsLibrary key={`${auth?.user?.id || 'local'}:${props.scope || 'atlas'}`} {...props} />
}

function MaterialsLibrary({ attached = [], onToggleAttach, scope = 'atlas', onLibraryChange }) {
  const [files, setFiles] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [pendingTag, setPendingTag] = useState('other')
  const [tagMenuFor, setTagMenuFor] = useState(null)
  const inputRef = useRef(null)
  const [preview, setPreview] = useState(null)
  const [previewQuery, setPreviewQuery] = useState('')
  const upload = useDocumentUpload(scope, data => {
    setFiles(previous => [data, ...previous])
    onLibraryChange?.()
  })
  const uploading = upload.busy

  const loadFiles = async () => {
    setLoading(true)
    try {
      const data = await api(`/${scope}/files`)
      if (!Array.isArray(data?.files)) throw new Error('The file library returned an invalid response.')
      setFiles(data.files)
      setError('')
    } catch (e) {
      setError(e?.message || 'Failed to load materials')
      setFiles([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadFiles()
  }, [])

  const handleUpload = async (e) => {
    const fileList = Array.from(e.target.files || [])
    if (!fileList.length) return
    e.target.value = ''
    setError('')
    await upload.upload(fileList, pendingTag)
  }

  const handleDelete = async (fileId) => {
    try {
      await api(`/${scope}/files/${fileId}`, { method: 'DELETE' })
      setFiles(prev => prev.filter(f => f.file_id !== fileId))
      onToggleAttach && onToggleAttach({ file_id: fileId }, false)
      if (preview?.file_id === fileId) setPreview(null)
      upload.loadPolicy()
      onLibraryChange?.()
    } catch (e) {
      setError(e?.message || 'Delete failed')
    }
  }

  const handleRetag = async (fileId, newTag) => {
    try {
      await api(`/${scope}/files/${fileId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tag: newTag }),
      })
      setFiles(prev => prev.map(f => f.file_id === fileId ? { ...f, tag: newTag } : f))
    } catch (e) {
      setError(e?.message || 'Tag update failed')
    }

    setTagMenuFor(null)
  }

  const showPreview = async (fileId, query = '') => {
    try {
      const result = await api(`/${scope}/files/${fileId}/content?query=${encodeURIComponent(query)}`)
      setPreview(result)
      setError('')
    } catch (cause) { setError(cause.message || 'Could not load document sections.') }
  }

  return (
    <div className="glass-card-solid" style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 12 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10, flexWrap: 'wrap' }}>
        <div>
          <div style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.14em', color: 'var(--txt-mut)', fontWeight: 700, marginBottom: 3 }}>
            {scope === 'atlas' ? 'My Learning Materials' : 'My Chat Files'}
          </div>
          <div style={{ fontSize: '0.78rem', color: 'var(--txt-sec)' }}>
            {scope === 'atlas' ? 'Upload textbooks, homework, notes, or worksheets. ATLAS uses them as lesson context.' : 'Review, reuse, or delete your private chat documents. Removing an attachment does not delete the stored file.'}
          </div>
        </div>

        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          {/* Tag picker for upload */}
          {scope === 'atlas' && <select
            value={pendingTag}
            onChange={e => setPendingTag(e.target.value)}
            style={{ background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.12)', borderRadius: 7, color: 'var(--txt-sec)', fontSize: '0.72rem', padding: '5px 8px', cursor: 'pointer' }}
          >
            {Object.entries(TAG_META).map(([k, v]) => (
              <option key={k} value={k}>{v.label}</option>
            ))}
          </select>}
          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            disabled={uploading || !upload.policy}
            style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '7px 12px', borderRadius: 8, border: '1px solid rgba(99,102,241,0.35)', background: 'rgba(99,102,241,0.12)', color: 'var(--photon)', cursor: uploading ? 'default' : 'pointer', fontSize: '0.76rem', fontWeight: 600 }}
          >
            {uploading ? <Loader size={13} style={{ animation: 'spin 1s linear infinite' }} /> : <Upload size={13} />}
            {uploading ? 'Uploading…' : 'Upload'}
          </button>
          <button type="button" disabled={loading} onClick={() => { loadFiles(); upload.loadPolicy() }}>Refresh library</button>
          <input
            ref={inputRef}
            type="file"
            style={{ display: 'none' }}
            accept={upload.policy?.extensions.join(',') || ''}
            multiple
            onChange={handleUpload}
          />
        </div>
      </div>

      {error && <div style={{ fontSize: '0.74rem', color: '#f87171' }}>{error}</div>}
      <DocumentUploadStatus upload={upload} tag={pendingTag} />
      {scope === 'atlas' && attached.length > 6 && <div role="alert">Only the first six materials are used in each tutor request.</div>}
      {preview && (
        <section aria-label="Document extraction preview" style={{ overflowWrap: 'anywhere' }}>
          <strong>{preview.name}</strong> · {preview.processing_status}
          <form style={{ display: 'flex', flexWrap: 'wrap', gap: 8, margin: '12px 0' }} onSubmit={event => { event.preventDefault(); showPreview(preview.file_id, previewQuery) }}>
            <input aria-label="Search document sections" value={previewQuery} onChange={event => setPreviewQuery(event.target.value)} placeholder="Topic, page 42, or slide 12" />
            <button type="submit">Find sections</button>
            <button type="button" onClick={() => setPreview(null)}>Close preview</button>
          </form>
          {preview.sections?.map((section, index) => <div key={index}><strong>{section.location}</strong><pre style={{ whiteSpace: 'pre-wrap', fontFamily: 'inherit' }}>{section.text}</pre></div>)}
          {!preview.sections?.length && <div>No usable text. {preview.warnings?.join(' ')}</div>}
        </section>
      )}

      {/* Files list */}
      {loading && <div style={{ fontSize: '0.78rem', color: 'var(--txt-mut)', padding: '8px 0' }}>Loading materials…</div>}
      {!loading && files.length === 0 && (
        <div style={{ fontSize: '0.78rem', color: 'var(--txt-mut)', padding: '12px 0', textAlign: 'center', borderRadius: 10, border: '1px dashed var(--border)' }}>
          No materials yet. Upload your first file to let ATLAS reference it during lessons.
        </div>
      )}

      <div style={{ display: 'grid', gap: 6 }}>
        {files.map(file => {
          const isAttached = attached.includes(file.file_id)
          return (
            <div
              key={file.file_id}
              style={{
                display: 'flex', alignItems: 'center', gap: 10, padding: '9px 12px',
                borderRadius: 10, border: `1px solid ${isAttached ? 'rgba(77,166,255,0.3)' : 'var(--border)'}`,
                background: isAttached ? 'rgba(77,166,255,0.06)' : 'rgba(255,255,255,0.025)',
              }}
            >
              {/* Attach checkbox */}
              <button
                type="button"
                disabled={['needs_ocr', 'empty'].includes(file.processing_status)}
                onClick={() => onToggleAttach && onToggleAttach(file, !isAttached)}
                title={isAttached ? 'Remove from session' : 'Add to this lesson session'}
                style={{
                  width: 22, height: 22, padding: 0, borderRadius: 6, flexShrink: 0,
                  border: `1px solid ${isAttached ? 'rgba(77,166,255,0.6)' : 'rgba(255,255,255,0.18)'}`,
                  background: isAttached ? 'rgba(77,166,255,0.2)' : 'rgba(255,255,255,0.04)',
                  cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
                  color: isAttached ? '#60a5fa' : 'var(--txt-mut)',
                }}
              >
                {isAttached && <Check size={12} />}
              </button>

              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: '0.82rem', color: 'var(--txt-pri)', fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {file.name}
                </div>
                <div style={{ display: 'flex', gap: 8, marginTop: 3, alignItems: 'center', flexWrap: 'wrap' }}>
                  {scope === 'atlas' && <TagBadge tag={file.tag || 'other'} />}
                  <span style={{ fontSize: '0.64rem', color: 'var(--txt-mut)' }}>{formatSize(file.size)}</span>
                  <span>{file.processing_status || 'legacy_preview'}</span>
                </div>
                {file.warnings?.map(warning => <div key={warning} style={{ fontSize: '0.7rem' }}>{warning}</div>)}
              </div>
              <button type="button" onClick={() => { setPreviewQuery(''); showPreview(file.file_id) }}>Preview</button>

              {/* Tag change menu */}
              {scope === 'atlas' && <div style={{ position: 'relative' }}>
                <button
                  type="button"
                  onClick={() => setTagMenuFor(tagMenuFor === file.file_id ? null : file.file_id)}
                  title="Change tag"
                  style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 6, cursor: 'pointer', color: 'var(--txt-mut)', padding: '4px 6px', display: 'flex', alignItems: 'center' }}
                >
                  <Tag size={11} />
                </button>
                {tagMenuFor === file.file_id && (
                  <div style={{ position: 'absolute', right: 0, top: '100%', marginTop: 4, zIndex: 100, background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 9, padding: 6, boxShadow: '0 8px 24px rgba(0,0,0,0.4)', minWidth: 130 }}>
                    {Object.entries(TAG_META).map(([k, v]) => (
                      <button
                        key={k}
                        onClick={() => handleRetag(file.file_id, k)}
                        style={{ display: 'flex', alignItems: 'center', gap: 7, width: '100%', padding: '6px 8px', background: 'none', border: 'none', borderRadius: 6, cursor: 'pointer', color: v.color, fontSize: '0.74rem', textAlign: 'left' }}
                      >
                        <v.icon size={11} /> {v.label}
                        {file.tag === k && <Check size={10} style={{ marginLeft: 'auto' }} />}
                      </button>
                    ))}
                  </div>
                )}
              </div>}

              {/* Delete */}
              <button
                type="button"
                onClick={() => handleDelete(file.file_id)}
                title="Delete"
                style={{ background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.18)', borderRadius: 6, cursor: 'pointer', color: '#f87171', padding: '4px 6px', display: 'flex', alignItems: 'center', flexShrink: 0 }}
              >
                <Trash2 size={11} />
              </button>
            </div>
          )
        })}
      </div>
    </div>
  )
}
