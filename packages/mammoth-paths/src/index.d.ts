export declare const PATHS_CONTRACT_VERSION: 'mammoth.paths.v1'
export declare const RUN_CONTRACT_VERSION: 'mammoth.run.v1'
export declare const TERMINAL_RUN_EVENTS: readonly ['run.completed', 'run.failed', 'run.cancelled', 'run.awaiting_approval', 'run.partial']

export type RunEventType =
  | 'run.started'
  | 'plan.updated'
  | 'reasoning.summary'
  | 'tool.call'
  | 'tool.result'
  | 'approval.requested'
  | 'approval.resolved'
  | 'diff.proposed'
  | 'message.delta'
  | 'message.completed'
  | 'run.awaiting_approval'
  | 'run.completed'
  | 'run.failed'
  | 'run.cancelled'
  | 'run.partial'
  | 'run.continued'
  | 'run.recovering'
  | 'model.completed'
  | 'recursive.updated'

export interface RunEvent {
  contract: 'mammoth.run.v1'
  run_id: string
  seq: number
  type: RunEventType | (string & {})
  ts: string
  data: Record<string, unknown>
}

export interface Approval {
  id: string
  call_id: string
  tool: string
  args: Record<string, unknown>
  tier: 'read' | 'network' | 'write' | 'exec'
  reason: string
}

export interface RunState {
  id: string
  status: 'running' | 'awaiting_approval' | 'completed' | 'failed' | 'cancelled' | 'partial'
  events: RunEvent[]
  plan: Array<{ title: string; status: 'pending' | 'in_progress' | 'done' | 'skipped' }>
  approval: Approval | null
  reply: string
  error?: string
  repo?: unknown
  tools?: string[]
  summary?: Record<string, unknown>
  can_continue?: boolean
  recursive?: Record<string, unknown> | null
  failure_code?: string
  diagnostics?: Array<Record<string, unknown>>
  recovery?: Record<string, unknown> | null
  progress?: {
    goal: 'answer' | 'proposal' | 'validated' | 'applied'
    stage: 'answer' | 'proposal' | 'validated' | 'applied'
    goal_met: boolean
    state: string
    blocker: string
    readiness?: { observation: number; base_sha: string; ready: boolean; reason: string; profiles: Record<string, boolean>; profile_reasons?: Record<string, string> } | null
    inspected: Array<Record<string, unknown>>
    proposals: Array<Record<string, unknown>>
    executions: Array<{
      id: string
      status: string
      profile: string
      base_sha?: string
      checks?: Record<string, Record<string, unknown>>
      failure_excerpts?: Record<string, { text: string; truncated: boolean }>
      application?: { status: string; branch?: string; commit_sha?: string }
    }>
  } | null
}

export interface RunResult {
  runId: string
  status: RunState['status']
  reply: string
  error: string
  pendingApproval: Approval | null
  progress?: RunState['progress'] | null
  state: RunState | null
}

export interface RunSnapshot {
  id: string
  status: RunState['status']
  events: RunEvent[]
  reply?: string
  plan?: RunState['plan']
  pending_approval?: Approval | null
  progress?: RunState['progress'] | null
  diagnostics?: Array<Record<string, unknown>>
  failure_code?: string
  can_continue?: boolean
  recursive?: Record<string, unknown> | null
}

export interface UsageRecord {
  surface: 'mind' | 'repos' | 'notes' | 'buildlog' | 'terminal' | 'tasks' | 'artifacts' | 'documents' | 'owner_execution'
  method: string
  path: string
  status: number
  durationMs: number
}

export type OwnerExecutionChange = { path: string } & (
  | { content: string; edits?: never; delete?: never }
  | { edits: Array<{ old: string; new: string }>; content?: never; delete?: never }
  | { delete: true; content?: never; edits?: never }
)

export interface PathsClientOptions {
  baseUrl: string
  token?: string
  getToken?: () => string | null | undefined | Promise<string | null | undefined>
  fetch?: typeof fetch
  usageHook?: (usage: UsageRecord) => void
  headers?: Record<string, string>
}

export interface RunOptions {
  agentId?: string
  repo?: string
  approvalMode?: 'tools' | 'always'
  completionGoal?: 'answer' | 'proposal' | 'validated' | 'applied'
  threadId?: string
  surface?: 'mind' | 'agent_workspace'
  /** Server-owned task key; arbitrary instruction text is not used as a task brief. */
  task?: string
  history?: Array<{ role?: string; text?: string; message?: string; [field: string]: unknown }>
  attachedFileIds?: string[]
  recursive?: boolean | Record<string, number>
  signal?: AbortSignal
  onEvent?: (event: RunEvent, state?: RunState) => void
}

export declare class PathsError extends Error {
  status: number
  code: string
  payload: Record<string, unknown>
}

