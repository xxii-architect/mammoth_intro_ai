import { useRef, useState } from 'react'
import { BookOpen, Clock, Download, Hash, List } from 'lucide-react'

function ReadingTime({ wordCount }) {
  const mins = Math.max(1, Math.ceil(wordCount / 200))
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: '0.72rem', color: 'var(--txt-mut)' }}>
      <Clock size={11} />
      {mins} min read &middot; {wordCount.toLocaleString()} words
    </span>
  )
}

function SectionNav({ sections, activeIdx, onSelect }) {
  return (
    <div style={{
      background: 'rgba(255,255,255,0.03)',
      border: '1px solid var(--border)',
      borderRadius: 10, padding: '10px 0', marginBottom: 16,
    }}>
      <div style={{ fontSize: '0.6rem', textTransform: 'uppercase', letterSpacing: '0.14em', color: 'var(--txt-mut)', padding: '0 14px', marginBottom: 6, display: 'flex', alignItems: 'center', gap: 6 }}>
        <List size={10} /> Contents
      </div>
      {sections.map((sec, idx) => (
        <button
          key={idx}
          onClick={() => onSelect(idx)}
          style={{
            width: '100%', textAlign: 'left', display: 'block',
            padding: '6px 14px',
            background: activeIdx === idx ? 'rgba(77,166,255,0.08)' : 'none',
            borderLeft: `2px solid ${activeIdx === idx ? 'var(--photon)' : 'transparent'}`,
            border: 'none', cursor: 'pointer',
            color: activeIdx === idx ? 'var(--photon)' : 'var(--txt-sec)',
            fontSize: '0.76rem', lineHeight: 1.35,
            transition: 'all 0.15s ease',
          }}
        >
          <span style={{ fontSize: '0.62rem', color: 'var(--txt-mut)', fontFamily: 'JetBrains Mono,monospace', marginRight: 8 }}>
            {String(idx + 1).padStart(2, '0')}
          </span>
          {sec.heading}
        </button>
      ))}
      <button
        onClick={() => onSelect(sections.length)}
        style={{
          width: '100%', textAlign: 'left', display: 'block',
          padding: '6px 14px',
          background: activeIdx === sections.length ? 'rgba(77,166,255,0.08)' : 'none',
          borderLeft: `2px solid ${activeIdx === sections.length ? 'var(--photon)' : 'transparent'}`,
          border: 'none', cursor: 'pointer',
          color: activeIdx === sections.length ? 'var(--photon)' : 'var(--txt-mut)',
          fontSize: '0.76rem', lineHeight: 1.35, fontStyle: 'italic',
          transition: 'all 0.15s ease',
        }}
      >
        <span style={{ fontSize: '0.62rem', color: 'var(--txt-mut)', fontFamily: 'JetBrains Mono,monospace', marginRight: 8 }}>
          &#x2192;
        </span>
        Conclusion
      </button>
    </div>
  )
}

function DocSection({ section, idx, sectionRef }) {
  return (
    <div ref={sectionRef} id={`lf-section-${idx}`} style={{ marginBottom: 44, scrollMarginTop: 24 }}>
      <div style={{
        display: 'flex', alignItems: 'center', gap: 10,
        marginBottom: 16, paddingBottom: 12,
        borderBottom: '1px solid var(--border)',
      }}>
        <span style={{
          fontSize: '0.63rem', fontFamily: 'JetBrains Mono,monospace',
          color: 'var(--cyan)', background: 'rgba(34,211,238,0.08)',
          borderRadius: 6, padding: '2px 9px', flexShrink: 0,
        }}>
          {String(idx + 1).padStart(2, '0')}
        </span>
        <h2 style={{
          fontSize: '1.06rem', fontWeight: 700,
          color: 'var(--txt-pri)', margin: 0, lineHeight: 1.3,
        }}>
          {section.heading}
        </h2>
      </div>
      <div>
        {section.content.split('\n\n').map((para, pIdx) =>
          para.trim() ? (
            <p key={pIdx} style={{
              fontSize: '0.89rem', color: 'var(--txt-sec)',
              lineHeight: 1.84, margin: '0 0 18px 0',
            }}>
              {para.trim()}
            </p>
          ) : null
        )}
      </div>
    </div>
  )
}

