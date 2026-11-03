import { useRef, useState } from 'react'
import { Paperclip, X, FileText, Code, FileJson, Loader, FolderOpen } from 'lucide-react'
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
 *   children: the message input, rendered full width inside the composer box
 *   leadingActions / trailingAction: extra controls for the action row (e.g. templates, Send)
 */
export default function FileAttachmentPanel(props) {
  const auth = useAuth()
  return <AttachmentPanel key={auth?.user?.id || 'local'} {...props} />
}

const ICON_BUTTON = { display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 34, height: 34, borderRadius: 9, border: '1px solid transparent', background: 'transparent', color: 'var(--txt-sec)', cursor: 'pointer', flexShrink: 0 }

function AttachmentPanel({ attached = [], onAttach, onRemove, compact = false, leadingActions = null, trailingAction = null, children = null }) {
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

  const policyHint = upload.policy
    ? ` (up to ${Math.round(upload.policy.max_file_bytes / 1048576)} MB per file)`
    : ''
  const hasStatus = !compact || upload.items.length > 0 || upload.busy || Boolean(upload.policyError)

  return (
    <div style={{ display: 'grid', gap: 8, width: '100%', minWidth: 0 }}>
      {hasStatus && <DocumentUploadStatus upload={upload} compact={compact} showPolicy={!compact} />}
      {libraryOpen && <div style={{ width: '100%', minWidth: 0 }}><AtlasMaterialsLibrary
        scope="mammoth"
        attached={attached.map(file => file.file_id)}
        onToggleAttach={(file, attach) => attach ? onAttach(file) : onRemove(file.file_id)}
        onLibraryChange={upload.loadPolicy}
      /></div>}
      {attached.map(file => file.warnings?.length > 0 && <div key={file.file_id} style={{ width: '100%', fontSize: '0.72rem' }}>{file.name}: {file.processing_status} — {file.warnings.join(' ')}</div>)}
      {attached.length > 0 && <div style={{ fontSize: '0.72rem', color: 'var(--txt-mut)' }}>Chat starts with selected excerpts, not a full-file review. Use the file library to search or browse indexed text; Agent mode can read additional sections.</div>}
      {attached.length > 4 && <div role="alert">Only the first four attached files are used in each chat request. Remove extras or send separate requests.</div>}

      <div className="composer-box" style={{ display: 'grid', gap: 4, minWidth: 0, padding: '6px 8px', borderRadius: 14, border: '1px solid rgba(255,255,255,0.1)', background: 'rgba(255,255,255,0.04)' }}>
        {attached.length > 0 && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, padding: '2px 2px 0' }}>
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
          </div>
        )}
        {children}
        <div style={{ display: 'flex', alignItems: 'center', gap: 2, minWidth: 0 }}>
          <button
            type="button"
            aria-label={uploading ? 'Uploading…' : 'Attach'}
            title={`Attach a document or source file${policyHint}; retrieved sections provide context`}
            onClick={() => inputRef.current?.click()}
            disabled={uploading || !upload.policy}
            className="composer-icon-button"
            style={{ ...ICON_BUTTON, cursor: uploading || !upload.policy ? 'default' : 'pointer', opacity: upload.policy ? 1 : 0.5 }}
          >
            {uploading ? <Loader size={15} style={{ animation: 'spin 1s linear infinite' }} /> : <Paperclip size={15} />}
          </button>
          <button
            type="button"
            aria-label={libraryOpen ? 'Close file library' : 'Manage saved files'}
            aria-expanded={libraryOpen}
            title={libraryOpen ? 'Close file library' : 'Manage saved files, upload limits and previews'}
            onClick={() => setLibraryOpen(value => !value)}
            className="composer-icon-button"
            style={{ ...ICON_BUTTON, ...(libraryOpen ? { color: 'var(--photon)', background: 'rgba(77,166,255,0.08)', border: '1px solid rgba(77,166,255,0.3)' } : {}) }}
          >
            <FolderOpen size={15} />
          </button>
          {leadingActions}
          {trailingAction && <div style={{ marginLeft: 'auto', flexShrink: 0 }}>{trailingAction}</div>}
        </div>
      </div>

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
