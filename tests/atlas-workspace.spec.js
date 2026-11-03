const { test, expect } = require('@playwright/test')

const baseURL = process.env.ATLAS_UI_URL || 'http://127.0.0.1:5194'
const agentIds = ['tutor_agent', 'curriculum_agent', 'research_agent', 'reflection_agent', 'coding_agent', 'browser_agent']

async function mountWorkspace(page, { catalogFailure = false, agents = agentIds, regular = false, curriculumReady = true, profileComplete = true, activationFailure = false, lessonFailure = false, saveFailure = false, lessonContent = 'Compare primary sources before drawing conclusions.', agentOutput = null, agentLimitReached = false } = {}) {
  const requests = []
  const errors = []
  page.on('pageerror', error => errors.push(error.message))
  let lessonId = 'lesson-1'
  let starterResponse = ''
  let chatHistory = []
  let lastSubmission = null
  let savedWorkspace = null
  let nextSaveGate = null
  const recovery = () => {
    const key = JSON.stringify([lessonId, starterResponse])
    return {
      contract: 'mammoth.learning-workspace.v1', exercise_key: key,
      revision: savedWorkspace?.revision || 0, saved_at: savedWorkspace?.saved_at,
      values: savedWorkspace?.exercise_key === key ? savedWorkspace.values : {
        view: savedWorkspace?.values.view || 'lesson', lesson_response: starterResponse,
        tutor_response: starterResponse, checklist: {}, tutor_message: '', tutor_mode: 'tutor',
      },
    }
  }
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
    learner_storage: { contract: 'mammoth.learner-storage.v1', legacy_imported: false, legacy_ownership: 'unverified_not_imported' },
    workspace_recovery: recovery(),
    last_submission: lastSubmission,
  })
  await page.route('**/src/main.jsx', route => route.fulfill({ contentType: 'application/javascript', body: '' }))
  await page.route(url => url.pathname.startsWith('/api/'), async route => {
    const path = new URL(route.request().url()).pathname
    const body = route.request().postDataJSON()
    requests.push({ path, body, headers: route.request().headers() })
    let result = {}
    if (path === '/api/atlas/status') result = snapshot()
    if (path === '/api/atlas/workspace') {
      if (nextSaveGate) {
        const gate = nextSaveGate
        nextSaveGate = null
        await gate
      }
      if (saveFailure) return route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Workspace storage unavailable' }) })
      const current = recovery()
      if (body.revision !== current.revision || body.exercise_key !== current.exercise_key) {
        return route.fulfill({ status: 409, contentType: 'application/json', body: JSON.stringify({ detail: 'Saved workspace changed in another tab' }) })
      }
      savedWorkspace = { ...body, revision: body.revision + 1, saved_at: '2026-11-02T18:00:00Z' }
      result = { status: 'saved', ...recovery() }
    }
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
    if (path === '/api/atlas/submit') {
      lastSubmission = { passed: false, mastery_evidence: false, hint: 'Include a primary source.' }
      result = { result: lastSubmission }
    }
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
      const reply = 'Compare the original evidence with an independent source.'
      chatHistory = [...chatHistory, { role: 'user', message: body.message || body.contextual_help?.selection }, { role: 'assistant', message: reply }]
      result = { status: 'ok', reply, chat_history: chatHistory }
    }
    if (path === '/api/atlas/study-preview') result = { status: 'draft', cards: [{ front: 'What should you compare?', back: body.learning_selection.selection }] }
    if (path === '/api/notes' && route.request().method() === 'POST') result = { id: 'note-linked', metadata: { learning_context: body.learning_selection } }
    if (path === '/api/flashcards' && route.request().method() === 'POST') result = { status: 'ok', count: 1, cards: [{ ...body.cards[0], learning_context: body.learning_selection }] }
    if (path === '/api/atlas/next') {
      if (!body?.override) result = { status: 'gated', gate: { message: 'Practice first.', allowed: false } }
      else { lessonId = 'lesson-2'; result = { status: 'ok' } }
    }
    if (path === '/api/atlas/agents/run' && agentLimitReached) {
      return route.fulfill({ status: 429, contentType: 'application/json',
        body: JSON.stringify({ detail: 'Your chosen daily learning request limit has been reached.' }) })
    }
    if (['/api/run', '/api/atlas/agents/run'].includes(path)) result = { status: 'ok', result: { output: agentOutput || (body.agent_id === 'curriculum_agent' ? { curriculum: course } : {
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
  const render = async () => {
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
    const { AuthProvider, useAuth } = await import('/src/lib/authContext.jsx')
    const { PageMemoryProvider } = await import('/src/lib/PageMemory.tsx')
    const { default: Workspace } = await import('/src/pages/AtlasWorkspacePage.jsx')
    const { default: AgentWorkspace } = await import('/src/components/agent-workspace/AgentWorkspace.jsx')
    await import('/src/index.css')
    document.body.innerHTML = '<div id="test-root" style="height:100vh"></div>'
    const workspace = regular ? React.createElement(AgentWorkspace, { agents: agents.map(id => ({ id, status: 'ready' })), temperature: 0.3, approvalMode: true }) : React.createElement(Workspace)
    class NavigableWorkspace extends React.Component {
      state = { visible: true }
      render() {
        globalThis.showTestWorkspace = visible => this.setState({ visible })
        return this.state.visible ? workspace : React.createElement('p', null, 'ATLAS is unmounted')
      }
    }
    function WorkspaceOwner() {
      const { user } = useAuth()
      return React.createElement(PageMemoryProvider, { key: user?.id || 'local', owner: user?.id || 'local' },
        React.createElement(NavigableWorkspace))
    }
    ReactDOM.createRoot(document.getElementById('test-root')).render(React.createElement(AuthProvider, null, React.createElement(WorkspaceOwner)))
    }, { regular, agents })
  }
  await render()
  if (!regular) await expect(page.getByRole('heading', { name: 'ATLAS', exact: true })).toBeVisible()
  return {
    requests, errors,
    setSaveFailure: value => { saveFailure = value },
    holdNextSave: () => { let release; nextSaveGate = new Promise(resolve => { release = resolve }); return release },
    reload: async () => { await page.reload(); await render() },
    conflict: () => { savedWorkspace = { ...recovery(), revision: recovery().revision + 1 } },
  }
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

test('selected lesson text requests explicit contextual help and preserves the exercise draft', async ({ page }) => {
  const { requests, errors } = await mountWorkspace(page)
  const response = page.getByRole('region', { name: 'Lesson and practice' }).locator('textarea')
  await response.fill('My unfinished answer remains here.')
  await page.locator('.atlas-lessons-page .lesson-reader-section').first().evaluate(element => {
    const range = document.createRange()
    range.selectNodeContents(element)
    window.getSelection().removeAllRanges()
    window.getSelection().addRange(range)
    element.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }))
  })
  await page.getByRole('button', { name: 'Study selection', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: 'Study selected text' })
  await expect(dialog.locator('blockquote').first()).toHaveText('Compare primary sources before drawing conclusions.')
  expect(requests.filter(request => request.path === '/api/atlas/chat')).toHaveLength(0)
  await dialog.getByLabel('Help type').selectOption('example')
  await dialog.getByRole('button', { name: 'Ask tutor', exact: true }).click()
  await expect(dialog.getByRole('region', { name: 'Contextual tutor response' })).toContainText('Compare the original evidence')
  const call = requests.find(request => request.path === '/api/atlas/chat')
  expect(call.body.contextual_help).toEqual({ exercise_key: JSON.stringify(['lesson-1', '']), source: 'lesson',
    selection: 'Compare primary sources before drawing conclusions.', action: 'example' })
  expect(requests.some(request => ['/api/atlas/regenerate', '/api/atlas/submit', '/api/atlas/next'].includes(request.path))).toBe(false)
  await dialog.getByRole('button', { name: 'Close', exact: true }).click()
  await expect(response).toHaveValue('My unfinished answer remains here.')
  expect(errors).toEqual([])
})

