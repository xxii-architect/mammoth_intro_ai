import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, CheckCircle2, Code2, Copy, GitBranch, ListChecks, FileText, Loader2, Sparkles } from 'lucide-react'

function normalizeList(value) {
  return Array.isArray(value) ? value.map(item => String(item).trim()).filter(Boolean) : []
}

function toArtifactText(artifact) {
  if (!artifact) return ''
  const sections = []
  if (artifact.summary) sections.push(`Summary: ${artifact.summary}`)
  if (artifact.taskKind) sections.push(`Task: ${artifact.taskKind}`)
  if (artifact.target) sections.push(`Target: ${artifact.target}`)
  if (artifact.confidence !== null && artifact.confidence !== undefined) {
    sections.push(`Confidence: ${Math.round(Number(artifact.confidence) * 100)}%`)
  }
  if (artifact.code) sections.push(`\nCode:\n${artifact.code}`)
  if (artifact.tests) sections.push(`\nTests:\n${artifact.tests}`)
  if (artifact.docs) sections.push(`\nDocs:\n${artifact.docs}`)
  if (artifact.diff) sections.push(`\nDiff:\n${artifact.diff}`)
  return sections.join('\n')
}

function TabButton({ active, icon: Icon, label, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        padding: '7px 11px',
        borderRadius: 999,
        border: `1px solid ${active ? 'rgba(77,166,255,0.45)' : 'var(--border)'}`,
        background: active ? 'rgba(77,166,255,0.12)' : 'rgba(255,255,255,0.03)',
        color: active ? 'var(--photon)' : 'var(--txt-sec)',
        fontSize: '0.72rem',
        fontWeight: 700,
        cursor: 'pointer',
      }}
    >
      <Icon size={13} />
      {label}
    </button>
  )
}

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

