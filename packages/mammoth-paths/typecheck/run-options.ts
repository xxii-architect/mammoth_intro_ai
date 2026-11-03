import { createPathsClient, type RunOptions, type UsageRecord } from '../src/index.js'

const options: RunOptions = {
  surface: 'agent_workspace',
  task: 'analyze_codebase',
  history: [{ role: 'user', text: 'Review the selected module' }],
  attachedFileIds: ['file-id'],
  recursive: { max_iterations: 1, max_tokens: 8000 },
}
const client = createPathsClient({ baseUrl: 'https://example.invalid' })
void client.run('Review', options)
void client.streamRun('Review', options)
const tasks: Promise<Array<Record<string, unknown>>> = client.listTasks()
const savedRun: Promise<Record<string, unknown>> = client.getRun('run-id')
void [tasks, savedRun]
const surface: UsageRecord['surface'] = 'owner_execution'
void surface

// @ts-expect-error Unknown run surfaces are rejected.
const badSurface: RunOptions = { surface: 'operator' }
// @ts-expect-error History must contain objects, not raw strings.
const badHistory: RunOptions = { history: ['private text'] }
// @ts-expect-error Attachment identifiers must be strings.
const badAttachments: RunOptions = { attachedFileIds: [1] }
void [badSurface, badHistory, badAttachments]
