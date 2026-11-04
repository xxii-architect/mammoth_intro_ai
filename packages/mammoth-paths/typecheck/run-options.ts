import { createPathsClient, readRunEventStream, validateDocumentReview, type OwnerExecutionChange, type RunOptions, type RunSnapshot, type UsageRecord } from '../src/index.js'

const options: RunOptions = {
  surface: 'agent_workspace',
  task: 'analyze_codebase',
  history: [{ role: 'user', text: 'Review the selected module' }],
  attachedFileIds: ['file-id'],
  recursive: { max_iterations: 1, max_tokens: 8000 },
}
const client = createPathsClient({ baseUrl: 'https://example.invalid' })
void client.runtimeUsage()
void client.runtimeTenants()
void client.tenantRuntimeUsage('tenant-id')
void client.setTenantRuntimeLimits('tenant-id', { dailyTokenLimit: null, dailyUsdLimitMicros: 1000000 })
// @ts-expect-error Dollar limits use integer microUSD, not strings.
void client.setTenantRuntimeLimits('tenant-id', { dailyTokenLimit: null, dailyUsdLimitMicros: '1' })
void client.setRuntimeTokenLimit(null)
void client.setRuntimeTokenLimit(0)
// @ts-expect-error Limits cannot be strings.
void client.setRuntimeTokenLimit('100')
const review: Record<string, unknown> = validateDocumentReview({}, { reviewId: 'review-id', fileId: 'file-id', scope: 'chat' })
void review
// @ts-expect-error Review identities cannot address arbitrary scopes.
validateDocumentReview({}, { scope: 'operator' })
void client.run('Review', options)
void client.streamRun('Review', options)
void client.readDocument('file-id', { scope: 'chat', start: 6, count: 6 })
void client.createDocumentReview('file-id', 'Assess the appendix.', { scope: 'atlas' })
void client.exportOwnerBranch('exec-id', { repo: 'owner/repo', expectedCommit: 'commit', confirmPrivateExport: true })
// @ts-expect-error Private source export requires explicit confirmation.
void client.exportOwnerBranch('exec-id', { repo: 'owner/repo', expectedCommit: 'commit' })
void client.advanceDocumentReview('review-id', { confirmModelUsage: true })
void client.synthesizeDocumentReview('review-id', { confirmModelUsage: true })
void client.extendDocumentReviewBudget('review-id', { expectedMaxTokens: 64000, maxTokens: 128000, confirmBudgetExtension: true })
// @ts-expect-error Synthesis requires explicit paid confirmation.
void client.synthesizeDocumentReview('review-id')
// @ts-expect-error Ceiling changes require explicit confirmation.
void client.extendDocumentReviewBudget('review-id', { expectedMaxTokens: 64000, maxTokens: 128000 })
// @ts-expect-error Paid document review requires explicit confirmation.
void client.advanceDocumentReview('review-id')
// @ts-expect-error Document scopes cannot address arbitrary API surfaces.
void client.readDocument('file-id', { scope: 'operator' })
const tasks: Promise<Array<Record<string, unknown>>> = client.listTasks()
const savedRun: Promise<Record<string, unknown>> = client.getRun('run-id')
void [tasks, savedRun]
const snapshot: RunSnapshot = {
  id: 'run-id', status: 'partial', events: [], can_continue: true,
  failure_code: 'step_limit', recursive: { stage: 'critic' },
}
void snapshot
void readRunEventStream(new Response(), event => { void event }, { runId: 'run-id' })
const surface: UsageRecord['surface'] = 'owner_execution'
void surface
const changes: OwnerExecutionChange[] = [{ path: 'src/next.config.ts', delete: true }]
void client.prepareOwnerExecution('owner/repo', changes, {
  baseSha: 'a'.repeat(40), profile: 'ui_browser',
  acceptance: { expected_behavior: ['Config remains available'], regression_tests: ['tests/workspace-reliability.spec.js'] },
})
// @ts-expect-error Deletion is explicit and cannot include content.
const ambiguousDelete: OwnerExecutionChange = { path: 'x', delete: true, content: '' }
// @ts-expect-error A false delete flag is not an operation.
const falseDelete: OwnerExecutionChange = { path: 'x', delete: false }
void [ambiguousDelete, falseDelete]

// @ts-expect-error Unknown run surfaces are rejected.
const badSurface: RunOptions = { surface: 'operator' }
// @ts-expect-error History must contain objects, not raw strings.
const badHistory: RunOptions = { history: ['private text'] }
// @ts-expect-error Attachment identifiers must be strings.
const badAttachments: RunOptions = { attachedFileIds: [1] }
void [badSurface, badHistory, badAttachments]
