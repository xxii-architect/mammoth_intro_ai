import { useState } from 'react'
import { api } from '../api/client'

const hidden = new Set(['reasoning_trace', 'trace', 'thought_steps', 'diagnostics'])

export function outputMarkdown(value, level = 2) {
  if (value == null) return ''
  if (Array.isArray(value)) return value.map(item => outputMarkdown(item, level)).filter(Boolean).join('\n\n')
  if (typeof value !== 'object') return String(value)
  return Object.entries(value)
    .filter(([key, child]) => !hidden.has(key) && child != null && child !== '')
    .map(([key, child]) => {
      const text = outputMarkdown(child, Math.min(level + 1, 6))
      return text ? `${'#'.repeat(level)} ${key.replaceAll('_', ' ')}\n\n${text}` : ''
    }).filter(Boolean).join('\n\n')
}

export function downloadOutput(value, title, format) {
  const content = format === 'json' ? JSON.stringify(value, null, 2) : outputMarkdown(value)
  const blob = new Blob([content], { type: format === 'json' ? 'application/json' : 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `${String(title || 'mammoth-output').replace(/[^a-z0-9_-]+/gi, '-').slice(0, 80)}.${format}`
  link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

export default function OutputActions({ output, saved, artifactId, title = 'Agent output', team = false, onSaved }) {
  const [saveState, setSaveState] = useState(null)
  const [busy, setBusy] = useState(false)
  const state = saveState || saved
  async function save() {
    setBusy(true)
    try {
      const res = await api('/workspace/artifacts', { method: 'POST', body: {
        id: state?.artifact_id || artifactId, title, body: outputMarkdown(output), format: 'md',
        snapshot: output, artifact_type: team ? 'team_run' : output?.artifact_type || 'report',
        agent_id: output?.agent || (team ? 'orchestrator' : ''),
        status: output?.plan_status || output?.status, quality: output?.quality || {},
        origin: { page: 'agent', ...(team && output?.plan_id ? { task_id: output.plan_id } : {}) },
      } })
      if (res?.status !== 'ok' || !res.artifact?.id) throw new Error('The server did not confirm the save.')
      const next = { status: 'saved', artifact_id: res.artifact.id }
      setSaveState(next)
      onSaved?.(next)
    } catch (error) {
      setSaveState({ status: 'failed', error: error.message || 'Save failed. Export before leaving this page.' })
    } finally { setBusy(false) }
  }
  return <section aria-label={team ? 'Team result actions' : 'Output actions'} style={{ marginTop: 10 }}>
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
      <button onClick={save} disabled={busy}>{busy ? 'Saving…' : state?.status === 'saved' ? 'Save again' : team ? 'Save entire run' : 'Save output'}</button>
      <button onClick={() => downloadOutput(output, title, 'md')}>Export Markdown</button>
      <button onClick={() => downloadOutput(output, title, 'json')}>Export complete JSON</button>
    </div>
    {state?.status === 'saved' && <p role="status">Saved to your Artifacts. Reopening does not run agents.</p>}
    {state?.status === 'failed' && <p role="alert">{state.error || 'Save failed. Export before leaving this page.'}</p>}
  </section>
}