test('reviewed notes and source-derived cards use existing stores without a model call', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  const { requests, errors } = await mountWorkspace(page)
  await page.getByRole('button', { name: 'Explain instructions', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: 'Study selected text' })
  await dialog.getByText('Save a linked study note', { exact: true }).click()
  await dialog.getByLabel('Study note', { exact: true }).fill('My own takeaway.')
  await dialog.getByRole('button', { name: 'Save reviewed note' }).click()
  await expect(dialog.getByRole('status')).toContainText('private Notes')
  await dialog.getByText('Create a linked recall card', { exact: true }).click()
  await dialog.getByRole('button', { name: 'Draft recall card' }).click()
  await expect(dialog.getByLabel('Recall answer')).toHaveValue('Explain how you verify a claim.')
  expect(requests.filter(request => request.path === '/api/flashcards')).toHaveLength(0)
  await dialog.getByLabel('Recall question').fill('How do I verify a claim?')
  await dialog.getByRole('button', { name: 'Save reviewed card' }).click()
  await expect(dialog.getByRole('status')).toContainText('lesson flashcards')
  expect(requests.find(request => request.path === '/api/notes').body.reviewed).toBe(true)
  expect(requests.find(request => request.path === '/api/flashcards').body.authorship).toBe('learner')
  expect(requests.some(request => ['/api/atlas/chat', '/api/atlas/agents/run', '/api/run'].includes(request.path))).toBe(false)
  expect(await dialog.evaluate(element => element.scrollWidth <= element.clientWidth)).toBe(true)
  await dialog.getByRole('button', { name: 'Close', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Explain instructions', exact: true })).toBeFocused()
  expect(errors).toEqual([])
})

test('targeted feedback help leaves the active exercise and learner answer untouched', async ({ page }) => {
  const { requests, errors } = await mountWorkspace(page)
  const response = page.getByRole('region', { name: 'Lesson and practice' }).locator('textarea')
  await response.fill('My actual attempt.')
  await page.getByRole('button', { name: 'Submit response', exact: true }).click()
  await page.getByRole('button', { name: 'Work on feedback', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: 'Study selected text' })
  await expect(dialog.getByLabel('Help type')).toHaveValue('remediate')
  await dialog.getByRole('button', { name: 'Ask tutor', exact: true }).click()
  await expect(dialog.getByRole('region', { name: 'Contextual tutor response' })).toBeVisible()
  expect(requests.find(request => request.path === '/api/atlas/chat').body.contextual_help)
    .toMatchObject({ source: 'feedback', selection: 'Include a primary source.', action: 'remediate' })
  await dialog.getByRole('button', { name: 'Close', exact: true }).click()
  await expect(response).toHaveValue('My actual attempt.')
  expect(requests.filter(request => request.path === '/api/atlas/submit')).toHaveLength(1)
  expect(requests.some(request => ['/api/atlas/regenerate', '/api/atlas/next'].includes(request.path))).toBe(false)
  expect(errors).toEqual([])
})

test('study drafts survive page navigation and failed saves without automatic model retries', async ({ page }) => {
  const { requests, errors } = await mountWorkspace(page)
  let modelCalls = 0
  await page.route('**/api/atlas/chat', route => {
    modelCalls += 1
    return route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Tutor temporarily unavailable' }) })
  })
  await page.route('**/api/notes', route => route.fulfill({
    status: 403, contentType: 'application/json', body: JSON.stringify({ detail: 'Pro access required' }),
  }))
  await page.getByRole('button', { name: 'Explain instructions', exact: true }).click()
  let dialog = page.getByRole('dialog', { name: 'Study selected text' })
  await dialog.getByText('Save a linked study note', { exact: true }).click()
  await dialog.getByLabel('Study note', { exact: true }).fill('Keep my complete unsaved study note.')
  await dialog.getByRole('button', { name: 'Save reviewed note' }).click()
  await expect(dialog.getByRole('alert')).toContainText('Pro access required')
  await expect(dialog.getByRole('textbox', { name: 'Study note', exact: true })).toHaveValue('Keep my complete unsaved study note.')
  await dialog.getByRole('button', { name: 'Ask tutor', exact: true }).click()
  await expect(dialog.getByRole('alert')).toContainText('Tutor temporarily unavailable')
  await expect(dialog.getByRole('region', { name: 'Contextual tutor response' })).toHaveCount(0)
  await page.evaluate(() => globalThis.showTestWorkspace(false))
  await expect(page.getByText('ATLAS is unmounted', { exact: true })).toBeVisible()
  await page.evaluate(() => globalThis.showTestWorkspace(true))
  await page.getByRole('button', { name: 'Explain instructions', exact: true }).click()
  dialog = page.getByRole('dialog', { name: 'Study selected text' })
  await expect(dialog.getByRole('alert')).toContainText('Tutor temporarily unavailable')
  await dialog.getByText('Save a linked study note', { exact: true }).click()
  await expect(dialog.getByRole('textbox', { name: 'Study note', exact: true })).toHaveValue('Keep my complete unsaved study note.')
  expect(modelCalls).toBe(1)
  expect(requests.some(request => ['/api/atlas/submit', '/api/flashcards'].includes(request.path))).toBe(false)
  await dialog.getByRole('button', { name: 'Close', exact: true }).click()
  await page.evaluate(() => globalThis.changeTestAccount('different-learner'))
  await page.getByRole('button', { name: 'Explain instructions', exact: true }).click()
  await dialog.getByText('Save a linked study note', { exact: true }).click()
  await expect(dialog.getByLabel('Study note', { exact: true })).toHaveValue('')
  await expect(dialog.getByRole('alert')).toHaveCount(0)
  expect(errors).toEqual([])
})

test('a pending contextual request is not duplicated by leaving and returning', async ({ page }) => {
  const { errors } = await mountWorkspace(page)
  let release
  let modelCalls = 0
  const gate = new Promise(resolve => { release = resolve })
  await page.route('**/api/atlas/chat', async route => {
    modelCalls += 1
    await gate
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ status: 'ok', reply: 'A complete delayed explanation.' }) })
  })
  await page.getByRole('button', { name: 'Explain instructions', exact: true }).click()
  await page.getByRole('button', { name: 'Ask tutor', exact: true }).click()
  await expect.poll(() => modelCalls).toBe(1)
  await page.evaluate(() => globalThis.showTestWorkspace(false))
  await expect(page.getByText('ATLAS is unmounted', { exact: true })).toBeVisible()
  await page.evaluate(() => globalThis.showTestWorkspace(true))
  await page.getByRole('button', { name: 'Explain instructions', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Asking tutor...', exact: true })).toBeDisabled()
  release()
  await expect(page.getByRole('region', { name: 'Contextual tutor response' })).toContainText('A complete delayed explanation.')
  expect(modelCalls).toBe(1)
  expect(errors).toEqual([])
})

