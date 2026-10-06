const { test, expect } = require('@playwright/test')

const baseURL = process.env.ATLAS_UI_URL || 'http://127.0.0.1:5194'
const agentIds = ['tutor_agent', 'curriculum_agent', 'research_agent', 'reflection_agent', 'coding_agent', 'browser_agent']

async function mountWorkspace(page, { catalogFailure = false, agents = agentIds, regular = false } = {}) {
  const requests = []
  const errors = []
  page.on('pageerror', error => errors.push(error.message))
  let lessonId = 'lesson-1'
  let starterResponse = ''
  let chatHistory = []
  const snapshot = () => ({
    lesson_id: lessonId,
    current_lesson: { title: lessonId === 'lesson-1' ? 'Reliable research' : 'Check your sources', content: 'Compare primary sources before drawing conclusions.', summary: 'Evaluate evidence.' },
    current_exercise: { exercise_type: 'writing', prompt: 'Explain how you verify a claim.', starter_response: starterResponse },
    lesson_history: [], available_modules: [], learner: {}, comprehension_gate: {}, chat_history: chatHistory,
  })
  await page.route('**/src/main.jsx', route => route.fulfill({ contentType: 'application/javascript', body: '' }))
  await page.route(url => url.pathname.startsWith('/api/'), async route => {
    const path = new URL(route.request().url()).pathname
    const body = route.request().postDataJSON()
    requests.push({ path, body, headers: route.request().headers() })
    let result = {}
    if (path === '/api/atlas/status') result = snapshot()
    if (path === '/api/atlas/agents') {
      if (catalogFailure) return route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Catalog unavailable' }) })
      result = { agents: agents.map(id => ({ id, name: id, status: 'ready', capabilities: [] })) }
    }
    if (path === '/api/atlas/submit') result = { result: { passed: false, hint: 'Include a primary source.' } }
    if (path === '/api/atlas/lesson') {
      lessonId = 'lesson-2'
      result = { status: 'ok', exercise: snapshot().current_exercise }
    }
    if (path === '/api/atlas/regenerate') {
      starterResponse = 'A new exercise variant'
      result = { exercise: snapshot().current_exercise }
    }
    if (path === '/api/atlas/chat') {
      chatHistory = [...chatHistory, { role: 'user', message: body.message }, { role: 'assistant', message: 'Compare the original evidence with an independent source.' }]
      result = { chat_history: chatHistory }
    }
    if (path === '/api/atlas/next') {
      if (!body?.override) result = { status: 'gated', gate: { message: 'Practice first.', allowed: false } }
      else { lessonId = 'lesson-2'; result = { status: 'ok' } }
    }
    if (path === '/api/run') result = { status: 'ok', result: { output: {
      artifact_type: 'long_form_research', title: 'Source validation report', abstract: 'Research findings from the lesson.',
      sections: [{ order: 0, heading: 'Evidence', content: 'Check primary evidence.' }],
      sources: [], docx_filename: 'lesson-research.docx',
    } } }
    if (path === '/api/download-docx/lesson-research.docx') {
      return route.fulfill({ contentType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', body: Buffer.from('test-only-document-download') })
    }
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(result) })
  })
  await page.goto(baseURL)
  await page.evaluate(async ({ regular, agents }) => {
    const { supabase } = await import('/src/lib/supabase.js')
    const session = { user: { id: 'learner-test' }, access_token: 'test-only-access-token' }
    supabase.auth.getSession = async () => ({ data: { session }, error: null })
    supabase.auth.onAuthStateChange = callback => {
      globalThis.changeTestAccount = id => callback('SIGNED_IN', { user: { id } })
      return { data: { subscription: { unsubscribe() {} } } }
    }
    const { default: React } = await import('/node_modules/.vite/deps/react.js')
    const { default: ReactDOM } = await import('/node_modules/.vite/deps/react-dom_client.js')
    const { AuthProvider } = await import('/src/lib/authContext.jsx')
    const { default: Workspace } = await import('/src/pages/AtlasWorkspacePage.jsx')
    const { default: AgentWorkspace } = await import('/src/components/agent-workspace/AgentWorkspace.jsx')
    await import('/src/index.css')
    document.body.innerHTML = '<div id="test-root" style="height:100vh"></div>'
    const workspace = regular ? React.createElement(AgentWorkspace, { agents: agents.map(id => ({ id, status: 'ready' })), temperature: 0.3, approvalMode: true }) : React.createElement(Workspace)
    ReactDOM.createRoot(document.getElementById('test-root')).render(React.createElement(AuthProvider, null, workspace))
  }, { regular, agents })
  if (!regular) await expect(page.getByRole('heading', { name: 'ATLAS', exact: true })).toBeVisible()
  return { requests, errors }
}

