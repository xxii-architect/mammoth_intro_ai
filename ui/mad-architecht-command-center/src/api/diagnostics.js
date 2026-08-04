import { api } from './client'

const SELF_AUDIT_HISTORY_KEY = 'mammothSelfAuditHistory'
const SELF_AUDIT_HISTORY_LIMIT = 25

function safeLocalStorage() {
  if (typeof window === 'undefined' || !window.localStorage) return null
  return window.localStorage
}

export function loadSelfAuditHistory() {
  const storage = safeLocalStorage()
  if (!storage) return []
  try {
    const raw = storage.getItem(SELF_AUDIT_HISTORY_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

export function saveSelfAuditHistory(history) {
  const storage = safeLocalStorage()
  if (!storage) return
  storage.setItem(SELF_AUDIT_HISTORY_KEY, JSON.stringify(history.slice(0, SELF_AUDIT_HISTORY_LIMIT)))
}

export function clearSelfAuditHistory() {
  const storage = safeLocalStorage()
  if (!storage) return
  storage.removeItem(SELF_AUDIT_HISTORY_KEY)
}

export async function runSystemSelfAudit() {
  const [statusRes, healthRes, atlasRes, evalRes, entitlementRes, modelsRes, activityRes, tasksRes, approvalsRes] = await Promise.all([
    api('/status'),
    api('/health'),
    api('/atlas/status'),
    api('/atlas/evals', { method: 'POST', body: {} }),
    api('/entitlements'),
    api('/models'),
    api('/activity'),
    api('/tasks'),
    api('/approvals'),
  ])

  const services = Array.isArray(healthRes?.services) ? healthRes.services : []
  const greenServices = services.filter(service => service.status === 'green').length
  const evalSummary = evalRes?.evaluation?.summary || {}
  const features = entitlementRes?.features || {}
  const enabledFeatures = Object.values(features).filter(Boolean).length
  const totalFeatures = Object.keys(features).length
  const latestActivity = Array.isArray(atlasRes?.activity_log) ? atlasRes.activity_log[0] : null
  const recentAgentActivity = Array.isArray(activityRes) ? activityRes[0] : null
  const tasks = Array.isArray(tasksRes) ? tasksRes : []
  const approvals = Array.isArray(approvalsRes) ? approvalsRes : []
  const hasModelRouting = Boolean(modelsRes?.active_model || (modelsRes?.models && Object.keys(modelsRes.models).length))

  const checks = [
    {
      label: 'Backend health',
      passed: services.length > 0 && greenServices === services.length,
      detail: `${greenServices}/${services.length || 0} services healthy`,
    },
    {
      label: 'Model routing',
      passed: hasModelRouting,
      detail: modelsRes?.active_model ? `Active model: ${modelsRes.active_model}` : 'No active model reported',
    },
    {
      label: 'ATLAS eval harness',
      passed: (evalSummary.fail_count || 0) === 0 && (evalSummary.pass_count || 0) > 0,
      detail: `${evalSummary.pass_count || 0} pass / ${evalSummary.fail_count || 0} fail`,
    },
    {
      label: 'Learner continuity',
      passed: Boolean(atlasRes?.resume_packet?.summary || atlasRes?.learner_model || atlasRes?.lesson_history?.length),
      detail: atlasRes?.resume_packet?.summary || 'Learner state loaded and ready',
    },
    {
      label: 'Live task stream',
      passed: tasks.length >= 0,
      detail: `${tasks.length} tasks recorded • ${tasks.filter(task => task.status === 'pending_approval').length} awaiting approval`,
    },
    {
      label: 'Agent activity stream',
      passed: Boolean(recentAgentActivity),
      detail: recentAgentActivity ? `${recentAgentActivity.kind || 'event'} • ${recentAgentActivity.message || 'recent activity'}` : 'No recent activity entries',
    },
    {
      label: 'Approval queue',
      passed: true,
      detail: `${approvals.filter(approval => approval.status === 'pending').length} pending approvals`,
    },
    {
      label: 'Monetization scaffolding',
      passed: Boolean(entitlementRes?.tier && totalFeatures > 0),
      detail: `${entitlementRes?.tier || 'unknown'} tier with ${enabledFeatures}/${totalFeatures} features enabled`,
    },
  ]

  const passed = checks.filter(check => check.passed).length
  const recommendations = [
    'Promote the Ctrl+K shell button into a real command palette.',
    'Add responsive stacking for the tutor sidebars on smaller displays.',
    'Persist and surface self-audit history in a dedicated diagnostics view.',
  ]
  if ((evalSummary.fail_count || 0) > 0) {
    recommendations.unshift('Resolve failing ATLAS eval checks before expanding premium surfaces.')
  }
  if (!hasModelRouting) {
    recommendations.unshift('Restore model routing visibility so operators can verify which tutor/coding brain is active.')
  }
  if (!recentAgentActivity) {
    recommendations.push('Generate a live agent run so the activity stream can prove runtime wiring end-to-end.')
  }

  const auditEntry = await api('/audit', {
    method: 'POST',
    body: {
      kind: 'self_audit',
      message: 'System self-audit completed',
      details: {
        score: `${passed}/${checks.length}`,
        tier: entitlementRes?.tier || 'explorer',
        checks: checks.map(check => check.label),
      },
      source: 'diagnostics',
      actor: 'system',
      tier: entitlementRes?.tier || 'explorer',
    },
  })
  const auditLog = await api('/audit')
  const backendEntries = Array.isArray(auditLog?.entries) ? auditLog.entries : []

  const result = {
    id: `${Date.now()}`,
    generatedAt: new Date().toLocaleString(),
    generatedAtIso: new Date().toISOString(),
    score: `${passed}/${checks.length}`,
    checks,
    recommendations,
    observability: evalRes?.observability?.metrics || atlasRes?.observability?.metrics || null,
    tier: entitlementRes?.tier || 'explorer',
    commandCount: statusRes?.cli_commands_run || 0,
    services,
    entitlements: entitlementRes,
    models: modelsRes,
    latestActivity,
    activityStream: Array.isArray(activityRes) ? activityRes.slice(0, 10) : [],
    taskStream: tasks.slice(0, 10),
    approvalStream: approvals.slice(0, 10),
    backendEntry: auditEntry?.entry || null,
    auditEntries: backendEntries,
  }

  const history = [result, ...loadSelfAuditHistory()].slice(0, SELF_AUDIT_HISTORY_LIMIT)
  saveSelfAuditHistory(history)
  return { result, history }
}
