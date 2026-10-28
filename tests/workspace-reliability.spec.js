const { test, expect } = require('@playwright/test')
const fs = require('node:fs')
const path = require('node:path')
const baseURL = process.env.ATLAS_UI_URL || 'http://127.0.0.1:5194'

async function mount(page, component, payloads = {}, { authFailure = false, stalledAuth = false, savedTheme = '', repo = '', runOverride = null } = {}) {
  const errors = []
  page.on('pageerror', error => errors.push(error.message))
  await page.route('**/src/main.jsx', route => route.fulfill({ contentType: 'application/javascript', body: '' }))
  await page.route(url => url.pathname.startsWith('/api/'), route => {
    const path = new URL(route.request().url()).pathname
    const configured = payloads[path]
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
  await page.evaluate(async ({ component, authFailure, stalledAuth, savedTheme, repo, runOverride }) => {
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
      : (await import(`/src/${component}.jsx`)).default
    const props = component === 'components/agent-workspace/OwnerExecutionPanel' ? { repo }
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
  }, { component, authFailure, stalledAuth, savedTheme, repo, runOverride })
  return errors
}

const ownerPanel = 'components/agent-workspace/OwnerExecutionPanel'
const ownerCapabilities = { status: 'ok', enabled: true, isolation: { ready: true, reason: 'Pinned Linux image available.', profiles: { python_unittest: true, python_pytest: false, node_test: false } }, profiles: ['python_unittest', 'python_pytest', 'node_test'], base_sha: 'a'.repeat(40) }
const ownerJob = { id: `exec-${'a'.repeat(24)}`, status: 'pending_approval', patch: '--- a/app.py\n+++ b/app.py\n-return 0\n+return 1\n', base_sha: 'a'.repeat(40), profile: 'python_unittest', approval_digest: 'b'.repeat(64), expires_at: 1999999999 }

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
      return { status: 'ok', execution: ownerJob }
    },
    [`/api/owner-executions/${ownerJob.id}/approve`]: request => {
      approval = request.postDataJSON()
      return { status: 'ok', execution: { ...ownerJob, status: 'validated', baseline: { passed: false, duration_ms: 10, log: 'baseline fails' }, candidate: { passed: true, duration_ms: 10, log: 'candidate passes' } } }
    },
  }, { repo: 'owner/repo' })
  await page.getByText('Owner isolated validation pilot').click()
  await page.getByRole('textbox').fill('[{"path":"app.py","content":"return 1\\n"}]')
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
  await expect(page.getByText(/These test profiles do not run the UI build/)).toBeVisible()
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
test(`chat at ${width}px keeps full-width input below one attachment and send toolbar`, async ({ page }) => {
  await page.setViewportSize({ width, height: 812 })
  const errors = await mount(page, 'pages/ChatPage')
  const input = page.getByRole('textbox', { name: 'Message MammothOS' })
  await expect(input).toBeVisible()
  await input.fill('My readable mobile message')
  const bounds = await input.boundingBox()
  expect(bounds.width).toBeGreaterThan(270)
  expect(bounds.x + bounds.width).toBeLessThanOrEqual(width)
  for (const control of [
    page.getByRole('button', { name: 'Attach', exact: true }),
    page.getByRole('button', { name: 'Manage saved files' }),
    page.getByText('Upload limits & extraction', { exact: true }),
    page.getByRole('button', { name: 'Send', exact: true }),
  ]) {
    const toolbarBounds = await control.boundingBox()
    expect(toolbarBounds.y + toolbarBounds.height).toBeLessThanOrEqual(bounds.y)
  }
  await page.getByText('Upload limits & extraction', { exact: true }).click()
  await expect(page.getByText('50 MB per file', { exact: false })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Manage saved files' })).toHaveCount(1)
  await page.getByRole('button', { name: 'Manage saved files' }).click()
  await expect(page.getByRole('button', { name: 'Refresh library' })).toBeVisible()
  expect(await page.getByRole('button', { name: 'Refresh library' }).evaluate(node => getComputedStyle(node).backgroundColor)).toBe('rgb(22, 27, 34)')
  await expect(input).toHaveValue('My readable mobile message')
  expect(await page.locator('body').evaluate(node => node.scrollWidth)).toBeLessThanOrEqual(width)
  expect(errors).toEqual([])
})
}

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