test('lesson drafts survive tabs; research stays scoped and receives lesson context', async ({ page }) => {
  const { requests, errors } = await mountWorkspace(page)
  const response = page.getByRole('region', { name: 'Lesson and practice' }).locator('textarea')
  await response.fill('My source comparison draft')
  await page.getByRole('button', { name: 'ATLAS Tutor', exact: true }).click()
  await expect(page.getByRole('region', { name: 'ATLAS tutor conversation' })).toBeVisible()
  await page.getByRole('button', { name: 'Lesson & practice', exact: true }).click()
  await expect(response).toHaveValue('My source comparison draft')
  await page.getByRole('button', { name: 'Learning agents', exact: true }).click()
  await expect(page.getByRole('button', { name: /Team run/i })).toHaveCount(0)
  await expect(page.getByText('Custodial', { exact: true })).toHaveCount(0)
  const composer = page.getByRole('region', { name: 'Education agents' }).locator('textarea').last()
  await composer.fill('Find primary research on source validation')
  await composer.press('Enter')
  await expect.poll(() => requests.some(request => request.path === '/api/run')).toBe(true)
  const request = requests.find(request => request.path === '/api/run').body
  expect(request.agent_id).toBe('research_agent')
  expect(request.payload.prompt).toBe('Find primary research on source validation')
  expect(request.payload.background).toContain('Reliable research')
  expect(request.payload.lesson_id).toBe('lesson-1')
  await expect(page.getByRole('heading', { name: 'Source validation report' })).toBeVisible()
  const downloadPromise = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Download DOCX', exact: true }).click()
  expect((await downloadPromise).suggestedFilename()).toBe('lesson-research.docx')
  expect(requests.find(request => request.path === '/api/download-docx/lesson-research.docx').headers.authorization).toBe('Bearer test-only-access-token')
  await page.getByRole('button', { name: 'Lesson & practice', exact: true }).click()
  await expect(response).toHaveValue('My source comparison draft')
  expect(errors).toEqual([])
})

test('mobile switches primary panes without horizontal overflow and isolates accounts', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  const { errors } = await mountWorkspace(page)
  const response = page.getByRole('region', { name: 'Lesson and practice' }).locator('textarea')
  await response.fill('Private learner draft')
  await page.getByRole('button', { name: 'Consult tutor', exact: true }).click()
  await expect(page.getByRole('region', { name: 'Lesson and practice' })).toBeHidden()
  await expect(page.getByRole('region', { name: 'ATLAS tutor conversation' })).toBeVisible()
  await page.getByRole('button', { name: 'Learning agents', exact: true }).click()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.getByRole('button', { name: 'ATLAS Tutor', exact: true }).click()
  await page.getByRole('button', { name: 'Advanced tutor tools', exact: true }).click()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.evaluate(() => globalThis.changeTestAccount('another-learner'))
  await expect(response).toHaveValue('')
  expect(errors).toEqual([])
})

test('desktop can consult tutor beside the lesson without losing its draft', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 })
  const { requests, errors } = await mountWorkspace(page)
  const lesson = page.getByRole('region', { name: 'Lesson and practice' })
  await lesson.locator('textarea').fill('Keep this draft')
  await page.getByRole('button', { name: 'Consult tutor', exact: true }).click()
  await expect(lesson).toBeVisible()
  const tutor = page.getByRole('region', { name: 'ATLAS tutor conversation' })
  await expect(tutor).toBeVisible()
  await tutor.getByPlaceholder('Ask ATLAS Tutor…').fill('How do I compare these sources?')
  await tutor.getByPlaceholder('Ask ATLAS Tutor…').press('Enter')
  await expect(tutor.getByText('Compare the original evidence with an independent source.', { exact: true })).toBeVisible()
  const request = requests.find(request => request.path === '/api/atlas/chat').body
  expect(request.mode).toBe('tutor')
  expect(request.page_context.lesson.lesson_id).toBe('lesson-1')
  await page.getByRole('button', { name: 'Hide tutor', exact: true }).click()
  await expect(lesson.locator('textarea')).toHaveValue('Keep this draft')
  expect(errors).toEqual([])
})