export default function CodingArtifactPanel({ artifact, rawJson, onApplyPatch, applyingPatch = false }) {
  const [activeTab, setActiveTab] = useState('overview')
  const [copied, setCopied] = useState(false)

  const sections = useMemo(() => {
    if (!artifact) return {}
    const qualityFlags = normalizeList(artifact.qualityFlags)
    const warnings = normalizeList(artifact.warnings)
    const qualityChecks = normalizeList(artifact.qualityChecks)
    return {
      overview: {
        summary: artifact.summary || 'Coding agent returned a structured payload.',
        taskPlan: artifact.taskPlan || null,
        qualityChecks,
        qualityFlags,
        warnings,
      },
      code: artifact.code || '',
      tests: artifact.tests || '',
      docs: artifact.docs || '',
      diff: artifact.diff || '',
      raw: rawJson || JSON.stringify(artifact.raw || artifact, null, 2),
    }
  }, [artifact, rawJson])

  useEffect(() => {
    setActiveTab('overview')
  }, [artifact?.target, artifact?.summary, artifact?.taskKind])

  if (!artifact) return null

  const hasTaskPlan = Boolean(sections.overview.taskPlan)
  const hasCode = Boolean(sections.code)
  const hasTests = Boolean(sections.tests)
  const hasDocs = Boolean(sections.docs)
  const hasDiff = Boolean(sections.diff)
  const canApplyPatch = Boolean(onApplyPatch) && hasCode && Boolean(artifact.target)
  const tabs = [
    { id: 'overview', label: 'Overview', icon: ListChecks, show: true },
    { id: 'code', label: 'Code', icon: Code2, show: hasCode },
    { id: 'tests', label: 'Tests', icon: FileText, show: hasTests },
    { id: 'docs', label: 'Docs', icon: FileText, show: hasDocs },
    { id: 'diff', label: 'Diff', icon: GitBranch, show: hasDiff },
    { id: 'raw', label: 'Raw', icon: FileText, show: true },
  ].filter(tab => tab.show)

  const activeCopyText = activeTab === 'overview'
    ? toArtifactText(artifact)
    : String(sections[activeTab] || '')

  const copyActive = async () => {
    await navigator.clipboard.writeText(activeCopyText || toArtifactText(artifact))
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1200)
  }

  const statusTone = artifact.status === 'ok' ? 'success' : artifact.status === 'warning' ? 'warning' : 'neutral'
  const applyTone = artifact.applied ? 'success' : 'info'

  return (
    <div style={{ display: 'grid', gap: 12 }}>
      <div className="glass-card-solid" style={{ padding: 16, borderLeft: '3px solid var(--photon)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', alignItems: 'flex-start' }}>
          <div style={{ minWidth: 0, flex: '1 1 320px' }}>
            <div style={{ fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.14em', color: 'var(--txt-mut)', marginBottom: 6 }}>
              Coding artifact ready
            </div>
            <div style={{ fontSize: '1rem', fontWeight: 800, color: 'var(--txt-pri)', lineHeight: 1.35 }}>
              {artifact.summary || 'Structured coding response'}
            </div>
            <div style={{ color: 'var(--txt-sec)', fontSize: '0.78rem', marginTop: 6, lineHeight: 1.5, wordBreak: 'break-word' }}>
              {artifact.taskKind || 'generate_code'}{artifact.target ? ` • ${artifact.target}` : ''}{artifact.agent ? ` • ${artifact.agent}` : ''}
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 6 }}>
            <Pill tone={statusTone}>{artifact.status || 'ok'}</Pill>
            {artifact.applied && (
              <Pill tone="success">
                <CheckCircle2 size={12} />
                applied
              </Pill>
            )}
            {artifact.confidence !== null && artifact.confidence !== undefined && (
              <span style={{ fontSize: '0.68rem', color: 'var(--txt-mut)', fontFamily: 'JetBrains Mono,monospace' }}>
                confidence {Math.round(Number(artifact.confidence) * 100)}%
              </span>
            )}
          </div>
        </div>

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 12 }}>
          {artifact.target && <Pill tone="info">target {artifact.target}</Pill>}
          {artifact.diff && <Pill tone="success"><Sparkles size={12} /> patch ready</Pill>}
          {artifact.applyResult?.status === 'ok' && <Pill tone="success">write complete</Pill>}
        </div>

        <div style={{ marginTop: 12, color: 'var(--txt-sec)', fontSize: '0.82rem', lineHeight: 1.65 }}>
          {artifact.summary || 'No summary was returned by the coding runtime.'}
        </div>

        {hasTaskPlan && (
          <div style={{ marginTop: 12, padding: '12px 14px', borderRadius: 12, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)' }}>
            <div style={{ fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-mut)', marginBottom: 8 }}>
              Task plan
            </div>
            <div style={{ display: 'grid', gap: 8 }}>
              <div>
                <div style={{ fontSize: '0.72rem', color: 'var(--txt-mut)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Objective</div>
                <div style={{ fontSize: '0.8rem', color: 'var(--txt-pri)', lineHeight: 1.55 }}>{artifact.taskPlan.objective || 'Not specified'}</div>
              </div>
              {normalizeList(artifact.taskPlan.constraints).length > 0 && (
                <div>
                  <div style={{ fontSize: '0.72rem', color: 'var(--txt-mut)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Constraints</div>
                  <ul style={{ margin: '6px 0 0', paddingLeft: 18, display: 'grid', gap: 4 }}>
                    {normalizeList(artifact.taskPlan.constraints).map(item => (
                      <li key={item} style={{ fontSize: '0.78rem', color: 'var(--txt-sec)', lineHeight: 1.45 }}>{item}</li>
                    ))}
                  </ul>
                </div>
              )}
              {normalizeList(artifact.taskPlan.validation).length > 0 && (
                <div>
                  <div style={{ fontSize: '0.72rem', color: 'var(--txt-mut)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Validation</div>
                  <ul style={{ margin: '6px 0 0', paddingLeft: 18, display: 'grid', gap: 4 }}>
                    {normalizeList(artifact.taskPlan.validation).map(item => (
                      <li key={item} style={{ fontSize: '0.78rem', color: 'var(--txt-sec)', lineHeight: 1.45 }}>{item}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>
        )}

        {(sections.overview.qualityFlags.length > 0 || sections.overview.qualityChecks.length > 0 || sections.overview.warnings.length > 0) && (
          <div style={{ display: 'grid', gap: 10, marginTop: 12 }}>
            {sections.overview.qualityFlags.length > 0 && (
              <div>
                <div style={{ fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-mut)', marginBottom: 6 }}>
                  Quality flags
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {sections.overview.qualityFlags.map(flag => (
                    <Pill key={flag} tone="info">{flag}</Pill>
                  ))}
                </div>
              </div>
            )}

            {sections.overview.qualityChecks.length > 0 && (
              <div>
                <div style={{ fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-mut)', marginBottom: 6 }}>
                  Validation checks
                </div>
                <div style={{ display: 'grid', gap: 6 }}>
                  {sections.overview.qualityChecks.map(check => (
                    <div key={check} style={{ padding: '9px 11px', borderRadius: 10, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)', color: 'var(--txt-sec)', fontSize: '0.76rem', lineHeight: 1.45 }}>
                      {check}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {sections.overview.warnings.length > 0 && (
              <div>
                <div style={{ fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-mut)', marginBottom: 6 }}>
                  Warnings
                </div>
                <div style={{ display: 'grid', gap: 6 }}>
                  {sections.overview.warnings.map(warning => (
                    <div key={warning} style={{ padding: '9px 11px', borderRadius: 10, border: '1px solid rgba(245,158,11,0.22)', background: 'rgba(245,158,11,0.06)', color: '#fbbf24', fontSize: '0.76rem', lineHeight: 1.45, display: 'flex', gap: 8, alignItems: 'flex-start' }}>
                      <AlertTriangle size={14} style={{ flexShrink: 0, marginTop: 2 }} />
                      <span>{warning}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      <div className="glass-card-solid" style={{ padding: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', alignItems: 'center', marginBottom: 10 }}>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {tabs.map(tab => (
              <TabButton
                key={tab.id}
                active={activeTab === tab.id}
                icon={tab.icon}
                label={tab.label}
                onClick={() => setActiveTab(tab.id)}
              />
            ))}
          </div>

          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {canApplyPatch && (
              <button
                type="button"
                onClick={onApplyPatch}
                disabled={applyingPatch}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 6,
                  padding: '7px 12px',
                  borderRadius: 8,
                  border: '1px solid rgba(34,197,94,0.25)',
                  background: applyingPatch ? 'rgba(34,197,94,0.12)' : 'rgba(34,197,94,0.18)',
                  color: '#86efac',
                  fontSize: '0.75rem',
                  fontWeight: 700,
                  cursor: applyingPatch ? 'not-allowed' : 'pointer',
                }}
              >
                {applyingPatch ? <Loader2 size={13} style={{ animation: 'spin 1s linear infinite' }} /> : <CheckCircle2 size={13} />}
                {applyingPatch ? 'Applying…' : 'Apply patch'}
              </button>
            )}

            <button
              type="button"
              onClick={copyActive}
              style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '7px 12px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.04)', color: 'var(--txt-sec)', fontSize: '0.75rem', cursor: 'pointer' }}
            >
              <Copy size={13} />
              {copied ? 'Copied' : `Copy ${activeTab}`}
            </button>
          </div>
        </div>

        {artifact.applyResult?.status === 'ok' && (
          <div style={{ marginBottom: 12, padding: '10px 12px', borderRadius: 10, border: '1px solid rgba(34,197,94,0.2)', background: 'rgba(34,197,94,0.06)', color: '#86efac', fontSize: '0.78rem', lineHeight: 1.5 }}>
            Patch applied to <strong>{artifact.applyResult.result?.path || artifact.target || 'target file'}</strong>.
          </div>
        )}

        {activeTab === 'overview' ? (
          <div style={{ color: 'var(--txt-sec)', fontSize: '0.82rem', lineHeight: 1.7 }}>
            <div style={{ marginBottom: 8 }}>
              {artifact.code ? 'Code, tests, docs, and diff are available in the tabs below.' : 'The agent did not return a code block. Try patch_existing with a concrete target file.'}
            </div>
            {artifact.evidence && (
              <div style={{ padding: '10px 12px', borderRadius: 10, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)' }}>
                <div style={{ fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-mut)', marginBottom: 6 }}>Evidence</div>
                <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontFamily: 'JetBrains Mono,monospace', fontSize: '0.72rem', lineHeight: 1.6, color: 'var(--txt-pri)' }}>
                  {JSON.stringify(artifact.evidence, null, 2)}
                </pre>
              </div>
            )}
          </div>
        ) : (
          <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontFamily: 'JetBrains Mono,monospace', fontSize: '0.76rem', lineHeight: 1.7, color: 'var(--txt-pri)', maxHeight: 420, overflowY: 'auto', padding: '2px 0' }}>
            {(sections[activeTab] || 'No content available for this tab.').trim()}
          </pre>
        )}
      </div>
    </div>
  )
}
