import { useRef, useState } from 'react'
import { BookOpen, Clock, Download, Hash } from 'lucide-react'

export default function LongFormResearchPanel({ artifact, rawJson }) {
  const [showRaw, setShowRaw] = useState(false)
  const [downloading, setDownloading] = useState(false)
  const refs = useRef([])

  if (!artifact) return null

  const { title = '', abstract = '', sections = [], conclusion = '', sources = [], word_count = 0, docx_filename } = artifact
  const sorted = [...sections].sort((a, b) => (a.order ?? 0) - (b.order ?? 0))
  const wc = word_count || sorted.reduce((a, s) => a + (s.content?.split(' ').length || 0), 0)
  const mins = Math.max(1, Math.ceil(wc / 200))

  const scrollTo = (idx) => refs.current[idx]?.scrollIntoView({ behavior: 'smooth', block: 'start' })

  const dlDocx = () => {
    if (!docx_filename) return
    setDownloading(true)
    const a = document.createElement('a')
    a.href = `/api/download-docx/${docx_filename}`
    a.download = docx_filename
    document.body.appendChild(a); a.click(); document.body.removeChild(a)
    setTimeout(() => setDownloading(false), 2000)
  }

  return (
    <div>
      <div className="glass-card-solid" style={{ padding: '18px 22px', borderLeft: '3px solid var(--cyan)', marginBottom: 14 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
          <div style={{ flex: 1 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
              <BookOpen size={13} color="var(--cyan)" />
              <span style={{ fontSize: '0.62rem', textTransform: 'uppercase', letterSpacing: '0.14em', color: 'var(--txt-mut)' }}>Long-Form Research Document</span>
            </div>
            <h1 style={{ fontSize: '1.15rem', fontWeight: 800, color: 'var(--txt-pri)', lineHeight: 1.3, margin: '0 0 10px' }}>{title}</h1>
            <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: '0.72rem', color: 'var(--txt-mut)' }}>
                <Clock size={11} /> {mins} min read &middot; {wc.toLocaleString()} words
              </span>
              {sorted.length > 0 && <span style={{ fontSize: '0.72rem', color: 'var(--txt-mut)' }}>{sorted.length} sections</span>}
              {sources.length > 0 && <span style={{ fontSize: '0.72rem', color: 'var(--txt-mut)' }}>{sources.length} sources</span>}
            </div>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 7, flexShrink: 0 }}>
            {docx_filename && (
              <button onClick={dlDocx} disabled={downloading} style={{ display: 'flex', alignItems: 'center', gap: 7, padding: '7px 13px', borderRadius: 8, background: 'rgba(34,211,238,0.10)', border: '1px solid rgba(34,211,238,0.25)', color: 'var(--cyan)', fontSize: '0.73rem', fontWeight: 700, cursor: downloading ? 'wait' : 'pointer' }}>
                <Download size={12} />{downloading ? 'Preparing...' : 'Download DOCX'}
              </button>
            )}
            <button onClick={() => setShowRaw(r => !r)} style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '6px 11px', borderRadius: 8, background: 'none', border: '1px solid var(--border)', color: 'var(--txt-mut)', fontSize: '0.68rem', cursor: 'pointer' }}>
              <Hash size={11} />{showRaw ? 'Document' : 'Raw JSON'}
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
          {abstract && (
            <div className="glass-card-solid" style={{ padding: '15px 20px', borderLeft: '3px solid var(--photon)', marginBottom: 14 }}>
              <div style={{ fontSize: '0.62rem', textTransform: 'uppercase', letterSpacing: '0.14em', color: 'var(--txt-mut)', marginBottom: 8 }}>Abstract</div>
              <p style={{ fontSize: '0.88rem', color: 'var(--txt-pri)', lineHeight: 1.74, margin: 0, fontStyle: 'italic' }}>{abstract}</p>
            </div>
          )}

          {sorted.length > 0 && (
            <div className="glass-card-solid" style={{ padding: '10px 0', marginBottom: 14, border: '1px solid var(--border)', borderRadius: 10 }}>
              <div style={{ fontSize: '0.6rem', textTransform: 'uppercase', letterSpacing: '0.14em', color: 'var(--txt-mut)', padding: '0 14px', marginBottom: 6 }}>Contents</div>
              {sorted.map((sec, idx) => (
                <button key={idx} onClick={() => scrollTo(idx)} style={{ width: '100%', textAlign: 'left', display: 'block', padding: '6px 14px', background: 'none', border: 'none', cursor: 'pointer', color: 'var(--txt-sec)', fontSize: '0.76rem', lineHeight: 1.35, transition: 'color 0.15s' }}>
                  <span style={{ fontSize: '0.62rem', color: 'var(--txt-mut)', fontFamily: 'JetBrains Mono,monospace', marginRight: 8 }}>{String(idx + 1).padStart(2, '0')}</span>
                  {sec.heading}
                </button>
              ))}
            </div>
          )}

          {sorted.length > 0 && (
            <div className="glass-card-solid" style={{ padding: '26px 30px' }}>
              {sorted.map((sec, idx) => (
                <div key={idx} ref={el => { refs.current[idx] = el }} style={{ marginBottom: 44, scrollMarginTop: 24 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16, paddingBottom: 12, borderBottom: '1px solid var(--border)' }}>
                    <span style={{ fontSize: '0.63rem', fontFamily: 'JetBrains Mono,monospace', color: 'var(--cyan)', background: 'rgba(34,211,238,0.08)', borderRadius: 6, padding: '2px 9px' }}>{String(idx + 1).padStart(2, '0')}</span>
                    <h2 style={{ fontSize: '1.06rem', fontWeight: 700, color: 'var(--txt-pri)', margin: 0 }}>{sec.heading}</h2>
                  </div>
                  <div>
                    {sec.content.split('\n\n').map((para, pi) => para.trim() ? (
                      <p key={pi} style={{ fontSize: '0.89rem', color: 'var(--txt-sec)', lineHeight: 1.84, margin: '0 0 18px' }}>{para.trim()}</p>
                    ) : null)}
                  </div>
                </div>
              ))}
              {conclusion && (
                <div style={{ marginTop: 44, paddingTop: 26, borderTop: '2px solid var(--border)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
                    <span style={{ fontSize: '0.63rem', fontFamily: 'JetBrains Mono,monospace', color: 'var(--photon)', background: 'rgba(77,166,255,0.08)', borderRadius: 6, padding: '2px 9px' }}>CONCLUSION</span>
                  </div>
                  {conclusion.split('\n\n').map((para, pi) => para.trim() ? (
                    <p key={pi} style={{ fontSize: '0.89rem', color: 'var(--txt-sec)', lineHeight: 1.84, margin: '0 0 18px' }}>{para.trim()}</p>
                  ) : null)}
                </div>
              )}
            </div>
          )}

          {sources.length > 0 && (
            <div className="glass-card-solid" style={{ padding: 16, marginTop: 14 }}>
              <div style={{ fontSize: '0.62rem', textTransform: 'uppercase', letterSpacing: '0.14em', color: 'var(--txt-mut)', marginBottom: 10 }}>Sources</div>
              <div style={{ display: 'grid', gap: 9 }}>
                {sources.map((src, idx) => (
                  <div key={idx} style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
                    <span style={{ fontSize: '0.65rem', color: 'var(--cyan)', fontFamily: 'JetBrains Mono,monospace', flexShrink: 0, minWidth: 30 }}>S{idx + 1}</span>
                    <div>
                      <div style={{ fontSize: '0.78rem', color: 'var(--txt-sec)', fontWeight: 600 }}>{src.title || src.label || 'Source'}</div>
                      {(src.url || src.source) && <div style={{ fontSize: '0.65rem', color: 'var(--txt-mut)', fontFamily: 'JetBrains Mono,monospace', marginTop: 2, overflowWrap: 'anywhere' }}>{src.url || src.source}</div>}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
