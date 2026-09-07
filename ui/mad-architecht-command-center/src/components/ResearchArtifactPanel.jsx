import { useState } from 'react'
import { AlertTriangle, BookOpen, CheckCircle2, ChevronDown, ChevronRight, Link2, Search, Sparkles } from 'lucide-react'

function Pill({ children, tone = 'neutral' }) {
  const styles = {
    neutral: { background: 'rgba(255,255,255,0.04)', border: '1px solid var(--border)', color: 'var(--txt-sec)' },
    info:    { background: 'rgba(77,166,255,0.08)',  border: '1px solid rgba(77,166,255,0.2)',  color: 'var(--photon)' },
    success: { background: 'rgba(34,197,94,0.08)',   border: '1px solid rgba(34,197,94,0.2)',   color: '#22c55e' },
    warning: { background: 'rgba(245,158,11,0.08)',  border: '1px solid rgba(245,158,11,0.2)',  color: '#fbbf24' },
  }
  const style = styles[tone] || styles.neutral
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '5px 9px', borderRadius: 999, fontSize: '0.68rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', ...style }}>
      {children}
    </span>
  )
}

function SourceCard({ source, kind }) {
  const title   = source?.title   || source?.label || 'Source'
  const url     = source?.url     || source?.source || ''
  const snippet = source?.snippet || source?.summary || source?.quote || 'No snippet provided.'
  return (
    <div style={{ padding: '10px 12px', borderRadius: 10, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
        {kind === 'citation' ? <Link2 size={13} color="var(--cyan)" /> : <BookOpen size={13} color="var(--photon)" />}
        <span style={{ fontSize: '0.76rem', fontWeight: 700, color: 'var(--txt-pri)' }}>{title}</span>
      </div>
      <div style={{ fontSize: '0.73rem', color: 'var(--txt-sec)', lineHeight: 1.55 }}>{snippet}</div>
      {url && (
        <div style={{ fontSize: '0.64rem', color: 'var(--txt-mut)', fontFamily: 'JetBrains Mono,monospace', marginTop: 5, overflowWrap: 'anywhere' }}>
          {url}
        </div>
      )}
    </div>
  )
}

export default function ResearchArtifactPanel({ artifact, rawJson }) {
  const [showRaw, setShowRaw] = useState(false)
  if (!artifact) return null

  // ── Research agent schema ────────────────────────────────────────────────
  const title       = artifact.title || artifact.summary || 'Research Brief'
  const execSummary = artifact.executive_summary || artifact.summary || ''
  const findings    = Array.isArray(artifact.findings)                   ? artifact.findings                   : []
  const keyFacts    = Array.isArray(artifact.key_facts)                  ? artifact.key_facts                  : []
  const nextSteps   = Array.isArray(artifact.recommended_next_steps)     ? artifact.recommended_next_steps     : []
  const confidence  = artifact.confidence_assessment || ''
  const gaps        = artifact.knowledge_gaps        || ''

  // ── Legacy / pipeline fields (keep backward-compat) ─────────────────────
  const sources        = Array.isArray(artifact.sources)        ? artifact.sources        : []
  const citations      = Array.isArray(artifact.citations)      ? artifact.citations      : []
  const references     = Array.isArray(artifact.references)     ? artifact.references     : []
  const flags          = Array.isArray(artifact.qualityFlags)   ? artifact.qualityFlags   : []
  const retrievalErrors= Array.isArray(artifact.retrievalErrors)? artifact.retrievalErrors: []
  const hasSourceMaterial = sources.length > 0 || citations.length > 0 || references.length > 0

  return (
    <div style={{ display: 'grid', gap: 12 }}>

      {/* ── Header ────────────────────────────────────────────────────────── */}
      <div className="glass-card-solid" style={{ padding: 16, borderLeft: '3px solid var(--cyan)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'flex-start' }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: '0.65rem', textTransform: 'uppercase', letterSpacing: '0.14em', color: 'var(--txt-mut)', marginBottom: 6 }}>
              Research Brief
            </div>
            <div style={{ fontSize: '1rem', fontWeight: 800, color: 'var(--txt-pri)', lineHeight: 1.35 }}>
              {title}
            </div>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 6, flexShrink: 0 }}>
            {findings.length > 0 && <Pill tone="success"><CheckCircle2 size={12} /> {findings.length} findings</Pill>}
            {sources.length  > 0 && <Pill tone="info"><Search size={12} /> {sources.length} sources</Pill>}
          </div>
        </div>
        {flags.length > 0 && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 12 }}>
            {flags.map(f => <Pill key={f} tone="warning"><AlertTriangle size={10} /> {f.replace(/_/g, ' ')}</Pill>)}
          </div>
        )}
      </div>

      {/* ── Executive Summary ─────────────────────────────────────────────── */}
      {execSummary && (
        <div className="glass-card-solid" style={{ padding: 16, borderLeft: '3px solid var(--photon)' }}>
          <div style={{ fontSize: '0.65rem', textTransform: 'uppercase', letterSpacing: '0.14em', color: 'var(--txt-mut)', marginBottom: 8 }}>
            Executive Summary
          </div>
          <p style={{ fontSize: '0.88rem', color: 'var(--txt-pri)', lineHeight: 1.72, margin: 0 }}>
            {execSummary}
          </p>
        </div>
      )}

      {/* ── Key Findings ──────────────────────────────────────────────────── */}
      {findings.length > 0 && (
        <div className="glass-card-solid" style={{ padding: 16 }}>
          <div style={{ fontSize: '0.65rem', textTransform: 'uppercase', letterSpacing: '0.14em', color: 'var(--txt-mut)', marginBottom: 10 }}>
            Key Findings
          </div>
          <div style={{ display: 'grid', gap: 10 }}>
            {findings.map((f, idx) => {
              const heading = f.heading || f.claim || f.title || `Finding ${idx + 1}`
              const content = f.content || f.summary || f.statement || (typeof f === 'string' ? f : '')
              const support = Array.isArray(f.source_support) ? f.source_support : []
              const isSynthesized = f.source_type === 'llm_synthesized'
              return (
                <div key={idx} style={{ padding: '11px 13px', borderRadius: 10, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 5, flexWrap: 'wrap' }}>
                    <span style={{ fontSize: '0.79rem', fontWeight: 700, color: 'var(--txt-pri)' }}>{heading}</span>
                    {isSynthesized && (
                      <span style={{ fontSize: '0.6rem', background: 'rgba(167,139,250,0.12)', color: '#a78bfa', borderRadius: 8, padding: '1px 7px', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                        synthesized
                      </span>
                    )}
                  </div>
                  {content && (
                    <div style={{ fontSize: '0.76rem', color: 'var(--txt-sec)', lineHeight: 1.62 }}>{content}</div>
                  )}
                  {support.length > 0 && (
                    <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginTop: 7 }}>
                      {support.map(s => (
                        <span key={s} style={{ fontSize: '0.63rem', background: 'rgba(77,166,255,0.10)', color: 'var(--photon)', borderRadius: 10, padding: '2px 7px', fontFamily: 'JetBrains Mono,monospace' }}>
                          {s}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* ── Key Facts ─────────────────────────────────────────────────────── */}
      {keyFacts.length > 0 && (
        <div className="glass-card-solid" style={{ padding: 16 }}>
          <div style={{ fontSize: '0.65rem', textTransform: 'uppercase', letterSpacing: '0.14em', color: 'var(--txt-mut)', marginBottom: 10 }}>
            Key Facts
          </div>
          <div style={{ display: 'grid', gap: 7 }}>
            {keyFacts.map((fact, idx) => (
              <div key={idx} style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
                <span style={{ color: 'var(--cyan)', fontSize: '0.7rem', fontFamily: 'JetBrains Mono,monospace', paddingTop: 3, flexShrink: 0, minWidth: 22 }}>
                  {String(idx + 1).padStart(2, '0')}
                </span>
                <span style={{ fontSize: '0.8rem', color: 'var(--txt-sec)', lineHeight: 1.62 }}>
                  {typeof fact === 'string' ? fact : JSON.stringify(fact)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Recommended Next Steps ────────────────────────────────────────── */}
      {nextSteps.length > 0 && (
        <div className="glass-card-solid" style={{ padding: 16 }}>
          <div style={{ fontSize: '0.65rem', textTransform: 'uppercase', letterSpacing: '0.14em', color: 'var(--txt-mut)', marginBottom: 10 }}>
            Recommended Next Steps
          </div>
          <div style={{ display: 'grid', gap: 8 }}>
            {nextSteps.map((step, idx) => (
              <div key={idx} style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
                <CheckCircle2 size={14} color="var(--photon)" style={{ flexShrink: 0, marginTop: 3 }} />
                <span style={{ fontSize: '0.8rem', color: 'var(--txt-sec)', lineHeight: 1.62 }}>
                  {typeof step === 'string' ? step : JSON.stringify(step)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Knowledge Gaps + Confidence ───────────────────────────────────── */}
      {(gaps || confidence) && (
        <div className="glass-card-solid" style={{ padding: 16 }}>
          {gaps && (
            <div style={{ marginBottom: confidence ? 14 : 0 }}>
              <div style={{ fontSize: '0.65rem', textTransform: 'uppercase', letterSpacing: '0.14em', color: 'var(--txt-mut)', marginBottom: 6 }}>
                Knowledge Gaps
              </div>
              <p style={{ fontSize: '0.79rem', color: 'var(--txt-sec)', lineHeight: 1.62, margin: 0 }}>{gaps}</p>
            </div>
          )}
          {confidence && (
            <div>
              <div style={{ fontSize: '0.65rem', textTransform: 'uppercase', letterSpacing: '0.14em', color: 'var(--txt-mut)', marginBottom: 6 }}>
                Confidence Assessment
              </div>
              <p style={{ fontSize: '0.79rem', color: 'var(--txt-sec)', lineHeight: 1.62, margin: 0 }}>{confidence}</p>
            </div>
          )}
        </div>
      )}

      {/* ── Sources + Citations ───────────────────────────────────────────── */}
      {hasSourceMaterial && (
        <div className="glass-card-solid" style={{ padding: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
            <Sparkles size={15} color="var(--cyan)" />
            <div style={{ fontSize: '0.65rem', textTransform: 'uppercase', letterSpacing: '0.14em', color: 'var(--txt-mut)' }}>
              Sources and Citations
            </div>
          </div>
          {sources.length > 0 && (
            <div style={{ display: 'grid', gap: 8, marginBottom: citations.length > 0 ? 12 : 0 }}>
              {sources.slice(0, 4).map((s, idx) => <SourceCard key={s.id || idx} source={s} />)}
            </div>
          )}
          {citations.length > 0 && (
            <div style={{ display: 'grid', gap: 8, marginBottom: references.length > 0 ? 12 : 0 }}>
              <div style={{ fontSize: '0.65rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-mut)', marginBottom: 2 }}>Citations</div>
              {citations.slice(0, 6).map((c, idx) => <SourceCard key={c.id || idx} source={c} kind="citation" />)}
            </div>
          )}
          {references.length > 0 && (
            <div style={{ display: 'grid', gap: 8 }}>
              <div style={{ fontSize: '0.65rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-mut)', marginBottom: 2 }}>References</div>
              {references.slice(0, 6).map((r, idx) => <SourceCard key={r.id || idx} source={r} />)}
            </div>
          )}
          {retrievalErrors.length > 0 && (
            <div style={{ marginTop: 12, display: 'grid', gap: 6 }}>
              <div style={{ fontSize: '0.65rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-mut)' }}>Retrieval Notes</div>
              {retrievalErrors.map((err, idx) => (
                <div key={idx} style={{ padding: '9px 11px', borderRadius: 10, border: '1px solid rgba(245,158,11,0.22)', background: 'rgba(245,158,11,0.06)', color: '#fbbf24', fontSize: '0.76rem', lineHeight: 1.5 }}>
                  {err}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── Raw JSON — collapsed by default ───────────────────────────────── */}
      {rawJson && (
        <div className="glass-card-solid" style={{ padding: 16 }}>
          <button
            onClick={() => setShowRaw(r => !r)}
            style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.65rem', color: 'var(--txt-mut)', background: 'none', border: 'none', cursor: 'pointer', padding: 0, textTransform: 'uppercase', letterSpacing: '0.12em' }}
          >
            {showRaw ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
            Raw JSON
          </button>
          {showRaw && (
            <pre style={{ margin: '10px 0 0', whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontFamily: 'JetBrains Mono,monospace', fontSize: '0.72rem', lineHeight: 1.6, color: 'var(--txt-sec)', maxHeight: 300, overflowY: 'auto' }}>
              {rawJson}
            </pre>
          )}
        </div>
      )}

    </div>
  )
}
