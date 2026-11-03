const { test, expect } = require('@playwright/test')
const fs = require('node:fs')
const path = require('node:path')
const baseURL = process.env.ATLAS_UI_URL || 'http://127.0.0.1:5194'

async function mount(page, component, payloads = {}, { authFailure = false, stalledAuth = false, savedTheme = '', repo = '', runOverride = null, trustProps = {} } = {}) {
  const errors = []
  page.on('pageerror', error => errors.push(error.message))
  await page.route('**/src/main.jsx', route => route.fulfill({ contentType: 'application/javascript', body: '' }))
  await page.route(url => url.pathname.startsWith('/api/'), route => {
    const path = new URL(route.request().url()).pathname
    const configured = payloads[path]
    if (configured === 'fallback') return route.fallback()
    if (typeof configured === 'function') {
      const response = configured(route.request())
      const isFulfillShape = response && typeof response === 'object'
        && (typeof response.status === 'number' || Object.prototype.hasOwnProperty.call(response, 'body') || Object.prototype.hasOwnProperty.call(response, 'contentType'))
      if (isFulfillShape) return route.fulfill(response)
      const body = response === undefined ? {} : response
      return route.fulfill({ contentType: 'application/json', body: JSON.stringify(body) })
    }
    if (configured && typeof configured === 'object' && (typeof configured.status === 'number' || 'contentType' in configured || 'body' in configured)) {
      return route.fulfill(configured)
    }
    const result = configured || (path.endsWith('/capabilities')
      ? { extensions: ['.pdf'], max_file_bytes: 50 * 1048576, max_storage_bytes: 500 * 1048576, usage: {} }
      : {})
    return route.fulfill({ contentType: 'application/json', body: JSON.stringify(result) })
  })
  await page.goto(baseURL)
  await page.evaluate(async ({ component, authFailure, stalledAuth, savedTheme, repo, runOverride, trustProps }) => {
    const { supabase } = await import('/src/lib/supabase.js')
    let attempts = 0
    supabase.auth.getSession = async () => {
      attempts++
      if (stalledAuth && attempts === 1) return new Promise(() => {})
      if (authFailure && attempts === 1) throw new Error('Session unavailable')
      return { data: { session: { access_token: 'test-only', user: { id: 'reader' } } } }
    }
    supabase.auth.onAuthStateChange = callback => {
      callback('INITIAL_SESSION', null)
      globalThis.switchWorkspaceAccount = id => callback('SIGNED_IN', { access_token: 'test-only', user: { id } })
      return { data: { subscription: { unsubscribe() {} } } }
    }
    const { default: React } = await import('/node_modules/.vite/deps/react.js')
    const { default: ReactDOM } = await import('/node_modules/.vite/deps/react-dom_client.js')
    const { AuthProvider, useAuth } = await import('/src/lib/authContext.jsx')
    const { default: Boundary } = await import('/src/components/RenderBoundary.jsx')
    await import('/src/design/tokens.css')
    await import('/src/index.css')
    localStorage.setItem('mammoth_onboarding_complete', 'true')
    sessionStorage.setItem('mammoth_welcomed_v1', '1')
    if (savedTheme) {
      localStorage.setItem('mammoth-theme', savedTheme)
      document.documentElement.style.setProperty('--txt-pri', '#0f172a')
      document.documentElement.style.setProperty('--card', '#ffffff')
      document.documentElement.style.colorScheme = 'light'
    }
    function AuthProbe() { return React.createElement('p', null, useAuth().loading ? 'Checking session...' : 'Session ready') }
    function BrokenView() { throw new Error('Simulated render error') }
    const View = component === 'auth' ? AuthProbe : component === 'broken' ? BrokenView
      : component === 'trust' ? (await import('/src/components/TrustSurfaces.jsx')).TrustBadgeRow
      : (await import(`/src/${component}.jsx`)).default
    const props = component === 'trust' ? trustProps : component === 'components/agent-workspace/OwnerExecutionPanel' ? { repo }
      : component === 'components/ResearchArtifactPanel' || component === 'components/LongFormResearchPanel' ? { artifact: runOverride }
      : component === 'components/PlanExecuteResultPanel' ? { planRun: runOverride }
      : component === 'components/agent-workspace/AgentWorkspace' ? { agents: [], temperature: 0.3, approvalMode: true }
      : component === 'components/AgentCommandLibrary' ? { onClose() {} }
      : component === 'components/RunTimeline' ? {
        run: runOverride || { id: 'run-test', status: 'partial', can_continue: true, events: [], plan: [], diagnostics: [
          { provider: 'test-provider', model: 'test-model', finish_reason: 'length', decision_protocol: 'json_schema', usage: { total_tokens: 42 } },
        ] },
        onContinue() { globalThis.continuationClicks = (globalThis.continuationClicks || 0) + 1 },
        onApprove() { globalThis.ownerApprovalClicks = (globalThis.ownerApprovalClicks || 0) + 1 },
        onReject() { globalThis.ownerRejectionClicks = (globalThis.ownerRejectionClicks || 0) + 1 },
      } : {}
    document.body.innerHTML = '<div id="root"></div>'
    ReactDOM.createRoot(document.getElementById('root')).render(
      React.createElement(Boundary, null, React.createElement(AuthProvider, null, React.createElement(View, props))),
    )
  }, { component, authFailure, stalledAuth, savedTheme, repo, runOverride, trustProps })
  return errors
}

const ownerPanel = 'components/agent-workspace/OwnerExecutionPanel'
const ownerCapabilities = { status: 'ok', enabled: true, isolation: { ready: true, reason: 'Pinned Linux image available.', profiles: { python_unittest: true, python_pytest: false, node_test: false } }, profiles: ['python_unittest', 'python_pytest', 'node_test'], base_sha: 'a'.repeat(40) }
const ownerJob = { id: `exec-${'a'.repeat(24)}`, status: 'pending_approval', patch: '--- a/app.py\n+++ b/app.py\n-return 0\n+return 1\n', base_sha: 'a'.repeat(40), profile: 'python_unittest', approval_digest: 'b'.repeat(64), expires_at: 1999999999 }

test('Mammoth Mind recursive review is opt-in and does not add a toolbar row', async ({ page }) => {
  let submitted
  const errors = await mount(page, 'pages/ChatPage', {
    '/api/mammoth/runs': request => {
      submitted = request.postDataJSON()
      return { contentType: 'text/event-stream', body: `data: ${JSON.stringify({
        contract: 'mammoth.run.v1', run_id: 'run-0123456789abcdef', seq: 1,
        type: 'run.completed', data: { reply: 'Reviewed options.' },
      })}\n\n` }
    },
  })
  await page.getByRole('button', { name: 'More chat options' }).click()
  const toggle = page.getByRole('menuitemcheckbox', { name: /Recursive review/ })
  await expect(toggle).toHaveAttribute('aria-checked', 'false')
  await toggle.click()
  await expect(toggle).toHaveAttribute('aria-checked', 'true')
  await page.getByRole('button', { name: 'More chat options' }).click()
  await page.getByRole('textbox').last().fill('Compare these approaches.')
  await page.getByRole('button', { name: 'Send', exact: true }).click()
  await expect.poll(() => submitted?.recursive).toBe(true)
  await expect(page.getByText('Reviewed options.', { exact: true })).toBeVisible()
  expect(submitted.repo_context).toBeUndefined()
  expect(errors).toEqual([])
})

test('recursive trace shows actual stage and budgets with a synthesis-only approval', async ({ page }) => {
  const recursive = { stage: 'critic', iteration: 1, limits: { max_iterations: 2, max_tokens: 64000, max_tool_calls: 12 },
    usage: { tokens: 420, tool_calls: 3 } }
  const errors = await mount(page, 'components/RunTimeline', {}, { runOverride: {
    id: 'run-0123456789abcdef', status: 'awaiting_approval', events: [
      { seq: 1, type: 'recursive.updated', data: recursive },
    ], plan: [], recursive, approval: { id: 'apr-recursive', tool: 'recursive_review', tier: 'review',
      args: { critique: { label: 'uncertain' } }, reason: 'Approve synthesis with caveats. This does not authorize tools.' },
  } })
  await expect(page.getByLabel('Recursive usage')).toContainText('420/64000 reported tokens')
  await expect(page.getByLabel('Recursive usage')).toContainText('pass 2/2')
  await expect(page.getByText('Recursive review: critic · pass 2', { exact: true })).toBeVisible()
  await expect(page.getByText(/This does not authorize tools/)).toBeVisible()
  await page.getByRole('button', { name: 'Approve', exact: true }).click()
  expect(await page.evaluate(() => globalThis.ownerApprovalClicks)).toBe(1)
  expect(errors).toEqual([])
})

for (const status of ['awaiting_approval', 'cancelled']) {
test(`Mammoth Mind restores recursive checkpoints from authoritative saved state (${status})`, async ({ page }) => {
  const runId = 'run-0123456789abcdef'
  const approval = { id: 'apr-restored', tool: 'recursive_review', tier: 'review', args: {},
    reason: 'Approve synthesis with caveats; no tool authorization.' }
  const recursive = { stage: 'critic', iteration: 0, limits: { max_iterations: 2, max_tokens: 64000, max_tool_calls: 12 },
    usage: { tokens: 300, tool_calls: 0 } }
  let decisions = 0
  let reads = 0
  const event = (seq, type, data = {}) => ({ contract: 'mammoth.run.v1', run_id: runId, seq, type, data })
  const errors = await mount(page, 'pages/ChatPage', {
    '/api/mammoth/chat/history': { chat_history: [
      { role: 'user', message: 'Explore a hypothesis.' },
      { role: 'assistant', local_id: runId, agent_id: 'reasoning_agent', message: '',
        run: { id: runId, status: 'awaiting_approval', events: [], plan: [], approval, recursive } },
    ] },
    [`/api/mammoth/runs/${runId}`]: () => {
      reads++
      return { run: { id: runId, status, reply: '', recursive, plan: [],
        pending_approval: status === 'awaiting_approval' ? approval : null,
        events: [event(1, 'recursive.updated', recursive), event(2, 'approval.requested', approval),
          event(3, 'run.awaiting_approval')] } }
    },
    [`/api/mammoth/runs/${runId}/approval`]: () => {
      decisions++
      return { contentType: 'text/event-stream', body: [
        event(4, 'approval.resolved', { approval_id: approval.id, approved: true, tool: 'recursive_review' }),
        event(5, 'run.completed', { reply: 'Restored and reviewed.', recursive }),
      ].map(value => `data: ${JSON.stringify(value)}\n\n`).join('') }
    },
  })
  await expect.poll(() => reads).toBe(1)
  expect(decisions).toBe(0)
  if (status === 'awaiting_approval') {
    await page.getByRole('button', { name: 'Approve', exact: true }).click()
    await expect(page.getByText('Restored and reviewed.', { exact: true })).toBeVisible()
    expect(decisions).toBe(1)
  } else {
    await expect(page.getByRole('button', { name: 'Approve', exact: true })).toHaveCount(0)
    await expect(page.getByText(/Stopped · 0 tool calls/)).toBeVisible()
  }
  expect(errors).toEqual([])
})
}

const reviewRunId = 'run-0123456789abcdef'
function reviewSnapshot(status = 'cancelled') {
  const approval = { id: 'apr-review', tool: 'owner_execution_run', tier: 'exec', args: {}, reason: 'Validate' }
  return {
    id: reviewRunId, status, message: 'Merge chat headers', reply: 'Saved review reply',
    pending_approval: status === 'awaiting_approval' ? approval : null, can_continue: status === 'partial',
    progress: { goal: 'applied', stage: 'proposal', goal_met: false, inspected: [], executions: [] },
    events: [
      { run_id: reviewRunId, seq: 1, type: 'approval.requested', data: approval },
      { run_id: reviewRunId, seq: 2, type: 'run.awaiting_approval', data: {} },
    ],
  }
}

