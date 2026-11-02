import { normalizeConfidence } from '../lib/confidence'

/**
 * Trust Surfaces — Per-response confidence, provider, contradiction, and evidence badges
 * Displayed alongside assistant responses in Chat and Tutor surfaces
 */

/**
 * ProvenianceBadge — Shows which provider generated the response
 */
export function ProvenianceBadge({ provider = 'unknown' }) {
  const providerInfo = {
    deepseek: { label: 'DeepSeek', color: 'var(--mm-color-agent-default)', icon: '🧠' },
    openai: { label: 'OpenAI', color: 'var(--mm-color-system-default)', icon: '⚡' },
    ollama: { label: 'Local (Ollama)', color: 'var(--gold)', icon: '🖥️' },
    unknown: { label: 'Mixed', color: 'var(--txt-sec)', icon: '?' },
  }

  const info = providerInfo[String(provider || 'unknown').toLowerCase()] || providerInfo.unknown

  return (
    <div
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 4,
        padding: '4px 10px',
        borderRadius: 999,
        background: `color-mix(in srgb, ${info.color} 8.24%, transparent)`,
        border: `1px solid color-mix(in srgb, ${info.color} 25.10%, transparent)`,
        fontSize: '0.7rem',
        fontWeight: 500,
        color: info.color,
        marginRight: 6,
      }}
      title={`Provider: ${info.label}. Provider identity is not answer verification.`}
    >
      <span>{info.icon}</span>
      <span>{info.label}</span>
    </div>
  )
}

/**
 * ConfidenceIndicator — Visual confidence score (0–1)
 */
export function ConfidenceIndicator({ score, label = 'Reported score (uncalibrated)' }) {
  const normalized = normalizeConfidence(score)
  const getColor = (s) => {
    if (s >= 0.85) return 'var(--mm-color-system-default)'
    if (s >= 0.7) return 'var(--gold)'
    return '#ff6b6b'
  }

  const color = normalized === null ? 'var(--txt-sec)' : getColor(normalized)
  const percentage = normalized === null ? null : Math.round(normalized * 100)

  return (
    <div
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        padding: '4px 10px',
        borderRadius: 999,
        background: `color-mix(in srgb, ${color} 8.24%, transparent)`,
        border: `1px solid color-mix(in srgb, ${color} 25.10%, transparent)`,
        fontSize: '0.7rem',
        fontWeight: 500,
        color,
      }}
      title={percentage === null ? 'Answer correctness has not been assessed. Provider availability and citations do not establish correctness.' : `${label}: ${percentage}%. Not a measured probability of correctness.`}
    >
      <div style={{ width: 12, height: 12, borderRadius: '50%', background: color, opacity: 0.6 }} />
      <span>{percentage === null ? 'Not assessed' : `${percentage}%`}</span>
    </div>
  )
}

/**
 * ContradictionFlag — Shows if response contradicts prior context or sources
 */
export function ContradictionFlag({ contradictions = [], severity = 'low' }) {
  if (!contradictions || contradictions.length === 0) {
    return null
  }

  const severityColor = {
    low: 'var(--gold)',
    medium: '#ff9500',
    high: '#ff6b6b',
  }

  return (
    <div
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 4,
        padding: '4px 10px',
        borderRadius: 999,
        background: `${severityColor[severity]}15`,
        border: `1px solid ${severityColor[severity]}40`,
        fontSize: '0.7rem',
        fontWeight: 500,
        color: severityColor[severity],
        cursor: 'pointer',
      }}
      title={`Contradictions detected:\n${contradictions.map((c) => `• ${c}`).join('\n')}`}
    >
      <span>⚠️</span>
      <span>{contradictions.length} contradiction{contradictions.length !== 1 ? 's' : ''}</span>
    </div>
  )
}

/**
 * EvidenceQualityBadge — Shows evidence breadth, ranking, and source credibility
 */
export function EvidenceQualityBadge({
  sourceCount = 0,
  avgRelevance,
  avgCredibility,
  citationCoverage,
}) {
  const metrics = [avgRelevance, avgCredibility, citationCoverage].map(normalizeConfidence)
  if (metrics.some(value => value === null)) {
    return <span title="Source count only; source quality and answer correctness are not assessed.">{sourceCount} source{sourceCount === 1 ? '' : 's'}</span>
  }
  const overallScore = metrics.reduce((sum, value) => sum + value, 0) / 3

  const getGrade = (score) => {
    if (score >= 0.85) return { label: 'A', color: 'var(--mm-color-system-default)' }
    if (score >= 0.75) return { label: 'B', color: 'var(--gold)' }
    if (score >= 0.6) return { label: 'C', color: '#ff9500' }
    return { label: 'D', color: '#ff6b6b' }
  }

  const grade = getGrade(overallScore)

  return (
    <div
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        padding: '4px 10px',
        borderRadius: 999,
        background: `color-mix(in srgb, ${grade.color} 8.24%, transparent)`,
        border: `1px solid color-mix(in srgb, ${grade.color} 25.10%, transparent)`,
        fontSize: '0.7rem',
        fontWeight: 600,
        color: grade.color,
      }}
      title={`Evidence grade: ${grade.label}
Sources: ${sourceCount}
Relevance: ${(metrics[0] * 100).toFixed(0)}%
Credibility: ${(metrics[1] * 100).toFixed(0)}%
Citation coverage: ${(metrics[2] * 100).toFixed(0)}%`}
    >
      <span>📚</span>
      <span>{grade.label}</span>
    </div>
  )
}

