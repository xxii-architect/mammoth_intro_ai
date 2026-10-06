import { useId, useMemo, useRef } from 'react'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import './lesson-content.css'

const TEACHING_HEADING = /^(?:\*\*)?(Introduction|Key concepts|Worked examples|Guided practice|Recap and next step)(?:\*\*)?:?$/i
const ALLOWED_TAGS = ['p', 'br', 'hr', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'strong', 'em', 'del', 'ul', 'ol', 'li', 'blockquote', 'pre', 'code', 'a', 'table', 'thead', 'tbody', 'tr', 'th', 'td']

function normalizeHeadings(content) {
  let fence = null
  return content.split('\n').map(line => {
    const marker = line.match(/^ {0,3}(`{3,}|~{3,})(.*)$/)
    if (marker) {
      if (!fence) fence = { character: marker[1][0], length: marker[1].length }
      else if (marker[1][0] === fence.character && marker[1].length >= fence.length && !marker[2].trim()) fence = null
      return line
    }
    if (fence || /^\s{4}/.test(line)) return line
    const heading = line.trim().match(TEACHING_HEADING)
    return heading ? `\n## ${heading[1]}\n` : line
  }).join('\n')
}

function renderTokens(tokens) {
  return DOMPurify.sanitize(marked.parser(tokens, { gfm: true }), {
    ALLOWED_TAGS,
    ALLOWED_ATTR: ['href', 'title', 'start'],
    ALLOWED_URI_REGEXP: /^(?:https?:|mailto:|#)/i,
  })
}

export default function LessonContent({ content, navigation = false }) {
  const prefix = useId()
  const sectionsRef = useRef([])
  const sections = useMemo(() => {
    if (typeof content !== 'string' || !content.trim()) return []
    const tokens = marked.lexer(normalizeHeadings(content), { gfm: true })
    const groups = []
    let current = { title: '', tokens: [] }
    for (const token of tokens) {
      if (token.type === 'heading' && token.depth <= 3) {
        if (current.tokens.length) groups.push(current)
        current = { title: token.text, tokens: [] }
      }
      current.tokens.push(token)
    }
    if (current.tokens.length) groups.push(current)
    return groups.map(group => ({ title: group.title, html: renderTokens(group.tokens) }))
  }, [content])
  if (!sections.length) return null
  const headings = sections.map((section, index) => ({ ...section, index })).filter(section => section.title)
  const jumpTo = index => {
    const section = sectionsRef.current[index]
    section?.focus({ preventScroll: true })
    section?.scrollIntoView({ block: 'start' })
  }
  return (
    <div className="lesson-reader">
      {navigation && headings.length >= 3 && <nav aria-label="Lesson sections" className="lesson-reader-nav">
        <span>In this lesson</span>
        {headings.map(section => <button key={section.index} type="button" aria-controls={`${prefix}-${section.index}`} onClick={() => jumpTo(section.index)}>{section.title}</button>)}
      </nav>}
      <div className="lesson-reader-body">
        {sections.map((section, index) => <section key={index} id={`${prefix}-${index}`} ref={element => { sectionsRef.current[index] = element }}
          tabIndex={-1} aria-label={section.title || 'Lesson text'}
          className="lesson-reader-section" dangerouslySetInnerHTML={{ __html: section.html }} />)}
      </div>
    </div>
  )
}
