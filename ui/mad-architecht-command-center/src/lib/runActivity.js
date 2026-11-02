const TOOL_ACTIVITY = {
  owner_execution_status: 'Checking repository readiness…',
  owner_execution_prepare: 'Preparing exact edits…',
  owner_execution_run: 'Validating in isolation… builds can take a few minutes',
  owner_execution_apply: 'Committing to a new local branch…',
  repo_read_file: 'Reading source…',
  repo_search: 'Searching the repository…',
  repo_list_files: 'Mapping the repository…',
  repo_recall_observation: 'Recalling saved source…',
  repo_propose_patch: 'Saving the proposal…',
  web_search: 'Searching the web…',
  web_fetch: 'Reading a web page…',
}

/** Describe what an unfinished run is doing right now, derived only from recorded events. */
export function describeRunActivity(run, { decisionInFlight = true } = {}) {
  if (!run) return ''
  if (decisionInFlight && run.decision_pending) return run.decision_pending === 'reject' ? 'Sending your rejection…' : 'Approval sent — resuming the run…'
  if (run.status !== 'running') return ''
  const open = new Map()
  for (const event of run.events || []) {
    if (event.type === 'tool.call') open.set(event.data?.call_id, event.data?.tool)
    else if (event.type === 'tool.result') open.delete(event.data?.call_id)
  }
  const tool = [...open.values()].pop()
  if (tool) return TOOL_ACTIVITY[tool] || `Running ${tool}…`
  return 'Considering the next step…'
}
