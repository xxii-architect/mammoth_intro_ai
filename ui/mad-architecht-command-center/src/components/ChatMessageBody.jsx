import { useState } from 'react'
import { Copy, Check } from 'lucide-react'

/**
 * Lightweight markdown-like renderer for Mammoth Mind chat bubbles.
 * Handles: fenced code blocks, inline code, **bold**, bullet lists,
 * numbered lists, and --- horizontal rules.
 * No external dependencies required.
 */

function CodeBlock({ lang, code }) {
  const [copied, setCopied] = useState(false)
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(code)
      setCopied(true)
      setTimeout(() => setCopied(false), 1400)
    } catch { /* clipboard not available */ }
  }
  return (
    <div style={{
      margin: '10px 0',
      borderRadius: 10,
      border: '1px solid rgba(255,255,255,0.1)',
      background: 'rgba(0,0,0,0.36)',
      overflow: 'hidden',
    }}>
      {/* Code block header */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '6px 12px',
        background: 'rgba(255,255,255,0.04)',
        borderBottom: '1px solid rgba(255,255,255,0.08)',
      }}>
        <span style={{ fontSize: '0.66rem', fontFamily: 'JetBrains Mono,monospace', color: 'var(--txt-mut)', textTransform: 'uppercase', letterSpacing: '0.1em' }}>
          {lang || 'code'}
        </span>
        <button
          type="button"
          onClick={copy}
          style={{
            display: 'inline-flex', alignItems: 'center', gap: 5,
            padding: '3px 7px', borderRadius: 6,
            border: '1px solid rgba(255,255,255,0.1)',
            background: 'rgba(255,255,255,0.04)',
            color: copied ? '#22c55e' : 'var(--txt-mut)',
            fontSize: '0.64rem', cursor: 'pointer',
          }}
        >
          {copied ? <Check size={11} /> : <Copy size={11} />}
          {copied ? 'Copied' : 'Copy'}
        </button>
      </div>
      <pre style={{
        margin: 0,
        padding: '12px 14px',
        overflowX: 'auto',
        fontFamily: 'JetBrains Mono,monospace',
        fontSize: '0.8rem',
        lineHeight: 1.65,
        color: 'var(--txt-pri)',
        whiteSpace: 'pre',
      }}>
        <code>{code}</code>
      </pre>
    </div>
  )
}

function InlineCode({ children }) {
  return (
    <code style={{
      fontFamily: 'JetBrains Mono,monospace',
      fontSize: '0.82em',
      padding: '2px 5px',
      borderRadius: 5,
      background: 'rgba(77,166,255,0.1)',
      border: '1px solid rgba(77,166,255,0.18)',
      color: 'var(--photon)',
    }}>
      {children}
    </code>
  )
}

/** Parse a single non-code line into React inline spans. */
function renderInline(text) {
  // Split on **bold**, then on `inline code`
  const boldParts = text.split(/(\*\*[^*]+\*\*)/g)
  return boldParts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={i} style={{ color: 'var(--txt-pri)', fontWeight: 700 }}>{part.slice(2, -2)}</strong>
    }
    // Handle inline code within non-bold segments
    const codeParts = part.split(/(`[^`]+`)/g)
    return codeParts.map((seg, j) => {
      if (seg.startsWith('`') && seg.endsWith('`')) {
        return <InlineCode key={`${i}-${j}`}>{seg.slice(1, -1)}</InlineCode>
      }
      return seg
    })
  })
}

/** Parse the message text into an array of block descriptors. */
function parseBlocks(text) {
  const raw = String(text || '')
  const blocks = []
  // Split out fenced code blocks first
  const fenceRe = /```(\w*)\n?([\s\S]*?)```/g
  let lastIndex = 0
  let match

  while ((match = fenceRe.exec(raw)) !== null) {
    if (match.index > lastIndex) {
      blocks.push({ type: 'text', content: raw.slice(lastIndex, match.index) })
    }
    blocks.push({ type: 'code', lang: match[1] || '', content: match[2].trimEnd() })
    lastIndex = fenceRe.lastIndex
  }
  if (lastIndex < raw.length) {
    blocks.push({ type: 'text', content: raw.slice(lastIndex) })
  }
  return blocks
}

/** Render a text block as lines, grouping consecutive bullets. */
function renderTextBlock(content) {
  const lines = content.split('\n')
  const elements = []
  let bulletBuffer = []
  let numberedBuffer = []

  const flushBullets = () => {
    if (!bulletBuffer.length) return
    elements.push(
      <ul key={`ul-${elements.length}`} style={{ margin: '6px 0 6px 4px', paddingLeft: 18, display: 'grid', gap: 3 }}>
        {bulletBuffer.map((li, i) => (
          <li key={i} style={{ lineHeight: 1.6 }}>{renderInline(li)}</li>
        ))}
      </ul>
    )
    bulletBuffer = []
  }

  const flushNumbered = () => {
    if (!numberedBuffer.length) return
    elements.push(
      <ol key={`ol-${elements.length}`} style={{ margin: '6px 0 6px 4px', paddingLeft: 20, display: 'grid', gap: 3 }}>
        {numberedBuffer.map((li, i) => (
          <li key={i} style={{ lineHeight: 1.6 }}>{renderInline(li)}</li>
        ))}
      </ol>
    )
    numberedBuffer = []
  }

  lines.forEach((line, idx) => {
    // Horizontal rule
    if (/^---+$/.test(line.trim())) {
      flushBullets(); flushNumbered()
      elements.push(<hr key={`hr-${idx}`} style={{ border: 'none', borderTop: '1px solid var(--border)', margin: '10px 0' }} />)
      return
    }
    // Heading ##
    const headingMatch = line.match(/^(#{1,3})\s+(.+)$/)
    if (headingMatch) {
      flushBullets(); flushNumbered()
      const level = headingMatch[1].length
      const sizes = ['1rem', '0.95rem', '0.9rem']
      elements.push(
        <div key={`h-${idx}`} style={{ fontSize: sizes[level - 1] || '0.9rem', fontWeight: 700, color: 'var(--txt-pri)', marginTop: 10, marginBottom: 2 }}>
          {renderInline(headingMatch[2])}
        </div>
      )
      return
    }
    // Bullet list
    const bulletMatch = line.match(/^[\-\*•]\s+(.+)$/)
    if (bulletMatch) {
      flushNumbered()
      bulletBuffer.push(bulletMatch[1])
      return
    }
    // Numbered list
    const numberedMatch = line.match(/^\d+\.\s+(.+)$/)
    if (numberedMatch) {
      flushBullets()
      numberedBuffer.push(numberedMatch[1])
      return
    }
    // Normal line
    flushBullets(); flushNumbered()
    if (line.trim() === '') {
      elements.push(<div key={`br-${idx}`} style={{ height: 6 }} />)
    } else {
      elements.push(
        <div key={`line-${idx}`} style={{ lineHeight: 1.72 }}>{renderInline(line)}</div>
      )
    }
  })
  flushBullets()
  flushNumbered()
  return elements
}

export default function ChatMessageBody({ text }) {
  if (!text) return null
  const blocks = parseBlocks(text)

  return (
    <div>
      {blocks.map((block, i) => {
        if (block.type === 'code') {
          return <CodeBlock key={i} lang={block.lang} code={block.content} />
        }
        return (
          <div key={i}>
            {renderTextBlock(block.content)}
          </div>
        )
      })}
    </div>
  )
}