export default function LongFormResearchPanel({ artifact, rawJson }) {
  const [showRaw, setShowRaw] = useState(false)
  const [activeSection, setActiveSection] = useState(0)
  const [downloading, setDownloading] = useState(false)
  const sectionRefs = useRef([])
  const conclusionRef = useRef(null)

  if (!artifact) return null

  const {
    title = 'Research Document',
    abstract = '',
    sections = [],
    conclusion = '',
    sources = [],
    word_count = 0,
    docx_filename,
  } = artifact

  const sorted = [...sections].sort((a, b) => (a.order ?? 0) - (b.order ?? 0))
  const wordCount = word_count || sorted.reduce((acc, s) => acc + (s.content?.split(' ').length ?? 0), 0)

  const scrollTo = (idx) => {
    setActiveSection(idx)
    if (idx === sorted.length) {
      conclusionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    } else {
      sectionRefs.current[idx]?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  }

  const handleDownload = () => {
    if (!docx_filename) return
    setDownloading(true)
    const a = document.createElement('a')
    a.href = `/api/download-docx/${docx_filename}`
    a.download = docx_filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    setTimeout(() => setDownloading(false), 2000)
  }

  return (
    <div>
      {/* ── Header card ─────────────────────────────────────────────────── */}
      <div className="glass-card-solid" style={{ padding: '18px 22px', borderLeft: '3px solid var(--cyan)', marginBottom: 14 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 14 }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
              <BookOpen size={13} color="var(--cyan)" />
              <span style={{ fontSize: '0.62rem', textTransform: 'uppercase', letterSpacing: '0.14em', color: 'var(--txt-mut)' }}>
                Long-Form Research Document
              </span>
            </div>
            <h1 style={{ fontSize: '1.18rem', fontWeight: 800, color: 'var(--txt-pri)', lineHeight: 1.3, margin: '0 0 10px' }}>
              {title}
            </h1>
            <div style={{ display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap' }}>
              <ReadingTime wordCount={wordCount} />
              {sorted.length > 0 && (
                <span style={{ fontSize: '0.72rem', color: 'var(--txt-mut)' }}>{sorted.length} sections</span>
              )}
              {sources.length > 0 && (
                <span style={{ fontSize: '0.72rem', color: 'var(--txt-mut)' }}>{sources.length} sources</span>
              )}
            </div>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 7, flexShrink: 0 }}>
            {docx_filename && (
              <button
                onClick={handleDownload}
                disabled={downloading}
                style={{
                  display: 'flex', alignItems: 'center', gap: 7,
                  padding: '7px 13px', borderRadius: 8,
                  background: 'rgba(34,211,238,0.10)',
                  border: '1px solid rgba(34,211,238,0.25)',
                  color: 'var(--cyan)', fontSize: '0.73rem', fontWeight: 700,
                  cursor: downloading ? 'wait' : 'pointer',
                }}
              >
                <Download size={12} />
                {downloading ? 'Preparing…' : 'Download DOCX'}
              </button>
            )}
            <button
              onClick={() => setShowRaw(r => !r)}
              style={{
                display: 'flex', alignItems: 'center', gap: 5,
                padding: '6px 11px', borderRadius: 8,
                background: 'none', border: '1px solid var(--border)',
                color: 'var(--txt-mut)', fontSize: '0.68rem', cursor: 'pointer',
              }}
            >
              <Hash size={11} />
              {showRaw ? 'Document' : 'Raw JSON'}
            </button>
          </div>
        </div>
      </div>

      {showRaw ? (
        <div className="glass-card-solid" style={{ padding: 16 }}>
          <pre style={{ fontSize: '0.72rem', fontFamily: 'JetBrains Mono,monospace', color: 'var(--txt-sec)', whiteSpace: 'pre-wrap', lineHeight: 1.6, maxHeight: 500, overflowY: 'auto', margin: 0 }}>
            {rawJson || JSON.stringify(artifact, null, 2)}
          </pre>
        </div>
      ) : (
        <>
          {/* ── Abstract ────────────────────────────────────────────────── */}
          {abstract && (
            <div className="glass-card-solid" style={{ padding: '15px 20px', borderLeft: '3px solid var(--photon)', marginBottom: 14 }}>
              <div style={{ fontSize: '0.62rem', textTransform: 'uppercase', letterSpacing: '0.14em', color: 'var(--txt-mut)', marginBottom: 8 }}>
                Abstract
              </div>
              <p style={{ fontSize: '0.88rem', color: 'var(--txt-pri)', lineHeight: 1.74, margin: 0, fontStyle: 'italic' }}>
                {abstract}
              </p>
            </div>
          )}

          {/* ── Section nav ─────────────────────────────────────────────── */}
          {sorted.length > 0 && (
            <SectionNav sections={sorted} activeIdx={activeSection} onSelect={scrollTo} />
          )}

          {/* ── Document body ────────────────────────────────────────────── */}
          {sorted.length > 0 && (
            <div className="glass-card-solid" style={{ padding: '26px 30px' }}>
              {sorted.map((sec, idx) => (
                <DocSection
                  key={idx}
                  section={sec}
                  idx={idx}
                  sectionRef={el => { sectionRefs.current[idx] = el }}
                />
              ))}

              {/* ── Conclusion ─────────────────────────────────────────── */}
              {conclusion && (
                <div
                  ref={conclusionRef}
                  id="lf-conclusion"
                  style={{ marginTop: 44, paddingTop: 26, borderTop: '2px solid var(--border)', scrollMarginTop: 24 }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
                    <span style={{
                      fontSize: '0.63rem', fontFamily: 'JetBrains Mono,monospace',
                      color: 'var(--photon)', background: 'rgba(77,166,255,0.08)',
                      borderRadius: 6, padding: '2px 9px',
                    }}>
                      CONCLUSION
                    </span>
                  </div>
                  <div>
                    {conclusion.split('\n\n').map((para, idx) =>
                      para.trim() ? (
                        <p key={idx} style={{
                          fontSize: '0.89rem', color: 'var(--txt-sec)',
                          lineHeight: 1.84, margin: '0 0 18px 0',
                        }}>
                          {para.trim()}
                        </p>
                      ) : null
                    )}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* ── Sources ─────────────────────────────────────────────────── */}
          {sources.length > 0 && (
            <div className="glass-card-solid" style={{ padding: 16, marginTop: 14 }}>
              <div style={{ fontSize: '0.62rem', textTransform: 'uppercase', letterSpacing: '0.14em', color: 'var(--txt-mut)', marginBottom: 10 }}>
                Sources &amp; References
              </div>
              <div style={{ display: 'grid', gap: 9 }}>
                {sources.map((src, idx) => {
                  const srcTitle = src.title || src.label || `Source ${idx + 1}`
                  const srcUrl = src.url || src.source || ''
                  return (
                    <div key={idx} style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
                      <span style={{
                        fontSize: '0.65rem', color: 'var(--cyan)',
                        fontFamily: 'JetBrains Mono,monospace',
                        flexShrink: 0, minWidth: 30, paddingTop: 2,
                      }}>
                        S{idx + 1}
                      </span>
                      <div>
                        <div style={{ fontSize: '0.78rem', color: 'var(--txt-sec)', fontWeight: 600 }}>{srcTitle}</div>
                        {srcUrl && (
                          <div style={{ fontSize: '0.65rem', color: 'var(--txt-mut)', fontFamily: 'JetBrains Mono,monospace', marginTop: 2, overflowWrap: 'anywhere' }}>
                            {srcUrl}
                          </div>
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
