export default function DocumentUploadStatus({ upload, tag }) {
  return (
    <div aria-live="polite" style={{ width: '100%', fontSize: '0.74rem', overflowWrap: 'anywhere' }}>
      {upload.policy && <div>{Math.round(upload.policy.max_file_bytes / 1048576)} MB per file · {Math.round((upload.policy.usage?.storage_bytes || 0) / 1048576)} / {Math.round(upload.policy.max_storage_bytes / 1048576)} MB stored · OCR and media transcription are not enabled.</div>}
      {upload.policyError && <div role="alert">{upload.policyError} <button type="button" onClick={upload.loadPolicy}>Retry upload settings</button></div>}
      {upload.items.map(item => (
        <div key={item.id}>
          <strong>{item.name}</strong>: {item.state}{item.state === 'uploading' ? ` ${item.progress}%` : ''}
          {item.state === 'processing' && ' — extracting and indexing'}
          {item.error && <span role="alert"> — {item.error}</span>}
          {item.warnings?.map(warning => <div key={warning}>{warning}</div>)}
        </div>
      ))}
      {upload.busy && <button type="button" onClick={upload.cancel}>Cancel uploads</button>}
      {!upload.busy && upload.items.some(item => item.state === 'failed') && <button type="button" onClick={() => upload.retry(tag)}>Retry failed uploads</button>}
    </div>
  )
}
