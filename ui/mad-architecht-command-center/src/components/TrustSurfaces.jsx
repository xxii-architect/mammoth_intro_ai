/**
 * Trust Surfaces — Per-response confidence, provider, contradiction, and evidence badges
 * Displayed alongside assistant responses in Chat and Tutor surfaces
 */

/**
 * ProvenianceBadge — Shows which provider generated the response
 */
export function ProvenianceBadge({ provider = 'unknown', confidence = 0.8 }) {
  const providerInfo = {
    deepseek: { label: 'DeepSeek', color: 'var(--violet)', icon: '🧠' },
    openai: { label: 'OpenAI', color: 'var(--cyan)', icon: '⚡' },
    ollama: { label: 'Local (Ollama)', color: 'var(--gold)', icon: '🖥️' },
    unknown: { label: 'Mixed', color: 'var(--txt-sec)', icon: '?' },
  }

  const info = providerInfo[provider.toLowerCase()] || providerInfo.unknown

  return (
    <div
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 4,
        padding: '4px 10px',
        borderRadius: 999,
        background: `${info.color}15`,
        border: `1px solid ${info.color}40`,
        fontSize: '0.7rem',
        fontWeight: 500,
        color: info.color,
        marginRight: 6,
      }}
      title={`Provider: ${info.label}\nConfidence: ${(confidence * 100).toFixed(0)}%`}
    >
      <span>{info.icon}</span>
      <span>{info.label}</span>
      {confidence < 0.7 && (
        <span style={{ marginLeft: 2, opacity: 0.7 }}>
          ⚠️ {(confidence * 100).toFixed(0)}%
        </span>
      )}
    </div>
  )
}

/**
 * ConfidenceIndicator — Visual confidence score (0–1)
 */
export function ConfidenceIndicator({ score = 0.8, label = 'Confidence' }) {
  const getColor = (s) => {
    if (s >= 0.85) return 'var(--cyan)'
    if (s >= 0.7) return 'var(--gold)'
    return '#ff6b6b'
  }

  const color = getColor(score)
  const percentage = Math.round(score * 100)

  return (
    <div
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        padding: '4px 10px',
        borderRadius: 999,
        background: `${color}15`,
        border: `1px solid ${color}40`,
        fontSize: '0.7rem',
        fontWeight: 500,
        color,
      }}
      title={`${label}: ${percentage}%`}
    >
      <div style={{ width: 12, height: 12, borderRadius: '50%', background: color, opacity: 0.6 }} />
      <span>{percentage}%</span>
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
  avgRelevance = 0.8,
  avgCredibility = 0.75,
  citationCoverage = 0.6,
}) {
  const overallScore = (avgRelevance + avgCredibility + citationCoverage) / 3

  const getGrade = (score) => {
    if (score >= 0.85) return { label: 'A', color: 'var(--cyan)' }
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
        background: `${grade.color}15`,
        border: `1px solid ${grade.color}40`,
        fontSize: '0.7rem',
        fontWeight: 600,
        color: grade.color,
      }}
      title={`Evidence grade: ${grade.label}
Sources: ${sourceCount}
Relevance: ${(avgRelevance * 100).toFixed(0)}%
Credibility: ${(avgCredibility * 100).toFixed(0)}%
Citation coverage: ${(citationCoverage * 100).toFixed(0)}%`}
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
  confidence = 0.8,
  contradictions = [],
  sourceCount = 0,
  avgRelevance = 0.8,
  avgCredibility = 0.75,
  citationCoverage = 0.6,
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
      <ConfidenceIndicator score={confidence} label="Output confidence" />
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
  confidence = 0.8,
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
              <div style={{ fontWeight: 600, color: 'var(--cyan)', marginBottom: 2 }}>Provider</div>
              <div style={{ color: 'var(--txt-sec)' }}>{provider}</div>
            </div>

            <div>
              <div style={{ fontWeight: 600, color: 'var(--cyan)', marginBottom: 2 }}>Model</div>
              <div style={{ color: 'var(--txt-sec)' }}>{model}</div>
            </div>

            <div>
              <div style={{ fontWeight: 600, color: 'var(--cyan)', marginBottom: 2 }}>Confidence</div>
              <div style={{ color: 'var(--txt-sec)' }}>{(confidence * 100).toFixed(1)}%</div>
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
                <div style={{ fontWeight: 600, color: 'var(--cyan)', marginBottom: 4 }}>Sources ({sources.length})</div>
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
