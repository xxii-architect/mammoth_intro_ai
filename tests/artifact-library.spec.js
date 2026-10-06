const { test, expect } = require('@playwright/test')

const baseURL = process.env.ATLAS_UI_URL || 'http://127.0.0.1:5194'
const categories = [
  ['curricula', 'Curricula'], ['lessons', 'Lessons'], ['research', 'Research & reports'],
  ['notes', 'Notes'], ['flashcards', 'Flashcards'], ['code', 'Code & patch proposals'],
  ['plans', 'Plans'], ['uncategorized', 'Uncategorized'],
].map(([id, label]) => ({ id, label }))
const fixtures = [
  { id: 'research', title: 'Nutrition research', body: 'Sources and evidence\nDetailed findings.', category: 'research', artifact_status: 'draft', agent_id: 'research_agent', format: 'md', created_at: '2026-10-05T12:00:00', docx_filename: 'nutrition.docx', origin: { page: 'agent', trace_id: 'run-one' } },
  { id: 'code', title: 'Parser patch', body: 'A proposal, not applied.', category: 'code', artifact_status: 'failed', agent_id: 'coding_agent', created_at: '2026-10-02T12:00:00' },
  { id: 'old', title: 'Legacy output', body: 'Original legacy text.', category: 'uncategorized', artifact_status: 'unknown', created_at: 'invalid-date' },
  { id: 'lesson', title: 'Variable practice', body: 'Explain assignment.', category: 'lessons', artifact_status: 'ready', agent_id: 'tutor_agent', created_at: '2026-10-04T12:00:00', origin: { page: 'atlas', lesson_id: 'lesson-one' } },
]