test('empty source-derived previews do not invent or save a recall answer', async ({ page }) => {
  const { requests, errors } = await mountWorkspace(page)
  await page.route('**/api/atlas/study-preview', route => route.fulfill({
    contentType: 'application/json', body: JSON.stringify({ status: 'draft', cards: [] }),
  }))
  await page.getByRole('button', { name: 'Explain instructions', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: 'Study selected text' })
  await dialog.getByText('Create a linked recall card', { exact: true }).click()
  await dialog.getByRole('button', { name: 'Draft recall card' }).click()
  await expect(dialog.getByRole('alert')).toContainText('write your own card')
  await expect(dialog.getByLabel('Recall answer')).toHaveCount(0)
  expect(requests.some(request => ['/api/atlas/chat', '/api/flashcards'].includes(request.path))).toBe(false)
  await dialog.getByRole('button', { name: 'Write my own card' }).click()
  await expect(dialog.getByLabel('Recall answer')).toHaveValue('Explain how you verify a claim.')
  expect(errors).toEqual([])
})

test('confirmed workspace recovery restores drafts, selected view and tutor history after reload', async ({ page }) => {
  const { requests, errors, reload } = await mountWorkspace(page)
  const response = page.getByRole('region', { name: 'Lesson and practice' }).locator('textarea')
  await response.fill('A complete response worth keeping, not a summary.')
  await page.getByRole('button', { name: 'ATLAS Tutor', exact: true }).click()
  const tutor = page.getByRole('region', { name: 'ATLAS tutor conversation' })
  const composer = tutor.getByRole('textbox', { name: 'Ask ATLAS Tutor…', exact: true })
  await composer.fill('Explain this lesson')
  await composer.press('Enter')
  await expect(tutor).toContainText('Compare the original evidence with an independent source.')
  await composer.fill('Unsent follow-up question')
  await expect(page.getByText('Workspace saved', { exact: true })).toBeVisible()
  const modelCalls = requests.filter(request => request.path === '/api/atlas/chat').length
  await reload()
  await expect(page.getByRole('button', { name: 'ATLAS Tutor', exact: true })).toHaveAttribute('aria-pressed', 'true')
  await expect(composer).toHaveValue('Unsent follow-up question')
  await expect(tutor).toContainText('Compare the original evidence with an independent source.')
  await page.getByRole('button', { name: 'Lesson & practice', exact: true }).click()
  await expect(response).toHaveValue('A complete response worth keeping, not a summary.')
  expect(requests.filter(request => request.path === '/api/atlas/chat')).toHaveLength(modelCalls)
  expect(requests.some(request => ['/api/atlas/submit', '/api/atlas/next'].includes(request.path))).toBe(false)
  expect(errors).toEqual([])
})

