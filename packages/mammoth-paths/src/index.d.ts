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
  failure_code?: string
  diagnostics?: Array<Record<string, unknown>>
  recovery?: Record<string, unknown> | null
}

export interface RunResult {
  runId: string
  status: RunState['status']
  reply: string
  error: string
  pendingApproval: Approval | null
  state: RunState | null
}

export interface UsageRecord {
  surface: 'mind' | 'repos' | 'notes' | 'buildlog' | 'terminal'
  method: string
  path: string
  status: number
  durationMs: number
}

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
  threadId?: string
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
  getRun(runId: string, options?: { after?: number }): Promise<Record<string, unknown> | null>
  listRuns(): Promise<Array<Record<string, unknown>>>
  listRepos(): Promise<Record<string, unknown>>
  connectRepo(repo: string): Promise<Record<string, unknown>>
  syncRepo(sourceId: string): Promise<Record<string, unknown>>
  removeRepo(sourceId: string): Promise<Record<string, unknown>>
  proposeChange(sourceId: string, changes: Array<Record<string, unknown>>, options?: { title?: string }): Promise<Record<string, unknown>>
  listNotes(): Promise<Array<Record<string, unknown>>>
  saveNote(content: string, options?: { title?: string; id?: string; [field: string]: unknown }): Promise<Record<string, unknown>>
  deleteNote(noteId: string): Promise<Record<string, unknown>>
  listBuildLog(): Promise<Array<Record<string, unknown>>>
  logBuild(title: string, options?: { description?: string; [field: string]: unknown }): Promise<Record<string, unknown>>
  execTerminal(cmd: string): Promise<Record<string, unknown>>
}

export declare function createPathsClient(options: PathsClientOptions): PathsClient
export declare function reduceRunEvent(run: RunState | null, event: RunEvent): RunState
export declare function readRunEventStream(response: Response, onEvent: (event: RunEvent) => void): Promise<void>
export declare function createSseParser(onData: (payload: Record<string, unknown>) => void): { push(chunk: string): void; end(): void }
export declare function createRunStore(initial?: RunState | null): {
  getSnapshot(): RunState | null
  subscribe(listener: () => void): () => void
  dispatch(event: RunEvent): RunState
  reset(value?: RunState | null): void
}