test('Run Review uses saved cancellation, exports exact receipts and performs no mutations on mobile', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  const requests = []
  page.on('request', request => { if (new URL(request.url()).pathname.startsWith('/api/')) requests.push(request) })
  const saved = reviewSnapshot()
  const errors = await mount(page, 'pages/RunReviewPage', {
    '/api/mammoth/runs': { runs: [{ id: reviewRunId, status: 'cancelled', message: saved.message }] },
    [`/api/mammoth/runs/${reviewRunId}`]: { run: saved },
  })
  await expect(page.getByText('Saved review reply')).toBeVisible()
  await expect(page.getByText('Saved status:', { exact: false })).toContainText('cancelled')
  await expect(page.getByRole('group', { name: 'Approval required' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Continue task' })).toHaveCount(0)
  const downloadEvent = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Download review JSON' }).click()
  const download = await downloadEvent
  expect(JSON.parse(fs.readFileSync(await download.path(), 'utf8'))).toEqual(saved)
  await page.getByRole('button', { name: 'Refresh saved runs' }).click()
  await expect(page.getByText('Saved review reply')).toBeVisible()
  expect(requests.every(request => request.method() === 'GET')).toBe(true)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  expect(errors).toEqual([])
})

test('Run Review is reachable from workspace navigation without changing chat', async ({ page }) => {
  const errors = await mount(page, 'App', {
    '/api/entitlements': { admin_controls_enabled: true, tier: 'pro' },
    '/api/mammoth/runs': { runs: [] },
    '/api/buildlog': [],
    '/api/logsale': [],
  })

  await page.getByRole('button', { name: 'Run Review', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Run Review', exact: true })).toBeVisible()
  await expect(page.getByText('No saved runs yet.')).toBeVisible()
  expect(errors).toEqual([])
})

test('real page navigation preserves full agent output and Notes drafts', async ({ page }) => {
    const complete = { ...marketReport, summary: 'Full navigation test output', extra_detail: 'Detailed evidence. '.repeat(4000) }
    const requests = []
    const errors = await mount(page, 'App', {
      '/api/entitlements': { admin_controls_enabled: true, tier: 'pro' },
      '/api/buildlog': [], '/api/logsale': [], '/api/notes': [],
      '/api/approvals': [], '/api/activity': [], '/api/tasks': [], '/api/snapshots': [],
      '/api/agents': [{ id: 'market_intel_agent', name: 'Market Intel', status: 'ready' }],
      '/api/run': request => {
        requests.push(request.postDataJSON())
        return { status: 'ok', result: { status: 'ok', output: complete } }
      },
    })

    await page.getByRole('button', { name: 'Agent', exact: true }).click()
    await page.getByRole('navigation', { name: 'Agents' }).getByRole('button', { name: /Market Intel/ }).click()
    await page.getByRole('textbox', { name: 'Message Market Intel' }).fill('Keep all my evidence.')
    await page.getByRole('button', { name: 'Send', exact: true }).click()
    await expect(page.getByRole('button', { name: 'Export complete JSON', exact: true })).toBeVisible()
    await page.getByRole('textbox', { name: 'Message Market Intel' }).fill('Unsent next question')
    await page.getByRole('button', { name: 'Notes', exact: true }).click()
    await page.getByLabel('New note').fill('Private note draft while reviewing evidence')
    await page.getByRole('button', { name: 'Agent', exact: true }).click()
    await expect(page.getByRole('textbox', { name: 'Message Market Intel' })).toHaveValue('Unsent next question')
    const downloadPromise = page.waitForEvent('download')
    await page.getByRole('button', { name: 'Export complete JSON', exact: true }).click()
    const exported = JSON.parse(fs.readFileSync(await (await downloadPromise).path(), 'utf8'))
    expect(exported).toEqual(complete)
    expect(requests).toHaveLength(1)
    await page.getByRole('button', { name: 'Notes', exact: true }).click()
    await expect(page.getByLabel('New note')).toHaveValue('Private note draft while reviewing evidence')
    await page.evaluate(() => globalThis.switchWorkspaceAccount('another-reader'))
    await expect(page.getByLabel('New note')).toHaveValue('')
    expect(errors).toEqual([])
})

test('Mammoth Mind retains the full conversation and draft without hidden-page polling', async ({ page }) => {
      await page.clock.install()
      let historyLoads = 0
      let runCalls = 0
      let approvalLoads = 0
      const reply = 'Complete answer retained across pages, not an archived summary.'
      const errors = await mount(page, 'App', {
        '/api/entitlements': { admin_controls_enabled: true, tier: 'pro' },
        '/api/buildlog': [], '/api/logsale': [], '/api/notes': [],
        '/api/approvals': () => { approvalLoads++; return [] },
        '/api/mammoth/chat/history': () => { historyLoads++; return { chat_history: [] } },
        '/api/mammoth/runs': request => {
          if (request.method() !== 'POST') return { runs: [] }
          runCalls++
          return { contentType: 'text/event-stream', body: `data: ${JSON.stringify({
            contract: 'mammoth.run.v1', run_id: 'run-0123456789abcdef', seq: 1,
            type: 'run.completed', data: { reply },
          })}\n\n` }
        },
      })
      await page.locator('nav').first().getByRole('button', { name: 'Mammoth Mind', exact: true }).click()
      await expect.poll(() => historyLoads).toBe(1)
      await page.getByRole('textbox').last().fill('Keep the complete conversation.')
      await page.getByRole('button', { name: 'Send', exact: true }).click()
      await expect(page.getByText(reply, { exact: true })).toBeVisible()
      await page.getByRole('textbox').last().fill('Unsent Mammoth Mind question')
      await page.getByRole('button', { name: 'Notes', exact: true }).click()
      await expect(page.getByLabel('New note')).toBeVisible()
      const before = approvalLoads
      await page.clock.fastForward(31000)
      expect(approvalLoads).toBe(before)
      await page.locator('nav').first().getByRole('button', { name: 'Mammoth Mind', exact: true }).click()
      await expect(page.getByText(reply, { exact: true })).toBeVisible()
      await expect(page.getByRole('textbox').last()).toHaveValue('Unsent Mammoth Mind question')
      expect(historyLoads).toBe(1)
      expect(runCalls).toBe(1)
      expect(errors).toEqual([])
    })

test('team preview, complete result and follow-up survive real page navigation without replay', async ({ page }) => {
      const requests = []
      const errors = await mount(page, 'App', {
        '/api/entitlements': { admin_controls_enabled: true, tier: 'pro' },
        '/api/buildlog': [], '/api/logsale': [], '/api/notes': [],
        '/api/agents': [], '/api/approvals': [], '/api/activity': [], '/api/tasks': [], '/api/snapshots': [],
        '/api/plan-execute': request => {
          const body = request.postDataJSON()
          requests.push(body)
          return { status: 'ok', plan_id: 'plan-memory', objective: body.objective,
            plan_steps: [{ id: 'one', title: 'Inspect the evidence', agent_id: 'market_intel_agent', intent: 'market_intel',
              status: body.dry_run ? 'planned' : 'completed', response: { result: { output: marketReport } } }],
            plan_status: body.dry_run ? 'preview' : 'completed',
            artifact_save: { status: 'saved', artifact_id: 'plan-memory' } }
        },
      })
      await page.getByRole('button', { name: 'Agent', exact: true }).click()
      await page.getByRole('navigation', { name: 'Agents' }).getByRole('button', { name: 'Team run', exact: true }).click()
      await page.getByRole('textbox', { name: 'Objective', exact: true }).fill('Compare this coffee evidence.')
      await page.getByRole('button', { name: 'Preview the plan' }).click()
      await expect(page.getByRole('button', { name: 'Run 2 steps', exact: true })).toBeVisible()
      await page.getByRole('button', { name: 'Notes', exact: true }).click()
      await page.getByRole('button', { name: 'Agent', exact: true }).click()
      await page.getByRole('button', { name: 'Run 2 steps', exact: true }).click()
      await expect(page.getByRole('textbox', { name: 'Team follow-up' })).toBeVisible()
      await page.getByRole('textbox', { name: 'Team follow-up' }).fill('Keep this unsent team follow-up')
      await page.getByRole('button', { name: 'Notes', exact: true }).click()
      await page.getByRole('button', { name: 'Agent', exact: true }).click()
      await expect(page.getByRole('textbox', { name: 'Team follow-up' })).toHaveValue('Keep this unsent team follow-up')
      await expect(page.getByText('Saved to your Artifacts. Reopening does not run agents.', { exact: true })).toBeVisible()
      expect(requests).toHaveLength(2)
      expect(errors).toEqual([])
})

test('Notes edits, search and Build Log drafts survive navigation but clear on account change', async ({ page }) => {
  const errors = await mount(page, 'App', {
    '/api/entitlements': { admin_controls_enabled: true, tier: 'pro' },
    '/api/buildlog': [], '/api/logsale': [],
    '/api/notes': [{ id: 'notes-one', title: 'Coffee research', content: 'Coffee research\nSaved text', body: 'Coffee research\nSaved text', source: 'personal' }],
  })
  await page.getByRole('button', { name: 'Notes', exact: true }).click()
  await page.getByLabel('Search notes').fill('coffee')
  await page.getByRole('button', { name: 'Edit note', exact: true }).click()
  await page.getByLabel('Edit note content').fill('My full unsaved edit')
  await page.getByRole('button', { name: 'Build Log', exact: true }).click()
  await page.getByRole('button', { name: 'New Session Entry' }).click()
  await page.locator('form textarea').first().fill('Unsubmitted session goal')
  await page.getByRole('button', { name: 'Notes', exact: true }).click()
  await expect(page.getByLabel('Edit note content')).toHaveValue('My full unsaved edit')
  await expect(page.getByLabel('Search notes')).toHaveValue('coffee')
  await page.getByRole('button', { name: 'Build Log', exact: true }).click()
  await expect(page.locator('form textarea').first()).toHaveValue('Unsubmitted session goal')
  await page.evaluate(() => globalThis.switchWorkspaceAccount('other-account'))
  await expect(page.getByRole('button', { name: 'New Session Entry' })).toBeVisible()
  await page.getByRole('button', { name: 'New Session Entry' }).click()
  await expect(page.locator('form textarea').first()).toHaveValue('')
  expect(errors).toEqual([])
})

test('Run Review shows pending evidence without approval or continuation controls', async ({ page }) => {
  const saved = reviewSnapshot('awaiting_approval')
  await mount(page, 'pages/RunReviewPage', {
    '/api/mammoth/runs': { runs: [{ id: reviewRunId, status: saved.status }] },
    [`/api/mammoth/runs/${reviewRunId}`]: { run: saved },
  })
  await expect(page.getByText('Saved approval request only.', { exact: false })).toBeVisible()
  await expect(page.getByRole('button', { name: /^Approve|^Reject|Continue task/ })).toHaveCount(0)
})

test('Run Review surfaces denied and malformed snapshots rather than showing successful work', async ({ page }) => {
  let validIdentity = false
  await mount(page, 'pages/RunReviewPage', {
    '/api/mammoth/runs': { runs: [{ id: reviewRunId, status: 'completed' }] },
    [`/api/mammoth/runs/${reviewRunId}`]: () => validIdentity
      ? { status: 403, body: JSON.stringify({ error: 'Access denied' }) }
      : { run: { ...reviewSnapshot(), id: 'other' } },
  })
  await expect(page.getByRole('alert')).toContainText('identity')
  await expect(page.getByRole('button', { name: 'Download review JSON' })).toHaveCount(0)
  validIdentity = true
  await page.getByRole('button', { name: 'Refresh saved runs' }).click()
  await expect(page.getByRole('alert')).toContainText('Access denied')
  await expect(page.getByRole('region', { name: 'Saved run review' })).toHaveCount(0)
})

test('Run Review clears account-scoped evidence immediately when the user changes', async ({ page }) => {
  await mount(page, 'pages/RunReviewPage', {
    '/api/mammoth/runs': { runs: [{ id: reviewRunId, status: 'cancelled' }] },
    [`/api/mammoth/runs/${reviewRunId}`]: { run: reviewSnapshot() },
  })
  await expect(page.getByText('Saved review reply')).toBeVisible()
  let releaseList
  await page.route('**/api/mammoth/runs', route => {
    releaseList = () => route.fulfill({ contentType: 'application/json', body: JSON.stringify({ runs: [] }) })
  })
  await page.evaluate(() => globalThis.switchWorkspaceAccount('other-user'))
  await expect(page.getByRole('status')).toContainText('Loading saved runs')
  await expect(page.getByText('Saved review reply')).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Download review JSON' })).toHaveCount(0)
  await expect.poll(() => typeof releaseList).toBe('function')
  await releaseList()
  await expect(page.getByText('No saved runs yet.')).toBeVisible()
})

test('trust row keeps provider and source counts without inventing confidence or an evidence grade', async ({ page }) => {
  const errors = await mount(page, 'trust', {}, { trustProps: { provider: 'openai', sourceCount: 2 } })
  await expect(page.getByText('OpenAI', { exact: true })).toBeVisible()
  await expect(page.getByText('Not assessed', { exact: true })).toBeVisible()
  await expect(page.getByText('2 sources', { exact: true })).toBeVisible()
  await expect(page.getByText(/74%|80%/)).toHaveCount(0)
  expect(errors).toEqual([])
})

test('explicit zero score is retained but labelled uncalibrated rather than correctness', async ({ page }) => {
  await mount(page, 'trust', {}, { trustProps: { provider: 'openai', confidence: 0 } })
  await expect(page.getByTitle(/Reported score \(uncalibrated\): 0%/)).toBeVisible()
  await expect(page.getByText('OpenAI', { exact: true })).toBeVisible()
  await expect(page.getByText('Not assessed')).toHaveCount(0)
})

for (const [status, label] of [
  ['interpretation', 'Interpretation'],
  ['source_linked', 'Source-linked · not fact-verified'],
  ['unverified', 'Unverified'],
]) {
  test(`trust row labels ${status} without a truth score`, async ({ page }) => {
    const errors = await mount(page, 'trust', {}, { trustProps: { evidenceStatus: status, sourceCount: 1 } })
    await expect(page.getByText(label, { exact: true })).toBeVisible()
    await expect(page.getByText('Not assessed', { exact: true })).toBeVisible()
    await expect(page.getByText(/100%|verified true/i)).toHaveCount(0)
    expect(errors).toEqual([])
  })
}

for (const component of ['ResearchArtifactPanel', 'LongFormResearchPanel']) {
  test(`${component} shows source preference without certifying a claim`, async ({ page }) => {
    const errors = await mount(page, `components/${component}`, {}, { runOverride: {
      title: 'State fishing rules', status: 'ok', sources: [{
        title: 'Idaho Fish and Game', url: 'https://idfg.idaho.gov/fish',
        snippet: 'Review the current fishing rules and location-specific restrictions.',
        source_category: 'government', authority_basis: 'government_hostname_policy',
        verification_status: 'not_fact_verified',
      }],
    } })
    await expect(page.getByText('Government source · not fact-verified', { exact: true })).toBeVisible()
    expect(errors).toEqual([])
  })
}

const marketReport = {
  status: 'ok', agent: 'MarketIntelAgent', artifact_type: 'market_intel', title: 'Product research',
  summary: 'The test listing documents a 12-ounce whole-bean bag. [S1]',
  executive_summary: 'The test listing documents a 12-ounce whole-bean bag. [S1]',
  findings: [{
    heading: 'Documented bag', content: 'The test listing documents a 12-ounce whole-bean bag. [S1]',
    source_support: ['S1'], evidence_status: 'source_linked',
    evidence: [{ source_id: 'S1', quote: 'Just Black whole-bean coffee, 12-ounce bag.' }],
  }],
  analysis: [{ heading: 'Household tradeoff', detail: 'Compare cost per ounce and how quickly you finish an opened bag.' }],
  risks: ['Ground coffee is a different format.'], key_trends: [], competitive_landscape: [],
  knowledge_gaps: 'Larger bags and current stock were not established.',
  confidence_assessment: 'Only the supplied test excerpt was checked.',
  recommended_next_steps: ['Check the manufacturer size selector and whole-bean option.'],
  sources: [{ label: 'S1', title: 'Manufacturer test listing', url: 'https://example.com/coffee',
    snippet: 'Just Black whole-bean coffee, 12-ounce bag.' }],
  citations: [], references: [], quality: { ready: true, evidence_status: 'source_linked' },
}

test('team results archive feedback, full exports and follow-up are explicit', async ({ page }) => {
  const requests = []
  const errors = await mount(page, 'components/agent-workspace/AgentWorkspace', {
    '/api/plan-execute': request => {
      const body = request.postDataJSON()
      requests.push(body)
      const plan_steps = [{ id: 'one', title: 'Inspect the evidence', agent_id: 'market_intel_agent', intent: 'market_intel',
        status: body.dry_run ? 'planned' : 'completed', response: { result: { output: marketReport } } }]
      return { status: 'ok', plan_id: 'plan-saved', objective: body.objective, plan_steps,
        plan_status: body.dry_run ? 'preview' : 'completed', artifact_save: { status: 'saved', artifact_id: 'plan-saved' } }
    },
  })
  await page.getByRole('navigation', { name: 'Agents' }).getByRole('button', { name: 'Team run', exact: true }).click()
  await page.getByRole('textbox', { name: 'Objective', exact: true }).fill('Research the exact coffee variant.')
  await page.getByRole('button', { name: 'Preview the plan' }).click()
  await page.getByRole('button', { name: 'Run 2 steps' }).click()
  await expect(page.getByText('Saved to your Artifacts. Reopening does not run agents.', { exact: true })).toBeVisible()
  const downloaded = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Export complete JSON', exact: true }).click()
  expect((await downloaded).suggestedFilename()).toMatch(/\.json$/)
  expect(requests).toHaveLength(2)
  await page.getByRole('textbox', { name: 'Team follow-up' }).fill('Compare cost per ounce.')
  await page.getByRole('button', { name: 'Prepare follow-up plan' }).click()
  await expect(page.getByText(/Follow-up using a saved team result/)).toBeVisible()
  expect(requests).toHaveLength(2) // Preparing a follow-up does not spend model calls.
  await page.getByRole('button', { name: 'Preview the plan' }).click()
  expect(requests[2].parent_artifact_id).toBe('plan-saved')
  expect(requests[2].objective).toBe('Compare cost per ounce.')
  expect(errors).toEqual([])
})

test('specialist output can be exported when archival saving fails', async ({ page }) => {
  const errors = await mount(page, 'components/agent-workspace/AgentWorkspace', {
    '/api/run': { status: 'ok', result: { status: 'ok', output: marketReport,
      artifact_save: { status: 'failed', error: 'Archive unavailable. Export before leaving.' } } },
    '/api/workspace/artifacts': { status: 503, body: '{"error":"Archive unavailable"}', contentType: 'application/json' },
  })
  await page.getByRole('navigation', { name: 'Agents' }).getByRole('button', { name: /Market Intel/ }).click()
  await page.getByRole('textbox', { name: 'Message Market Intel' }).fill('Research this product.')
  await page.getByRole('button', { name: 'Send', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('Archive unavailable')
  await page.getByRole('button', { name: 'Save output', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('Archive unavailable')
  const download = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Export Markdown', exact: true }).click()
  expect((await download).suggestedFilename()).toMatch(/\.md$/)
  expect(errors).toEqual([])
})

test('Notes supports search, edits, full export and confirmed deletion on mobile', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  let note = { id: 'notes-one', title: 'Coffee research', content: 'Coffee research\nKeep the exact variant.', body: 'Coffee research\nKeep the exact variant.', source: 'personal' }
  const errors = await mount(page, 'pages/NotesPage', {
    '/api/notes': request => {
      if (request.method() === 'GET') return [note]
      note = request.postDataJSON()
      return note
    },
    '/api/notes/notes-one': { status: 'ok', deleted: 'notes-one' },
  })
  await page.getByLabel('Search notes').fill('missing term')
  await expect(page.getByRole('status')).toContainText('0 of 1')
  await page.getByLabel('Search notes').fill('coffee')
  await page.getByRole('button', { name: 'Edit note', exact: true }).click()
  await page.getByLabel('Edit note content').fill('Coffee research\nCheck whole-bean and current sizes.')
  await page.getByRole('button', { name: 'Save changes', exact: true }).click()
  await expect(page.getByText('Coffee research\nCheck whole-bean and current sizes.', { exact: true })).toBeVisible()
  const download = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Export note', exact: true }).click()
  expect((await download).suggestedFilename()).toBe('Coffee-research.md')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  await page.getByRole('button', { name: 'Delete', exact: true }).click()
  await expect(page.getByRole('group', { name: 'Confirm note deletion' })).toBeVisible()
  await page.getByRole('button', { name: 'Confirm delete', exact: true }).click()
  await expect(page.getByRole('status')).toContainText('0 of 0')
  expect(errors).toEqual([])
})

test('Notes retains an unsaved draft and Build Log exposes load failures', async ({ page }) => {
  let errors = await mount(page, 'pages/NotesPage', {
    '/api/notes': request => request.method() === 'GET' ? [] : { status: 503, body: '{"error":"Notes storage unavailable"}', contentType: 'application/json' },
  })
  await page.getByLabel('New note').fill('Do not lose this draft.')
  await page.getByRole('button', { name: 'Create note', exact: true }).click()
  await expect(page.getByLabel('New note')).toHaveValue('Do not lose this draft.')
  await expect(page.getByRole('alert').first()).toContainText('Notes storage unavailable')
  expect(errors).toEqual([])
  errors = await mount(page, 'pages/BuildLogPage', {
    '/api/buildlog': { status: 503, body: '{"error":"Build log unavailable"}', contentType: 'application/json' },
  })
  await expect(page.getByRole('alert')).toContainText('Build log unavailable')
  await expect(page.getByRole('button', { name: 'Refresh build log' })).toBeEnabled()
  await expect(page.getByRole('button', { name: 'Export build log JSON' })).toBeDisabled()
  expect(errors).toEqual([])
})

for (const surface of ['specialist', 'team']) {
  test(`Market Intel ${surface} shows evidence and useful depth, not empty sections`, async ({ page }) => {
    let errors
    if (surface === 'specialist') {
      errors = await mount(page, 'components/agent-workspace/AgentWorkspace', {
        '/api/run': { status: 'ok', result: { status: 'ok', output: marketReport } },
      })
      await page.getByRole('navigation', { name: 'Agents' }).getByRole('button', { name: /Market Intel/ }).click()
      await page.getByRole('textbox', { name: 'Message Market Intel' }).fill('Does Just Black come in large whole-bean bags?')
      await page.getByRole('button', { name: 'Send', exact: true }).click()
    } else {
      errors = await mount(page, 'components/PlanExecuteResultPanel', {}, { runOverride: {
        status: 'completed', plan_steps: [{ agent_id: 'market_intel_agent', status: 'completed',
          description: 'Check the exact product', response: { result: { output: marketReport } } }],
      } })
      await page.getByRole('button', { name: /Market Intel/ }).click()
    }
    await expect(page.getByText('Market & Product Research', { exact: true })).toBeVisible()
    await expect(page.getByRole('region', { name: /Interpretation & tradeoffs/ })).toContainText('cost per ounce')
    await expect(page.getByText('Larger bags and current stock were not established.', { exact: true })).toBeVisible()
    await expect(page.getByText('Check the manufacturer size selector and whole-bean option.', { exact: true })).toBeVisible()
    await expect(page.getByRole('link', { name: 'https://example.com/coffee' })).toBeVisible()
    await expect(page.locator('blockquote')).toContainText('12-ounce bag')
    await expect(page.getByRole('region', { name: /Market trends|Alternatives/ })).toHaveCount(0)
    await expect(page.getByText(/100%|practical production workflow|Private model text/)).toHaveCount(0)
    expect(errors).toEqual([])
  })
}

test('Brand Voice displays the actual copy rather than only its change summary', async ({ page }) => {
  const errors = await mount(page, 'components/PlanExecuteResultPanel', {}, { runOverride: {
    status: 'completed', plan_steps: [{ agent_id: 'brand_voice_agent', status: 'completed',
      response: { result: { output: {
        agent: 'brand_voice', status: 'ok', output: 'Start with one planter. Watch what grows.',
        summary: 'A practical caption.', tone_notes: 'Calm and direct.',
        reasoning_trace: 'Private model text.', quality: { ready: true, evidence_status: 'interpretation' },
      } } } }],
  } })
  await page.getByRole('button', { name: /Brand Voice/ }).click()
  await expect(page.getByText('Start with one planter. Watch what grows.', { exact: true })).toBeVisible()
  await expect(page.getByText('Private model text.', { exact: true })).toHaveCount(0)
  expect(errors).toEqual([])
})

test('legacy chat confidence is not resurrected from old history or provider health', async ({ page }) => {
  await mount(page, 'pages/ChatPage', { '/api/mammoth/chat/history': { chat_history: [
    { role: 'user', message: 'Test old history' },
    { role: 'assistant', message: 'Historical response', confidence: .74, adapter: 'deepseek',
      trust_metadata: { confidence: .8 }, runtime_status: { confidence: .99, state: 'ready' } },
  ] } })
  await expect(page.getByText('Historical response', { exact: true })).toBeVisible()
  await expect(page.getByText('Not assessed', { exact: true })).toBeVisible()
  await expect(page.getByText('DeepSeek', { exact: true })).toBeVisible()
  await expect(page.getByText(/74%|80%|99%/)).toHaveCount(0)
})

test('Classic reasoning failures remain visible without a completion toast', async ({ page }) => {
  const errors = await mount(page, 'pages/ChatPage')
  await page.getByRole('button', { name: 'Agent', exact: true }).click()
  await page.getByRole('combobox', { name: 'Mammoth Mind lane' }).selectOption('reasoning_agent')
  const reply = 'Reasoning could not be generated. Retry when a model provider is available.'
  await page.route('**/api/mammoth/chat/stream', route => route.fulfill({
    contentType: 'text/event-stream',
    body: `event: done\ndata: ${JSON.stringify({
      status: 'failed', agent_id: 'reasoning_agent', reply,
      chat_history: [{ role: 'assistant', message: reply, agent_id: 'reasoning_agent',
        trust_metadata: { evidence_status: 'unverified', confidence_status: 'not_assessed' } }],
    })}\n\n`,
  }))
  await page.getByRole('textbox', { name: 'Message MammothOS' }).fill('Compare two approaches')
  await page.getByRole('button', { name: 'Send', exact: true }).click()
  await expect(page.getByText(reply, { exact: true })).toBeVisible()
  await expect(page.getByText('Analysis did not complete. Review the response and retry.')).toBeVisible()
  await expect(page.getByText('Unverified', { exact: true })).toBeVisible()
  await expect(page.getByText('Run complete', { exact: true })).toHaveCount(0)
  expect(errors).toEqual([])
})

test('owner panel hides tenant-denied execution and honestly shows a disabled pilot', async ({ page }) => {
  let errors = await mount(page, ownerPanel, { '/api/owner-executions/capabilities': { status: 403, body: '{"error":"Owner only"}' } })
  await expect(page.getByText('Owner isolated validation pilot')).toHaveCount(0)
  errors = errors.concat(await mount(page, ownerPanel, { '/api/owner-executions/capabilities': { enabled: false, isolation: { ready: false, reason: 'Owner execution pilot is disabled.' } } }))
  await page.getByText('Owner isolated validation pilot').click()
  await expect(page.getByText('Owner execution pilot is disabled.')).toBeVisible()
  await expect(page.getByText('Select a repository first. No default repository is used.')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Prepare proposal' })).toHaveCount(0)
  expect(errors).toEqual([])
})

test('owner panel submits frozen approval and renders unapplied check evidence on mobile', async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 800 })
  let approval
  const errors = await mount(page, ownerPanel, {
    '/api/owner-executions/capabilities': ownerCapabilities,
    '/api/owner-executions': request => {
      const body = request.postDataJSON()
      expect(body.repo_context.root).toBe('owner/repo')
      expect(body.base_sha).toBe(ownerCapabilities.base_sha)
      expect(body.changes[0].path).toBe('app.py')
      expect(body.changes[0].edits).toEqual([{ old: 'return 0', new: 'return 1' }])
      return { status: 'ok', execution: ownerJob }
    },
    [`/api/owner-executions/${ownerJob.id}/approve`]: request => {
      approval = request.postDataJSON()
      return { status: 'ok', execution: { ...ownerJob, status: 'validated', baseline: { passed: false, duration_ms: 10, log: 'baseline fails' }, candidate: { passed: true, duration_ms: 10, log: 'candidate passes' } } }
    },
  }, { repo: 'owner/repo' })
  await page.getByText('Owner isolated validation pilot').click()
  await page.getByRole('textbox').fill('[{"path":"app.py","edits":[{"old":"return 0","new":"return 1"}]}]')
  await page.getByRole('button', { name: 'Prepare proposal' }).click()
  await page.getByRole('button', { name: 'Approve isolated baseline and candidate checks' }).click()
  await expect(page.getByText('validated', { exact: true })).toBeVisible()
  await expect(page.getByText(/Passing a profile is not review approval/)).toBeVisible()
  await expect(page.getByText('candidate: profile passed (10 ms)')).toBeVisible()
  expect(approval).toEqual({ repo_context: { root: 'owner/repo' }, approval_digest: ownerJob.approval_digest })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  expect(errors).toEqual([])
})

test('owner panel surfaces stale approval and cancels the prepared job', async ({ page }) => {
  const errors = await mount(page, ownerPanel, {
    '/api/owner-executions/capabilities': ownerCapabilities,
    '/api/owner-executions': { status: 'ok', execution: ownerJob },
    [`/api/owner-executions/${ownerJob.id}/approve`]: { status: 409, body: '{"status":"error","error":"Repository HEAD changed. Prepare a new proposal."}' },
    [`/api/owner-executions/${ownerJob.id}/cancel`]: { status: 'ok', execution: { ...ownerJob, status: 'cancelled' } },
  }, { repo: 'owner/repo' })
  await page.getByText('Owner isolated validation pilot').click()
  await page.getByRole('button', { name: 'Prepare proposal' }).click()
  await page.getByRole('button', { name: 'Approve isolated baseline and candidate checks' }).click()
  await expect(page.getByRole('alert')).toContainText('HEAD changed')
  await page.getByRole('button', { name: 'Cancel validation' }).click()
  await expect(page.getByText('cancelled', { exact: true })).toBeVisible()
  expect(errors).toEqual([])
})

test('owner panel applies only after a second approval and shows local branch evidence', async ({ page }) => {
  const application = { status: 'ready', branch: `mammoth/owner/${ownerJob.id}`, approval_digest: 'c'.repeat(64), expires_at: 1999999999 }
  let submitted
  await mount(page, ownerPanel, {
    '/api/owner-executions/capabilities': ownerCapabilities,
    '/api/owner-executions': { status: 'ok', execution: ownerJob },
    [`/api/owner-executions/${ownerJob.id}/approve`]: { status: 'ok', execution: { ...ownerJob, status: 'validated', application } },
    [`/api/owner-executions/${ownerJob.id}/apply`]: request => {
      submitted = request.postDataJSON()
      return { status: 'ok', execution: { ...ownerJob, status: 'validated', application: { ...application, status: 'applied', commit_sha: 'd'.repeat(40) } } }
    },
  }, { repo: 'owner/repo' })
  await page.getByText('Owner isolated validation pilot').click()
  await page.getByRole('button', { name: 'Prepare proposal' }).click()
  await expect(page.getByRole('button', { name: 'Approve changes to new branch' })).toHaveCount(0)
  await page.getByRole('button', { name: 'Approve isolated baseline and candidate checks' }).click()
  await page.getByRole('button', { name: 'Approve changes to new branch' }).click()
  await expect(page.getByText('applied', { exact: true })).toBeVisible()
  await expect(page.getByText(/Not pushed or deployed/)).toBeVisible()
  expect(submitted).toEqual({ repo_context: { root: 'owner/repo' }, approval_digest: application.approval_digest })
})

test('owner profile picker disables tools absent from the pinned image', async ({ page }) => {
  await mount(page, ownerPanel, { '/api/owner-executions/capabilities': ownerCapabilities }, { repo: 'owner/repo' })
  await page.getByText('Owner isolated validation pilot').click()
  await expect(page.getByRole('option', { name: 'node_test (unavailable in image)', exact: true })).toHaveJSProperty('disabled', true)
  await expect(page.getByRole('option', { name: 'python_pytest (unavailable in image)', exact: true })).toHaveJSProperty('disabled', true)
  await expect(page.getByRole('option', { name: 'python_unittest', exact: true })).toHaveJSProperty('disabled', false)
  await expect(page.getByText(/ui_build compiles the production UI/)).toBeVisible()
})

test('frontend picker exposes separate locked-image readiness and narrow component coverage', async ({ page }) => {
  const capabilities = {
    ...ownerCapabilities,
    profiles: [...ownerCapabilities.profiles, 'ui_build', 'ui_component'],
    isolation: { ...ownerCapabilities.isolation, profiles: { ...ownerCapabilities.isolation.profiles, ui_build: true, ui_component: false } },
    frontend_isolation: { ready: true, reason: 'Reviewed frontend image checked.' },
  }
  await mount(page, ownerPanel, { '/api/owner-executions/capabilities': capabilities }, { repo: 'owner/repo' })
  await page.getByText('Owner isolated validation pilot').click()
  await expect(page.getByText('Frontend image: Reviewed frontend image checked.')).toBeVisible()
  await expect(page.getByRole('option', { name: 'ui_build', exact: true })).toHaveJSProperty('disabled', false)
  await expect(page.getByRole('option', { name: 'ui_component (unavailable in image)', exact: true })).toHaveJSProperty('disabled', true)
  await expect(page.getByText(/not browser interaction or general acceptance coverage/)).toBeVisible()
})

for (const evidence of ['valid', 'denied', 'mismatched', 'missing-expiry']) {
  test(`Mind apply approval loads full patch and fails closed on invalid evidence (${evidence})`, async ({ page }) => {
    const application = { status: 'ready', branch: `mammoth/owner/${ownerJob.id}`, approval_digest: 'c'.repeat(64), expires_at: 1999999999 }
    await mount(page, 'components/RunTimeline', {
      [`/api/owner-executions/${ownerJob.id}`]: evidence === 'denied' ? { status: 403, body: '{"error":"Owner only"}' }
        : { status: 'ok', execution: { ...ownerJob, status: 'validated',
          application: { ...application, ...(evidence === 'mismatched' ? { approval_digest: 'wrong' } : {}),
            ...(evidence === 'missing-expiry' ? { expires_at: null } : {}) },
          candidate: { passed: true, log: 'Ran fixed checks' } } },
    }, { runOverride: { id: 'run-test', status: 'awaiting_approval', events: [], plan: [], approval: {
      id: 'apr-owner', tool: 'owner_execution_apply', tier: 'exec',
      args: { execution_id: ownerJob.id, approval_digest: application.approval_digest },
    } } })
    const approve = page.getByRole('button', { name: 'Approve changes to new branch' })
    if (evidence !== 'valid') {
      await expect(page.getByRole('alert')).toContainText(evidence === 'denied' ? 'Owner only' : 'Approval no longer matches')
      await expect(approve).toBeDisabled()
      await page.getByRole('button', { name: 'Reject', exact: true }).click()
      expect(await page.evaluate(() => globalThis.ownerApprovalClicks || 0)).toBe(0)
    } else {
      await expect(page.getByRole('region', { name: 'Owner approval evidence' })).toContainText(ownerJob.patch)
      await expect(page.getByText(/Your selected checkout, remote and production deployment stay unchanged/)).toBeVisible()
      await expect(approve).toBeEnabled()
      await approve.click()
      expect(await page.evaluate(() => globalThis.ownerApprovalClicks)).toBe(1)
    }
  })
}

test('Mind approval evidence that stalls times out visibly and recovers on retry', async ({ page }) => {
  const application = { status: 'ready', branch: `mammoth/owner/${ownerJob.id}`, approval_digest: 'c'.repeat(64), expires_at: 1999999999 }
  let calls = 0
  await page.clock.install()
  await page.route(`**/api/owner-executions/${ownerJob.id}`, route => {
    calls++
    if (calls === 1) return
    return route.fulfill({ contentType: 'application/json', body: JSON.stringify({ status: 'ok', execution: {
      ...ownerJob, status: 'validated', application, candidate: { passed: true, log: 'built' } } }) })
  })
  const errors = await mount(page, 'components/RunTimeline', { [`/api/owner-executions/${ownerJob.id}`]: 'fallback' }, { runOverride: { id: 'run-test', status: 'awaiting_approval', events: [], plan: [], approval: {
    id: 'apr-owner', tool: 'owner_execution_apply', tier: 'exec',
    args: { execution_id: ownerJob.id, approval_digest: application.approval_digest },
  } } })
  const approve = page.getByRole('button', { name: 'Approve changes to new branch' })
  await expect(page.getByText('Loading recorded patch and approval evidence...')).toBeVisible()
  await expect(approve).toBeDisabled()
  await page.clock.runFor(20500)
  await expect(page.getByRole('alert')).toContainText('did not load within 20 seconds. Nothing was approved.')
  await expect(approve).toBeDisabled()
  await page.getByRole('button', { name: 'Retry loading evidence' }).click()
  await expect(page.getByRole('region', { name: 'Owner approval evidence' })).toContainText(ownerJob.patch)
  await expect(approve).toBeEnabled()
  expect(calls).toBe(2)
  expect(await page.evaluate(() => globalThis.ownerApprovalClicks || 0)).toBe(0)
  expect(errors).toEqual([])
})

test('Mind apply approval that already expired says so plainly and offers no retry', async ({ page }) => {
  const application = { status: 'ready', branch: `mammoth/owner/${ownerJob.id}`, approval_digest: 'c'.repeat(64), expires_at: 1000000000 }
  const errors = await mount(page, 'components/RunTimeline', {
    [`/api/owner-executions/${ownerJob.id}`]: { status: 'ok', execution: { ...ownerJob, status: 'validated', application, candidate: { passed: true, log: 'built' } } },
  }, { runOverride: { id: 'run-test', status: 'awaiting_approval', events: [], plan: [], approval: {
    id: 'apr-owner', tool: 'owner_execution_apply', tier: 'exec',
    args: { execution_id: ownerJob.id, approval_digest: application.approval_digest },
  } } })
  await expect(page.getByRole('alert')).toContainText('This approval expired at')
  await expect(page.getByRole('alert')).toContainText('Nothing was approved or applied. Reject this request, then start a new run')
  await expect(page.getByRole('button', { name: 'Approve changes to new branch' })).toBeDisabled()
  await expect(page.getByRole('button', { name: 'Retry loading evidence' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Reject', exact: true })).toBeEnabled()
  expect(errors).toEqual([])
})

test('Mind apply approval shows its window and disables Approve when the window closes', async ({ page }) => {
  await page.clock.install({ time: new Date('2026-11-02T05:00:00Z') })
  const expiresAt = Date.parse('2026-11-02T05:01:00Z') / 1000
  const application = { status: 'ready', branch: `mammoth/owner/${ownerJob.id}`, approval_digest: 'c'.repeat(64), expires_at: expiresAt }
  const errors = await mount(page, 'components/RunTimeline', {
    [`/api/owner-executions/${ownerJob.id}`]: { status: 'ok', execution: { ...ownerJob, status: 'validated', application, candidate: { passed: true, log: 'built' } } },
  }, { runOverride: { id: 'run-test', status: 'awaiting_approval', events: [], plan: [], approval: {
    id: 'apr-owner', tool: 'owner_execution_apply', tier: 'exec',
    args: { execution_id: ownerJob.id, approval_digest: application.approval_digest },
  } } })
  const approve = page.getByRole('button', { name: 'Approve changes to new branch' })
  await expect(page.getByText(/Approval window closes at/)).toBeVisible()
  await expect(approve).toBeEnabled()
  await page.clock.runFor(61000)
  await expect(page.getByRole('alert')).toContainText('This approval expired at')
  await expect(approve).toBeDisabled()
  expect(await page.evaluate(() => globalThis.ownerApprovalClicks || 0)).toBe(0)
  expect(errors).toEqual([])
})

test('Agents page drops the right rail and keeps approvals, rollback and history in header panels', async ({ page }) => {
  const calls = {}
  const count = (path, body) => () => { calls[path] = (calls[path] || 0) + 1; return body }
  let approvedPath = ''
  const errors = await mount(page, 'pages/AgentPage', {
    '/api/agents': count('/api/agents', []),
    '/api/activity': count('/api/activity', []),
    '/api/tasks': [],
    '/api/approvals': count('/api/approvals', [{ id: 'ap-1', status: 'pending', operation: 'write_file', target: 'app.py' }]),
    '/api/snapshots': count('/api/snapshots', [{ id: 'snap-1', operation: 'write_file', file_path: 'app.py', existed_before: true, created_at: '2026-11-02T05:00:00Z' }]),
    '/api/autonomous/runs': { runs: [] },
    '/api/workspace/run-history': { entries: [{ id: 'h1', prompt: 'Summarize the build log', agent_id: 'research_agent', created_at: '2026-11-02T05:00:00Z' }] },
    '/api/approvals/ap-1/approve': request => { approvedPath = new URL(request.url()).pathname; return { status: 'ok' } },
  })
  await expect(page.getByRole('heading', { name: /Agents/ })).toBeVisible()
  await expect(page.getByText('Reasoning Trace')).toHaveCount(0)
  await expect(page.getByText('Pending Approvals')).toHaveCount(0)
  const changes = page.getByRole('button', { name: 'Changes, 1 pending approval' })
  await expect(changes).toBeVisible()
  await changes.click()
  const panel = page.getByRole('dialog', { name: 'Changes' })
  await expect(panel).toContainText('Pending Approvals')
  await expect(panel).toContainText('Rollback Snapshots')
  await expect(panel.getByRole('button', { name: 'Restore' })).toBeVisible()
  await panel.getByRole('button', { name: 'Approve' }).click()
  await expect.poll(() => approvedPath).toBe('/api/approvals/ap-1/approve')
  await page.keyboard.press('Escape')
  await expect(panel).toHaveCount(0)
  await page.getByRole('button', { name: 'History & memory' }).click()
  await expect(page.getByRole('dialog', { name: 'History and memory' })).toContainText('Summarize the build log')
  await page.getByRole('button', { name: 'Close panel' }).click()
  await expect(page.getByRole('dialog')).toHaveCount(0)
  const snapshotCalls = calls['/api/snapshots'] || 0
  await page.waitForTimeout(3000)
  expect(calls['/api/snapshots'] || 0).toBe(snapshotCalls)
  expect(errors).toEqual([])
})

test('startup import failure displays recovery instead of a black screen', async ({ page }) => {
  await page.route('**/src/App*', route => route.abort())
  await page.goto(baseURL)
  await expect(page.getByRole('heading', { name: 'MammothOS could not start' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Reload platform' })).toBeVisible()
})

test('semantic palette preserves status colors and measurable text/action contrast', () => {
  const root = path.join(__dirname, '..', 'ui', 'mad-architecht-command-center', 'src')
  const tokens = JSON.parse(fs.readFileSync(path.join(root, 'design', 'tokens.json'), 'utf8')).color
  const value = node => node.$value
  function luminance(hex) {
    const channels = hex.slice(1).match(/../g).map(part => parseInt(part, 16) / 255)
      .map(channel => channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4)
    return channels[0] * 0.2126 + channels[1] * 0.7152 + channels[2] * 0.0722
  }
  function contrast(a, b) {
    const values = [luminance(a), luminance(b)].sort((x, y) => y - x)
    return (values[0] + 0.05) / (values[1] + 0.05)
  }
  for (const surface of Object.values(tokens.surface)) {
    for (const text of Object.values(tokens.text)) expect(contrast(value(text), value(surface))).toBeGreaterThanOrEqual(4.5)
    expect(contrast(value(tokens.agent.default), value(surface))).toBeGreaterThanOrEqual(4.5)
    expect(contrast(value(tokens.system.default), value(surface))).toBeGreaterThanOrEqual(4.5)
  }
  for (const background of [tokens.action.primary, tokens.action.hover]) {
    expect(contrast(value(tokens.action.text), value(background))).toBeGreaterThanOrEqual(4.5)
  }
  expect(value(tokens.status.success)).toBe('#34d399')
  expect(value(tokens.status.warning)).toBe('#f5b942')
  expect(value(tokens.status.danger)).toBe('#f87171')
  expect(value(tokens.border.focus)).toBe(value(tokens.system.default))
  const generated = fs.readFileSync(path.join(root, 'design', 'tokens.css'), 'utf8')
  for (const [name, node] of Object.entries(tokens.action)) {
    if (!name.startsWith('$')) expect(generated).toContain(`--mm-color-action-${name}: ${value(node)};`)
  }
  function inspect(directory) {
    for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
      const file = path.join(directory, entry.name)
      if (entry.isDirectory()) { inspect(file); continue }
      if (!/\.(jsx|js|css)$/.test(entry.name)) continue
      const source = fs.readFileSync(file, 'utf8')
      expect(source, file).not.toMatch(/#(?:b47cff|a78bfa|c4b5fd|818cf8|a855f7|7c3aed|f472b6|00f5d4|22d3ee|2dd4bf)\b/i)
      expect(source, file).not.toMatch(/rgba?\(\s*(?:180,\s*124,\s*255|168,\s*85,\s*247|0,\s*245,\s*212|99,\s*102,\s*241)/)
      expect(source, file).not.toMatch(/\$\{[\w.]*(?:color|accent)\}[0-9a-f]{2}\b/i)
    }
  }
  inspect(root)
})

for (const width of [375, 1280]) {
  test(`Mammoth Mind lane and primary action follow semantic roles at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    await mount(page, 'pages/ChatPage', {
      '/mammoth/chat/threads': { threads: [] },
    })
    const lane = page.getByRole('combobox', { name: 'Mammoth Mind lane' })
    await expect(lane).toBeVisible()
    await expect(lane).toHaveCSS('background-color', 'rgb(13, 17, 23)')
    await expect(lane).toHaveCSS('color', 'rgb(226, 232, 240)')
    await expect(lane).toHaveCSS('min-height', '36px')
    await lane.selectOption('coding_agent')
    await expect(page.getByRole('combobox', { name: 'Coding task' })).toBeVisible()
    await lane.selectOption('assistant')
    await expect(page.getByRole('combobox', { name: 'Coding task' })).toHaveCount(0)
    await lane.focus()
    await page.keyboard.press('Tab')
    await page.keyboard.press('Shift+Tab')
    await expect(lane).toBeFocused()
    await expect(lane).toHaveCSS('outline-color', 'rgb(77, 166, 255)')
    await expect(page.getByRole('button', { name: 'Send', exact: true })).toHaveCSS('background-color', 'rgb(208, 138, 82)')
    await expect(page.getByRole('button', { name: 'Send', exact: true })).toHaveCSS('color', 'rgb(5, 6, 8)')
    const sizes = await page.evaluate(() => ({ scroll: document.documentElement.scrollWidth, viewport: innerWidth }))
    expect(sizes.scroll).toBeLessThanOrEqual(sizes.viewport)
    console.log(`Palette screenshot: ${test.info().outputPath(`palette-chat-${width}.png`)}`)
    await page.screenshot({ path: test.info().outputPath(`palette-chat-${width}.png`), fullPage: true })
  })
}

for (const status of [200, 502, 504]) {
test(`HTML API response ${status} reports path and status without assuming missing configuration`, async ({ page }) => {
  await mount(page, 'auth')
  await page.route('**/api/run', route => route.fulfill({
    status, contentType: 'text/html', body: '<html><body>Gateway error</body></html>',
  }))
  const message = await page.evaluate(async () => {
    const { api } = await import('/src/api/client.js')
    try { await api('/run', { method: 'POST', body: { agent_id: 'coding_agent' } }) }
    catch (error) { return error.message }
  })
  expect(message).toContain(`HTTP ${status} at /api/run`)
  expect(message).not.toContain('Set VITE_MAMMOTH')
  expect(message).toContain(status === 200 ? 'routing' : status === 504 ? 'timed out' : 'unavailable')
})
}

test('Coding failure shows nested output explanation rather than status=error', async ({ page }) => {
  await mount(page, 'components/agent-workspace/AgentWorkspace', {
    '/api/run': { status: 'error', result: { status: 'error', output: {
      summary: 'Generated code failed output validation.',
      warnings: ['LLM returned no implementation code block'],
    }, execution_loop: { verification: { failed_checks: [{ detail: 'status=error' }] } } } },
  })
  await page.getByRole('navigation', { name: 'Agents' }).getByRole('button', { name: /Coding/ }).click()
  await expect(page.getByRole('button', { name: 'Send', exact: true })).toHaveCSS('background-color', 'rgb(22, 27, 34)')
  await page.getByRole('textbox', { name: 'Message Coding' }).fill('Build a utility')
  await expect(page.getByRole('button', { name: 'Send', exact: true })).toHaveCSS('background-color', 'rgb(208, 138, 82)')
  await page.getByRole('button', { name: 'Send', exact: true }).click()
  await expect(page.getByText(/Generated code failed output validation.*no implementation code block/)).toBeVisible()
  await expect(page.getByText('The agent could not complete this request (status=error).')).toHaveCount(0)
})

test('Coding renders advice without code tabs or patch controls', async ({ page }) => {
  await mount(page, 'components/agent-workspace/AgentWorkspace', {
    '/api/run': { status: 'ok', result: { status: 'ok', output: {
      status: 'ok', artifact_type: 'advice', task_kind: 'advice',
      summary: 'Design advice only; no code was generated or files changed.',
      content: '## Recommendation\nKeep brass for primary actions.',
    } } },
  })
  await page.getByRole('navigation', { name: 'Agents' }).getByRole('button', { name: /Coding/ }).click()
  await page.getByRole('textbox', { name: 'Message Coding' }).fill('What are your suggestions?')
  await page.getByRole('button', { name: 'Send', exact: true }).click()
  await expect(page.getByText('Keep brass for primary actions.', { exact: true })).toBeVisible()
  await expect(page.getByText('Design advice only; no code was generated or files changed.')).toBeVisible()
  await expect(page.getByRole('button', { name: /Apply patch/ })).toHaveCount(0)
})

test('partial run shows honest status, credit notice and collapsed diagnostics on mobile', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  const errors = await mount(page, 'components/RunTimeline')
  await expect(page.getByRole('button', { name: /Incomplete/ })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Continue task' })).toBeVisible()
  await expect(page.getByText(/Uses additional model credits/)).toBeVisible()
  await expect(page.getByText('Model call diagnostics')).toHaveCount(0)
  await page.getByRole('button', { name: /Incomplete/ }).click()
  await page.getByText('Model call diagnostics').click()
  await expect(page.getByText(/finish: length/)).toBeVisible()
  await expect(page.getByText(/42 tokens/)).toBeVisible()
  await expect(page.getByText(/protocol: json_schema/)).toBeVisible()
  await page.getByRole('button', { name: 'Continue task' }).click()
  expect(await page.evaluate(() => globalThis.continuationClicks)).toBe(1)
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(375)
  expect(errors).toEqual([])
})

for (const [status, goal, stage, header, blocker] of [
  ['completed', 'answer', 'answer', 'Answered', ''],
  ['partial', 'applied', 'proposal', 'Blocked', 'Application was not approved.'],
  ['completed', 'applied', 'applied', 'Completed', ''],
]) {
  test(`timeline uses recorded ${stage} evidence for ${header} rather than Worked`, async ({ page }) => {
    const application = stage === 'applied' ? { status: 'applied', branch: 'mammoth/owner/test', commit_sha: 'f'.repeat(40) } : null
    const errors = await mount(page, 'components/RunTimeline', {}, { runOverride: {
      id: 'run-test', status, reply: 'Model says done', plan: [],
      events: [{ seq: 1, type: 'tool.call', data: { call_id: 'test', tool: 'owner_execution_apply' } }],
      progress: { goal, stage, goal_met: status === 'completed', blocker,
        executions: application ? [{ id: 'exec-test', status: 'validated', profile: 'ui_component', application }] : [] },
    } })
    await expect(page.getByRole('button', { name: new RegExp(`^${header}`) })).toBeVisible()
    await expect(page.getByRole('region', { name: 'Recorded work progress' })).toContainText(`Goal: ${goal}. Recorded stage: ${stage}.`)
    await expect(page.getByRole('button', { name: /^Worked/ })).toHaveCount(0)
    if (blocker) await expect(page.getByRole('status')).toContainText(blocker)
    if (application) await expect(page.getByText(application.commit_sha)).toBeVisible()
    expect(errors).toEqual([])
  })
}

test('required coding result demands explicit repo then reaches the run API without lowering its goal', async ({ page }) => {
  let submitted
  await mount(page, 'components/agent-workspace/AgentWorkspace', {
    '/api/mammoth/repo-sources': { options: [{ value: 'owner/repo', label: 'Owner repo' }] },
    '/api/mammoth/runs': request => {
      submitted = request.postDataJSON()
      return { contentType: 'text/event-stream', body: `data: ${JSON.stringify({
        contract: 'mammoth.run.v1', run_id: 'run-0123456789abcdef', seq: 1, type: 'run.partial',
        data: { reply: 'Application not completed.', code: 'missing_evidence', can_continue: true,
          progress: { goal: 'applied', stage: 'answer', goal_met: false, blocker: '', executions: [] } },
      })}\n\n` }
    },
  })
  await page.getByRole('navigation', { name: 'Agents' }).getByRole('button', { name: /Coding/ }).click()
  await page.getByRole('combobox', { name: 'Required coding result' }).selectOption('applied')
  await page.getByRole('textbox', { name: 'Message Coding' }).fill('What are your suggestions?')
  await page.getByRole('button', { name: 'Send', exact: true }).click()
  await expect(page.getByText(/required result \(applied\) needs an explicitly selected repository/)).toBeVisible()
  expect(submitted).toBeUndefined()
  await page.getByRole('combobox', { name: 'Repository context' }).selectOption('owner/repo')
  await page.getByRole('textbox', { name: 'Message Coding' }).fill('What are your suggestions?')
  await page.getByRole('button', { name: 'Send', exact: true }).click()
  await expect(page.getByText('Application not completed.', { exact: true })).toBeVisible()
  expect(submitted.completion_goal).toBe('applied')
  expect(submitted.repo_context).toEqual({ root: 'owner/repo' })
})

test('Coding approval works after a terminal event even when the response transport stays open', async ({ page }) => {
  const errors = await mount(page, 'components/agent-workspace/AgentWorkspace', {
    '/api/mammoth/repo-sources': { options: [{ value: 'owner/repo', label: 'Owner repo' }] },
  })
  await page.evaluate(() => {
    const original = globalThis.fetch
    const runId = 'run-0123456789abcdef'
    const encode = events => new TextEncoder().encode(events.map((event, index) =>
      `data: ${JSON.stringify({ ...event, run_id: runId, seq: event.seq || index + 1, contract: 'mammoth.run.v1' })}\n\n`).join(''))
    globalThis.approvalRequests = []
    globalThis.fetch = async (input, init) => {
      const path = new URL(String(input), location.origin).pathname
      if (path === '/api/mammoth/runs') return new Response(new ReadableStream({
        start(controller) {
          controller.enqueue(encode([
            { type: 'run.started', data: {} },
            { type: 'approval.requested', data: { id: 'apr-held', tool: 'owner_execution_prepare', tier: 'write', args: {} } },
            { type: 'run.awaiting_approval', data: {} },
          ]))
        },
        cancel() { globalThis.approvalTransportReleased = true },
      }), { headers: { 'Content-Type': 'text/event-stream' } })
      if (path === `/api/mammoth/runs/${runId}/approval`) {
        globalThis.approvalRequests.push(JSON.parse(init.body))
        return new Response(encode([
          { seq: 4, type: 'approval.resolved', data: { approved: true, tool: 'owner_execution_prepare' } },
          { seq: 5, type: 'run.partial', data: { reply: 'Preparation received; testing still requires separate approval.', code: 'step_limit' } },
        ]), { headers: { 'Content-Type': 'text/event-stream' } })
      }
      return original(input, init)
    }
  })
  await page.getByRole('navigation', { name: 'Agents' }).getByRole('button', { name: /Coding/ }).click()
  await page.getByRole('combobox', { name: 'Required coding result' }).selectOption('applied')
  await page.getByRole('combobox', { name: 'Repository context' }).selectOption('owner/repo')
  await page.getByRole('textbox', { name: 'Message Coding' }).fill('Prepare the inspected edit')
  await page.getByRole('button', { name: 'Send', exact: true }).click()
  const approve = page.getByRole('button', { name: 'Approve', exact: true })
  await expect(approve).toBeEnabled()
  expect(await page.evaluate(() => globalThis.approvalTransportReleased)).toBe(true)
  await approve.click()
  await expect(page.getByText('Preparation received; testing still requires separate approval.', { exact: true })).toBeVisible()
  expect(await page.evaluate(() => globalThis.approvalRequests)).toEqual([
    { approval_id: 'apr-held', decision: 'approve', note: '' },
  ])
  expect(errors).toEqual([])
})

for (const denied of [false, true]) {
test(`Coding saved preparation approval survives reload and reports its backend outcome (${denied ? 'denied' : 'approved'})`, async ({ page }) => {
  const runId = 'run-0123456789abcdef'
  await page.addInitScript(({ runId }) => {
    localStorage.setItem('mammoth_agent_threads_v1:reader:selected', 'coding_agent')
    localStorage.setItem('mammoth_agent_threads_v1:reader', JSON.stringify({ coding_agent: [{
      id: 'saved-approval-message', role: 'agent', agent_id: 'coding_agent', status: 'pending',
      run: { id: runId, status: 'awaiting_approval', events: [], plan: [],
        approval: { id: 'apr-saved', tool: 'owner_execution_prepare', tier: 'write', args: {} } },
    }] }))
  }, { runId })
  let submitted
  const errors = await mount(page, 'components/agent-workspace/AgentWorkspace', {
    [`/api/mammoth/runs/${runId}/approval`]: request => {
      submitted = request.postDataJSON()
      return denied
        ? { status: 409, body: JSON.stringify({ error: 'Repository base changed; prepare a fresh candidate.' }) }
        : { contentType: 'text/event-stream', body: `data: ${JSON.stringify({
          contract: 'mammoth.run.v1', run_id: runId, seq: 1, type: 'run.partial',
          data: { reply: 'Saved approval received.', code: 'step_limit' },
        })}\n\n` }
    },
  })
  await expect(page.getByRole('button', { name: 'Approve', exact: true })).toBeEnabled()
  await page.getByRole('button', { name: 'Approve', exact: true }).click()
  await expect(page.getByText(denied ? /Repository base changed/ : 'Saved approval received.', { exact: !denied })).toBeVisible()
  expect(submitted).toEqual({ approval_id: 'apr-saved', decision: 'approve', note: '' })
  expect(errors).toEqual([])
})
}

test('Coding run approval hands off to apply evidence and shows working state', async ({ page }) => {
  const runId = 'run-0123456789abcdef'
  const application = { status: 'ready', branch: `mammoth/owner/${ownerJob.id}`, approval_digest: 'c'.repeat(64), expires_at: 1999999999 }
  await page.addInitScript(({ runId, ownerJob }) => {
    localStorage.setItem('mammoth_agent_threads_v1:reader:selected', 'coding_agent')
    localStorage.setItem('mammoth_agent_threads_v1:reader', JSON.stringify({ coding_agent: [{
      id: 'saved-run-message', role: 'agent', agent_id: 'coding_agent', status: 'pending',
      run: { id: runId, status: 'awaiting_approval', events: [], plan: [],
        approval: { id: 'apr-run', tool: 'owner_execution_run', tier: 'exec', args: { execution_id: ownerJob.id, approval_digest: ownerJob.approval_digest } } },
    }] }))
  }, { runId, ownerJob })
  let evidenceCalls = 0
  let applied = false
  const errors = await mount(page, 'components/agent-workspace/AgentWorkspace', {
    [`/api/owner-executions/${ownerJob.id}`]: () => {
      evidenceCalls++
      return { status: 'ok', execution: applied
        ? { ...ownerJob, status: 'validated', application, candidate: { passed: true, log: 'built' } }
        : ownerJob }
    },
  })
  await page.evaluate(({ runId, ownerJob, application }) => {
    const original = globalThis.fetch
    const encode = events => new TextEncoder().encode(events.map(event =>
      `data: ${JSON.stringify({ ...event, run_id: runId, contract: 'mammoth.run.v1' })}\n\n`).join(''))
    globalThis.fetch = async (input, init) => {
      const path = new URL(String(input), location.origin).pathname
      if (path === `/api/mammoth/runs/${runId}/approval`) {
        await new Promise(resolve => { globalThis.releaseApproval = resolve })
        return new Response(new ReadableStream({
          start(controller) {
            controller.enqueue(encode([
              { seq: 10, type: 'approval.resolved', data: { approved: true, tool: 'owner_execution_run' } },
              { seq: 11, type: 'tool.call', data: { call_id: 'call-run', tool: 'owner_execution_run', tier: 'exec', args: {} } },
            ]))
            globalThis.finishBuild = () => {
              controller.enqueue(encode([
                { seq: 12, type: 'tool.result', data: { call_id: 'call-run', tool: 'owner_execution_run', status: 'ok', result: { status: 'ok' } } },
                { seq: 13, type: 'approval.requested', data: { id: 'apr-apply', tool: 'owner_execution_apply', tier: 'exec',
                  args: { execution_id: ownerJob.id, approval_digest: application.approval_digest } } },
                { seq: 14, type: 'run.awaiting_approval', data: {} },
              ]))
            }
          },
        }), { headers: { 'Content-Type': 'text/event-stream' } })
      }
      return original(input, init)
    }
  }, { runId, ownerJob, application })
  const approve = page.getByRole('button', { name: 'Approve', exact: true })
  await expect(approve).toBeEnabled()
  await approve.click()
  await expect(page.getByRole('status', { name: 'Run activity', exact: true })).toHaveText('Approval sent — resuming the run…')
  await expect(page.getByRole('button', { name: /^Approve|^Reject/ })).toHaveCount(0)
  await page.evaluate(() => globalThis.releaseApproval())
  await expect(page.getByRole('status', { name: 'Run activity', exact: true })).toContainText(/Validating/)
  await expect(page.getByRole('status', { name: 'Composer run activity' })).toContainText(/Validating/)
  await expect(page.getByRole('button', { name: 'Approve', exact: true })).toHaveCount(0)
  applied = true
  await page.evaluate(() => globalThis.finishBuild())
  await expect(page.getByRole('region', { name: 'Owner approval evidence' })).toContainText(ownerJob.patch)
  await expect(page.getByRole('button', { name: 'Approve changes to new branch' })).toBeEnabled()
  expect(evidenceCalls).toBe(2)
  expect(errors).toEqual([])
})

test('Mammoth Mind continues saved work in the same message without a success toast for partial output', async ({ page }) => {
  const runId = 'run-0123456789abcdef'
  const errors = await mount(page, 'pages/ChatPage', {
    '/api/mammoth/chat/history': { chat_history: [
      { role: 'user', message: 'Inspect my work' },
      { role: 'assistant', message: 'Saved progress', local_id: runId, agent_id: 'assistant',
        run: { id: runId, status: 'partial', can_continue: true, reply: 'Saved progress', events: [], plan: [] } },
    ] },
  })
  await page.route(`**/api/mammoth/runs/${runId}/continue`, route => route.fulfill({
    contentType: 'text/event-stream',
    body: [
      { type: 'run.continued', data: {} },
      { type: 'message.delta', data: { text: 'Finished from saved evidence' } },
      { type: 'run.completed', data: { reply: 'Finished from saved evidence' } },
    ].map((event, idx) => `data: ${JSON.stringify({ ...event, run_id: runId, seq: idx + 1, contract: 'mammoth.run.v1' })}\n\n`).join(''),
  }))
  await expect(page.getByRole('button', { name: 'Continue task' })).toBeVisible()
  await page.getByRole('button', { name: 'Continue task' }).click()
  await expect(page.getByText('Finished from saved evidence', { exact: true }).first()).toBeVisible()
  await expect(page.getByRole('button', { name: 'Continue task' })).toHaveCount(0)
  await expect(page.getByText('Inspect my work', { exact: true })).toHaveCount(1)
  expect(errors).toEqual([])
})

for (const savedTheme of ['aurora', 'midnight']) {
test(`first-load shell migrates ${savedTheme} to dark and opens lazy pages without refresh`, async ({ page }) => {
  const errors = await mount(page, 'App', {
    '/api/entitlements': { admin_controls_enabled: true, tier: 'pro' },
    '/api/flashcards': { cards: [] },
    '/api/buildlog': [],
    '/api/logsale': [],
  }, { savedTheme })
  await expect(page.getByRole('button', { name: 'Flashcards', exact: true })).toBeVisible()
  await expect(page.getByLabel('Color theme')).toHaveCount(0)
  expect(await page.locator('html').evaluate(node => getComputedStyle(node).getPropertyValue('--txt-pri').trim())).toBe('#e2e8f0')
  expect(await page.locator('html').evaluate(node => getComputedStyle(node).colorScheme)).toBe('dark')
  expect(await page.evaluate(() => localStorage.getItem('mammoth-theme'))).toBe('dark')
  await page.getByRole('button', { name: 'Flashcards', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Flashcards', exact: true })).toBeVisible()
  await expect(page.getByText('No answered flashcards yet.', { exact: false })).toBeVisible()
  await expect(page.getByText('Aurora', { exact: true })).toHaveCount(0)
  expect(errors).toEqual([])
})
}

test('Settings reports dark-only appearance without an inactive theme toggle', async ({ page }) => {
  const errors = await mount(page, 'pages/SettingsPage')
  await expect(page.getByText('Dark mode is active.')).toBeVisible()
  await expect(page.getByText('Aurora', { exact: true })).toHaveCount(0)
  expect(errors).toEqual([])
})

test('session rejection is explicit and retry restores the session', async ({ page }) => {
  const errors = await mount(page, 'auth', {}, { authFailure: true })
  await expect(page.getByRole('alert')).toContainText('Could not check your sign-in session')
  await page.getByRole('button', { name: 'Retry sign-in check' }).click()
  await expect(page.getByText('Session ready', { exact: true })).toBeVisible()
  expect(errors).toEqual([])
})

test('a stalled sign-in check times out and remains retryable', async ({ page }) => {
  await page.clock.install()
  await mount(page, 'auth', {}, { stalledAuth: true })
  await expect(page.getByText('Checking session...')).toBeVisible()
  await page.clock.fastForward(15001)
  await expect(page.getByRole('button', { name: 'Retry sign-in check' })).toBeVisible()
  await page.getByRole('button', { name: 'Retry sign-in check' }).click()
  await expect(page.getByText('Session ready', { exact: true })).toBeVisible()
})

test('render failure offers recovery without removing the whole platform', async ({ page }) => {
  await mount(page, 'broken')
  await expect(page.getByRole('alert')).toContainText('This view could not load')
  await expect(page.getByRole('button', { name: 'Reload platform' })).toBeVisible()
})

test('command library uses real theme styles and fits a portrait viewport', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  const errors = await mount(page, 'components/AgentCommandLibrary')
  const dialog = page.getByRole('dialog')
  await expect(dialog).toBeVisible()
  expect(await page.locator('.command-overlay').evaluate(node => getComputedStyle(node).position)).toBe('fixed')
  await expect(page.getByLabel('Filter commands by agent')).toBeVisible()
  await page.getByLabel('Filter commands by agent').focus()
  await page.keyboard.press('Tab')
  await expect(page.getByRole('button', { name: 'Close command library' })).toBeFocused()
  await page.getByLabel('Search commands').fill('refactor')
  await expect(page.getByText('Refactor existing code for clarity and performance')).toBeVisible()
  const bounds = await dialog.boundingBox()
  expect(bounds.x).toBeGreaterThanOrEqual(0)
  expect(bounds.x + bounds.width).toBeLessThanOrEqual(375)
  expect(await page.getByLabel('Filter commands by agent').evaluate(node => getComputedStyle(node).backgroundColor)).toBe('rgb(13, 17, 23)')
  expect(errors).toEqual([])
})

for (const width of [375, 1280]) {
test(`chat at ${width}px keeps a full-width input above one compact composer action row`, async ({ page }) => {
  await page.setViewportSize({ width, height: 812 })
  const errors = await mount(page, 'pages/ChatPage')
  const input = page.getByRole('textbox', { name: 'Message MammothOS' })
  await expect(input).toBeVisible()
  await input.fill('My readable mobile message')
  const controls = [
    page.getByRole('button', { name: 'Attach', exact: true }),
    page.getByRole('button', { name: 'Manage saved files' }),
    page.getByRole('button', { name: 'Prompt templates' }),
    page.getByRole('button', { name: 'Send', exact: true }),
  ]
  const handles = await Promise.all([input, ...controls].map(control => control.elementHandle()))
  // Sample one layout frame rather than mixing positions during composer growth.
  const [bounds, ...controlBounds] = await page.evaluate(
    nodes => nodes.map(node => node.getBoundingClientRect().toJSON()), handles,
  )
  expect(bounds.width).toBeGreaterThan(270)
  expect(bounds.x + bounds.width).toBeLessThanOrEqual(width)
  const rowTops = []
  for (const control of controlBounds) {
    expect(control.y).toBeGreaterThanOrEqual(bounds.y + bounds.height - 1)
    rowTops.push(Math.round(control.y + control.height / 2))
  }
  expect(Math.max(...rowTops) - Math.min(...rowTops)).toBeLessThanOrEqual(2)
  await expect(page.getByText('Upload limits & extraction', { exact: true })).toHaveCount(0)
  await page.getByRole('button', { name: 'Manage saved files' }).click()
  await expect(page.getByText('50 MB per file', { exact: false })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Refresh library' })).toBeVisible()
  expect(await page.getByRole('button', { name: 'Refresh library' }).evaluate(node => getComputedStyle(node).backgroundColor)).toBe('rgb(22, 27, 34)')
  await page.getByRole('button', { name: 'Close file library' }).click()
  await expect(page.getByRole('button', { name: 'Refresh library' })).toHaveCount(0)
  await expect(input).toHaveValue('My readable mobile message')
  expect(await page.locator('body').evaluate(node => node.scrollWidth)).toBeLessThanOrEqual(width)
  expect(errors).toEqual([])
})
}

for (const [width, height] of [[1280, 720], [390, 844]]) {
test(`chat feed gets most of a ${width}x${height} screen with a one-row toolbar and growing input`, async ({ page }) => {
  await page.setViewportSize({ width, height })
  const errors = await mount(page, 'pages/ChatPage', { '/mammoth/chat/threads': { threads: [] } })
  await page.addStyleTag({ content: 'html, body, #root { height: 100%; margin: 0; }' })
  const input = page.getByRole('textbox', { name: 'Message MammothOS' })
  await expect(input).toBeVisible()
  const sidebarToggle = await page.getByRole('button', { name: 'Toggle chat history sidebar' }).boundingBox()
  const more = await page.getByRole('button', { name: 'More chat options' }).boundingBox()
  expect(Math.abs((sidebarToggle.y + sidebarToggle.height / 2) - (more.y + more.height / 2))).toBeLessThanOrEqual(6)
  const composer = await page.getByLabel('Message composer').boundingBox()
  const feedHeight = composer.y - (more.y + more.height)
  expect(feedHeight).toBeGreaterThan(height * 0.6)
  expect(composer.y + composer.height).toBeLessThanOrEqual(height)
  const oneLine = (await input.boundingBox()).height
  await input.fill('line one\nline two\nline three\nline four')
  await expect.poll(async () => (await input.boundingBox()).height).toBeGreaterThan(oneLine + 30)
  await input.fill(Array.from({ length: 30 }, (_, i) => `line ${i}`).join('\n'))
  await expect.poll(async () => (await input.boundingBox()).height).toBeLessThanOrEqual(221)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
  await input.fill('')
  await page.screenshot({ path: test.info().outputPath(`chat-layout-${width}x${height}.png`) })
  expect(errors).toEqual([])
})
}

test('chat templates open from the composer or by typing a slash, and the options menu holds details and delete', async ({ page }) => {
  const errors = await mount(page, 'pages/ChatPage', { '/mammoth/chat/threads': { threads: [] } })
  const input = page.getByRole('textbox', { name: 'Message MammothOS' })
  await page.getByRole('button', { name: 'Prompt templates' }).click()
  const dialog = page.getByRole('dialog', { name: 'Prompt templates' })
  await expect(dialog.getByRole('button', { name: /^\/plan/ })).toBeVisible()
  await expect(dialog.getByText('Deep reasoning', { exact: true })).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(dialog).toHaveCount(0)
  await input.fill('/pl')
  await expect(dialog.getByRole('button', { name: /^\/plan/ })).toBeVisible()
  await expect(dialog.getByRole('button', { name: /^\/guide/ })).toHaveCount(0)
  await expect(dialog.getByText('Deep reasoning', { exact: true })).toHaveCount(0)
  await dialog.getByRole('button', { name: /^\/plan/ }).click()
  await expect(dialog).toHaveCount(0)
  await expect(input).toHaveValue('/plan Build the next MammothOS upgrade slice')
  await expect(input).toBeFocused()
  await input.fill('/x')
  await expect(dialog).toBeVisible()
  await input.fill('hello there')
  await expect(dialog).toHaveCount(0)
  await page.getByRole('button', { name: 'More chat options' }).click()
  const menu = page.getByRole('menu', { name: 'Chat options' })
  await expect(menu.getByRole('menuitem', { name: /Show repo & run details/ })).toBeVisible()
  await expect(menu.getByRole('menuitem', { name: /Delete Chat/ })).toHaveCount(0)
  await menu.getByRole('menuitem', { name: /Show repo & run details/ }).click()
  await expect(menu).toHaveCount(0)
  await expect(page.getByText('Routing Snapshot', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Collapse rail' }).click()
  await expect(page.getByText('Routing Snapshot', { exact: true })).toHaveCount(0)
  await page.getByRole('button', { name: 'More chat options' }).click()
  await expect(page.getByRole('menuitem', { name: /Show repo & run details/ })).toBeVisible()
  await page.mouse.click(5, 5)
  await expect(page.getByRole('menu', { name: 'Chat options' })).toHaveCount(0)
  expect(errors).toEqual([])
})

test('flashcards show produced answers, preserve sources and reset across accounts', async ({ page }) => {
  await mount(page, 'pages/FlashcardsPage', { '/api/flashcards': { cards: [{ q: 'What does protein do?', a: 'Supports tissue growth and repair.', source: { title: 'Nutrition lesson' } }] } })
  await expect(page.getByText('What does protein do?', { exact: true })).toBeVisible()
  await page.getByText('What does protein do?', { exact: true }).click()
  await expect(page.getByText('Supports tissue growth and repair.', { exact: true })).toBeVisible()
  await page.route('**/api/flashcards', route => route.fulfill({ contentType: 'application/json', body: JSON.stringify({ cards: [] }) }))
  await page.evaluate(() => globalThis.switchWorkspaceAccount('another-reader'))
  await expect(page.getByText('No answered flashcards yet.', { exact: false })).toBeVisible()
  await expect(page.getByText('Supports tissue growth and repair.', { exact: true })).toHaveCount(0)
  await expect(page.getByText('What is a closure in JavaScript?', { exact: true })).toHaveCount(0)
})

test('empty or invalid decks never display demo cards or success-shaped fallbacks', async ({ page }) => {
  await mount(page, 'pages/FlashcardsPage', { '/api/flashcards': { cards: [] } })
  await expect(page.getByText('No answered flashcards yet.', { exact: false })).toBeVisible()
  await page.route('**/api/flashcards', route => route.fulfill({ contentType: 'application/json', body: JSON.stringify({ wrong: [] }) }))
  await page.getByRole('button', { name: 'Refresh deck' }).click()
  await expect(page.getByText('The backend returned an invalid flashcard deck.')).toBeVisible()
})

test('lesson notes uses scoped resources and excludes operational plan entries', async ({ page }) => {
  await mount(page, 'pages/LessonNotesPage', { '/api/atlas/lesson-notes': { lessons: [
    { lesson_id: 'plan-4f70ef91', lesson: { title: 'Bed Rock BBQ' }, summary: '{"steps": ["task"]}' },
    { lesson_id: 'lesson-1', lesson: { title: 'Nutrition basics' }, resume_packet: { notes: [{ id: 'note-1', title: 'Protein', preview: 'Protein supports tissue repair.' }] } },
  ] } })
  await expect(page.getByText('Protein supports tissue repair.')).toBeVisible()
  await expect(page.getByText('Bed Rock BBQ')).toHaveCount(0)
})

test('module cards use backend MCP state and explicitly report failed refreshes', async ({ page }) => {
  await mount(page, 'pages/ModulesPage', {
    '/api/modules': [{ id: 'coding_agent', name: 'CodingAgent', status: 'registered' }],
    '/api/mcp/servers': { servers: [{ id: 'browser', label: 'Browser bridge', available: true, enabled: true, status: 'configured', health_verified: false, tools: ['browser_snapshot'] }] },
  })
  await expect(page.getByText('configured', { exact: true })).toBeVisible()
  await expect(page.getByText('configured', { exact: true })).toHaveCSS('color', 'rgb(96, 165, 250)')
  await expect(page.getByText('Connection health not verified;', { exact: false })).toBeVisible()
  await expect(page.getByText('ready', { exact: true })).toHaveCount(0)
  await page.route('**/api/mcp/servers', route => route.fulfill({ contentType: 'application/json', body: JSON.stringify({ servers: [{ id: 'browser', label: 'Browser bridge', status: 'connected', health_verified: true }] }) }))
  await page.getByRole('button', { name: 'Refresh', exact: true }).click()
  await expect(page.getByText('Live MCP handshake verified', { exact: false })).toBeVisible()
  await expect(page.getByText('connected', { exact: true })).toHaveCSS('color', 'rgb(34, 197, 94)')
  await page.route('**/api/modules', route => route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ error: 'Registry unavailable' }) }))
  await page.getByRole('button', { name: 'Refresh', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('Registry unavailable')
  await expect(page.getByText('CodingAgent', { exact: true })).toHaveCount(0)
})

test('task inbox uses backend truth and keeps run-backed statuses read-only', async ({ page }) => {
  let status = 'queued'
  await mount(page, 'pages/TaskInboxPage', {
    '/api/tasks': (request) => {
      if (request.method() === 'POST') {
        const body = JSON.parse(request.postData() || '{}')
        status = body.status
        return { id: 'manual-1', title: 'Inbox card', status, status_editable: true, status_origin: 'manual', details: { source: 'manual_task_card' } }
      }
      return [
        { id: 'run-1', title: 'plan+execute run', status: 'pending_approval', status_editable: false, status_origin: 'run', details: { source: 'plan_execute' } },
        { id: 'manual-1', title: 'Inbox card', status, status_editable: true, status_origin: 'manual', details: { source: 'manual_task_card' } },
      ]
    },
  })
  await expect(page.getByText('2 open')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Pending approval' })).toBeDisabled()
  await expect(page.getByText('Run-backed status', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Queued' }).click()
  await expect(page.getByRole('button', { name: 'In progress' })).toBeVisible()
  await expect(page.getByText('Manual card in progress', { exact: true })).toBeVisible()
})

test('task inbox surfaces backend failures instead of local success fallbacks', async ({ page }) => {
  await mount(page, 'pages/TaskInboxPage', {
    '/api/tasks': {
      status: 503,
      contentType: 'application/json',
      body: JSON.stringify({ error: 'Task API unavailable' }),
    },
  })
  await expect(page.getByRole('alert')).toContainText('Task API unavailable')
  await expect(page.getByText('Task inbox unavailable', { exact: true })).toBeVisible()
})

for (const invalidResponse of [false, true]) {
  test(`task inbox rolls back failed or invalid writes (${invalidResponse}) without overwriting card details`, async ({ page }) => {
    let posted
    await mount(page, 'pages/TaskInboxPage', {
      '/api/tasks': request => {
        if (request.method() === 'POST') {
          posted = JSON.parse(request.postData())
          return invalidResponse ? { unrelated: 'response' } : { status: 503, contentType: 'application/json', body: JSON.stringify({ error: 'Write unavailable' }) }
        }
        return [{ id: 'manual', title: 'Original card', status: 'queued', status_editable: true, details: { prompt: 'Preserve me' } }]
      },
    })
    await page.getByRole('button', { name: 'Queued', exact: true }).click()
    await expect(page.getByRole('alert')).toContainText(invalidResponse ? 'did not confirm' : 'Write unavailable')
    await expect(page.getByRole('button', { name: 'Queued', exact: true })).toBeEnabled()
    expect(posted).toEqual({ id: 'manual', status: 'in_progress' })
  })
}

test('task inbox preserves partial and unknown states and clears recovered load errors', async ({ page }) => {
  let failed = true
  await mount(page, 'pages/TaskInboxPage', {
    '/api/tasks': () => failed
      ? { status: 503, contentType: 'application/json', body: JSON.stringify({ error: 'Temporarily unavailable' }) }
      : [{ id: 'partial', title: 'Partial run', status: 'partial' }, { id: 'unknown', title: 'Old run', status: 'unrecognized' }],
  })
  await expect(page.getByRole('alert')).toBeVisible()
  failed = false
  await page.getByRole('button', { name: 'Sync', exact: true }).click()
  await expect(page.getByRole('alert')).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Partial', exact: true })).toBeDisabled()
  await expect(page.getByRole('button', { name: 'Unknown', exact: true })).toBeDisabled()
})
