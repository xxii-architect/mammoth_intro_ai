const { test, expect } = require('@playwright/test')

const baseURL = process.env.ATLAS_UI_URL || 'http://127.0.0.1:5194'
const agentIds = ['tutor_agent', 'curriculum_agent', 'research_agent', 'reflection_agent', 'coding_agent', 'browser_agent']

async function mountWorkspace(page, { catalogFailure = false, agents = agentIds, regular = false, curriculumReady = true, profileComplete = true, activationFailure = false, lessonFailure = false, lessonContent = 'Compare primary sources before drawing conclusions.', agentOutput = null } = {}) {
  const requests = []
  const errors = []
  page.on('pageerror', error => errors.push(error.message))
  let lessonId = 'lesson-1'
  let starterResponse = ''
  let chatHistory = []
  let onboarding = { experience_level: 'beginner', preferred_pacing: 'gentle', learning_style: 'guided', goals: [], focus_areas: [], completed_at: profileComplete ? '2026-10-05' : null }
  let savedCurricula = []
  const course = {
    curriculum_id: 'saved-course', title: 'Nutrition foundations', subject: 'Nutrition',
    quality: { ready: curriculumReady, status: curriculumReady ? 'ready' : 'draft', lessons: [{ lesson_id: 'nutrition-one', ready: curriculumReady, errors: curriculumReady ? [] : ['Lesson content is too brief.'] }] },
    modules: [{ module_id: 'nutrition-module', title: 'Food and energy', lessons: [{ lesson_id: 'nutrition-one', title: 'Understanding macronutrients', summary: 'Learn the roles of carbohydrates, protein, and fats.', objectives: ['Explain macronutrient roles'], content: lessonContent === 'Compare primary sources before drawing conclusions.' ? 'Nutrition lesson preview content.' : lessonContent }] }],
  }
  const snapshot = () => ({
    lesson_id: lessonId,
    current_lesson: { title: lessonId === 'lesson-1' ? 'Reliable research' : 'Check your sources', content: lessonContent, summary: 'Evaluate evidence.' },
    current_exercise: { exercise_type: 'writing', prompt: 'Explain how you verify a claim.', starter_response: starterResponse },
    lesson_history: [], available_modules: [], learner: {}, comprehension_gate: {}, chat_history: chatHistory,
    learner_model: { onboarding }, learner_context: { starting_level: onboarding.experience_level, recommended_difficulty: onboarding.experience_level, adaptation_reason: 'Using your selected starting level until there is practice evidence.' },
  })
  await page.route('**/src/main.jsx', route => route.fulfill({ contentType: 'application/javascript', body: '' }))
  await page.route(url => url.pathname.startsWith('/api/'), async route => {
    const path = new URL(route.request().url()).pathname
    const body = route.request().postDataJSON()
    requests.push({ path, body, headers: route.request().headers() })
    let result = {}
    if (path === '/api/atlas/status') result = snapshot()
    if (path === '/api/atlas/library') result = { modules: [], totals: { persisted_lessons: 0, lessons: 0 } }
    if (path === '/api/atlas/modules') result = { modules: [] }
    if (path === '/api/atlas/onboard') {
      onboarding = { ...body, goals: body.goals.split(',').filter(Boolean), focus_areas: body.focus_areas.split(',').filter(Boolean), completed_at: '2026-10-05' }
      result = { status: 'ok', learner_model: { onboarding } }
    }
    if (path === '/api/atlas/curricula') {
      if (route.request().method() === 'POST') {
        const record = { curriculum: body.curriculum, saved_at: '2026-10-05' }
        savedCurricula = [record]
        result = { status: 'ok', ...record }
      } else result = { status: 'ok', curricula: savedCurricula }
    }
    if (path === '/api/atlas/curricula/start') {
      if (activationFailure) return route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Could not prepare the first exercise.' }) })
      lessonId = 'nutrition-one'
      result = { status: 'ok' }
    }
    if (path === '/api/atlas/agents') {
      if (catalogFailure) return route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Catalog unavailable' }) })
      result = { agents: agents.map(id => ({ id, name: id, status: 'ready', capabilities: [] })) }
    }
    if (path === '/api/atlas/submit') result = { result: { passed: false, hint: 'Include a primary source.' } }
    if (path === '/api/atlas/lesson') {
      if (lessonFailure) return route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Lesson generation unavailable' }) })
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
    if (path === '/api/run') result = { status: 'ok', result: { output: agentOutput || (body.agent_id === 'curriculum_agent' ? { curriculum: course } : {
      artifact_type: 'long_form_research', title: 'Source validation report', abstract: 'Research findings from the lesson.',
      sections: [{ order: 0, heading: 'Evidence', content: 'Check primary evidence.' }],
      sources: [], docx_filename: 'lesson-research.docx',
    }) } }
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

test('a failed lesson start preserves the active exercise draft', async ({ page }) => {
  const { errors } = await mountWorkspace(page, { lessonFailure: true })
  const response = page.getByRole('region', { name: 'Lesson and practice' }).locator('textarea')
  await response.fill('Keep this unfinished exercise.')
  await page.getByPlaceholder('e.g. Python for loops').fill('Compare sources')
  await page.getByRole('button', { name: 'Start Lesson', exact: true }).click()
  await expect(page.getByText(/Lesson action failed:.*Lesson generation unavailable/)).toBeVisible()
  await expect(response).toHaveValue('Keep this unfinished exercise.')
  expect(errors).toEqual([])
})

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
  expect(request.intent).toBe('research')
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
  await page.getByRole('button', { name: 'ATLAS Tutor', exact: true }).click()
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

test('onboarding is visible, saves level independently of pace, and remains editable', async ({ page }) => {
  const { requests, errors } = await mountWorkspace(page, { profileComplete: false })
  const profile = page.getByRole('region', { name: 'Learning profile' })
  await expect(profile.getByRole('button', { name: 'Save learning profile' })).toBeVisible()
  await profile.getByRole('combobox', { name: 'Starting level', exact: true }).selectOption('expert')
  await profile.getByRole('combobox', { name: 'Pacing', exact: true }).selectOption('gentle')
  await profile.getByLabel('Goals', { exact: true }).fill('Understand nutrition evidence')
  await profile.getByRole('button', { name: 'Save learning profile' }).click()
  await expect(profile).toContainText('Learning profile saved.')
  await expect(profile).toContainText('Current recommendation: expert')
  expect(requests.find(request => request.path === '/api/atlas/onboard').body.experience_level).toBe('expert')
  await profile.getByRole('button', { name: 'Edit learning profile' }).click()
  await expect(profile.getByLabel('Goals', { exact: true })).toHaveValue('Understand nutrition evidence')
  expect(errors).toEqual([])
})

async function generateCourse(page) {
  await page.getByRole('button', { name: 'Learning agents', exact: true }).click()
  await page.getByRole('navigation', { name: 'Agents', exact: true }).getByRole('button', { name: /Curriculum/ }).click()
  const region = page.getByRole('region', { name: 'Education agents' })
  await region.locator('textarea').last().fill('Create a curriculum for Nutrition')
  await region.getByRole('button', { name: 'Send', exact: true }).click()
  const preview = region.getByRole('article', { name: 'Curriculum preview' })
  await expect(preview.getByRole('heading', { name: 'Nutrition foundations' })).toBeVisible()
  return preview
}

test('review, save and start a generated course without losing its exact identity', async ({ page }) => {
  const { requests, errors } = await mountWorkspace(page)
  const preview = await generateCourse(page)
  await expect(preview.getByRole('button', { name: 'Start this curriculum' })).toBeDisabled()
  await preview.getByText('Food and energy (1 lessons)', { exact: true }).click()
  await preview.getByText('Understanding macronutrients', { exact: true }).click()
  await expect(preview.getByText('Nutrition lesson preview content.', { exact: true })).toBeVisible()
  await preview.getByRole('button', { name: 'Save to my curricula' }).click()
  await expect(preview.getByText('Saved to your curricula.', { exact: true })).toBeVisible()
  await preview.getByRole('button', { name: 'Start this curriculum' }).click()
  await expect(page.getByRole('region', { name: 'Lesson and practice' })).toBeVisible()
  expect(requests.find(request => request.path === '/api/atlas/curricula/start').body.curriculum_id).toBe('saved-course')
  await page.getByRole('button', { name: 'My curricula', exact: true }).click()
  await page.getByRole('region', { name: 'Saved curricula' }).getByText('Nutrition foundations', { exact: true }).first().click()
  await expect(page.getByRole('region', { name: 'Saved curricula' }).getByRole('button', { name: 'Start this curriculum' })).toBeEnabled()
  expect(errors).toEqual([])
})

test('draft curriculum stays saveable for review but cannot be started', async ({ page }) => {
  const { requests, errors } = await mountWorkspace(page, { curriculumReady: false })
  const preview = await generateCourse(page)
  await expect(preview).toContainText('Draft: teaching content needs review')
  await preview.getByRole('button', { name: 'Save to my curricula' }).click()
  await expect(preview.getByRole('button', { name: 'Start this curriculum' })).toBeDisabled()
  expect(requests.some(request => request.path === '/api/atlas/curricula/start')).toBe(false)
  expect(errors).toEqual([])
})

test('activation errors remain visible without changing the learning surface', async ({ page }) => {
  await mountWorkspace(page, { activationFailure: true })
  const preview = await generateCourse(page)
  await preview.getByRole('button', { name: 'Save to my curricula' }).click()
  await preview.getByRole('button', { name: 'Start this curriculum' }).click()
  await expect(preview.getByRole('alert')).toContainText('Could not prepare the first exercise.')
  await expect(page.getByRole('region', { name: 'Education agents' })).toBeVisible()
})

test('portrait onboarding can be deferred without covering the learning-agent composer', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  const { errors } = await mountWorkspace(page, { profileComplete: false })
  const profile = page.getByRole('region', { name: 'Learning profile' })
  await profile.getByRole('button', { name: 'Edit learning profile', exact: true }).click()
  await profile.getByRole('button', { name: 'Not now', exact: true }).click()
  await page.getByRole('button', { name: 'Learning agents', exact: true }).click()
  const composer = page.getByRole('region', { name: 'Education agents' }).locator('textarea').last()
  await composer.fill('Help me learn')
  await expect(composer).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  expect(errors).toEqual([])
})

const readableLesson = [
  'Introduction', 'Food provides **energy** and materials.\n\nA second paragraph stays separate.',
  'Key concepts', '- Protein supports repair.\n- Fiber helps explain food quality.',
  'Worked examples', '1. Read the serving size.\n2. Compare the amounts.',
  '```python\nIntroduction\nprint("A code example, not a section heading")\n```',
  'Guided practice', 'Explain one choice in your own words.',
  'Recap and next step', 'Review the label before choosing.',
].join('\n\n')

test('lesson reader gives plain headings, paragraphs, lists and code a readable structure', async ({ page }) => {
  const { errors } = await mountWorkspace(page, { lessonContent: readableLesson })
  const lesson = page.getByRole('region', { name: 'Lesson and practice' })
  await expect(lesson.getByRole('heading', { name: 'Key concepts', exact: true })).toBeVisible()
  await expect(lesson.locator('.lesson-reader strong')).toHaveText('energy')
  await expect(lesson.locator('.lesson-reader ul > li')).toHaveCount(2)
  await expect(lesson.locator('.lesson-reader ol > li')).toHaveCount(2)
  await expect(lesson.locator('.lesson-reader pre code')).toHaveText('Introduction\nprint("A code example, not a section heading")\n')
  const navigation = lesson.getByRole('navigation', { name: 'Lesson sections' })
  await lesson.locator('.lesson-reader-outline > summary').click()
  await expect(navigation.getByRole('button')).toHaveCount(5)
  await navigation.getByRole('button', { name: 'Guided practice', exact: true }).click()
  await expect(lesson.locator('.lesson-reader-section[aria-label="Guided practice"]')).toBeFocused()
  await expect(lesson.locator('.lesson-reader p', { hasText: 'A second paragraph stays separate.' })).toHaveCount(1)
  expect(errors).toEqual([])
})

for (const viewport of [{ width: 320, height: 568 }, { width: 390, height: 844 }, { width: 430, height: 932 }]) {
  test(`mobile lesson prioritizes content and keeps controls reachable at ${viewport.width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize(viewport)
    const { requests, errors } = await mountWorkspace(page, { lessonContent: readableLesson, profileComplete: false })
    // Reserve room for the app's separate navigation header.
    await page.locator('#test-root').evaluate(element => { element.style.height = 'calc(100dvh - 64px)' })
    const readingArea = page.getByLabel('Lesson reading area', { exact: true })
    await expect(readingArea).toBeVisible()
    const bounds = await readingArea.boundingBox()
    expect(bounds.height).toBeGreaterThan((viewport.height - 64) * 0.55)
    expect(bounds.y + bounds.height).toBeLessThanOrEqual(viewport.height - 64 + 1)
    await expect(page.getByRole('heading', { name: 'Reliable research', exact: true })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Save learning profile', exact: true })).toBeHidden()
    await expect(page.locator('.atlas-lesson-sidebar')).toBeHidden()
    for (const button of await page.getByRole('navigation', { name: 'ATLAS workspace' }).getByRole('button').all()) {
      await expect(button).toHaveCSS('min-height', '44px')
    }
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await page.screenshot({ path: testInfo.outputPath(`atlas-lesson-${viewport.width}.png`) })
    await page.getByRole('button', { name: 'Modules', exact: true }).click()
    await expect(readingArea).toBeHidden()
    await expect(page.getByPlaceholder('e.g. Python for loops')).toBeVisible()
    await page.getByRole('button', { name: 'Back to lesson', exact: true }).click()
    await expect(readingArea).toBeVisible()
    await page.getByRole('button', { name: 'Edit learning profile', exact: true }).click()
    await expect(page.getByRole('button', { name: 'Save learning profile', exact: true })).toBeVisible()
    await page.getByRole('button', { name: 'Not now', exact: true }).click()
    expect(requests.some(request => ['/api/run', '/api/atlas/lesson', '/api/atlas/onboard'].includes(request.path))).toBe(false)
    expect(errors).toEqual([])
  })
}

test('reading controls, real progress and mobile modules preserve the exercise draft', async ({ page }) => {
  const { requests, errors } = await mountWorkspace(page, { lessonContent: readableLesson })
  const readingArea = page.getByLabel('Lesson reading area', { exact: true })
  const response = page.getByRole('region', { name: 'Lesson and practice' }).locator('textarea')
  await response.fill('Keep this response while changing layout.')
  await page.getByRole('button', { name: 'Read', exact: true }).click()
  await page.getByRole('button', { name: 'Reading options', exact: true }).click()
  await page.getByRole('combobox', { name: 'Text size', exact: true }).selectOption('large')
  await page.getByRole('checkbox', { name: 'More line spacing', exact: true }).check()
  await expect(page.locator('.atlas-lessons-page .lesson-reader-body').first()).toHaveCSS('font-size', '20px')
  await expect(page.locator('.atlas-lessons-page .lesson-reader-body').first()).toHaveCSS('line-height', '42px')
  await page.getByRole('button', { name: 'Focus reading', exact: true }).click()
  await expect(page.getByRole('region', { name: 'Learning profile' })).toBeHidden()
  await expect(page.locator('.atlas-lesson-sidebar')).toBeHidden()
  await page.setViewportSize({ width: 390, height: 844 })
  await page.getByRole('button', { name: 'Modules', exact: true }).click()
  await expect(readingArea).toBeHidden()
  await page.getByRole('button', { name: 'Back to lesson', exact: true }).click()
  await page.getByRole('button', { name: 'Practice', exact: true }).click()
  await expect(page.getByLabel('Practice exercise', { exact: true })).toBeFocused()
  await expect(response).toHaveValue('Keep this response while changing layout.')
  await page.getByRole('button', { name: 'Read', exact: true }).click()
  await page.getByText('Learning progress & lesson flow', { exact: true }).click()
  await expect(page.getByText('Retention (spaced recall)', { exact: true })).toHaveCount(0)
  await expect(page.getByText('Time to competency', { exact: true })).toHaveCount(0)
  expect(requests.some(request => ['/api/atlas/lesson', '/api/atlas/submit', '/api/atlas/next', '/api/run'].includes(request.path))).toBe(false)
  expect(errors).toEqual([])
})

test('landscape phones keep a compact single-pane workspace and a usable focused reader', async ({ page }) => {
  await page.setViewportSize({ width: 844, height: 390 })
  const { errors } = await mountWorkspace(page, { lessonContent: readableLesson })
  await page.locator('#test-root').evaluate(element => { element.style.height = 'calc(100dvh - 64px)' })
  await expect(page.locator('.atlas-lesson-sidebar')).toBeHidden()
  await page.getByRole('button', { name: 'Reading options', exact: true }).click()
  await page.getByRole('button', { name: 'Focus reading', exact: true }).click()
  await expect(page.getByRole('region', { name: 'Learning profile' })).toBeHidden()
  const bounds = await page.getByLabel('Lesson reading area', { exact: true }).boundingBox()
  expect(bounds.height).toBeGreaterThan((390 - 64) * 0.55)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.getByRole('button', { name: 'ATLAS Tutor', exact: true }).click()
  await expect(page.getByRole('region', { name: 'Lesson and practice' })).toBeHidden()
  await expect(page.getByRole('region', { name: 'ATLAS tutor conversation' })).toBeVisible()
  expect(errors).toEqual([])
})

test('lesson reader sanitizes active HTML and links without fetching embedded images', async ({ page }) => {
  const external = []
  await page.route('https://lesson-image.example/**', route => { external.push(route.request().url()); return route.abort() })
  const content = '## Introduction\n\nSafe teaching text.\n\n<img src="https://lesson-image.example/track" onerror="globalThis.lessonInjected=true"><script>globalThis.lessonInjected=true</script>\n\n[Unsafe](javascript:alert(1)) [Source](https://example.com/nutrition)\n\n## Key concepts\n\nRead critically.\n\n## Guided practice\n\nExplain the evidence.'
  const { errors } = await mountWorkspace(page, { lessonContent: content })
  const reader = page.getByRole('region', { name: 'Lesson and practice' }).locator('.lesson-reader').first()
  await expect(reader.locator('img, script, iframe, [onerror]')).toHaveCount(0)
  await expect(reader.getByText('Unsafe', { exact: true })).not.toHaveAttribute('href')
  await expect(reader.getByRole('link', { name: 'Source', exact: true })).toHaveAttribute('href', 'https://example.com/nutrition')
  expect(await page.evaluate(() => globalThis.lessonInjected)).toBeUndefined()
  expect(external).toEqual([])
  expect(errors).toEqual([])
})

test('curriculum previews share readable formatting and portrait lessons preserve draft and fit', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  const { errors } = await mountWorkspace(page, { lessonContent: readableLesson })
  const response = page.getByRole('region', { name: 'Lesson and practice' }).locator('textarea')
  await response.fill('Keep this learning draft')
  const preview = await generateCourse(page)
  await preview.getByText('Food and energy (1 lessons)', { exact: true }).click()
  await preview.getByText('Understanding macronutrients', { exact: true }).click()
  await expect(preview.getByRole('heading', { name: 'Worked examples', exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Lesson & practice', exact: true }).click()
  await expect(response).toHaveValue('Keep this learning draft')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  expect(errors).toEqual([])
})

test('research displays matched excerpts and safe source links without fabricated certainty', async ({ page }) => {
  const output = {
    status: 'partial', artifact_type: 'research', title: 'Nutrition evidence',
    executive_summary: 'Protein provides amino acids.',
    findings: [{ heading: 'Protein', content: 'Protein provides amino acids. [S1]', source_support: ['S1'], evidence: [{ source_id: 'S1', quote: 'Protein provides amino acids.' }] }],
    unverified_findings: [{ content: 'Unsupported cure claim.' }],
    sources: [{ label: 'S1', title: 'Nutrition guide', excerpt: 'Protein provides amino acids.', url: 'https://example.com/nutrition' },
      { label: 'S2', title: 'Unsafe source', excerpt: 'Not used.', url: 'javascript:alert(1)' }],
    citations: [], references: [], confidence_assessment: 'Exact excerpt checks are not fact verification.',
  }
  const { errors } = await mountWorkspace(page, { agentOutput: output })
  await page.getByRole('button', { name: 'Learning agents', exact: true }).click()
  const composer = page.getByRole('region', { name: 'Education agents' }).locator('textarea').last()
  await composer.fill('@research Research protein')
  await page.getByRole('button', { name: 'Send', exact: true }).click()
  await expect(page.getByText('Nutrition evidence', { exact: true })).toBeVisible()
  await expect(page.locator('blockquote', { hasText: 'Protein provides amino acids.' })).toBeVisible()
  await expect(page.getByRole('link', { name: 'https://example.com/nutrition', exact: true })).toHaveAttribute('href', 'https://example.com/nutrition')
  await expect(page.locator('a[href^="javascript:"]')).toHaveCount(0)
  await expect(page.getByText('No snippet provided.', { exact: true })).toHaveCount(0)
  await page.getByText('Excluded unverified findings (1)', { exact: true }).click()
  await expect(page.getByText('Unsupported cure claim.', { exact: true })).toBeVisible()
  expect(errors).toEqual([])
})

test('write code cannot bypass repository grounding and multiline prose is not source', async ({ page }) => {
  await mountWorkspace(page)
  const routes = await page.evaluate(async () => {
    const { codingRoute } = await import('/src/components/agent-workspace/agentCatalog.js')
    const route = prompt => codingRoute({ agentId: 'coding_agent', intent: 'generate_code', repo: '', prompt })
    return [
      route('Add a nutrition layer inside the existing Health Module and leave the rest alone.'),
      route('Modify existing file.\nKeep imports.\nAdd validation.\nReturn tests.'),
      route('Create a standalone Python calculator.'),
      route('Fix this code:\n```python\ndef add(a, b):\n    return a - b\n```'),
    ]
  })
  expect(routes).toEqual(['needs_repo', 'needs_repo', 'run', 'run'])
})
