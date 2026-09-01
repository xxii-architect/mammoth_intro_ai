import { useState, useEffect } from 'react'
import { Bot, Play, Info, ChevronRight, Brain, CheckCircle, AlertTriangle, XCircle, Loader } from 'lucide-react'
import { api } from '../api/client'
import RunHistoryPanel from '../components/RunHistoryPanel'
import AutonomousRunPanel from '../components/AutonomousRunPanel'
import OnboardingGuide from '../components/OnboardingGuide'
import CodingArtifactPanel from '../components/CodingArtifactPanel'
import ResearchArtifactPanel from '../components/ResearchArtifactPanel'
import WorkspaceMemoryPanel from '../components/WorkspaceMemoryPanel'
import PlanExecuteResultPanel from '../components/PlanExecuteResultPanel'
import AgentResultPanel from '../components/AgentResultPanel'
import MammothEmpty from '../components/MammothEmpty'

const INTENTS = [
  'plant_seed', 'field_ops', 'market_intel', 'reflection', 'brand_voice',
  'research_curriculum', 'research_survival', 'research_plants', 'compare_gear', 'browse_web', 'summarize',
  'lesson_curriculum', 'lesson_coaching', 'grade_submission',
  'generate_code', 'patch_existing', 'refactor_code', 'analyze_codebase', 'run_tests', 'write_docs',
]

const INTENT_TO_AGENT = {
  plant_seed:          'plant_the_seed_agent',
  field_ops:           'field_ops_agent',
  market_intel:        'market_intel_agent',
  reflection:          'reflection_agent',
  brand_voice:         'brand_voice_agent',
  research_curriculum: 'research_agent',
  research_survival:   'research_agent',
  research_plants:     'research_agent',
  compare_gear:        'research_agent',
  browse_web:          'browser_agent',
  summarize:           'research_agent',
  lesson_curriculum:   'curriculum_agent',
  lesson_coaching:     'tutor_agent',
  grade_submission:    'tutor_agent',
  generate_code:       'coding_agent',
  patch_existing:      'coding_agent',
  refactor_code:       'coding_agent',
  analyze_codebase:    'coding_agent',
  run_tests:           'coding_agent',
  write_docs:          'coding_agent',
}

const AGENT_TO_INTENT = {
  plant_the_seed_agent: 'plant_seed',
  field_ops_agent:      'field_ops',
  market_intel_agent:   'market_intel',
  reflection_agent:     'reflection',
  brand_voice_agent:    'brand_voice',
  research_agent:       'research_curriculum',
  browser_agent:        'browse_web',
  curriculum_agent:     'lesson_curriculum',
  tutor_agent:          'lesson_coaching',
  coding_agent:         'generate_code',
  community_engine_agent: 'summarize',
  custodial_agent:      'summarize',
}

const CODING_INTENT_OPTIONS = [
  { value: 'generate_code', label: 'Generate Code' },
  { value: 'patch_existing', label: 'Patch Existing Files' },
  { value: 'refactor_code', label: 'Refactor Code' },
  { value: 'analyze_codebase', label: 'Analyze Codebase' },
  { value: 'run_tests', label: 'Run Test Guidance' },
  { value: 'write_docs', label: 'Write Docs' },
  { value: 'summarize', label: 'Implementation Brief' },
]

const SMOKE_TESTS = [
  { agent_id: 'plant_the_seed_agent', intent: 'plant_seed', prompt: 'Smoke test: confirm plant seed agent is online in one sentence.' },
  { agent_id: 'field_ops_agent', intent: 'field_ops', prompt: 'Smoke test: return a one-line field operation checklist.' },
  { agent_id: 'market_intel_agent', intent: 'market_intel', prompt: 'Smoke test: provide one market signal in one sentence.' },
  { agent_id: 'reflection_agent', intent: 'reflection', prompt: 'Smoke test: provide a one-sentence reflection prompt.' },
  { agent_id: 'brand_voice_agent', intent: 'brand_voice', prompt: 'Smoke test: provide one sentence in brand voice.' },
  { agent_id: 'research_agent', intent: 'research_curriculum', prompt: 'Smoke test: summarize one curriculum tip in one sentence.' },
  { agent_id: 'browser_agent', intent: 'browse_web', prompt: 'Smoke test: snapshot https://example.com and report the page title.' },
  { agent_id: 'curriculum_agent', intent: 'lesson_curriculum', prompt: 'Smoke test: provide one sentence on lesson framing.' },
  { agent_id: 'tutor_agent', intent: 'lesson_coaching', prompt: 'Smoke test: provide one coaching checkpoint.' },
  { agent_id: 'coding_agent', intent: 'generate_code', prompt: 'Smoke test: respond with one sentence confirming coding agent availability.' },
]

const PROMPT_PLAYBOOK = [
  {
    label: 'Quick one-liner',
    agent_id: 'coding_agent',
    intent: 'generate_code',
    codingIntent: 'generate_code',
    prompt: 'Upgrade NotesPanel to MammothOS style with neon accents and approval-safe edits.',
  },
  {
    label: 'Scoped build prompt',
    agent_id: 'coding_agent',
    intent: 'patch_existing',
    codingIntent: 'patch_existing',
    prompt: 'Create a user tutorial panel for the command center. Scope: ui\mad-architecht-command-center\src. Keep preview first on and preserve existing navigation.',
  },
  {
    label: 'Browser snapshot',
    agent_id: 'browser_agent',
    intent: 'browse_web',
    prompt: 'Snapshot https://example.com and summarize the title, headings, and links.',
  },
  {
    label: 'Plan + Execute objective',
    planProfile: 'atlas',
    codingIntent: 'summarize',
    executionMode: 'plan',
    prompt: 'Plan and implement an onboarding/manual experience for agent prompting, terminal usage, and safe approvals.',
  },
  {
    label: 'Health module split test',
    planProfile: 'coding',
    codingIntent: 'patch_existing',
    executionMode: 'plan',
    prompt: 'Plan and implement Health page split: keep existing System Health, add Personal Health module with habit metrics and daily check-in. Scope: ui\mad-architecht-command-center\src\pages\HealthPage.jsx and related UI components only. Preserve existing backend health wiring and dark theme.',
  },
  {
    label: 'Finance split test',
    planProfile: 'coding',
    codingIntent: 'patch_existing',
    executionMode: 'plan',
    prompt: 'Plan and implement Log Sale page split: Personal Finances and Business Finances sections with separate totals and entries. Scope: ui\mad-architecht-command-center\src\pages\LogSalePage.jsx and related local UI state only. Keep existing styling and current behavior intact.',
  },
]

