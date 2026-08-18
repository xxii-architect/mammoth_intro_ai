import React, { useState } from 'react'

const composerCardStyle: React.CSSProperties = {
  padding: 16,
  borderRadius: 14,
  border: '1px solid rgba(255,255,255,0.08)',
  background: 'linear-gradient(180deg, rgba(13,17,23,0.96), rgba(13,17,23,0.82))',
  boxShadow: '0 10px 30px rgba(0,0,0,0.28), 0 0 0 1px rgba(0,245,212,0.06)',
}

const inputStyle: React.CSSProperties = {
  width: '100%',
  minHeight: 112,
  resize: 'vertical',
  borderRadius: 12,
  border: '1px solid rgba(77,166,255,0.22)',
  background: 'rgba(5,6,8,0.78)',
  color: 'var(--txt-pri)',
  padding: '12px 14px',
  fontSize: '0.9rem',
  lineHeight: 1.6,
  outline: 'none',
}

const submitStyle: React.CSSProperties = {
  padding: '10px 16px',
  border: 0,
  borderRadius: 999,
  background: 'linear-gradient(90deg, var(--photon), var(--cyan))',
  color: '#050608',
  fontWeight: 700,
  fontSize: '0.82rem',
  cursor: 'pointer',
}

const NotesComposer: React.FC<{ onCreate: (content: string) => Promise<void>; busy?: boolean }> = ({
  onCreate,
  busy = false,
}) => {
  const [content, setContent] = useState<string>('')
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false)

  const handleSubmit = async () => {
    if (!content.trim() || busy || isSubmitting) {
      return
    }
    setIsSubmitting(true)
    try {
      await onCreate(content.trim())
      setContent('')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div style={composerCardStyle}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, marginBottom: 12, alignItems: 'center' }}>
        <div>
          <div className="eyebrow" style={{ marginBottom: 4 }}>Quick capture</div>
          <h3 style={{ fontSize: '0.95rem' }}>Drop a note into the queue</h3>
        </div>
        <button style={submitStyle} onClick={handleSubmit} disabled={busy || isSubmitting}>
          {busy || isSubmitting ? 'Saving…' : 'Create note'}
        </button>
      </div>
      <textarea
        value={content}
        onChange={(event) => setContent(event.target.value)}
        placeholder="Write a note, task, or prompt fragment..."
        style={inputStyle}
        disabled={busy || isSubmitting}
      />
      <div style={{ marginTop: 10, color: 'var(--txt-mut)', fontSize: '0.74rem' }}>
        High-contrast editor, Command Center theme, and safe inline save.
      </div>
    </div>
  )
}

export { NotesComposer }