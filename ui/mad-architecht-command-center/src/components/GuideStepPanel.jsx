import { useState } from 'react'
import { ChevronDown, ChevronRight, Copy, Check, BookOpen, Code2, FileText, ExternalLink } from 'lucide-react'
import { Editor } from '@monaco-editor/react'

const MAMMOTH_THEME = {
  base: 'vs-dark', inherit: true, rules: [],
  colors: {
    'editor.background': '#0d0d12',
    'editor.lineHighlightBackground': '#1a1a2e',
    'minimap.background': '#0d0d12',
  },
}

function StepCodeBlock({ code, lang, height = 200 }) {
  const [copied, setCopied] = useState(false)
  const [monacoError, setMonacoError] = useState(false)

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(code)
      setCopied(true)
      setTimeout(() => setCopied(false), 1400)
    } catch { /* no-op */ }
  }

  // Map common lang identifiers to Monaco language IDs
  const monacoLang = {
    py: 'python', python: 'python',
    js: 'javascript', javascript: 'javascript',
    ts: 'typescript', typescript: 'typescript',
    jsx: 'javascript', tsx: 'typescript',
    sh: 'shell', bash: 'shell', shell: 'shell',
    sql: 'sql', json: 'json', yaml: 'yaml', yml: 'yaml',
    md: 'markdown', markdown: 'markdown',
    txt: 'plaintext', '': 'plaintext',
  }[lang?.toLowerCase() || ''] || 'plaintext'

  return (
    <div style={{ margin: '10px 0', borderRadius: 10, border: '1px solid rgba(255,255,255,0.1)', overflow: 'hidden' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '6px 12px', background: 'rgba(255,255,255,0.04)', borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
        <span style={{ fontSize: '0.66rem', fontFamily: 'JetBrains Mono,monospace', color: 'var(--txt-mut)', textTransform: 'uppercase', letterSpacing: '0.1em' }}>
          {lang || 'code'}
        </span>
        <button type="button" onClick={copy} style={{ display: 'inline-flex', alignItems: 'center', gap: 5, padding: '3px 7px', borderRadius: 6, border: '1px solid rgba(255,255,255,0.1)', background: 'rgba(255,255,255,0.04)', color: copied ? '#22c55e' : 'var(--txt-mut)', fontSize: '0.64rem', cursor: 'pointer' }}>
          {copied ? <Check size={11} /> : <Copy size={11} />}
          {copied ? 'Copied' : 'Copy'}
        </button>
      </div>
      {monacoError ? (
        <pre style={{ margin: 0, padding: '12px 14px', overflowX: 'auto', fontFamily: 'JetBrains Mono,monospace', fontSize: '0.8rem', lineHeight: 1.65, color: 'var(--txt-pri)', whiteSpace: 'pre', background: 'rgba(0,0,0,0.36)' }}>
          <code>{code}</code>
        </pre>
      ) : (
        <Editor
          height={height}
          language={monacoLang}
          value={code}
          theme="mammoth-dark"
          options={{
            readOnly: true,
            minimap: { enabled: false },
            scrollBeyondLastLine: false,
            fontSize: 13,
            lineNumbers: 'on',
            wordWrap: 'on',
            padding: { top: 10, bottom: 10 },
            scrollbar: { vertical: 'auto', horizontal: 'auto' },
          }}
          beforeMount={monaco => monaco.editor.defineTheme('mammoth-dark', MAMMOTH_THEME)}
          onMount={() => setMonacoError(false)}
          onValidate={() => {}}
        />
      )}
    </div>
  )
}

function GuideStep({ step, index, isOpen, onToggle }) {
  const hasCode = Boolean(step.code && step.code.trim())
  const accent = step.kind === 'warning' ? '#f59e0b' : step.kind === 'tip' ? '#22c55e' : 'var(--photon)'
  const codeHeight = hasCode ? Math.min(Math.max(step.code.split('\n').length * 22 + 40, 120), 320) : 0

  return (
    <div style={{ borderRadius: 12, border: `1px solid ${isOpen ? 'rgba(77,166,255,0.22)' : 'var(--border)'}`, background: isOpen ? 'rgba(77,166,255,0.04)' : 'rgba(255,255,255,0.025)', overflow: 'hidden', transition: 'border-color 0.15s' }}>
      <button
        type="button"
        onClick={onToggle}
        style={{ width: '100%', textAlign: 'left', padding: '12px 14px', background: 'none', border: 'none', cursor: 'pointer', color: 'var(--txt-pri)' }}
      >
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
          {/* Step number badge */}
          <div style={{ flexShrink: 0, width: 28, height: 28, borderRadius: '50%', background: `rgba(77,166,255,0.12)`, border: `1px solid ${accent}`, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.72rem', fontWeight: 800, color: accent, fontFamily: 'JetBrains Mono,monospace' }}>
            {index + 1}
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
              <span style={{ fontSize: '0.9rem', fontWeight: 700, color: 'var(--txt-pri)', lineHeight: 1.4 }}>{step.title}</span>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
                {hasCode && <Code2 size={13} color="var(--txt-mut)" />}
                {step.file_ref && <FileText size={13} color="var(--txt-mut)" />}
                {isOpen ? <ChevronDown size={14} color="var(--txt-mut)" /> : <ChevronRight size={14} color="var(--txt-mut)" />}
              </div>
            </div>
            {step.detail && (
              <p style={{ margin: '5px 0 0', fontSize: '0.82rem', color: 'var(--txt-sec)', lineHeight: 1.6 }}>{step.detail}</p>
            )}
            {step.file_ref && !isOpen && (
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, marginTop: 5, fontSize: '0.68rem', fontFamily: 'JetBrains Mono,monospace', color: 'var(--photon)', background: 'rgba(77,166,255,0.08)', padding: '2px 7px', borderRadius: 5 }}>
                {step.file_ref}
              </span>
            )}
          </div>
        </div>
      </button>

      {isOpen && (
        <div style={{ padding: '0 14px 14px 54px' }}>
          {step.file_ref && (
            <div style={{ marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
              <FileText size={12} color="var(--photon)" />
              <span style={{ fontSize: '0.72rem', fontFamily: 'JetBrains Mono,monospace', color: 'var(--photon)' }}>{step.file_ref}</span>
              {step.line_ref && (
                <span style={{ fontSize: '0.68rem', color: 'var(--txt-mut)', fontFamily: 'JetBrains Mono,monospace' }}>:{step.line_ref}</span>
              )}
            </div>
          )}
          {hasCode && (
            <StepCodeBlock code={step.code} lang={step.lang || 'python'} height={codeHeight} />
          )}
          {step.notes && (
            <div style={{ marginTop: 8, padding: '9px 11px', borderRadius: 8, border: '1px solid rgba(245,158,11,0.2)', background: 'rgba(245,158,11,0.05)', fontSize: '0.78rem', color: '#fbbf24', lineHeight: 1.55 }}>
              💡 {step.notes}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

/**
 * Renders structured guide steps returned by MammothGuideAgent.
 * Steps have: { title, detail, code?, lang?, file_ref?, line_ref?, notes?, kind? }
 */
export default function GuideStepPanel({ steps, branch, query }) {
  const [openIndex, setOpenIndex] = useState(0)
  const [copied, setCopied] = useState(false)

  const stepList = Array.isArray(steps) ? steps : []
  if (!stepList.length) return null

  const copyAll = async () => {
    const text = stepList.map((s, i) => [
      `## Step ${i + 1}: ${s.title}`,
      s.detail || '',
      s.file_ref ? `File: ${s.file_ref}` : '',
      s.code ? '```' + (s.lang || '') + '\n' + s.code + '\n```' : '',
    ].filter(Boolean).join('\n')).join('\n\n')
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 1400)
    } catch { /* no-op */ }
  }

  const toggle = (i) => setOpenIndex(cur => cur === i ? -1 : i)

  return (
    <div style={{ margin: '12px 0', borderRadius: 14, border: '1px solid rgba(77,166,255,0.2)', background: 'rgba(77,166,255,0.03)', overflow: 'hidden' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 14px', borderBottom: '1px solid rgba(255,255,255,0.07)', background: 'rgba(77,166,255,0.06)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <BookOpen size={15} color="var(--photon)" />
          <span style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.14em', color: 'var(--photon)', fontWeight: 700 }}>
            MammothOS Guide — {stepList.length} step{stepList.length !== 1 ? 's' : ''}
          </span>
          {branch && (
            <span style={{ fontSize: '0.66rem', fontFamily: 'JetBrains Mono,monospace', color: 'var(--txt-mut)', background: 'rgba(255,255,255,0.05)', padding: '1px 6px', borderRadius: 4 }}>
              {branch}
            </span>
          )}
        </div>
        <button type="button" onClick={copyAll} style={{ display: 'inline-flex', alignItems: 'center', gap: 5, padding: '4px 8px', borderRadius: 7, border: '1px solid rgba(255,255,255,0.1)', background: 'rgba(255,255,255,0.04)', color: copied ? '#22c55e' : 'var(--txt-mut)', fontSize: '0.66rem', cursor: 'pointer' }}>
          {copied ? <Check size={11} /> : <Copy size={11} />}
          {copied ? 'Copied all' : 'Copy all'}
        </button>
      </div>

      {/* Steps */}
      <div style={{ display: 'grid', gap: 8, padding: 12 }}>
        {stepList.map((step, i) => (
          <GuideStep key={i} step={step} index={i} isOpen={openIndex === i} onToggle={() => toggle(i)} />
        ))}
      </div>
    </div>
  )
}