function normalizeResearchArtifact(runResult) {
  if (!runResult || typeof runResult !== 'object') return null
  let output = runResult?.result?.output ?? runResult?.output ?? null
  if (typeof output === 'string') {
    try { output = JSON.parse(output) } catch { output = null }
  }
  if (!output || typeof output !== 'object' || Array.isArray(output)) return null
  if (!Array.isArray(output.citations) && !Array.isArray(output.sources) && !Array.isArray(output.references)) return null
  const normalizeList = (value) => (Array.isArray(value) ? value.map(item => String(item).trim()).filter(Boolean) : [])
  return {
    status: String(output.status || runResult.status || 'ok'),
    agent: String(output.agent || runResult.agent || 'ResearchAgent'),
    mode: String(output.mode || runResult.mode || 'research'),
    prompt: String(output.prompt || runResult.prompt || ''),
    focus: String(output.focus || ''),
    summary: String(output.summary || ''),
    findings: Array.isArray(output.findings) ? output.findings : [],
    citations: Array.isArray(output.citations) ? output.citations : [],
    references: Array.isArray(output.references) ? output.references : [],
    sources: Array.isArray(output.sources) ? output.sources : [],
    sourceCoverage: output.source_coverage && typeof output.source_coverage === 'object' ? output.source_coverage : null,
    qualityFlags: normalizeList(output.quality_flags),
    retrievalErrors: normalizeList(output.retrieval_errors),
    workflowHints: output.workflow_hints && typeof output.workflow_hints === 'object' ? output.workflow_hints : null,
    confidence: typeof output.confidence === 'number' ? output.confidence : null,
    raw: output,
  }
}

function normalizeCodingArtifact(runResult) {
  if (!runResult || typeof runResult !== 'object') return null
  let output = runResult?.result?.output ?? runResult?.output ?? null
  if (typeof output === 'string') {
    try { output = JSON.parse(output) } catch { output = null }
  }
  if (!output || typeof output !== 'object' || Array.isArray(output)) return null
  const normalizeList = (value) => (Array.isArray(value) ? value.map(item => String(item).trim()).filter(Boolean) : [])
  const taskPlan = output.task_plan && typeof output.task_plan === 'object' ? output.task_plan : null
  return {
    status: String(output.status || runResult.status || 'ok'),
    agent: String(output.agent || runResult.agent || 'CodingAgent'),
    mode: String(output.mode || runResult.mode || 'coding'),
    taskKind: String(output.task_kind || runResult.task_kind || runResult.intent || 'generate_code'),
    target: String(output.target || runResult.target || ''),
    prompt: String(output.prompt || runResult.prompt || ''),
    summary: String(output.summary || ''),
    code: String(output.code || ''),
    tests: String(output.tests || ''),
    docs: String(output.docs || ''),
    diff: String(output.diff || ''),
    confidence: typeof output.confidence === 'number' ? output.confidence : null,
    warnings: normalizeList(output.warnings),
    qualityChecks: normalizeList(output.quality_checks),
    qualityFlags: normalizeList(output.quality_flags),
    taskPlan,
    evidence: output.evidence && typeof output.evidence === 'object' ? output.evidence : null,
    raw: output,
  }
}

