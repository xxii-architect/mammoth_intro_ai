const { test, expect } = require('@playwright/test')
const baseURL = process.env.ATLAS_UI_URL || 'http://127.0.0.1:5194'

async function mount(page, component, payloads = {}, { authFailure = false, stalledAuth = false, savedTheme = '' } = {}) {
  const errors = []
  page.on('pageerror', error => errors.push(error.message))
  await page.route('**/src/main.jsx', route => route.fulfill({ contentType: 'application/javascript', body: '' }))
  await page.route(url => url.pathname.startsWith('/api/'), route => {
    const path = new URL(route.request().url()).pathname
    const result = payloads[path] || (path.endsWith('/capabilities')
      ? { extensions: ['.pdf'], max_file_bytes: 50 * 1048576, max_storage_bytes: 500 * 1048576, usage: {} }
      : {})
    return route.fulfill({ contentType: 'application/json', body: JSON.stringify(result) })
  })
  await page.goto(baseURL)
  await page.evaluate(async ({ component, authFailure, stalledAuth, savedTheme }) => {
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
    const props = component === 'components/AgentCommandLibrary' ? { onClose() {} }
      : component === 'components/RunTimeline' ? {
        run: { id: 'run-test', status: 'partial', can_continue: true, events: [], plan: [], diagnostics: [
          { provider: 'test-provider', model: 'test-model', finish_reason: 'length', decision_protocol: 'json_schema', usage: { total_tokens: 42 } },
        ] },
        onContinue() { globalThis.continuationClicks = (globalThis.continuationClicks || 0) + 1 },
      } : {}
    document.body.innerHTML = '<div id="root"></div>'
    ReactDOM.createRoot(document.getElementById('root')).render(
      React.createElement(Boundary, null, React.createElement(AuthProvider, null, React.createElement(View, props))),
    )
  }, { component, authFailure, stalledAuth, savedTheme })
  return errors
}

test('startup import failure displays recovery instead of a black screen', async ({ page }) => {
  await page.route('**/src/App*', route => route.abort())
  await page.goto(baseURL)
  await expect(page.getByRole('heading', { name: 'MammothOS could not start' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Reload platform' })).toBeVisible()
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
  await expect(page.getByText('Connection health not verified;', { exact: false })).toBeVisible()
  await expect(page.getByText('ready', { exact: true })).toHaveCount(0)
  await page.route('**/api/mcp/servers', route => route.fulfill({ contentType: 'application/json', body: JSON.stringify({ servers: [{ id: 'browser', label: 'Browser bridge', status: 'connected', health_verified: true }] }) }))
  await page.getByRole('button', { name: 'Refresh', exact: true }).click()
  await expect(page.getByText('Live MCP handshake verified', { exact: false })).toBeVisible()
  await page.route('**/api/modules', route => route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ error: 'Registry unavailable' }) }))
  await page.getByRole('button', { name: 'Refresh', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('Registry unavailable')
  await expect(page.getByText('CodingAgent', { exact: true })).toHaveCount(0)
})
