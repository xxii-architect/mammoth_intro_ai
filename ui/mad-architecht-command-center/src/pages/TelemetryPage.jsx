import { useEffect, useState } from 'react'
import { BarChart3, TrendingUp, TrendingDown, RefreshCw, Gauge, AlertTriangle, CheckCircle } from 'lucide-react'
import { api } from '../api/client'
import { useInterval } from '../hooks/useApi'

export default function TelemetryPage() {
  const [telemetry, setTelemetry] = useState(null)
  const [loading, setLoading] = useState(true)
  const [lastCheck, setLastCheck] = useState(null)
  const [expandedProvider, setExpandedProvider] = useState(null)

  const fetch = async () => {
    setLoading(true)
    try {
      const response = await api('/telemetry/summary')
      if (response?.data) {
        setTelemetry(response.data)
        setLastCheck(new Date())
      }
    } catch (error) {
      console.error('Failed to fetch telemetry:', error)
    }
    setLoading(false)
  }

  useEffect(() => { fetch() }, [])
  useInterval(fetch, 5000)

  const data = telemetry || {}
  const metrics = data.metrics || {}
  const readiness = data.release_readiness || {}
  const trends = data.trends || {}

  const renderGauge = (score, size = 200) => {
    const readyScore = Math.min(100, Math.max(0, score || 0))
    const angle = (readyScore / 100) * 180 - 90
    
    const statusColor = readyScore >= 70 ? '#22c55e' : readyScore >= 50 ? '#eab308' : '#ef4444'
    const statusText = readyScore >= 70 ? 'READY' : readyScore >= 50 ? 'CAUTION' : 'NOT READY'

    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
        <svg width={size} height={size * 0.6} viewBox={`0 0 ${size} ${size * 0.6}`} style={{ marginBottom: 8 }}>
          {/* Background arc */}
          <path
            d={`M ${size * 0.1} ${size * 0.5} A ${size * 0.4} ${size * 0.4} 0 0 1 ${size * 0.9} ${size * 0.5}`}
            fill="none"
            stroke="var(--border)"
            strokeWidth="8"
          />
          {/* Progress arc */}
          <path
            d={`M ${size * 0.1} ${size * 0.5} A ${size * 0.4} ${size * 0.4} 0 0 1 ${size * 0.9} ${size * 0.5}`}
            fill="none"
            stroke={statusColor}
            strokeWidth="8"
            strokeDasharray={`${(readyScore / 100) * Math.PI * size * 0.4} ${Math.PI * size * 0.4}`}
            strokeLinecap="round"
          />
          {/* Needle */}
          <g transform={`translate(${size / 2} ${size * 0.5})`}>
            <line x1="0" y1="0" x2={`${Math.cos(angle * Math.PI / 180) * size * 0.35}`} y2={`${Math.sin(angle * Math.PI / 180) * size * 0.35}`} 
              stroke={statusColor} strokeWidth="3" strokeLinecap="round" />
            <circle cx="0" cy="0" r="6" fill={statusColor} />
          </g>
          {/* Labels */}
          <text x={size * 0.1} y={size * 0.55} fontSize="10" fill="var(--txt-mut)" textAnchor="middle">0%</text>
          <text x={size * 0.5} y={size * 0.58} fontSize="10" fill="var(--txt-mut)" textAnchor="middle">50%</text>
          <text x={size * 0.9} y={size * 0.55} fontSize="10" fill="var(--txt-mut)" textAnchor="middle">100%</text>
        </svg>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: '2.2rem', fontWeight: 700, color: statusColor, lineHeight: 1 }}>
            {readyScore.toFixed(1)}
          </div>
          <div style={{ fontSize: '0.75rem', fontWeight: 600, color: statusColor, textTransform: 'uppercase', letterSpacing: '0.12em', marginTop: 4 }}>
            {statusText}
          </div>
        </div>
      </div>
    )
  }

  const renderTrendChart = (data, height = 120) => {
    if (!data?.data_points || data.data_points.length < 2) {
      return <div style={{ padding: 20, color: 'var(--txt-mut)', fontSize: '0.85rem', textAlign: 'center' }}>No trend data yet</div>
    }

    const points = data.data_points
    const values = points.map(p => p.value)
    const minVal = Math.min(...values)
    const maxVal = Math.max(...values)
    const range = maxVal - minVal || 1

    const width = 100
    const padding = 12
    const chartWidth = width - padding * 2
    const chartHeight = height - padding * 2

    const pathPoints = points.map((p, i) => {
      const x = padding + (i / (points.length - 1)) * chartWidth
      const y = padding + ((maxVal - p.value) / range) * chartHeight
      return [x, y]
    })

    const pathString = pathPoints.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p[0]} ${p[1]}`).join(' ')

    const trendIcon = data.trend === 'up' ? <TrendingUp size={14} /> : data.trend === 'down' ? <TrendingDown size={14} /> : null
    const trendColor = data.trend === 'up' ? '#22c55e' : data.trend === 'down' ? '#ef4444' : 'var(--txt-mut)'

    return (
      <div>
        <svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" style={{ display: 'block' }}>
          <path d={pathString} fill="none" stroke="var(--cyan)" strokeWidth="1.5" vectorEffect="non-scaling-stroke" />
        </svg>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 8, fontSize: '0.75rem', color: 'var(--txt-mut)' }}>
          <span>{minVal.toFixed(3)}</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: 4, color: trendColor }}>
            {trendIcon} {data.trend}
          </div>
          <span>{maxVal.toFixed(3)}</span>
        </div>
      </div>
    )
  }

  return (
    <div className="page-enter" style={{ padding: 24 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
        <h1 style={{ fontSize: '1.1rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 8 }}>
          <BarChart3 size={20} color="var(--cyan)" /> Release Telemetry Dashboard
        </h1>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          {lastCheck && (
            <span style={{ fontSize: '0.7rem', color: 'var(--txt-mut)', fontFamily: 'JetBrains Mono,monospace' }}>
              Last: {lastCheck.toLocaleTimeString()}
            </span>
          )}
          <button onClick={fetch} disabled={loading}
            style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '7px 14px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.04)', color: 'var(--txt-sec)', cursor: 'pointer', fontSize: '0.82rem' }}>
            <RefreshCw size={14} style={{ animation: loading ? 'spin 1s linear infinite' : 'none' }} /> Refresh
          </button>
        </div>
      </div>

      {!telemetry || loading ? (
        <div style={{ padding: 40, textAlign: 'center', color: 'var(--txt-mut)' }}>
          {loading ? 'Loading telemetry data…' : 'No data available yet. Wait for metrics to accumulate.'}
        </div>
      ) : (
        <>
          {/* Release Readiness Score */}
          <div className="glass-card-solid" style={{ borderRadius: 12, marginBottom: 20, overflow: 'hidden' }}>
            <div style={{ padding: '14px 20px', borderBottom: '1px solid var(--border)', fontSize: '0.8rem', fontWeight: 600, color: 'var(--txt-sec)', textTransform: 'uppercase', letterSpacing: '0.12em', display: 'flex', alignItems: 'center', gap: 8 }}>
              <Gauge size={14} /> Release Readiness Score
            </div>
            <div style={{ padding: 20, display: 'grid', gridTemplateColumns: '1fr 2fr', gap: 20 }}>
              <div>
                {renderGauge(readiness.score, 160)}
              </div>
              <div>
                <h3 style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--txt-pri)', marginBottom: 12 }}>
                  {readiness.ready ? (
                    <span style={{ display: 'flex', alignItems: 'center', gap: 8, color: '#22c55e' }}>
                      <CheckCircle size={16} /> Ready for Release
                    </span>
                  ) : (
                    <span style={{ display: 'flex', alignItems: 'center', gap: 8, color: '#ef4444' }}>
                      <AlertTriangle size={16} /> Not Ready
                    </span>
                  )}
                </h3>
                {readiness.recommendations?.length ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {readiness.recommendations.map((rec, i) => (
                      <div key={i} style={{ fontSize: '0.8rem', color: 'var(--txt-sec)', padding: '8px 12px', background: 'rgba(255,255,255,0.03)', borderRadius: 6, borderLeft: '2px solid var(--border)' }}>
                        {rec}
                      </div>
                    ))}
                  </div>
                ) : (
                  <div style={{ fontSize: '0.8rem', color: 'var(--txt-mut)' }}>All metrics are within acceptable ranges.</div>
                )}
              </div>
            </div>
          </div>

          {/* Key Factors */}
          {readiness.factors && Object.keys(readiness.factors).length > 0 && (
            <div className="glass-card-solid" style={{ borderRadius: 12, marginBottom: 20, overflow: 'hidden' }}>
              <div style={{ padding: '14px 20px', borderBottom: '1px solid var(--border)', fontSize: '0.8rem', fontWeight: 600, color: 'var(--txt-sec)', textTransform: 'uppercase', letterSpacing: '0.12em' }}>
                Score Factors
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 0 }}>
                {Object.entries(readiness.factors).map(([key, factor], idx, arr) => (
                  <div key={key} style={{ 
                    padding: 16, 
                    borderRight: idx % 2 === 0 && idx < arr.length - 1 ? '1px solid var(--border)' : 'none',
                    borderBottom: idx < arr.length - 1 ? '1px solid var(--border)' : 'none'
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                      <span style={{ fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', color: 'var(--txt-mut)', flex: 1 }}>
                        {key.replace(/_/g, ' ')}
                      </span>
                      <span style={{ 
                        fontSize: '0.7rem', 
                        fontWeight: 600, 
                        padding: '2px 6px', 
                        borderRadius: 4,
                        background: factor.status === 'pass' ? 'rgba(34, 197, 94, 0.1)' : 'rgba(239, 68, 68, 0.1)',
                        color: factor.status === 'pass' ? '#22c55e' : '#ef4444',
                        textTransform: 'uppercase'
                      }}>
                        {factor.status}
                      </span>
                    </div>
                    <div style={{ fontSize: '1.1rem', fontWeight: 600, color: 'var(--txt-pri)' }}>
                      {typeof factor.value === 'number' ? factor.value.toFixed(2) : Array.isArray(factor.value) ? `${factor.value.length} issues` : factor.value}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Metrics Summary */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 16, marginBottom: 20 }}>
            <div className="glass-card-solid" style={{ borderRadius: 12, padding: 16 }}>
              <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--txt-mut)', textTransform: 'uppercase', letterSpacing: '0.12em', marginBottom: 8 }}>
                Avg Confidence
              </div>
              <div style={{ fontSize: '1.8rem', fontWeight: 700, color: 'var(--cyan)' }}>
                {(metrics.avg_confidence * 100).toFixed(1)}%
              </div>
              <div style={{ fontSize: '0.7rem', color: 'var(--txt-mut)', marginTop: 8 }}>
                {metrics.avg_confidence >= 0.72 ? '✓ Above threshold' : '⚠ Below 72% minimum'}
              </div>
            </div>

            <div className="glass-card-solid" style={{ borderRadius: 12, padding: 16 }}>
              <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--txt-mut)', textTransform: 'uppercase', letterSpacing: '0.12em', marginBottom: 8 }}>
                Contradiction Rate
              </div>
              <div style={{ fontSize: '1.8rem', fontWeight: 700, color: 'var(--cyan)' }}>
                {(metrics.contradiction_rate * 100).toFixed(2)}%
              </div>
              <div style={{ fontSize: '0.7rem', color: 'var(--txt-mut)', marginTop: 8 }}>
                {metrics.contradiction_rate < 0.08 ? '✓ Below 8% threshold' : '⚠ Exceeds limit'}
              </div>
            </div>

            <div className="glass-card-solid" style={{ borderRadius: 12, padding: 16 }}>
              <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--txt-mut)', textTransform: 'uppercase', letterSpacing: '0.12em', marginBottom: 8 }}>
                Avg Citations
              </div>
              <div style={{ fontSize: '1.8rem', fontWeight: 700, color: 'var(--cyan)' }}>
                {metrics.avg_citation_count.toFixed(1)}
              </div>
              <div style={{ fontSize: '0.7rem', color: 'var(--txt-mut)', marginTop: 8 }}>
                {metrics.avg_citation_count >= 2.5 ? '✓ Above 2.5 minimum' : '⚠ Below threshold'}
              </div>
            </div>

            <div className="glass-card-solid" style={{ borderRadius: 12, padding: 16 }}>
              <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--txt-mut)', textTransform: 'uppercase', letterSpacing: '0.12em', marginBottom: 8 }}>
                Responses Tracked
              </div>
              <div style={{ fontSize: '1.8rem', fontWeight: 700, color: 'var(--cyan)' }}>
                {metrics.record_count || 0}
              </div>
              <div style={{ fontSize: '0.7rem', color: 'var(--txt-mut)', marginTop: 8 }}>
                Last {metrics.window_hours} hours
              </div>
            </div>
          </div>

          {/* Trends */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 16, marginBottom: 20 }}>
            {trends.confidence && (
              <div className="glass-card-solid" style={{ borderRadius: 12, padding: 16, overflow: 'hidden' }}>
                <div style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--txt-pri)', marginBottom: 12 }}>
                  Confidence Trend
                </div>
                {renderTrendChart(trends.confidence, 140)}
              </div>
            )}
            {trends.contradiction_rate && (
              <div className="glass-card-solid" style={{ borderRadius: 12, padding: 16, overflow: 'hidden' }}>
                <div style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--txt-pri)', marginBottom: 12 }}>
                  Contradiction Rate Trend
                </div>
                {renderTrendChart(trends.contradiction_rate, 140)}
              </div>
            )}
          </div>

          {/* Provider Breakdown */}
          {metrics.provider_breakdown && Object.keys(metrics.provider_breakdown).length > 0 && (
            <div className="glass-card-solid" style={{ borderRadius: 12, overflow: 'hidden' }}>
              <div style={{ padding: '14px 20px', borderBottom: '1px solid var(--border)', fontSize: '0.8rem', fontWeight: 600, color: 'var(--txt-sec)', textTransform: 'uppercase', letterSpacing: '0.12em' }}>
                Provider Health
              </div>
              <div>
                {Object.entries(metrics.provider_breakdown).map(([provider, pmetrics], idx) => (
                  <div key={provider}>
                    <div
                      onClick={() => setExpandedProvider(expandedProvider === provider ? null : provider)}
                      style={{
                        padding: '12px 20px',
                        borderTop: idx > 0 ? '1px solid var(--border)' : 'none',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        transition: 'background 0.2s',
                        background: expandedProvider === provider ? 'rgba(255,255,255,0.02)' : 'transparent'
                      }}
                      onMouseOver={(e) => e.currentTarget.style.background = 'rgba(255,255,255,0.02)'}
                      onMouseOut={(e) => e.currentTarget.style.background = expandedProvider === provider ? 'rgba(255,255,255,0.02)' : 'transparent'}
                    >
                      <div style={{ flex: 1 }}>
                        <div style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--txt-pri)' }}>{provider}</div>
                        <div style={{ fontSize: '0.7rem', color: 'var(--txt-mut)', marginTop: 2 }}>
                          {pmetrics.count} responses
                        </div>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                        <div style={{ textAlign: 'right' }}>
                          <div style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--txt-pri)' }}>
                            {(pmetrics.avg_confidence * 100).toFixed(1)}%
                          </div>
                          <div style={{ fontSize: '0.7rem', color: 'var(--txt-mut)' }}>confidence</div>
                        </div>
                      </div>
                    </div>
                    {expandedProvider === provider && (
                      <div style={{ padding: '12px 20px', background: 'rgba(255,255,255,0.02)', borderTop: '1px solid var(--border)', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: 12 }}>
                        <div>
                          <div style={{ fontSize: '0.7rem', color: 'var(--txt-mut)', marginBottom: 4 }}>Avg Contradictions</div>
                          <div style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--txt-pri)' }}>
                            {pmetrics.avg_contradictions.toFixed(2)}
                          </div>
                        </div>
                        <div>
                          <div style={{ fontSize: '0.7rem', color: 'var(--txt-mut)', marginBottom: 4 }}>Avg Citations</div>
                          <div style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--txt-pri)' }}>
                            {pmetrics.avg_citations.toFixed(2)}
                          </div>
                        </div>
                        <div>
                          <div style={{ fontSize: '0.7rem', color: 'var(--txt-mut)', marginBottom: 4 }}>Avg Latency (ms)</div>
                          <div style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--txt-pri)' }}>
                            {pmetrics.avg_latency_ms.toFixed(0)}
                          </div>
                        </div>
                      </div>
                    )}
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
