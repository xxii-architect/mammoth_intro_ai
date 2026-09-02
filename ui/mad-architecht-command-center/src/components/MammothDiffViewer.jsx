import { DiffEditor, Editor } from '@monaco-editor/react'

const MAMMOTH_THEME = {
  base: 'vs-dark', inherit: true, rules: [],
  colors: {
    'editor.background': '#0d0d12',
    'editor.lineHighlightBackground': '#1a1a2e',
    'diffEditor.insertedTextBackground': '#22c55e22',
    'diffEditor.removedTextBackground': '#ef444422',
  },
}

export default function MammothDiffViewer({ before = '', after = '', mode = 'readonly', language = 'python', onAccept, height = 380 }) {
  if (mode === 'readonly' || mode === 'approvable') {
    return (
      <div style={{ borderRadius: 10, overflow: 'hidden', border: '1px solid rgba(255,255,255,0.08)' }}>
        <DiffEditor
          height={height}
          language={language}
          original={before}
          modified={after}
          theme="mammoth-dark"
          options={{ readOnly: true, renderSideBySide: true, minimap: { enabled: false }, scrollBeyondLastLine: false, fontSize: 13, lineNumbers: 'on', wordWrap: 'on' }}
          beforeMount={monaco => monaco.editor.defineTheme('mammoth-dark', MAMMOTH_THEME)}
        />
        {mode === 'approvable' && onAccept && (
          <div style={{ display: 'flex', gap: 8, padding: '10px 14px', background: '#0d0d12', borderTop: '1px solid rgba(255,255,255,0.06)' }}>
            <button onClick={onAccept} style={{ padding: '6px 18px', borderRadius: 8, background: '#22c55e', color: '#fff', fontWeight: 700, border: 'none', cursor: 'pointer', fontSize: '0.82rem' }}>
              ✓ Apply Patch
            </button>
            <span style={{ fontSize: '0.75rem', color: 'rgba(255,255,255,0.35)', alignSelf: 'center' }}>Left = current · Right = proposed</span>
          </div>
        )}
      </div>
    )
  }
  return (
    <div style={{ borderRadius: 10, overflow: 'hidden', border: '1px solid rgba(255,255,255,0.08)' }}>
      <Editor
        height={height}
        language={language}
        value={after}
        theme="mammoth-dark"
        options={{ minimap: { enabled: false }, scrollBeyondLastLine: false, fontSize: 13, lineNumbers: 'on', wordWrap: 'on' }}
        beforeMount={monaco => monaco.editor.defineTheme('mammoth-dark', MAMMOTH_THEME)}
        onChange={val => onAccept && onAccept(val)}
      />
    </div>
  )
}