export default function AgentPage({ setPage }) {
  const [agents, setAgents] = useState([])
  const [selectedAgent, setSelected] = useState('')
  const [intent, setIntent] = useState('plant_seed')
  const [prompt, setPrompt] = useState('')
  const [temperature, setTemp] = useState(0.7)
  const [output, setOutput] = useState(null)
  const [running, setRunning] = useState(false)
  const [archOpen, setArchOpen] = useState(false)
  const [activity, setActivity] = useState([])
  const [tasks, setTasks] = useState([])
  const [approvals, setApprovals] = useState([])
  const [snapshots, setSnapshots] = useState([])
  const [agentPinned, setAgentPinned] = useState(false)
  const [approvalMode, setApprovalMode] = useState(true)
  const [thoughtSteps, setThoughtSteps] = useState([])
  const [traceOpen, setTraceOpen] = useState(true)
  const [runHistory, setRunHistory] = useState(() => {
    try {
      const raw = localStorage.getItem('mammoth_run_history')
      return raw ? JSON.parse(raw) : []
    } catch { return [] }
  })
  const [smokeRunning, setSmokeRunning] = useState(false)
  const [smokeResults, setSmokeResults] = useState([])
  const [executionMode, setExecutionMode] = useState('single')
  const [planProfile, setPlanProfile] = useState('atlas')
  const [codingIntent, setCodingIntent] = useState('generate_code')
  const [planRun, setPlanRun] = useState(null)
  const [autonomousRuns, setAutonomousRuns] = useState({ summary: null, runs: [] })
  const [codingArtifact, setCodingArtifact] = useState(null)
  const [researchArtifact, setResearchArtifact] = useState(null)
  const [applyingPatch, setApplyingPatch] = useState(false)
  const [lastRunResult, setLastRunResult] = useState(null)
  const [lastRunMode, setLastRunMode] = useState('single')

  const refreshAgents = async () => {
    try {
      const a = await api('/agents')
      setAgents(a)
      if ((!selectedAgent || !a.some(x => x.id === selectedAgent)) && a.length) {
        const mapped = INTENT_TO_AGENT[intent]
        const match = mapped ? a.find(x => x.id === mapped) : null
        setSelected(match ? match.id : a[0].id)
      }
    } catch (_) {}
  }

  const refreshTimeline = async () => {
    try {
      const [feed, taskList] = await Promise.all([api('/activity'), api('/tasks')])
      setActivity((feed || []).slice(-8).reverse())
      setTasks((taskList || []).slice(-8).reverse())
    } catch (_) {}
  }

  const refreshApprovals = async () => {
    try {
      const list = await api('/approvals')
      setApprovals(list || [])
    } catch (_) {}
  }

  const refreshSnapshots = async () => {
    try {
      const list = await api('/snapshots')
      setSnapshots(list || [])
    } catch (_) {}
  }

  const refreshAutonomousRuns = async () => {
    try {
      const data = await api('/autonomous/runs')
      setAutonomousRuns({
        summary: data?.summary || null,
        runs: Array.isArray(data?.runs) ? data.runs : [],
      })
    } catch (_) {}
  }

  const approveApproval = async (approvalId) => {
    try {
      await api(`/approvals/${approvalId}/approve`, { method: 'POST' })
      await refreshApprovals()
      await refreshTimeline()
      await refreshSnapshots()
    } catch (_) {}
  }

  const deleteApproval = async (approvalId) => {
    try {
      await api(`/approvals/${approvalId}`, { method: 'DELETE' })
      await refreshApprovals()
      await refreshTimeline()
    } catch (_) {}
  }

  const restoreSnapshot = async (snapshotId) => {
    try {
      await api(`/snapshots/${snapshotId}/restore`, { method: 'POST' })
      await Promise.all([refreshSnapshots(), refreshTimeline()])
    } catch (_) {}
  }

  useEffect(() => {
    refreshAgents()
    refreshTimeline()
    refreshApprovals()
    refreshSnapshots()
    refreshAutonomousRuns()
    const t = setInterval(() => {
      refreshAgents()
      refreshTimeline()
      refreshApprovals()
      refreshSnapshots()
      refreshAutonomousRuns()
    }, 2200)
    return () => clearInterval(t)
  }, [selectedAgent, intent, agentPinned])

  const chooseIntent = (i) => {
    setIntent(i)
    setAgentPinned(false)
    const mapped = INTENT_TO_AGENT[i]
    if (INTENT_TO_AGENT[i] === 'coding_agent') setCodingIntent(i)
    if (mapped) setSelected(mapped)
  }

  const chooseAgent = (agentId) => {
    setAgentPinned(true)
    setSelected(agentId)
    const mappedIntent = AGENT_TO_INTENT[agentId]
    if (mappedIntent) {
      setIntent(mappedIntent)
      if (agentId === 'coding_agent') setCodingIntent(mappedIntent)
    }
  }

  const loadCodingTemplate = (template) => {
    setSelected('coding_agent')
    setIntent('generate_code')
    setCodingIntent('generate_code')
    setAgentPinned(true)
    setApprovalMode(true)
    setCodingArtifact(null)
    setResearchArtifact(null)
    setOutput(null)
    setPrompt(template)
  }

  const loadPromptPlaybookEntry = (entry) => {
    if (entry.executionMode === 'plan') {
      setExecutionMode('plan')
      setPlanProfile(entry.planProfile || 'atlas')
      setCodingIntent(entry.codingIntent || 'generate_code')
    } else {
      setExecutionMode('single')
      if (entry.agent_id) chooseAgent(entry.agent_id)
      if (entry.intent) chooseIntent(entry.intent)
      if (entry.codingIntent) setCodingIntent(entry.codingIntent)
    }
    setApprovalMode(true)
    setCodingArtifact(null)
    setResearchArtifact(null)
    setOutput(null)
    setPrompt(entry.prompt)
  }

  const persistRunHistory = (entries) => {
    setRunHistory(entries)
    localStorage.setItem('mammoth_run_history', JSON.stringify(entries))
  }

  const addRunHistoryEntry = (res, currentPrompt, currentAgent, currentIntent, extras = {}) => {
    const entry = {
      id: `${Date.now()}-${Math.random().toString(16).slice(2, 8)}`,
      created_at: new Date().toISOString(),
      agent_id: currentAgent,
      intent: currentIntent,
      prompt: currentPrompt,
      status: res?.status || 'unknown',
      task_id: res?.task_id || null,
      trace_id: res?.trace_id || null,
      runtime_adapter: res?.adapter || null,
      runtime_model: res?.model || null,
      ...extras,
    }
    setRunHistory(prev => {
      const next = [...prev, entry].slice(-20)
      localStorage.setItem('mammoth_run_history', JSON.stringify(next))
      return next
    })
  }

  const replayHistoryEntry = (entry) => {
    if (!entry) return
    if (entry.execution_mode === 'plan' || String(entry.intent || '').startsWith('plan_execute')) {
      setExecutionMode('plan')
      if (entry.plan_profile) setPlanProfile(entry.plan_profile)
      if (entry.coding_intent) setCodingIntent(entry.coding_intent)
    } else {
      setExecutionMode('single')
      if (entry.agent_id) chooseAgent(entry.agent_id)
      if (entry.intent) chooseIntent(entry.intent)
      if (entry.coding_intent) setCodingIntent(entry.coding_intent)
    }
    setPrompt(entry.prompt || '')
    setCodingArtifact(entry.coding_artifact || null)
    setResearchArtifact(entry.research_artifact || null)
  }

  const replayAutonomousRun = (run) => {
    if (!run) return
    setExecutionMode('plan')
    setPlanProfile(run.plan_profile || 'atlas')
    setCodingIntent(run.coding_intent || 'summarize')
    setApprovalMode(Boolean(run.replay?.approval_mode ?? run.plan_status === 'pending_approval'))
    setPrompt(run.objective || '')
  }

  const clearRunHistory = () => {
    setCodingArtifact(null)
    setResearchArtifact(null)
    persistRunHistory([])
  }

  const run = async () => {
    if (!prompt.trim() && !intent) return
    setRunning(true)
    setOutput(null)
    setCodingArtifact(null)
    setResearchArtifact(null)
    setLastRunResult(null)
    setLastRunMode('single')
    await refreshAgents()
    try {
      const res = await api('/run', {
        method: 'POST',
        body: { intent, payload: { prompt, coding_intent: selectedAgent === 'coding_agent' ? codingIntent : undefined }, temperature, agent_id: selectedAgent, approval_mode: approvalMode },
      })
      const artifact = normalizeCodingArtifact(res)
      const research = normalizeResearchArtifact(res)
      setCodingArtifact(artifact)
      setResearchArtifact(research)
      if (res.thought_steps && res.thought_steps.length) setThoughtSteps(res.thought_steps)
      addRunHistoryEntry(res, prompt, selectedAgent, intent, {
        execution_mode: 'single',
        coding_intent: selectedAgent === 'coding_agent' ? codingIntent : null,
        coding_artifact: artifact,
        research_artifact: research,
        replay: {
          execution_mode: 'single',
          prompt,
          agent_id: selectedAgent,
          intent,
          coding_intent: selectedAgent === 'coding_agent' ? codingIntent : null,
        },
      })
      setLastRunResult(res)
      setLastRunMode('single')
      setOutput(JSON.stringify(res, null, 2))
    } catch (e) {
      setThoughtSteps([{ ts: new Date().toISOString(), label: 'Request failed', detail: e.message, status: 'error' }])
      setLastRunResult(null)
      setLastRunMode('single')
      setOutput(`Error: ${e.message}`)
      setCodingArtifact(null)
      setResearchArtifact(null)
    } finally {
      setRunning(false)
      await Promise.all([refreshAgents(), refreshTimeline(), refreshApprovals(), refreshSnapshots(), refreshAutonomousRuns()])
    }
  }

  const runPlanExecute = async () => {
    if (!prompt.trim()) return
    setRunning(true)
    setOutput(null)
    setCodingArtifact(null)
    setResearchArtifact(null)
    setLastRunResult(null)
    setLastRunMode('plan')
    setPlanRun({
      status: 'ok',
      objective: prompt,
      plan_profile: planProfile,
      coding_intent: codingIntent,
      plan_status: 'running',
      progress: { total: 0, executed: 0, completed: 0, pending_approval: 0, failed: 0 },
      plan_steps: [],
    })

    try {
      const res = await api('/plan-execute', {
        method: 'POST',
        body: { objective: prompt, temperature, approval_mode: approvalMode, stop_on_failure: true, plan_profile: planProfile, coding_intent: codingIntent },
      })
      const artifact = normalizeCodingArtifact(res)
      const research = normalizeResearchArtifact(res)
      setCodingArtifact(artifact)
      setResearchArtifact(research)
      setPlanRun({ ...res, plan_profile: res.plan_profile || planProfile, coding_intent: res.coding_intent || codingIntent })
      addRunHistoryEntry(res, prompt, 'orchestrator', 'plan_execute', {
        execution_mode: 'plan',
        plan_profile: res.plan_profile || planProfile,
        coding_intent: res.coding_intent || codingIntent,
        coding_artifact: artifact,
        research_artifact: research,
        replay: {
          execution_mode: 'plan',
          objective: prompt,
          plan_profile: res.plan_profile || planProfile,
          coding_intent: res.coding_intent || codingIntent,
          approval_mode: approvalMode,
        },
      })
      setLastRunResult(res)
      setLastRunMode('plan')
      setOutput(JSON.stringify(res, null, 2))
      const summarizedThoughts = (res.plan_steps || []).map((step, idx) => ({
        ts: step.finished_at || new Date().toISOString(),
        label: `Plan step ${idx + 1}: ${step.title}`,
        detail: `${step.agent_id} • ${step.status} • ${step.duration_ms || 0}ms`,
        status: step.status === 'completed' ? 'success' : step.status === 'pending_approval' ? 'warning' : 'error',
      }))
      setThoughtSteps(summarizedThoughts)
    } catch (e) {
      setPlanRun({
        status: 'error',
        objective: prompt,
        plan_profile: planProfile,
        coding_intent: codingIntent,
        plan_status: 'failed',
        progress: { total: 0, executed: 0, completed: 0, pending_approval: 0, failed: 1 },
        plan_steps: [],
        error: e.message,
      })
      setLastRunResult(null)
      setLastRunMode('plan')
      setThoughtSteps([{ ts: new Date().toISOString(), label: 'Plan run failed', detail: e.message, status: 'error' }])
      setOutput(`Error: ${e.message}`)
      setCodingArtifact(null)
      setResearchArtifact(null)
    } finally {
      setRunning(false)
      await Promise.all([refreshAgents(), refreshTimeline(), refreshApprovals(), refreshSnapshots(), refreshAutonomousRuns()])
    }
  }

  const runSmokeTests = async () => {
    if (smokeRunning || running) return
    setSmokeRunning(true)
    setSmokeResults([])
    const collected = []

    for (const spec of SMOKE_TESTS) {
      const startedAt = performance.now()
      try {
        const res = await api('/run', {
          method: 'POST',
          body: {
            intent: spec.intent,
            payload: { prompt: spec.prompt },
            temperature: 0.2,
            agent_id: spec.agent_id,
            approval_mode: false,
          },
        })
        const elapsedMs = Math.round(performance.now() - startedAt)
        const nestedStatus = res?.result?.status || ''
        const pass = res?.status === 'ok' && nestedStatus !== 'error'
        const rawPreview = res?.result?.output ?? res?.result?.preview ?? res?.error ?? ''
        const preview = typeof rawPreview === 'string' ? rawPreview : JSON.stringify(rawPreview)
        const item = {
          id: `${spec.agent_id}-${Date.now()}`,
          agent_id: spec.agent_id,
          intent: spec.intent,
          status: pass ? 'pass' : 'fail',
          runtime_status: nestedStatus || res?.status || 'unknown',
          duration_ms: elapsedMs,
          preview: preview.slice(0, 140),
        }
        collected.push(item)
        setSmokeResults([...collected])
      } catch (e) {
        const elapsedMs = Math.round(performance.now() - startedAt)
        const item = {
          id: `${spec.agent_id}-${Date.now()}`,
          agent_id: spec.agent_id,
          intent: spec.intent,
          status: 'fail',
          runtime_status: 'request_error',
          duration_ms: elapsedMs,
          preview: (e?.message || 'Request failed').slice(0, 140),
        }
        collected.push(item)
        setSmokeResults([...collected])
      }
    }

    setSmokeRunning(false)
    await Promise.all([refreshAgents(), refreshTimeline()])
  }

  const runPrimary = () => executionMode === 'plan' ? runPlanExecute() : run()
  const planProgressPercent = planRun?.progress?.total
    ? Math.round(((planRun.progress.completed || 0) / planRun.progress.total) * 100)
    : 0

  const applyCodingArtifactPatch = async () => {
    if (!codingArtifact?.target || !codingArtifact?.code || applyingPatch) return
    setApplyingPatch(true)
    try {
      const result = await api('/atlas/apply', {
        method: 'POST',
        body: {
          operation: 'apply_patch',
          file_path: codingArtifact.target,
          new_content: codingArtifact.code,
          approval_mode: false,
        },
      })
      const nextArtifact = {
        ...codingArtifact,
        applied: true,
        applyResult: result,
      }
      setCodingArtifact(nextArtifact)
      setRunHistory(prev => {
        const next = [...prev]
        for (let i = next.length - 1; i >= 0; i -= 1) {
          if (next[i]?.coding_artifact?.target !== codingArtifact.target) continue
          next[i] = {
            ...next[i],
            coding_artifact: {
              ...next[i].coding_artifact,
              applied: true,
              applyResult: result,
            },
          }
          break
        }
        localStorage.setItem('mammoth_run_history', JSON.stringify(next))
        return next
      })
      setOutput(JSON.stringify(result, null, 2))
      setThoughtSteps(prev => [
        ...prev,
        {
          ts: new Date().toISOString(),
          label: 'Patch applied',
          detail: `${codingArtifact.target} updated through /api/atlas/apply`,
          status: 'success',
        },
      ])
      await Promise.all([refreshTimeline(), refreshSnapshots(), refreshApprovals()])
    } catch (e) {
      setThoughtSteps(prev => [
        ...prev,
        {
          ts: new Date().toISOString(),
          label: 'Patch apply failed',
          detail: e.message,
          status: 'error',
        },
      ])
      setOutput(`Apply error: ${e.message}`)
    } finally {
      setApplyingPatch(false)
    }
  }

  return (
    <div className="page-enter" style={{ padding: 24 }}>
      <h1 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: 20, display: 'flex', alignItems: 'center', gap: 8 }}>
        <Bot size={20} color="var(--violet)" /> Agent Console
      </h1>

      <OnboardingGuide variant="banner" currentPage="agent" setPage={setPage} />

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16 }}>
        <div style={{ flex: '1 1 420px', minWidth: 0 }}>
          <div className="glass-card-solid" style={{ padding: 16, marginBottom: 16 }}>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, marginBottom: 12, alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <label style={{ fontSize: '0.7rem', color: 'var(--txt-mut)', textTransform: 'uppercase', letterSpacing: '0.12em' }}>Agent</label>
                <select className="filter-select" value={selectedAgent} onChange={e => chooseAgent(e.target.value)} style={{ padding: '6px 10px', fontSize: '0.82rem' }}>
                  {agents.length ? agents.map(a => (
                    <option key={a.id} value={a.id}>{a.name} ({(running && a.id === selectedAgent) || a.status === 'ACTIVE' ? 'ACTIVE' : a.status})</option>
                  )) : <option>Loading agents…</option>}
                </select>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <label style={{ fontSize: '0.7rem', color: 'var(--txt-mut)', textTransform: 'uppercase', letterSpacing: '0.12em' }}>Temp</label>
                <input type="range" min="0" max="1" step="0.1" value={temperature}
                  onChange={e => setTemp(parseFloat(e.target.value))}
                  style={{ width: 80, accentColor: 'var(--photon)' }} />
                <span style={{ fontSize: '0.72rem', fontFamily: 'JetBrains Mono,monospace', color: 'var(--photon)' }}>{temperature.toFixed(1)}</span>
              </div>
              <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.72rem', color: 'var(--txt-sec)' }}>
                <input type="checkbox" checked={approvalMode} onChange={e => setApprovalMode(e.target.checked)} />
                Preview first
              </label>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <label style={{ fontSize: '0.7rem', color: 'var(--txt-mut)', textTransform: 'uppercase', letterSpacing: '0.12em' }}>Mode</label>
                <select className="filter-select" value={executionMode} onChange={e => setExecutionMode(e.target.value)} style={{ padding: '6px 10px', fontSize: '0.78rem' }}>
                  <option value="single">Single Agent</option>
                  <option value="plan">Plan + Execute</option>
                </select>
              </div>
              {executionMode === 'plan' && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <label style={{ fontSize: '0.7rem', color: 'var(--txt-mut)', textTransform: 'uppercase', letterSpacing: '0.12em' }}>Plan Profile</label>
                  <select className="filter-select" value={planProfile} onChange={e => setPlanProfile(e.target.value)} style={{ padding: '6px 10px', fontSize: '0.78rem' }}>
                    <option value="atlas">ATLAS-First</option>
                    <option value="coding">ATLAS + Coding Assistant</option>
                    <option value="coding_only">Coding Agent Only</option>
                    <option value="balanced">Balanced</option>
                    <option value="autonomous">Autonomous Prep</option>
                  </select>
                </div>
              )}
              {((executionMode === 'single' && selectedAgent === 'coding_agent') || executionMode === 'plan') && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <label style={{ fontSize: '0.7rem', color: 'var(--txt-mut)', textTransform: 'uppercase', letterSpacing: '0.12em' }}>Coding Intent</label>
                  <select className="filter-select" value={codingIntent} onChange={e => { setCodingIntent(e.target.value); if (executionMode === 'single') setIntent(e.target.value) }} style={{ padding: '6px 10px', fontSize: '0.78rem' }}>
                    {CODING_INTENT_OPTIONS.map(option => (
                      <option key={option.value} value={option.value}>{option.label}</option>
                    ))}
                  </select>
                </div>
              )}
            </div>

            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 10 }}>
              {INTENTS.map(i => (
                <span key={i} onClick={() => chooseIntent(i)}
                  style={{
                    fontSize: '0.72rem', fontFamily: 'JetBrains Mono,monospace',
                    padding: '4px 10px', borderRadius: 20, cursor: 'pointer',
                    border: `1px solid ${intent === i ? 'var(--photon)' : 'var(--border)'}`,
                    background: intent === i ? 'rgba(77,166,255,0.12)' : 'rgba(255,255,255,0.04)',
                    color: intent === i ? 'var(--photon)' : 'var(--txt-sec)',
                  }}>
                  {i}
                </span>
              ))}
            </div>

            <div className="glass-card-solid" style={{ padding: 12, marginBottom: 12, borderLeft: '2px solid var(--violet)' }}>
              <p style={{ fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-sec)', marginBottom: 8 }}>Prompt guide</p>
              <div style={{ color: 'var(--txt-sec)', fontSize: '0.78rem', lineHeight: 1.7, marginBottom: 10 }}>
                Short prompts are fine. Best results usually include: <strong style={{ color: 'var(--txt-pri)' }}>outcome</strong>, <strong style={{ color: 'var(--txt-pri)' }}>scope/files</strong>, and <strong style={{ color: 'var(--txt-pri)' }}>constraints</strong>.
                For bigger work, switch to <strong style={{ color: 'var(--txt-pri)' }}>Plan + Execute</strong>.
              </div>
              <div style={{ color: 'var(--txt-mut)', fontSize: '0.72rem', lineHeight: 1.6, marginBottom: 10 }}>
                New: use <strong style={{ color: 'var(--txt-pri)' }}>Health module split test</strong> and <strong style={{ color: 'var(--txt-pri)' }}>Finance split test</strong> templates to task agents with your next module integrations.
              </div>
              <div style={{ color: 'var(--txt-mut)', fontSize: '0.72rem', lineHeight: 1.6, marginBottom: 10 }}>
                For coding work, prefer <strong style={{ color: 'var(--txt-pri)' }}>Coding Intent</strong> = <strong style={{ color: 'var(--txt-pri)' }}>Patch Existing Files</strong> or <strong style={{ color: 'var(--txt-pri)' }}>Generate Code</strong> instead of the summarize-style brief.
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {PROMPT_PLAYBOOK.map((entry) => (
                  <button
                    key={entry.label}
                    onClick={() => loadPromptPlaybookEntry(entry)}
                    style={{ fontSize: '0.72rem', padding: '6px 10px', borderRadius: 6, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.04)', color: 'var(--txt-pri)', cursor: 'pointer' }}
                  >
                    {entry.label}
                  </button>
                ))}
              </div>
            </div>

            <textarea value={prompt} onChange={e => setPrompt(e.target.value)}
              placeholder="Start with one sentence, then add scope or constraints if needed…"
              style={{ width: '100%', background: 'rgba(255,255,255,0.04)', border: '1px solid var(--border)', borderRadius: 8, padding: 12, fontSize: '0.85rem', fontFamily: 'JetBrains Mono,monospace', color: 'var(--txt-pri)', resize: 'none', height: 80, boxSizing: 'border-box', marginBottom: 12 }}
            />

            {selectedAgent === 'coding_agent' && (
              <div className="glass-card-solid" style={{ padding: 12, marginBottom: 12, borderLeft: '2px solid var(--cyan)' }}>
                <p style={{ fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-sec)', marginBottom: 8 }}>Coding Shortcuts</p>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  <button onClick={() => loadCodingTemplate('/create src/demo.txt\nHello from MammothOS')}
                    style={{ fontSize: '0.72rem', padding: '6px 10px', borderRadius: 6, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.04)', color: 'var(--txt-pri)', cursor: 'pointer' }}>
                    Create
                  </button>
                  <button onClick={() => loadCodingTemplate('/write src/demo.txt\nReplace this content')}
                    style={{ fontSize: '0.72rem', padding: '6px 10px', borderRadius: 6, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.04)', color: 'var(--txt-pri)', cursor: 'pointer' }}>
                    Write
                  </button>
                  <button onClick={() => loadCodingTemplate('/patch src/demo.txt\nUpdated content here')}
                    style={{ fontSize: '0.72rem', padding: '6px 10px', borderRadius: 6, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.04)', color: 'var(--txt-pri)', cursor: 'pointer' }}>
                    Patch
                  </button>
                  <button onClick={() => loadCodingTemplate('/insert src/demo.txt\nanchor text\n---\nInserted content')}
                    style={{ fontSize: '0.72rem', padding: '6px 10px', borderRadius: 6, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.04)', color: 'var(--txt-pri)', cursor: 'pointer' }}>
                    Insert
                  </button>
                </div>
              </div>
            )}

            <button onClick={() => setArchOpen(o => !o)}
              style={{ fontSize: '0.72rem', fontFamily: 'JetBrains Mono,monospace', color: 'var(--txt-sec)', background: 'none', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
              <ChevronRight size={12} style={{ transform: archOpen ? 'rotate(90deg)' : 'none', transition: 'transform 0.2s' }} />
              CLI Architecture Reference
            </button>
            {archOpen && (
              <div className="glass-card-solid" style={{ padding: 12, fontSize: '0.72rem', fontFamily: 'JetBrains Mono,monospace', color: 'var(--txt-sec)', borderLeft: '2px solid var(--cyan)', lineHeight: 1.7, marginBottom: 12 }}>
                <span style={{ color: 'var(--cyan)' }}>CLI Flow:</span> mammoth &lt;intent&gt; →{' '}
                <span style={{ color: 'var(--photon)' }}>api_server.py</span> (FastAPI :8000) →{' '}
                <span style={{ color: 'var(--violet)' }}>CortexRouter</span> → AutonomousEngine →{' '}
                CodingAgent / FieldOpsAgent / ResearchAgent
              </div>
            )}

            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <button onClick={runPrimary} disabled={running || smokeRunning}
              style={{ background: executionMode === 'plan' ? 'var(--violet)' : 'var(--photon)', color: '#050608', fontWeight: 700, fontSize: '0.85rem', padding: '8px 20px', borderRadius: 8, border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8, opacity: (running || smokeRunning) ? 0.7 : 1 }}>
              <Play size={14} /> {running ? (executionMode === 'plan' ? 'Planning + Executing…' : 'Running…') : (executionMode === 'plan' ? 'Plan + Execute' : 'Run Agent')}
            </button>
            <button onClick={runSmokeTests} disabled={smokeRunning || running}
              style={{ background: 'rgba(255,255,255,0.08)', color: 'var(--txt-pri)', fontWeight: 600, fontSize: '0.78rem', padding: '8px 12px', borderRadius: 8, border: '1px solid var(--border)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8, opacity: (running || smokeRunning) ? 0.7 : 1 }}>
              {smokeRunning ? <Loader size={13} style={{ animation: 'spin 1s linear infinite' }} /> : <CheckCircle size={13} />}
              {smokeRunning ? `Smoke Test ${smokeResults.length}/${SMOKE_TESTS.length}` : `Run Smoke Test (${SMOKE_TESTS.length})`}
            </button>
            </div>
          </div>

          <div className="glass-card-solid" style={{ padding: 16, minHeight: 160, maxHeight: 480, overflowY: 'auto' }}>
            {researchArtifact ? (
              <ResearchArtifactPanel artifact={researchArtifact} rawJson={output} />
            ) : codingArtifact ? (
              <CodingArtifactPanel
                artifact={codingArtifact}
                rawJson={output}
                onApplyPatch={applyCodingArtifactPatch}
                applyingPatch={applyingPatch}
              />
            ) : lastRunMode === 'plan' && (lastRunResult || planRun) ? (
              <PlanExecuteResultPanel planRun={lastRunResult || planRun} rawJson={output} />
            ) : lastRunResult ? (
              <AgentResultPanel result={lastRunResult} rawJson={output} agentId={selectedAgent} />
            ) : output ? (
              <pre style={{ fontSize: '0.82rem', fontFamily: 'JetBrains Mono,monospace', color: 'var(--txt-pri)', whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>{output}</pre>
            ) : (
              <MammothEmpty context="output" />
            )}
          </div>
        </div>

        <div style={{ width: 300, flexShrink: 0 }}>
          <div className="glass-card-solid" style={{ padding: 16 }}>
            <button onClick={() => setTraceOpen(o => !o)} style={{ background: 'none', border: 'none', cursor: 'pointer', width: '100%', padding: 0, marginBottom: traceOpen ? 12 : 0 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <h3 style={{ fontSize: '0.9rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 8, color: 'var(--txt-pri)' }}>
                  <Brain size={15} color="var(--violet)" /> Reasoning Trace
                </h3>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  {running && <Loader size={12} color="var(--photon)" style={{ animation: 'spin 1s linear infinite' }} />}
                  <span style={{
                    fontSize: '0.68rem', fontFamily: 'JetBrains Mono,monospace',
                    textTransform: 'uppercase', letterSpacing: '0.12em',
                    padding: '2px 8px', borderRadius: 20,
                    background: running ? 'rgba(77,166,255,0.15)' : 'rgba(255,255,255,0.05)',
                    color: running ? 'var(--photon)' : 'var(--txt-mut)',
                  }}>
                    {running ? 'THINKING' : thoughtSteps.length ? `${thoughtSteps.length} steps` : 'IDLE'}
                  </span>
                  <ChevronRight size={12} color="var(--txt-mut)" style={{ transform: traceOpen ? 'rotate(90deg)' : 'none', transition: 'transform 0.2s' }} />
                </div>
              </div>
            </button>

            {traceOpen && (
              <div>
                {thoughtSteps.length > 0 ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 14 }}>
                    {thoughtSteps.map((step, i) => {
                      const icon = step.status === 'success' ? <CheckCircle size={12} color="#22c55e" />
                        : step.status === 'warning' ? <AlertTriangle size={12} color="#f59e0b" />
                        : step.status === 'error' ? <XCircle size={12} color="#f87171" />
                        : <ChevronRight size={12} color="var(--photon)" />
                      const borderCol = step.status === 'success' ? '#22c55e33'
                        : step.status === 'warning' ? '#f59e0b33'
                        : step.status === 'error' ? '#f8717133'
                        : 'rgba(77,166,255,0.15)'
                      return (
                        <div key={i} style={{ background: 'rgba(255,255,255,0.025)', border: `1px solid ${borderCol}`, borderRadius: 6, padding: '7px 10px' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: step.detail ? 3 : 0 }}>
                            {icon}
                            <span style={{ fontSize: '0.76rem', color: 'var(--txt-pri)', fontWeight: 500 }}>{step.label}</span>
                            <span style={{ fontSize: '0.6rem', color: 'var(--txt-mut)', marginLeft: 'auto', fontFamily: 'JetBrains Mono,monospace' }}>{new Date(step.ts).toLocaleTimeString()}</span>
                          </div>
                          {step.detail && <div style={{ fontSize: '0.69rem', color: 'var(--txt-sec)', fontFamily: 'JetBrains Mono,monospace', lineHeight: 1.5, wordBreak: 'break-all' }}>{step.detail}</div>}
                        </div>
                      )
                    })}
                  </div>
                ) : (
                  <div style={{ color: 'var(--txt-sec)', fontSize: '0.75rem', marginBottom: 14, display: 'flex', alignItems: 'center', gap: 6 }}>
                    <Brain size={13} color="var(--txt-mut)" /> Run the agent to see its reasoning steps here.
                  </div>
                )}

                {agents.length > 0 && (
                  <div style={{ marginTop: 4 }}>
                    <p style={{ fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-sec)', marginBottom: 8 }}>Registered Agents</p>
                    {agents.slice(0, 10).map(a => (
                      <div key={a.id} style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderTop: '1px solid var(--border)', fontSize: '0.78rem' }}>
                        <span style={{ color: 'var(--txt-pri)' }}>{a.name}</span>
                        <span style={{ color: ((running && a.id === selectedAgent) || a.status === 'ACTIVE') ? '#22c55e' : 'var(--txt-mut)', fontFamily: 'JetBrains Mono,monospace', fontSize: '0.7rem' }}>
                          {(running && a.id === selectedAgent) || a.status === 'ACTIVE' ? 'ACTIVE' : a.status}
                        </span>
                      </div>
                    ))}
                  </div>
                )}

              </div>
            )}

            <RunHistoryPanel
              entries={runHistory}
              onReplay={replayHistoryEntry}
              onClear={clearRunHistory}
            />

            <div style={{ marginTop: 16 }}>
              <p style={{ fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-sec)', marginBottom: 8 }}>Agent Smoke Test</p>
              {smokeResults.length ? smokeResults.map(item => (
                <div key={item.id} style={{ padding: '8px 0', borderTop: '1px solid var(--border)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, alignItems: 'center' }}>
                    <span style={{ color: 'var(--txt-pri)', fontSize: '0.73rem' }}>{item.agent_id}</span>
                    <span style={{ fontSize: '0.66rem', textTransform: 'uppercase', color: item.status === 'pass' ? '#22c55e' : '#f87171', fontFamily: 'JetBrains Mono,monospace' }}>
                      {item.status}
                    </span>
                  </div>
                  <div style={{ color: 'var(--txt-sec)', fontSize: '0.69rem', marginTop: 4 }}>
                    {item.intent} • {item.runtime_status} • {item.duration_ms}ms
                  </div>
                  <div style={{ color: 'var(--txt-mut)', fontSize: '0.66rem', marginTop: 4, fontFamily: 'JetBrains Mono,monospace' }}>
                    {item.preview}
                  </div>
                </div>
              )) : <MammothEmpty context="smoke_test" compact />}
            </div>

            <div style={{ marginTop: 16 }}>
              <p style={{ fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-sec)', marginBottom: 8 }}>Plan + Execute</p>
              {planRun ? (
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, padding: '8px 0', borderTop: '1px solid var(--border)' }}>
                    <span style={{ color: 'var(--txt-pri)', fontSize: '0.74rem', flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {planRun.objective?.slice(0, 44) || 'Plan objective'}
                    </span>
                    <span style={{
                      fontSize: '0.64rem', textTransform: 'uppercase', flexShrink: 0,
                      color: planRun.plan_status === 'completed' ? '#22c55e'
                        : planRun.plan_status === 'pending_approval' ? '#f59e0b'
                        : planRun.plan_status === 'running' ? 'var(--photon)'
                        : '#f87171',
                      fontFamily: 'JetBrains Mono,monospace',
                    }}>
                      {planRun.plan_status || 'unknown'}
                    </span>
                  </div>
                  {/* Progress bar */}
                  <div style={{ marginBottom: 8 }}>
                    <div style={{ height: 4, borderRadius: 999, background: 'rgba(255,255,255,0.08)', overflow: 'hidden', marginBottom: 4 }}>
                      <div style={{
                        height: '100%', width: `${planProgressPercent}%`,
                        background: planRun.plan_status === 'completed' ? '#22c55e'
                          : planRun.plan_status === 'pending_approval' ? '#f59e0b'
                          : planRun.plan_status === 'running' ? 'var(--photon)' : '#f87171',
                        borderRadius: 999, transition: 'width 0.2s ease',
                      }} />
                    </div>
                    <div style={{ color: 'var(--txt-mut)', fontSize: '0.63rem', fontFamily: 'JetBrains Mono,monospace' }}>
                      {planProgressPercent}% · {planRun.progress?.completed || 0}/{planRun.progress?.total || 0} steps · {planRun.plan_profile || 'balanced'}
                    </div>
                  </div>
                  {/* Compact step list */}
                  {(planRun.plan_steps || []).map((step, idx) => {
                    const sc = step.status === 'completed' ? { color: '#22c55e', icon: '✓' }
                      : step.status === 'pending_approval' ? { color: '#f59e0b', icon: '…' }
                      : step.status === 'failed' ? { color: '#f87171', icon: '✗' }
                      : { color: 'var(--photon)', icon: '→' }
                    return (
                      <div key={`${step.id || idx}`} style={{
                        padding: '6px 8px', borderRadius: 6, marginBottom: 4,
                        background: 'rgba(255,255,255,0.025)',
                        border: `1px solid ${sc.color}22`,
                        borderLeft: `2px solid ${sc.color}`,
                      }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                          <span style={{ color: sc.color, fontSize: '0.7rem', flexShrink: 0 }}>{sc.icon}</span>
                          <span style={{ color: 'var(--txt-pri)', fontSize: '0.72rem', flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {step.title || step.agent_id}
                          </span>
                        </div>
                        <div style={{ color: 'var(--txt-mut)', fontSize: '0.64rem', marginTop: 2, paddingLeft: 14 }}>
                          {(step.agent_id || '').replace(/_agent$/, '')}
                          {step.duration_ms > 0 && ` · ${(step.duration_ms / 1000).toFixed(1)}s`}
                        </div>
                      </div>
                    )
                  })}
                  {(planRun.plan_steps || []).length === 0 && planRun.plan_status === 'running' && (
                    <div style={{ color: 'var(--txt-mut)', fontSize: '0.72rem', padding: '4px 0' }}>Agents working…</div>
                  )}
                  {(planRun.plan_steps || []).length === 0 && planRun.plan_status !== 'running' && (
                    <MammothEmpty context="plan_steps" compact />
                  )}
                </div>
              ) : <MammothEmpty context="plan_idle" compact />}
            </div>

            <AutonomousRunPanel
              summary={autonomousRuns.summary}
              runs={autonomousRuns.runs}
              onReplayRun={replayAutonomousRun}
            />

            <div style={{ marginTop: 16 }}>
              <WorkspaceMemoryPanel />
            </div>

            <div style={{ marginTop: 16 }}>
              <p style={{ fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-sec)', marginBottom: 8 }}>Task Queue</p>
              {tasks.length ? tasks.map(task => (
                <div key={task.id} style={{ padding: '8px 0', borderTop: '1px solid var(--border)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, alignItems: 'center' }}>
                    <span style={{ color: 'var(--txt-pri)', fontSize: '0.76rem' }}>{task.title}</span>
                    <span style={{ fontSize: '0.67rem', textTransform: 'uppercase', color: task.status === 'completed' ? '#22c55e' : task.status === 'failed' ? '#f87171' : 'var(--photon)', fontFamily: 'JetBrains Mono,monospace' }}>{task.status}</span>
                  </div>
                  {task.description ? <div style={{ color: 'var(--txt-sec)', fontSize: '0.7rem', marginTop: 4 }}>{task.description}</div> : null}
                </div>
              )) : <MammothEmpty context="tasks" compact />}
            </div>

            <div style={{ marginTop: 16 }}>
              <p style={{ fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-sec)', marginBottom: 8 }}>Pending Approvals</p>
              {approvals.filter(a => a.status === 'pending').length ? approvals.filter(a => a.status === 'pending').map(approval => (
                <div key={approval.id} style={{ padding: '8px 0', borderTop: '1px solid var(--border)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, alignItems: 'center' }}>
                    <span style={{ color: 'var(--txt-pri)', fontSize: '0.74rem' }}>{approval.operation}</span>
                   <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                     <button onClick={() => approveApproval(approval.id)} style={{ background: 'var(--photon)', color: '#050608', border: 'none', borderRadius: 6, padding: '4px 8px', fontSize: '0.68rem', cursor: 'pointer' }}>Approve</button>
                     <button onClick={() => deleteApproval(approval.id)} style={{ background: 'rgba(248,113,113,0.10)', color: '#fecaca', border: '1px solid rgba(248,113,113,0.25)', borderRadius: 6, padding: '4px 8px', fontSize: '0.68rem', cursor: 'pointer' }}>Delete</button>
                   </div>
                 </div>
                 <div style={{ color: 'var(--txt-sec)', fontSize: '0.7rem', marginTop: 4 }}>{approval.target}</div>
               </div>
              )) : <MammothEmpty context="approvals" compact />}
            </div>

            <div style={{ marginTop: 16 }}>
              <p style={{ fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-sec)', marginBottom: 8 }}>Rollback Snapshots</p>
              {snapshots.length ? snapshots.slice().reverse().slice(0, 8).map(snapshot => (
                <div key={snapshot.id} style={{ padding: '8px 0', borderTop: '1px solid var(--border)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, alignItems: 'center' }}>
                    <span style={{ color: 'var(--txt-pri)', fontSize: '0.74rem' }}>{snapshot.operation}</span>
                    <button onClick={() => restoreSnapshot(snapshot.id)} style={{ background: 'rgba(255,255,255,0.06)', color: 'var(--txt-pri)', border: '1px solid var(--border)', borderRadius: 6, padding: '4px 8px', fontSize: '0.68rem', cursor: 'pointer' }}>Restore</button>
                  </div>
                  <div style={{ color: 'var(--txt-sec)', fontSize: '0.7rem', marginTop: 4 }}>{snapshot.file_path}</div>
                  <div style={{ color: 'var(--txt-mut)', fontSize: '0.66rem', marginTop: 4 }}>
                    {snapshot.existed_before ? 'Previous file captured' : 'New file snapshot'} • {new Date(snapshot.created_at).toLocaleTimeString()}
                  </div>
                </div>
              )) : <MammothEmpty context="snapshots" compact />}
            </div>

            <div style={{ marginTop: 16 }}>
              <p style={{ fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-sec)', marginBottom: 8 }}>Live Activity</p>
              {activity.length ? activity.map(entry => (
                <div key={entry.id} style={{ padding: '8px 0', borderTop: '1px solid var(--border)' }}>
                  <div style={{ color: 'var(--txt-pri)', fontSize: '0.74rem', lineHeight: 1.5 }}>{entry.message}</div>
                  <div style={{ color: 'var(--txt-sec)', fontSize: '0.66rem', marginTop: 4, fontFamily: 'JetBrains Mono,monospace' }}>{entry.agent_id || 'system'} • {new Date(entry.created_at).toLocaleTimeString()}</div>
                </div>
              )) : <MammothEmpty context="activity" compact />}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