test('save failure retains the full local draft and explicit retry restores durability', async ({ page }) => {
  const { setSaveFailure, errors, reload } = await mountWorkspace(page, { saveFailure: true })
  const response = page.getByRole('region', { name: 'Lesson and practice' }).locator('textarea')
  await response.fill('Never lose this on a rejected save.')
  await expect(page.getByRole('button', { name: 'Retry save', exact: true })).toBeVisible()
  await expect(response).toHaveValue('Never lose this on a rejected save.')
  setSaveFailure(false)
  await page.getByRole('button', { name: 'Retry save', exact: true }).click()
  await expect(page.getByText('Workspace saved', { exact: true })).toBeVisible()
  await reload()
  await expect(response).toHaveValue('Never lose this on a rejected save.')
  expect(errors).toEqual([])
})

test('editing during a delayed save persists the latest complete response', async ({ page }) => {
  const { holdNextSave, requests, errors, reload } = await mountWorkspace(page)
  const release = holdNextSave()
  const response = page.getByRole('region', { name: 'Lesson and practice' }).locator('textarea')
  await response.fill('First version')
  await expect(page.getByText('Saving workspace...', { exact: true })).toBeVisible()
  await response.fill('Latest complete version typed while saving')
  release()
  await expect(page.getByText('Workspace saved', { exact: true })).toBeVisible()
  expect(requests.filter(request => request.path === '/api/atlas/workspace').map(request => request.body.values.lesson_response))
    .toEqual(['First version', 'Latest complete version typed while saving'])
  await reload()
  await expect(response).toHaveValue('Latest complete version typed while saving')
  await response.fill('')
  await expect(page.getByText('Workspace saved', { exact: true })).toBeVisible()
  await reload()
  await expect(response).toHaveValue('')
  expect(errors).toEqual([])
})

test('a late save for the old exercise cannot overwrite a new variant draft', async ({ page }) => {
  const { holdNextSave, errors, reload } = await mountWorkspace(page)
  const release = holdNextSave()
  const response = page.getByRole('region', { name: 'Lesson and practice' }).locator('textarea')
  await response.fill('Old exercise response')
  await expect(page.getByText('Saving workspace...', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'ATLAS Tutor', exact: true }).click()
  await page.getByRole('button', { name: 'Advanced tutor tools', exact: true }).click()
  await page.getByRole('button', { name: 'Show advanced', exact: true }).click()
  await page.getByRole('button', { name: 'New Variant', exact: true }).click()
  await page.getByRole('button', { name: 'Lesson & practice', exact: true }).click()
  await expect(response).toHaveValue('A new exercise variant')
  await response.fill('My new variant response')
  release()
  await expect(page.getByText('Workspace saved', { exact: true })).toBeVisible()
  await reload()
  await expect(response).toHaveValue('My new variant response')
  expect(errors).toEqual([])
})

test('navigation while a save is pending restores the full draft and honest save status', async ({ page }) => {
  const { holdNextSave, requests, errors } = await mountWorkspace(page)
  const release = holdNextSave()
  const response = page.getByRole('region', { name: 'Lesson and practice' }).locator('textarea')
  await response.fill('Full ATLAS draft saved while navigating')
  await expect(page.getByText('Saving workspace...', { exact: true })).toBeVisible()
  await page.evaluate(() => globalThis.showTestWorkspace(false))
  await expect(page.getByText('ATLAS is unmounted')).toBeVisible()
  await page.evaluate(() => globalThis.showTestWorkspace(true))
  await expect(response).toHaveValue('Full ATLAS draft saved while navigating')
  release()
  await expect(page.getByText('Workspace saved', { exact: true })).toBeVisible()
  expect(requests.filter(request => request.path === '/api/atlas/workspace')).toHaveLength(1)
  expect(requests.some(request => ['/api/run', '/api/atlas/agents/run', '/api/atlas/submit', '/api/atlas/next'].includes(request.path))).toBe(false)
  expect(errors).toEqual([])
})

test('another tab cannot silently overwrite a draft or make an obsolete exercise look saved', async ({ page }) => {
  const { conflict, errors } = await mountWorkspace(page)
  const response = page.getByRole('region', { name: 'Lesson and practice' }).locator('textarea')
  await response.fill('My first draft')
  await expect(page.getByText('Workspace saved', { exact: true })).toBeVisible()
  conflict()
  await response.fill('My full local conflicting edit')
  await expect(page.getByRole('alert').filter({ hasText: 'Saved workspace changed in another tab' })).toBeVisible()
  await expect(response).toHaveValue('My full local conflicting edit')
  await expect(page.getByText('Workspace saved', { exact: true })).toHaveCount(0)
  expect(errors).toEqual([])
})

