import { useRef, useState } from 'react'
import { Paperclip, X, FileText, Code, FileJson, Loader } from 'lucide-react'
import useDocumentUpload from './useDocumentUpload'
import DocumentUploadStatus from './DocumentUploadStatus'
import { useAuth } from '../lib/authContext'
import AtlasMaterialsLibrary from './AtlasMaterialsLibrary'

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
export default function FileAttachmentPanel(props) {
  const auth = useAuth()
  return <AttachmentPanel key={auth?.user?.id || 'local'} {...props} />
}

function AttachmentPanel({ attached = [], onAttach, onRemove, compact = false, trailingAction = null }) {
  const inputRef = useRef(null)
  const [libraryOpen, setLibraryOpen] = useState(false)
  const upload = useDocumentUpload('mammoth', data => {
    if (!['needs_ocr', 'empty'].includes(data.processing_status)) onAttach(data)
  })
  const uploading = upload.busy

  const handleFileChange = async (e) => {
    const files = Array.from(e.target.files || [])
    if (!files.length) return
    e.target.value = ''
    await upload.upload(files)
  }

  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 8, padding: '4px 0', width: '100%', minWidth: 0 }}>
      {/* Attached file chips */}
      {attached.map(f => (
        <div
          key={f.file_id}
          style={{ display: 'inline-flex', alignItems: 'center', gap: 5, padding: '3px 8px 3px 7px', borderRadius: 20, border: '1px solid rgba(77,166,255,0.3)', background: 'rgba(77,166,255,0.07)', fontSize: '0.72rem', color: 'var(--txt-sec)', maxWidth: 200 }}
        >
          {fileIcon(f.name)}
          <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>{f.name}</span>
          <span style={{ color: 'var(--txt-mut)', flexShrink: 0 }}>{formatSize(f.size)}</span>
          <button aria-label={`Detach ${f.name}`} onClick={() => onRemove(f.file_id)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--txt-mut)', padding: '4px', display: 'flex', lineHeight: 1 }}>
            <X size={11} />
          </button>
        </div>
      ))}

      {/* Upload trigger */}
      <button
        type="button"
        title="Attach a document or source file; retrieved sections provide context"
        onClick={() => inputRef.current?.click()}
        disabled={uploading || !upload.policy}
        style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '8px 12px', borderRadius: 10, border: '1px solid var(--border)', background: 'var(--card-hover)', color: 'var(--txt-pri)', cursor: uploading ? 'default' : 'pointer', fontSize: '0.8rem' }}
      >
        {uploading ? <Loader size={12} style={{ animation: 'spin 1s linear infinite' }} /> : <Paperclip size={12} />}
        {uploading ? 'Uploading…' : 'Attach'}
      </button>

      <button type="button" onClick={() => setLibraryOpen(value => !value)}>{libraryOpen ? 'Close file library' : 'Manage saved files'}</button>
      {trailingAction && <div style={{ marginLeft: 'auto' }}>{trailingAction}</div>}
      <DocumentUploadStatus upload={upload} compact={compact} />
      {libraryOpen && <div style={{ width: '100%', minWidth: 0 }}><AtlasMaterialsLibrary
        scope="mammoth"
        attached={attached.map(file => file.file_id)}
        onToggleAttach={(file, attach) => attach ? onAttach(file) : onRemove(file.file_id)}
        onLibraryChange={upload.loadPolicy}
      /></div>}
      {attached.map(file => file.warnings?.length > 0 && <div key={file.file_id} style={{ width: '100%', fontSize: '0.72rem' }}>{file.name}: {file.processing_status} — {file.warnings.join(' ')}</div>)}
      {attached.length > 4 && <div role="alert">Only the first four attached files are used in each chat request. Remove extras or send separate requests.</div>}

      <input
        ref={inputRef}
        type="file"
        style={{ display: 'none' }}
        accept={upload.policy?.extensions.join(',') || ''}
        multiple
        onChange={handleFileChange}
      />
    </div>
  )
}