async function mountLibrary(page, { loadFailure = false, deleteFailure = false, curriculaFailure = false, docxFailure = false } = {}) {
  let outputs = fixtures.map(item => ({ ...item }))
  const requests = []
  const errors = []
  page.on('pageerror', error => errors.push(error.message))
  await page.route('**/src/main.jsx', route => route.fulfill({ contentType: 'application/javascript', body: '' }))
  await page.route(url => url.pathname.startsWith('/api/'), async route => {
    const request = route.request()
    const path = new URL(request.url()).pathname
    requests.push({ path, method: request.method(), headers: request.headers() })
    const account = request.headers().authorization
    let data
    if (path.startsWith('/api/download-docx/')) {
      return route.fulfill({ status: docxFailure ? 404 : 200, contentType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', body: Buffer.from(docxFailure ? 'Expired' : 'test-only-document') })
    }
    if (path === '/api/atlas/curricula') {
      if (curriculaFailure) return route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Course store unavailable' }) })
      data = { curricula: account === 'Bearer second-account' ? [] : [{
        saved_at: '2026-10-05T14:00:00', curriculum: { curriculum_id: 'nutrition-course', title: 'Nutrition course', subject: 'Nutrition', quality: { ready: false }, modules: [] },
      }] }
    } else if (request.method() === 'DELETE') {
      if (deleteFailure) return route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Delete failed' }) })
      outputs = path === '/api/workspace/artifacts' ? [] : outputs.filter(item => item.id !== path.split('/').at(-1))
      data = { status: 'ok' }
    } else {
      if (loadFailure) return route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Index unavailable' }) })
      data = { artifacts: account === 'Bearer second-account' ? [] : outputs, categories }
    }
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(data) })
  })
  await page.goto(baseURL)
  await page.evaluate(async () => {
    localStorage.setItem('mammoth_artifact_library_v1', JSON.stringify([{ title: 'Other account cached secret', body: 'Never display' }]))
    const { supabase } = await import('/src/lib/supabase.js')
    let session = { user: { id: 'first-account' }, access_token: 'test-only-token' }
    supabase.auth.getSession = async () => ({ data: { session }, error: null })
    supabase.auth.onAuthStateChange = callback => {
      globalThis.changeArtifactAccount = () => {
        session = { user: { id: 'second-account' }, access_token: 'second-account' }
        callback('SIGNED_IN', session)
      }
      return { data: { subscription: { unsubscribe() {} } } }
    }
    const { default: React } = await import('/node_modules/.vite/deps/react.js')
    const { default: ReactDOM } = await import('/node_modules/.vite/deps/react-dom_client.js')
    const { AuthProvider } = await import('/src/lib/authContext.jsx')
    const { default: Library } = await import('/src/pages/ArtifactLibraryPage.jsx')
    await import('/src/index.css')
    document.body.innerHTML = '<div id="test-root"></div>'
    ReactDOM.createRoot(document.getElementById('test-root')).render(React.createElement(AuthProvider, null,
      React.createElement(Library, { setPage: page => { globalThis.artifactDestination = page } })))
  })
  await expect(page.getByRole('heading', { name: 'Artifact library' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Refresh library' })).toBeEnabled()
  return { requests, errors }
}

test('categories, combined filters and legacy status organize real saved items', async ({ page }) => {
  const { errors } = await mountLibrary(page)
  await expect(page.getByRole('article')).toHaveCount(5)
  await page.getByRole('button', { name: 'Research & reports (1)', exact: true }).click()
  await expect(page.getByRole('article')).toHaveCount(1)
  await page.getByRole('combobox', { name: 'Agent', exact: true }).selectOption('research_agent')
  await page.getByRole('combobox', { name: 'Status', exact: true }).selectOption('draft')
  await page.getByLabel('From date').fill('2026-10-05')
  await page.getByLabel('To date').fill('2026-10-05')
  await page.getByLabel('Search artifacts').fill('evidence')
  await expect(page.getByRole('article', { name: 'Nutrition research' })).toBeVisible()
  await page.getByLabel('From date').fill('2026-10-06')
  await expect(page.getByRole('alert')).toContainText('Start date')
  await page.getByRole('button', { name: 'Reset filters' }).click()
  await page.getByRole('button', { name: 'Uncategorized (1)', exact: true }).click()
  await expect(page.getByRole('article')).toContainText('Not assessed')
  await expect(page.getByRole('article')).toContainText('Date unavailable')
  expect(errors).toEqual([])
})

test('curricula stay previewable and exportable without destructive library actions', async ({ page }) => {
  const { requests } = await mountLibrary(page)
  await page.getByRole('button', { name: 'Curricula (1)', exact: true }).click()
  const course = page.getByRole('article', { name: 'Nutrition course' })
  await expect(course).toContainText('Draft')
  await expect(course.getByRole('button', { name: 'Remove', exact: true })).toHaveCount(0)
  const [download] = await Promise.all([page.waitForEvent('download'), course.getByRole('button', { name: 'Download JSON', exact: true }).click()])
  expect(download.suggestedFilename()).toBe('atlas-curriculum.json')
  await course.getByRole('button', { name: 'Open ATLAS', exact: true }).click()
  expect(await page.evaluate(() => globalThis.artifactDestination)).toBe('atlas')
  await page.getByRole('button', { name: 'Clear saved outputs' }).click()
  await page.getByRole('button', { name: 'Confirm removal' }).click()
  await expect(page.getByRole('article', { name: 'Nutrition course' })).toBeVisible()
  expect(requests.filter(item => item.method === 'DELETE').map(item => item.path)).toEqual(['/api/workspace/artifacts'])
})

test('preview, text and authenticated DOCX downloads retain original output', async ({ page }) => {
  const { requests } = await mountLibrary(page)
  const report = page.getByRole('article', { name: 'Nutrition research' })
  await report.getByText('Preview artifact', { exact: true }).click()
  await expect(report.locator('pre')).toHaveText('Sources and evidence\nDetailed findings.')
  await report.getByRole('button', { name: 'Open Agent workspace' }).click()
  expect(await page.evaluate(() => globalThis.artifactDestination)).toBe('agent')
  const [text] = await Promise.all([page.waitForEvent('download'), report.getByRole('button', { name: 'Download text' }).click()])
  expect(text.suggestedFilename()).toBe('Nutrition-research.md')
  const [docx] = await Promise.all([page.waitForEvent('download'), report.getByRole('button', { name: 'Download DOCX' }).click()])
  expect(docx.suggestedFilename()).toBe('nutrition.docx')
  expect(requests.find(item => item.path.endsWith('nutrition.docx')).headers.authorization).toBe('Bearer test-only-token')
})

test('failed deletes do not remove records and clearing requires confirmation', async ({ page }) => {
  await mountLibrary(page, { deleteFailure: true })
  const report = page.getByRole('article', { name: 'Nutrition research' })
  await report.getByRole('button', { name: 'Remove', exact: true }).click()
  await expect(report).toBeVisible()
  await page.getByRole('button', { name: 'Confirm removal' }).click()
  await expect(page.getByRole('alert')).toContainText('Delete failed')
  await expect(report).toBeVisible()
  await page.getByRole('button', { name: 'Cancel', exact: true }).click()
  await page.getByRole('button', { name: 'Clear saved outputs' }).click()
  await page.getByRole('button', { name: 'Cancel', exact: true }).click()
  await expect(page.getByRole('article')).toHaveCount(5)
})

test('backend failure is visible and never exposes the unscoped browser cache', async ({ page }) => {
  await mountLibrary(page, { loadFailure: true })
  await expect(page.getByRole('alert')).toContainText('Index unavailable')
  await expect(page.getByText('Other account cached secret')).toHaveCount(0)
  await expect(page.getByRole('article', { name: 'Nutrition course' })).toBeVisible()
})

test('partial curriculum and document errors remain explicit', async ({ page }) => {
  await mountLibrary(page, { curriculaFailure: true, docxFailure: true })
  await expect(page.getByRole('alert')).toContainText('Course store unavailable')
  await expect(page.getByRole('article')).toHaveCount(4)
  await page.getByRole('article', { name: 'Nutrition research' }).getByRole('button', { name: 'Download DOCX' }).click()
  await expect(page.getByRole('alert').last()).toContainText('Document download failed (404)')
})

test('portrait filters fit and account changes discard previous private records', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await mountLibrary(page)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.evaluate(() => globalThis.changeArtifactAccount())
  await expect(page.getByRole('article')).toHaveCount(0)
  await expect(page.getByText('Other account cached secret')).toHaveCount(0)
})