test('Learning agent cap failure is visible with no general-route fallback or retry', async ({ page }) => {
  const { requests, errors } = await mountWorkspace(page, { agentLimitReached: true })
  await page.getByRole('button', { name: 'Learning agents', exact: true }).click()
  const panel = page.getByRole('region', { name: 'Education agents' })
  const composer = panel.locator('textarea').last()
  await composer.fill('Compare evidence from this lesson')
  await composer.press('Enter')
  await expect(panel.getByText('Your chosen daily learning request limit has been reached.', { exact: true })).toBeVisible()
  await expect(composer).toBeEnabled()
  expect(requests.filter(request => request.path === '/api/atlas/agents/run')).toHaveLength(1)
  expect(requests.some(request => request.path === '/api/run')).toBe(false)
  await page.getByRole('button', { name: 'Lesson & practice', exact: true }).click()
  await page.getByRole('button', { name: 'Learning agents', exact: true }).click()
  expect(requests.filter(request => request.path === '/api/atlas/agents/run')).toHaveLength(1)
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
  await expect.poll(() => requests.some(request => request.path === '/api/atlas/agents/run')).toBe(true)
  expect(requests.some(request => request.path === '/api/run')).toBe(false)
  const request = requests.find(request => request.path === '/api/atlas/agents/run').body
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
  await expect.poll(() => requests.some(request => request.path === '/api/atlas/agents/run')).toBe(true)
  expect(requests.find(request => request.path === '/api/atlas/agents/run').body.agent_id).toBe('tutor_agent')
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
  await expect.poll(() => requests.some(request => request.path === '/api/atlas/agents/run')).toBe(true)
  expect(requests.find(request => request.path === '/api/atlas/agents/run').body.payload.lesson_id).toBe('lesson-2')
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
  const { requests, errors } = await mountWorkspace(page, { regular: true, agentLimitReached: true })
  await expect(page.getByRole('button', { name: /Team run/i })).toBeVisible()
  const composer = page.locator('textarea').last()
  await composer.fill('Compare general workspace evidence')
  await composer.press('Enter')
  await expect.poll(() => requests.some(request => request.path === '/api/run')).toBe(true)
  expect(requests.some(request => request.path === '/api/atlas/agents/run')).toBe(false)
  expect(errors).toEqual([])
})

test('mentions cannot target an unregistered learning agent', async ({ page }) => {
  const { requests, errors } = await mountWorkspace(page, { agents: ['tutor_agent'] })
  await page.getByRole('button', { name: 'Learning agents', exact: true }).click()
  const region = page.getByRole('region', { name: 'Education agents' })
  await region.locator('textarea').last().fill('@research Find a source')
  await region.locator('textarea').last().press('Enter')
  await expect(region.getByText('That learning agent is not registered. Choose one of the agents shown here.')).toBeVisible()
  expect(requests.some(request => ['/api/run', '/api/atlas/agents/run'].includes(request.path))).toBe(false)
  expect(errors).toEqual([])
})

test('onboarding is visible, saves level independently of pace, and remains editable', async ({ page }) => {
  const { requests, errors } = await mountWorkspace(page, { profileComplete: false })
  const profile = page.getByRole('region', { name: 'Learning profile' })
  await expect(profile.getByRole('note')).toContainText('Legacy shared mastery and profile data were not imported because ownership is unverified.')
  await expect(profile.getByRole('button', { name: 'Save learning profile' })).toBeVisible()
  await profile.getByRole('combobox', { name: 'Starting level', exact: true }).selectOption('expert')
  await profile.getByRole('combobox', { name: 'Pacing', exact: true }).selectOption('gentle')
  await profile.getByLabel('Goals', { exact: true }).fill('Understand nutrition evidence')
  await profile.getByRole('button', { name: 'Save learning profile' }).click()
  await expect(profile).toContainText('Learning profile saved.')
  await expect(profile.getByRole('button', { name: 'Save learning profile' })).toBeHidden()
  await expect(profile).toContainText('Current recommendation: expert')
  expect(requests.find(request => request.path === '/api/atlas/onboard').body.experience_level).toBe('expert')
  await profile.getByRole('button', { name: 'Edit learning profile' }).click()
  await expect(profile.getByLabel('Goals', { exact: true })).toHaveValue('Understand nutrition evidence')
  expect(errors).toEqual([])
})

