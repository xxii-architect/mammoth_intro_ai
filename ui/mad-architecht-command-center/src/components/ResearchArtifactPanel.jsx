import { AlertTriangle, BookOpen, CheckCircle2, Link2, Search, Sparkles } from 'lucide-react'

function Pill({ children, tone = 'neutral' }) {
  const styles = {
    neutral: { background: 'rgba(255,255,255,0.04)', border: '1px solid var(--border)', color: 'var(--txt-sec)' },
    info: { background: 'rgba(77,166,255,0.08)', border: '1px solid rgba(77,166,255,0.2)', color: 'var(--photon)' },
    success: { background: 'rgba(34,197,94,0.08)', border: '1px solid rgba(34,197,94,0.2)', color: '#22c55e' },
    warning: { background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.2)', color: '#fbbf24' },
  }
  const style = styles[tone] || styles.neutral
  return (
    <span style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: 6,
      padding: '5px 9px',
      borderRadius: 999,
      fontSize: '0.68rem',
      fontWeight: 700,
      textTransform: 'uppercase',
      letterSpacing: '0.06em',
      ...style,
    }}>
      {children}
    </span>
  )
}

function SourceCard({ source, kind }) {
  const title = source?.title || source?.label || 'Source'
  const url = source?.url || source?.source || ''
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
  if (!artifact) return null

  const sources = Array.isArray(artifact.sources) ? artifact.sources : []
  const citations = Array.isArray(artifact.citations) ? artifact.citations : []
  const references = Array.isArray(artifact.references) ? artifact.references : []
  const findings = Array.isArray(artifact.findings) ? artifact.findings : []
  const flags = Array.isArray(artifact.qualityFlags) ? artifact.qualityFlags : []
  const retrievalErrors = Array.isArray(artifact.retrievalErrors) ? artifact.retrievalErrors : []
  const sourceCoverage = artifact.sourceCoverage || {}

  return (
    <div style={{ display: 'grid', gap: 12 }}>
      <div className="glass-card-solid" style={{ padding: 16, borderLeft: '3px solid var(--cyan)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', alignItems: 'flex-start' }}>
          <div style={{ minWidth: 0, flex: '1 1 320px' }}>
            <div style={{ fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.14em', color: 'var(--txt-mut)', marginBottom: 6 }}>
              Research artifact ready
            </div>
            <div style={{ fontSize: '1rem', fontWeight: 800, color: 'var(--txt-pri)', lineHeight: 1.35 }}>
              {artifact.summary || 'Grounded research response'}
            </div>
            <div style={{ color: 'var(--txt-sec)', fontSize: '0.78rem', marginTop: 6, lineHeight: 1.5, wordBreak: 'break-word' }}>
              {artifact.focus || 'general'}{artifact.agent ? ` • ${artifact.agent}` : ''}{artifact.mode ? ` • ${artifact.mode}` : ''}
            </div>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 6 }}>
            <Pill tone={artifact.status === 'ok' ? 'success' : 'warning'}>{artifact.status || 'ok'}</Pill>
            {artifact.confidence !== null && artifact.confidence !== undefined && (
              <span style={{ fontSize: '0.68rem', color: 'var(--txt-mut)', fontFamily: 'JetBrains Mono,monospace' }}>
                confidence {Math.round(Number(artifact.confidence) * 100)}%
              </span>
            )}
          </div>
        </div>

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 12 }}>
          <Pill tone="info"><Search size={12} /> {sourceCoverage.source_count || sources.length || 0} sources</Pill>
          <Pill tone="success"><CheckCircle2 size={12} /> {sourceCoverage.citation_coverage ? `${Math.round(Number(sourceCoverage.citation_coverage) * 100)}% cited` : `${citations.length} citations`}</Pill>
          {retrievalErrors.length > 0 && <Pill tone="warning"><AlertTriangle size={12} /> retrieval notes</Pill>}
        </div>

        <div style={{ marginTop: 12, color: 'var(--txt-sec)', fontSize: '0.82rem', lineHeight: 1.7 }}>
          {artifact.summary || 'The research agent returned a structured evidence bundle.'}
        </div>

        {flags.length > 0 && (
          <div style={{ marginTop: 12 }}>
            <div style={{ fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-mut)', marginBottom: 6 }}>
              Quality flags
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {flags.map((flag) => <Pill key={flag} tone="warning">{flag}</Pill>)}
            </div>
          </div>
        )}
      </div>

      {findings.length > 0 && (
        <div className="glass-card-solid" style={{ padding: 16 }}>
          <div style={{ fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-mut)', marginBottom: 8 }}>
            Key findings
          </div>
          <div style={{ display: 'grid', gap: 8 }}>
            {findings.slice(0, 6).map((finding, idx) => (
              <div key={`${finding.id || idx}`} style={{ padding: '9px 11px', borderRadius: 10, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)', color: 'var(--txt-sec)', fontSize: '0.76rem', lineHeight: 1.5 }}>
                {typeof finding === 'string' ? finding : finding.statement || finding.summary || JSON.stringify(finding)}
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="glass-card-solid" style={{ padding: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
          <Sparkles size={15} color="var(--cyan)" />
          <div style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-mut)' }}>
            Sources and citations
          </div>
        </div>

        {sources.length > 0 && (
          <div style={{ display: 'grid', gap: 8, marginBottom: 12 }}>
            {sources.slice(0, 4).map((source, idx) => <SourceCard key={source.id || idx} source={source} />)}
          </div>
        )}

        {citations.length > 0 && (
          <div style={{ display: 'grid', gap: 8, marginBottom: 12 }}>
            <div style={{ fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-mut)' }}>
              Citations
            </div>
            {citations.slice(0, 6).map((citation, idx) => (
              <SourceCard key={citation.id || idx} source={citation} kind="citation" />
            ))}
          </div>
        )}

        {references.length > 0 && (
          <div style={{ display: 'grid', gap: 8 }}>
            <div style={{ fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-mut)' }}>
              References
            </div>
            {references.slice(0, 6).map((reference, idx) => (
              <SourceCard key={reference.id || idx} source={reference} />
            ))}
          </div>
        )}

        {retrievalErrors.length > 0 && (
          <div style={{ marginTop: 12, display: 'grid', gap: 6 }}>
            <div style={{ fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-mut)' }}>
              Retrieval notes
            </div>
            {retrievalErrors.map((error, idx) => (
              <div key={`${error}-${idx}`} style={{ padding: '9px 11px', borderRadius: 10, border: '1px solid rgba(245,158,11,0.22)', background: 'rgba(245,158,11,0.06)', color: '#fbbf24', fontSize: '0.76rem', lineHeight: 1.5 }}>
                {error}
              </div>
            ))}
          </div>
        )}
      </div>

      {rawJson && (
        <div className="glass-card-solid" style={{ padding: 16 }}>
          <div style={{ fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-mut)', marginBottom: 8 }}>
            Raw
          </div>
          <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontFamily: 'JetBrains Mono,monospace', fontSize: '0.72rem', lineHeight: 1.6, color: 'var(--txt-pri)' }}>
            {rawJson}
          </pre>
        </div>
      )}
    </div>
  )
}