/**
 * TrustBadgeRow — Composite component showing all trust signals for a response
 */
export function TrustBadgeRow({
  provider = 'unknown',
  confidence,
  contradictions = [],
  sourceCount = 0,
  avgRelevance,
  avgCredibility,
  citationCoverage,
  showEvidence = true,
  style = {},
}) {
  return (
    <div
      style={{
        display: 'flex',
        gap: 8,
        flexWrap: 'wrap',
        fontSize: '0.7rem',
        marginBottom: 8,
        padding: '8px 0',
        borderBottom: '1px solid rgba(77,166,255,0.1)',
        ...style,
      }}
    >
      <ProvenianceBadge provider={provider} confidence={confidence} />
      <ConfidenceIndicator score={confidence} />
      {contradictions.length > 0 && (
        <ContradictionFlag
          contradictions={contradictions}
          severity={contradictions.length > 2 ? 'high' : contradictions.length > 0 ? 'medium' : 'low'}
        />
      )}
      {showEvidence && sourceCount > 0 && (
        <EvidenceQualityBadge
          sourceCount={sourceCount}
          avgRelevance={avgRelevance}
          avgCredibility={avgCredibility}
          citationCoverage={citationCoverage}
        />
      )}
    </div>
  )
}

/**
 * DetailedTrustPanel — Expanded view showing full provenance details
 */
export function DetailedTrustPanel({
  provider = 'unknown',
  confidence,
  contradictions = [],
  sources = [],
  model = 'unknown',
  latency = 0,
  tokensUsed = 0,
  isOpen = false,
  onToggle = () => {},
}) {
  return (
    <div
      style={{
        borderRadius: 8,
        border: '1px solid rgba(77,166,255,0.2)',
        background: 'rgba(77,166,255,0.05)',
        overflow: 'hidden',
      }}
    >
      <button
        onClick={onToggle}
        style={{
          width: '100%',
          padding: '10px 12px',
          background: 'transparent',
          border: 'none',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          cursor: 'pointer',
          fontWeight: 500,
          fontSize: '0.8rem',
          color: 'var(--txt-primary)',
        }}
      >
        <span>🔍 Provenance & Trust Details</span>
        <span style={{ transform: isOpen ? 'rotate(180deg)' : '', transition: '0.2s' }}>▼</span>
      </button>

      {isOpen && (
        <div style={{ padding: '12px 16px', borderTop: '1px solid rgba(77,166,255,0.2)', fontSize: '0.8rem' }}>
          <div style={{ display: 'grid', gap: 10 }}>
            <div>
              <div style={{ fontWeight: 600, color: 'var(--mm-color-system-default)', marginBottom: 2 }}>Provider</div>
              <div style={{ color: 'var(--txt-sec)' }}>{provider}</div>
            </div>

            <div>
              <div style={{ fontWeight: 600, color: 'var(--mm-color-system-default)', marginBottom: 2 }}>Model</div>
              <div style={{ color: 'var(--txt-sec)' }}>{model}</div>
            </div>

            <div>
              <div style={{ fontWeight: 600, color: 'var(--mm-color-system-default)', marginBottom: 2 }}>Reported score (uncalibrated)</div>
              <div style={{ color: 'var(--txt-sec)' }}>{normalizeConfidence(confidence) === null ? 'Not assessed' : `${(normalizeConfidence(confidence) * 100).toFixed(1)}%`}</div>
            </div>

            {contradictions.length > 0 && (
              <div>
                <div style={{ fontWeight: 600, color: '#ff9500', marginBottom: 4 }}>⚠️ Contradictions</div>
                <div style={{ display: 'grid', gap: 4, marginLeft: 4 }}>
                  {contradictions.map((c, i) => (
                    <div key={i} style={{ fontSize: '0.75rem', color: 'var(--txt-sec)' }}>
                      • {c}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {sources.length > 0 && (
              <div>
                <div style={{ fontWeight: 600, color: 'var(--mm-color-system-default)', marginBottom: 4 }}>Sources ({sources.length})</div>
                <div style={{ display: 'grid', gap: 4, marginLeft: 4 }}>
                  {sources.slice(0, 3).map((src, i) => (
                    <div key={i} style={{ fontSize: '0.75rem', color: 'var(--txt-sec)' }}>
                      • {src.title || src.url}
                      <br />
                      <span style={{ color: 'var(--txt-mut)', fontSize: '0.7rem' }}>
                        Relevance: {src.relevance}% | Authority: {src.authority}%
                      </span>
                    </div>
                  ))}
                  {sources.length > 3 && (
                    <div style={{ fontSize: '0.75rem', color: 'var(--txt-mut)' }}>
                      +{sources.length - 3} more sources
                    </div>
                  )}
                </div>
              </div>
            )}

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, fontSize: '0.75rem' }}>
              <div>
                <div style={{ color: 'var(--txt-mut)', marginBottom: 2 }}>Latency</div>
                <div style={{ color: 'var(--txt-sec)', fontWeight: 500 }}>{latency}ms</div>
              </div>
              <div>
                <div style={{ color: 'var(--txt-mut)', marginBottom: 2 }}>Tokens</div>
                <div style={{ color: 'var(--txt-sec)', fontWeight: 500 }}>{tokensUsed}</div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