for (const width of [390, 1280]) {
  test(`profile header preserves unsaved edits and dismissal works at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 844 })
    const { requests, errors } = await mountWorkspace(page)
    const profile = page.getByRole('region', { name: 'Learning profile' })
    const openProfile = () => page.getByRole('button', { name: width === 390 ? 'Edit learning profile' : 'Learning profile', exact: true }).click()
    await openProfile()
    await profile.getByLabel('Goals', { exact: true }).fill('Unsaved learning goal')
    await page.getByRole('button', { name: width === 390 ? 'Close profile' : 'Hide learning profile', exact: true }).click()
    await expect(profile.getByLabel('Goals', { exact: true })).toBeHidden()
    await openProfile()
    await expect(profile.getByLabel('Goals', { exact: true })).toHaveValue('Unsaved learning goal')
    await profile.getByRole('button', { name: 'Not now', exact: true }).click()
    await expect(profile.getByLabel('Goals', { exact: true })).toBeHidden()
    await expect(page.getByRole('button', { name: width === 390 ? 'Edit learning profile' : 'Learning profile', exact: true })).toHaveAttribute('aria-expanded', 'false')
    expect(requests.filter(request => request.path === '/api/atlas/onboard')).toEqual([])
    await page.evaluate(() => globalThis.changeTestAccount('another-learner'))
    await openProfile()
    await expect(profile.getByLabel('Goals', { exact: true })).toHaveValue('')
    expect(errors).toEqual([])
  })
}

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
  await expect(page.getByText('Workspace saved', { exact: true })).toBeVisible()
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
    expect(requests.some(request => ['/api/run', '/api/atlas/agents/run', '/api/atlas/lesson', '/api/atlas/onboard'].includes(request.path))).toBe(false)
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
  expect(requests.some(request => ['/api/atlas/lesson', '/api/atlas/submit', '/api/atlas/next', '/api/run', '/api/atlas/agents/run'].includes(request.path))).toBe(false)
  expect(errors).toEqual([])
})

test('reading preferences survive navigation but clear for another signed-in account', async ({ page }) => {
  const { requests, errors } = await mountWorkspace(page, { lessonContent: readableLesson })
  const options = page.getByRole('button', { name: 'Reading options', exact: true })
  await options.click()
  await page.getByRole('combobox', { name: 'Text size', exact: true }).selectOption('large')
  await page.getByRole('checkbox', { name: 'More line spacing', exact: true }).check()
  await page.getByRole('button', { name: 'Focus reading', exact: true }).click()
  await expect(options).toBeFocused()
  await page.evaluate(() => globalThis.showTestWorkspace(false))
  await expect(page.getByText('ATLAS is unmounted', { exact: true })).toBeVisible()
  await page.evaluate(() => globalThis.showTestWorkspace(true))
  await expect(page.locator('.atlas-lessons-page')).toHaveAttribute('data-reading-size', 'large')
  await expect(page.locator('.atlas-lessons-page')).toHaveAttribute('data-reading-spacing', 'spacious')
  await expect(page.getByRole('region', { name: 'Learning profile' })).toBeHidden()
  await page.getByRole('button', { name: 'Read', exact: true }).click()
  await expect(page.getByLabel('Lesson reading area', { exact: true })).toBeFocused()
  await options.click()
  await page.getByRole('button', { name: 'Exit focused reading', exact: true }).click()
  await expect(options).toBeFocused()
  await expect(page.getByRole('region', { name: 'Learning profile' })).toBeVisible()
  await page.evaluate(() => globalThis.changeTestAccount('another-reader'))
  await expect(page.locator('.atlas-lessons-page')).toHaveAttribute('data-reading-size', 'standard')
  await expect(page.locator('.atlas-lessons-page')).toHaveAttribute('data-reading-spacing', 'standard')
  expect(requests.some(request => ['/api/atlas/chat', '/api/atlas/submit', '/api/run', '/api/atlas/agents/run'].includes(request.path))).toBe(false)
  expect(errors).toEqual([])
})

test('learning privacy exports confirmed saved data only without model calls or extra toolbar rows', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  const { requests, errors } = await mountWorkspace(page)
  let exports = 0
  const saved = { contract: 'mammoth.learning-export.v1', saved_learning: {
    chat_history: [{ role: 'assistant', message: 'A complete saved answer, not a summary.' }],
  }, workspace_recovery: { values: { lesson_response: 'Server-confirmed response.' } },
  learner_adaptation: { contract: 'mammoth.learner-export.v1', status: 'saved',
    model: { user_id: 'workspace:default', mastery: { evidence: 0.8 },
      recent_outcomes: Array.from({ length: 24 }, (_, i) => ({ concept: `evidence-${i}` })),
      memory_graph: { nodes: [{ id: 'real-concept', label: 'Saved concept' }], edges: [] } } } }
  await page.route('**/api/atlas/export', route => {
    exports += 1
    return route.fulfill({ contentType: 'application/json', body: JSON.stringify(saved) })
  })
  await expect(page.getByText('Learning privacy & costs', { exact: true })).toHaveCount(0)
  await page.getByRole('button', { name: 'Edit learning profile', exact: true }).click()
  await page.getByText('Learning privacy & costs', { exact: true }).click()
  await expect(page.getByText(/Resetting progress is not a privacy wipe/)).toBeVisible()
  await expect(page.getByText(/Standalone adaptation is still outside saved-learning deletion/)).toBeVisible()
  expect(exports).toBe(0)
  const downloadPromise = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Export saved learning JSON', exact: true }).click()
  const download = await downloadPromise
  expect(download.suggestedFilename()).toBe('mammoth-learning-export.json')
  const content = require('node:fs').readFileSync(await download.path(), 'utf8')
  expect(JSON.parse(content)).toEqual(saved)
  await expect(page.getByRole('status', { name: '' }).filter({ hasText: 'Export prepared' })).toBeVisible()
  expect(exports).toBe(1)
  expect(requests.some(request => ['/api/atlas/chat', '/api/atlas/onboard', '/api/run', '/api/atlas/agents/run'].includes(request.path))).toBe(false)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  expect(errors).toEqual([])
})

test('learning export failures stay explicit and are not retried automatically', async ({ page }) => {
  const { errors } = await mountWorkspace(page)
  let calls = 0
  await page.route('**/api/atlas/export', route => {
    calls += 1
    return route.fulfill({ status: 503, contentType: 'application/json',
      body: JSON.stringify({ detail: 'Saved workspace could not be read' }) })
  })
  await page.getByRole('button', { name: 'Edit learning profile', exact: true }).click()
  await page.getByText('Learning privacy & costs', { exact: true }).click()
  await page.getByRole('button', { name: 'Export saved learning JSON', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('Saved workspace could not be read')
  await expect(page.getByRole('alert')).toContainText('No automatic retry')
  await expect(page.getByText(/Export prepared/)).toHaveCount(0)
  expect(calls).toBe(1)
  expect(errors).toEqual([])
})

test('learning caps are opt-in and cancellation stays requested until a recorded boundary', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 568 })
  const { requests, errors } = await mountWorkspace(page)
  let state = { contract: 'mammoth.learning-controls.v1', day_utc: '2026-11-03',
    daily_request_limit: null, admitted_requests: 2, operations: [
      { id: 'one-private-operation', route: '/api/atlas/chat', account_id: 'default', status: 'running' },
    ] }
  const limits = []
  await page.route('**/api/atlas/controls', route => {
    if (route.request().method() === 'PUT') {
      limits.push(route.request().postDataJSON().daily_request_limit)
      state = { ...state, daily_request_limit: limits.at(-1) }
    }
    return route.fulfill({ contentType: 'application/json', body: JSON.stringify(state) })
  })
  await page.route('**/api/atlas/operations/*/cancel', route => {
    state = { ...state, operations: [{ ...state.operations[0], status: 'cancellation_requested' }] }
    return route.fulfill({ contentType: 'application/json', body: JSON.stringify({ status: 'cancellation_requested' }) })
  })
  await page.getByRole('button', { name: 'Edit learning profile', exact: true }).click()
  await page.getByText('Learning privacy & costs', { exact: true }).click()
  expect(limits).toEqual([])
  await page.getByRole('button', { name: 'Refresh learning request controls', exact: true }).click()
  const cap = page.getByRole('spinbutton', { name: 'Daily ATLAS request cap (blank means uncapped)', exact: true })
  await expect(cap).toHaveValue('')
  await cap.fill('0')
  await page.getByRole('button', { name: 'Save learning request cap', exact: true }).click()
  await expect(page.getByText(/cap saved. Existing requests are not cancelled/)).toBeVisible()
  await cap.fill('')
  await page.getByRole('button', { name: 'Save learning request cap', exact: true }).click()
  expect(limits).toEqual([0, null])
  await page.getByRole('button', { name: 'Request cancellation one-priv', exact: true }).click()
  await expect(page.getByText(/Request state: cancellation_requested/)).toBeVisible()
  await expect(page.getByRole('listitem').filter({ hasText: '/api/atlas/chat' })).toContainText('cancellation_requested')
  await expect(page.getByRole('button', { name: /Request cancellation/ })).toHaveCount(0)
  expect(requests.some(request => ['/api/atlas/chat', '/api/atlas/onboard', '/api/run', '/api/atlas/agents/run'].includes(request.path))).toBe(false)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  expect(errors).toEqual([])
})

test('pending contextual help can close its view to reach cancellation without pretending to stop', async ({ page }) => {
  const { errors } = await mountWorkspace(page)
  let release
  const gate = new Promise(resolve => { release = resolve })
  await page.route('**/api/atlas/chat', async route => {
    await gate
    await route.fulfill({ status: 409, contentType: 'application/json',
      body: JSON.stringify({ status: 'cancelled', detail: 'Cancellation reached a safe boundary.' }) })
  })
  await page.route('**/api/atlas/controls', route => route.fulfill({ contentType: 'application/json',
    body: JSON.stringify({ contract: 'mammoth.learning-controls.v1', day_utc: '2026-11-03',
      daily_request_limit: null, admitted_requests: 1, operations: [] }) }))
  try {
    await page.getByRole('button', { name: 'Explain instructions', exact: true }).click()
    const dialog = page.getByRole('dialog', { name: 'Study selected text', exact: true })
    await dialog.getByRole('button', { name: 'Ask tutor', exact: true }).click()
    await expect(dialog.getByText(/Closing this view does not cancel the request/)).toBeVisible()
    await dialog.getByRole('button', { name: 'Close view (request continues)', exact: true }).click()
    await expect(dialog).toBeHidden()
    await page.getByRole('button', { name: 'Edit learning profile', exact: true }).click()
    await page.getByText('Learning privacy & costs', { exact: true }).click()
    await page.getByRole('button', { name: 'Refresh learning request controls', exact: true }).click()
    await expect(page.getByRole('region', { name: 'Learning request controls', exact: true })).toBeVisible()
  } finally { release() }
  await page.getByRole('button', { name: 'Not now', exact: true }).click()
  await page.getByRole('button', { name: 'Explain instructions', exact: true }).click()
  await expect(page.getByRole('dialog', { name: 'Study selected text', exact: true }).getByRole('alert')).toContainText('Cancellation reached a safe boundary')
  expect(errors).toEqual([])
})

test('learning deletion requires reviewed scope and exact confirmation then clears this tab drafts', async ({ page }) => {
  const { errors } = await mountWorkspace(page)
  const lesson = page.getByRole('region', { name: 'Lesson and practice', exact: true })
  await lesson.locator('textarea').fill('A private response to remove from this tab.')
  await expect(page.getByText('Workspace saved', { exact: true })).toBeVisible()
  let deletes = 0
  await page.route('**/api/atlas/history/preview', route => route.fulfill({ contentType: 'application/json',
    body: JSON.stringify({ contract: 'mammoth.learning-erasure.v1', account_id: 'default',
      preview_token: 'reviewed-token', excludes: ['linked_notes', 'uploaded_files', 'provider_records', 'backups'] }) }))
  await page.route('**/api/atlas/history', async route => {
    expect(route.request().method()).toBe('DELETE')
    expect(route.request().postDataJSON()).toEqual({ confirmation: 'DELETE SAVED LEARNING', preview_token: 'reviewed-token' })
    deletes += 1
    await page.route('**/api/atlas/status', status => status.fulfill({ contentType: 'application/json',
      body: JSON.stringify({ lesson_id: null, current_lesson: null, current_exercise: null, chat_history: [],
        learner_model: { onboarding: { completed_at: 'today' } }, workspace_recovery: {
          contract: 'mammoth.learning-workspace.v1', exercise_key: 'after-erasure', revision: 0, saved_at: null,
          values: { view: 'lesson', lesson_response: '', tutor_response: '', tutor_message: '', tutor_mode: 'tutor', checklist: {} },
        } }) }))
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify({
      status: 'deleted_from_active_storage', receipt_id: 'confirmed-private-deletion',
    }) })
  })
  await page.getByRole('button', { name: 'Edit learning profile', exact: true }).click()
  await page.getByText('Learning privacy & costs', { exact: true }).click()
  await expect(page.getByRole('button', { name: 'Delete saved lesson session', exact: true })).toHaveCount(0)
  await page.getByRole('button', { name: 'Preview saved learning deletion', exact: true }).click()
  await expect(page.getByText(/NOT deleted: linked_notes, uploaded_files, provider_records, backups/)).toBeVisible()
  const remove = page.getByRole('button', { name: 'Delete saved lesson session', exact: true })
  await expect(remove).toBeDisabled()
  const confirm = page.getByRole('textbox', { name: 'Type DELETE SAVED LEARNING to confirm', exact: true })
  await confirm.fill('delete saved learning')
  await expect(remove).toBeDisabled()
  await confirm.fill('DELETE SAVED LEARNING')
  await remove.click()
  await expect(page.getByRole('status').filter({ hasText: 'Receipt: confirmed-private-deletion' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Edit learning profile', exact: true })).toBeVisible()
  expect(await page.locator('textarea').evaluateAll(nodes => nodes.map(node => node.value))).not.toContain('A private response to remove from this tab.')
  await page.evaluate(() => globalThis.showTestWorkspace(false))
  await page.evaluate(() => globalThis.showTestWorkspace(true))
  await expect(page.getByText('Reliable research', { exact: true })).toHaveCount(0)
  expect(deletes).toBe(1)
  expect(errors).toEqual([])
})

test('failed learning deletion preserves the preview and never shows a deletion receipt', async ({ page }) => {
  const { errors } = await mountWorkspace(page)
  let deletes = 0
  await page.route('**/api/atlas/history/preview', route => route.fulfill({ contentType: 'application/json',
    body: JSON.stringify({ contract: 'mammoth.learning-erasure.v1', account_id: 'default',
      preview_token: 'reviewed-token', excludes: ['backups'] }) }))
  await page.route('**/api/atlas/history', route => {
    deletes += 1
    return route.fulfill({ status: 409, contentType: 'application/json', body: JSON.stringify({ detail: 'Saved learning changed. Review a new deletion preview.' }) })
  })
  await page.getByRole('button', { name: 'Edit learning profile', exact: true }).click()
  await page.getByText('Learning privacy & costs', { exact: true }).click()
  await page.getByRole('button', { name: 'Preview saved learning deletion', exact: true }).click()
  await page.getByRole('textbox', { name: 'Type DELETE SAVED LEARNING to confirm', exact: true }).fill('DELETE SAVED LEARNING')
  await page.getByRole('button', { name: 'Delete saved lesson session', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('Review a new deletion preview')
  await expect(page.getByText(/Receipt:/)).toHaveCount(0)
  await expect(page.getByRole('textbox', { name: 'Type DELETE SAVED LEARNING to confirm', exact: true })).toHaveValue('DELETE SAVED LEARNING')
  expect(deletes).toBe(1)
  expect(errors).toEqual([])
})

test('large mobile lesson text scales headings code and tables with keyboard scrolling', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 568 })
  const wideCode = `const example = "${'original-evidence-'.repeat(20)}"`
  const content = `## Sources\n\nCompare original records.\n\n\`\`\`js\n${wideCode}\n\`\`\`\n\n| Record | Evidence |\n| --- | --- |\n| ${'source'.repeat(40)} | Original |\n`
  const { errors } = await mountWorkspace(page, { lessonContent: content })
  await page.getByRole('button', { name: 'Reading options', exact: true }).click()
  await page.getByRole('combobox', { name: 'Text size', exact: true }).selectOption('large')
  await page.getByRole('button', { name: 'Focus reading', exact: true }).click()
  const reader = page.locator('.atlas-lessons-page .lesson-reader').first()
  await expect(reader.getByRole('heading', { name: 'Sources', exact: true })).toHaveCSS('font-size', '22.4px')
  const code = reader.getByRole('region', { name: 'Scrollable code example', exact: true })
  const table = reader.getByRole('table', { name: 'Scrollable lesson table', exact: true })
  await expect(code).toHaveCSS('font-size', '17px')
  await expect(table).toHaveCSS('font-size', '18px')
  await code.focus()
  await expect(code).toBeFocused()
  await page.keyboard.press('ArrowRight')
  await expect.poll(() => code.evaluate(element => element.scrollLeft)).toBeGreaterThan(0)
  await table.focus()
  await expect(table).toBeFocused()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
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