export interface PathsClient {
  contract: 'mammoth.paths.v1'
  tools(options?: { repo?: string }): Promise<Record<string, unknown>>
  streamRun(message: string, options?: RunOptions): Promise<RunEvent[]>
  decide(runId: string, approvalId: string, decision: 'approve' | 'reject', options?: { note?: string; signal?: AbortSignal; onEvent?: (event: RunEvent) => void }): Promise<RunEvent[]>
  continueRun(runId: string, options?: { signal?: AbortSignal; onEvent?: (event: RunEvent) => void }): Promise<RunEvent[]>
  run(message: string, options?: RunOptions & { approve?: (approval: Approval) => boolean | 'approve' | 'reject' | Promise<boolean | 'approve' | 'reject'>; maxApprovals?: number }): Promise<RunResult>
  cancelRun(runId: string): Promise<Record<string, unknown>>
  getRun(runId: string, options?: { after?: number }): Promise<Record<string, unknown>>
  recoverRun(runId: string): Promise<RunState>
  listRuns(): Promise<Array<Record<string, unknown>>>
  listRepos(): Promise<Record<string, unknown>>
  connectRepo(repo: string): Promise<Record<string, unknown>>
  syncRepo(sourceId: string): Promise<Record<string, unknown>>
  removeRepo(sourceId: string): Promise<Record<string, unknown>>
  proposeChange(sourceId: string, changes: Array<Record<string, unknown>>, options?: { title?: string }): Promise<Record<string, unknown>>
  listTasks(): Promise<Array<Record<string, unknown>>>
  saveTask(task: Record<string, unknown>): Promise<Record<string, unknown>>
  listArtifacts(): Promise<Record<string, unknown>>
  saveArtifact(artifact: Record<string, unknown>): Promise<Record<string, unknown>>
  getArtifactRun(id: string): Promise<Record<string, unknown>>
  deleteArtifact(id: string): Promise<Record<string, unknown>>
  clearArtifacts(): Promise<Record<string, unknown>>
  readDocument(fileId: string, options?: { scope?: 'chat' | 'atlas'; start?: number; count?: number }): Promise<Record<string, unknown>>
  createDocumentReview(fileId: string, goal: string, options?: { scope?: 'chat' | 'atlas' }): Promise<Record<string, unknown>>
  listDocumentReviews(fileId: string, options?: { scope?: 'chat' | 'atlas' }): Promise<Record<string, unknown>>
  getDocumentReview(id: string): Promise<Record<string, unknown>>
  advanceDocumentReview(id: string, options: { confirmModelUsage: true }): Promise<Record<string, unknown>>
  deleteDocumentReview(id: string): Promise<Record<string, unknown>>
  synthesizeDocumentReview(id: string, options: { confirmModelUsage: true }): Promise<Record<string, unknown>>
  extendDocumentReviewBudget(id: string, options: { expectedMaxTokens: number; maxTokens: number; confirmBudgetExtension: true }): Promise<Record<string, unknown>>
  ownerExecutionCapabilities(repo?: string): Promise<Record<string, unknown>>
  prepareOwnerExecution(repo: string, changes: OwnerExecutionChange[], options: { baseSha: string; profile: 'python_unittest' | 'python_pytest' | 'node_test' | 'ui_build' | 'ui_component' | 'ui_browser'; acceptance?: { expected_behavior: string[]; regression_tests: string[] } }): Promise<Record<string, unknown>>
  getOwnerExecution(id: string): Promise<Record<string, unknown>>
  approveOwnerExecution(id: string, options: { repo: string; approvalDigest: string }): Promise<Record<string, unknown>>
  cancelOwnerExecution(id: string): Promise<Record<string, unknown>>
  applyOwnerExecution(id: string, options: { repo: string; approvalDigest: string }): Promise<Record<string, unknown>>
  listNotes(): Promise<Array<Record<string, unknown>>>
  saveNote(content: string, options?: { title?: string; id?: string; [field: string]: unknown }): Promise<Record<string, unknown>>
  deleteNote(noteId: string): Promise<Record<string, unknown>>
  listBuildLog(): Promise<Array<Record<string, unknown>>>
  logBuild(title: string, options?: { description?: string; [field: string]: unknown }): Promise<Record<string, unknown>>
  execTerminal(cmd: string): Promise<Record<string, unknown>>
}

export declare function createPathsClient(options: PathsClientOptions): PathsClient
export declare function reduceRunEvent(run: RunState | null, event: RunEvent): RunState
export declare function hydrateRun(snapshot: RunSnapshot): RunState
export declare function readRunEventStream(response: Response, onEvent: (event: RunEvent) => void, options?: { runId?: string }): Promise<void>
export declare function createSseParser(onData: (payload: Record<string, unknown>) => void): { push(chunk: string): void; end(): void }
export declare function createRunStore(initial?: RunState | null): {
  getSnapshot(): RunState | null
  subscribe(listener: () => void): () => void
  dispatch(event: RunEvent): RunState
  reset(value?: RunState | null): void
}