test('unavailable catalog is an explicit retryable error', async ({ page }) => {
  await mountWorkspace(page, { catalogFailure: true })
  await page.getByRole('button', { name: 'Learning agents', exact: true }).click()
  await expect(page.getByRole('alert').filter({ hasText: 'Catalog unavailable' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Retry catalog' })).toBeVisible()
})

test('corrections appear in the lesson pane; next retains an explicit mastery override', async ({ page }) => {
  const { requests, errors } = await mountWorkspace(page)
  const lesson = page.getByRole('region', { name: 'Lesson and practice' })
  const response = lesson.locator('textarea')
  await response.fill('My first attempt')
  await lesson.getByRole('button', { name: 'Submit response', exact: true }).click()
  await expect(lesson.getByText('Include a primary source.', { exact: true })).toBeVisible()
  expect(requests.find(request => request.path === '/api/atlas/submit').body.response).toBe('My first attempt')
  await lesson.getByRole('button', { name: 'Next', exact: true }).click()
  await expect(page.getByRole('alertdialog', { name: 'Lesson not passed yet' })).toBeVisible()
  await expect(response).toHaveValue('My first attempt')
  await page.getByRole('button', { name: 'Continue anyway' }).click()
  await expect(page.locator('.atlas-workspace-header')).toContainText('Check your sources')
  await expect(response).toHaveValue('')
  await expect(lesson.getByText('Include a primary source.', { exact: true })).toHaveCount(0)
  expect(requests.filter(request => request.path === '/api/atlas/next').map(request => request.body)).toEqual([{}, { override: true }])
  expect(errors).toEqual([])
})

test('scoped workspace selects an available agent when research is absent', async ({ page }) => {
  const { requests, errors } = await mountWorkspace(page, { agents: ['tutor_agent'] })
  await page.getByRole('button', { name: 'Learning agents', exact: true }).click()
  const composer = page.getByRole('region', { name: 'Education agents' }).locator('textarea').last()
  await composer.fill('Explain the lesson')
  await composer.press('Enter')
  await expect.poll(() => requests.some(request => request.path === '/api/run')).toBe(true)
  expect(requests.find(request => request.path === '/api/run').body.agent_id).toBe('tutor_agent')
  expect(errors).toEqual([])
})

test('starting a lesson updates the tutor and learning-agent context immediately', async ({ page }) => {
  const { requests, errors } = await mountWorkspace(page)
  await page.getByPlaceholder('e.g. Python for loops').fill('Source validation')
  await page.getByRole('button', { name: 'Start Lesson', exact: true }).click()
  await expect(page.locator('.atlas-workspace-header')).toContainText('Check your sources')
  await page.getByRole('button', { name: 'Learning agents', exact: true }).click()
  const composer = page.getByRole('region', { name: 'Education agents' }).locator('textarea').last()
  await composer.fill('Explain this new lesson')
  await composer.press('Enter')
  await expect.poll(() => requests.some(request => request.path === '/api/run')).toBe(true)
  expect(requests.find(request => request.path === '/api/run').body.payload.lesson_id).toBe('lesson-2')
  expect(errors).toEqual([])
})

test('an advanced tutor exercise variant also refreshes the lesson pane', async ({ page }) => {
  const { errors } = await mountWorkspace(page)
  await page.getByRole('button', { name: 'ATLAS Tutor', exact: true }).click()
  await page.getByRole('button', { name: 'Advanced tutor tools', exact: true }).click()
  await page.getByRole('button', { name: 'Show advanced', exact: true }).click()
  await page.getByRole('button', { name: 'New Variant', exact: true }).click()
  await page.getByRole('button', { name: 'Lesson & practice', exact: true }).click()
  await expect(page.getByRole('region', { name: 'Lesson and practice' }).locator('textarea')).toHaveValue('A new exercise variant')
  expect(errors).toEqual([])
})

test('the general Agent workspace retains its team-run control', async ({ page }) => {
  const { errors } = await mountWorkspace(page, { regular: true })
  await expect(page.getByRole('button', { name: /Team run/i })).toBeVisible()
  expect(errors).toEqual([])
})

test('mentions cannot target an unregistered learning agent', async ({ page }) => {
  const { requests, errors } = await mountWorkspace(page, { agents: ['tutor_agent'] })
  await page.getByRole('button', { name: 'Learning agents', exact: true }).click()
  const region = page.getByRole('region', { name: 'Education agents' })
  await region.locator('textarea').last().fill('@research Find a source')
  await region.locator('textarea').last().press('Enter')
  await expect(region.getByText('That learning agent is not registered. Choose one of the agents shown here.')).toBeVisible()
  expect(requests.some(request => request.path === '/api/run')).toBe(false)
  expect(errors).toEqual([])
})
