const { test, expect } = require('@playwright/test')
const baseURL = process.env.ATLAS_UI_URL || 'http://127.0.0.1:5194'
const reviewFixture = require('./fixtures/document-review-contract.json').review

async function mountLibrary(page, { uploadFailure = false, deleteFailure = false, delayed = false, chat = false, pagingFailure = false, pagingDelay = false, reviewFailure = false, synthesisFailure = false, budgetFailure = false, malformedReview = false, malformedList = false } = {}) {
  const errors = []
  page.on('pageerror', error => errors.push(error.message))
  let records = []
  let account = 'reader'
  let review = null
  await page.route('**/src/main.jsx', route => route.fulfill({ contentType: 'application/javascript', body: '' }))
  await page.route(url => url.pathname.startsWith('/api/'), async route => {
    const path = new URL(route.request().url()).pathname
    let result = {}
    if (path.includes('/document-reviews')) {
      if (path.endsWith('/synthesize')) {
        expect(route.request().postDataJSON()).toEqual({ confirm_model_usage: true })
        if (synthesisFailure) {
          review.synthesis = { ...reviewFixture.synthesis, status: 'blocked', stop_reason: 'provider_outcome_unknown' }
          review.inflight_section = 'synthesis'
          return route.fulfill({ status: 504, contentType: 'application/json', body: JSON.stringify({ status: 'error', error: 'Synthesis gateway timeout.' }) })
        }
        const node = {
          summary: 'A combined assessment with limitations.', section_indices: [0, 1, 2, 3], citations: [0, 3],
          source_sha256: review.source_sha256, model: 'fixture', reported_tokens: 100, reasoning_trace: '',
          quality: { fact_verification: 'not_performed' },
        }
        review.synthesis = { ...reviewFixture.synthesis, status: 'completed', stop_reason: '', nodes: [node], result: node }
        review.usage.tokens += 100
      } else if (path.endsWith('/budget')) {
        expect(route.request().postDataJSON()).toEqual({
          expected_max_tokens: 64000, max_tokens: 100000, confirm_budget_extension: true,
        })
        if (budgetFailure) return route.fulfill({ status: 409, contentType: 'application/json', body: JSON.stringify({ status: 'error', error: 'Budget changed. Reload saved state before confirming again.' }) })
        review.max_tokens = 100000
        review.budget_extensions = [{ previous_max_tokens: 64000, max_tokens: 100000,
          reported_tokens: review.usage.tokens, confirmed_at: review.updated_at }]
      } else if (path.endsWith('/advance')) {
        expect(route.request().postDataJSON()).toEqual({ confirm_model_usage: true })
        if (reviewFailure) return route.fulfill({ status: 504, contentType: 'application/json', body: JSON.stringify({ status: 'error', error: 'Review gateway timeout.' }) })
        const start = review.assessments.length
        review.assessments.push(...Array.from({ length: Math.min(3, 4 - start) }, (_, index) => ({
          ...reviewFixture.assessments[0], chunk_index: start + index, location: `section ${start + index + 1}`,
          summary: 'A source-grounded assessment.', quote: 'An exact source quote.',
        })))
        review.status = review.assessments.length === 4 ? 'completed' : 'partial'
        review.review_complete = review.status === 'completed'
        review.usage.tokens += 300
      } else if (route.request().method() === 'POST') {
        review = { ...structuredClone(reviewFixture), goal: route.request().postDataJSON().goal, file_id: 'atlas-book',
          scope: chat ? 'chat' : 'atlas', synthesis: undefined, review_complete: false,
          total_sections: 4, assessments: [], status: 'ready', usage: { tokens: 0, accounting_status: 'reported_successful_calls_only' }, max_tokens: 64000, max_extended_tokens: 128000,
          warnings: ['One scanned page needs OCR.'] }
      } else if (route.request().method() === 'DELETE') {
        const deleted = review.id
        review = null
        return route.fulfill({ contentType: 'application/json', body: JSON.stringify({ status: 'ok', deleted }) })
      }
      if (malformedReview && path.endsWith('/advance')) {
        return route.fulfill({ contentType: 'application/json', body: JSON.stringify({
          status: 'ok', review: { ...review, usage: { tokens: 'private-body-sentinel' } },
        }) })
      }
      result = path.endsWith('/document-reviews') && route.request().method() === 'GET'
        ? { status: 'ok', reviews: review ? [review] : [] } : { status: 'ok', review }
      if (malformedList && path.endsWith('/document-reviews') && route.request().method() === 'GET') {
        malformedList = false
        result.reviews = [{ ...reviewFixture, file_id: 'another-private-file' }]
      }
    }
    else if (path.endsWith('/capabilities')) result = { extensions: ['.pdf', '.docx', '.pptx', '.xlsx', '.txt'], max_file_bytes: 50 * 1048576, max_storage_bytes: 500 * 1048576, usage: { storage_bytes: 0 } }
    else if (path.endsWith('/upload')) {
      if (delayed) await new Promise(resolve => setTimeout(resolve, 1200))
      if (uploadFailure) return route.fulfill({ status: 413, contentType: 'application/json', body: JSON.stringify({ status: 'error', error: 'Private upload quota reached.' }) })
      result = { status: 'ok', file_id: 'atlas-book', name: 'textbook.pdf', size: 12345, tag: 'textbook', processing_status: 'partial', warnings: ['One scanned page needs OCR.'], chunk_count: 120 }
      records = [result]
    } else if (path.endsWith('/content')) {
      const params = new URL(route.request().url()).searchParams
      const start = params.has('start') ? Number(params.get('start')) : null
      if (start === 6 && pagingDelay) await new Promise(resolve => setTimeout(resolve, 600))
      if (start === 6 && pagingFailure) return route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ status: 'error', error: 'Document index temporarily unavailable.' }) })
      const sections = start === null ? [{ location: 'page 120', text: 'Zebrafish cardiac regeneration uses progenitor cells.', chunk_index: 12 }]
        : Array.from({ length: Math.min(6, 13 - start) }, (_, index) => ({ chunk_index: start + index, location: `section ${start + index + 1}`, text: `Indexed source ${start + index + 1}.` }))
      result = { status: 'ok', file_id: 'atlas-book', name: 'textbook.pdf', processing_status: 'partial',
        warnings: ['One scanned page needs OCR.'], sections, total_chunks: 13,
        next_start: start !== null && start + sections.length < 13 ? start + sections.length : null,
        selection: { mode: start === null ? 'search' : 'sequential', selected_chunks: sections.length, total_chunks: 13, review_complete: false } }
    }
    else if (route.request().method() === 'DELETE') {
      if (deleteFailure) return route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ status: 'error', error: 'Storage unavailable.' }) })
      records = []
      result = { status: 'ok' }
    } else result = { status: 'ok', files: account === 'reader' ? records : [] }
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(result) })
  })
  await page.goto(baseURL)
  await page.exposeFunction('switchUploadAccount', id => { account = id })
  await page.evaluate(async chat => {
    const { supabase } = await import('/src/lib/supabase.js')
    supabase.auth.getSession = async () => ({ data: { session: { access_token: 'test-only', user: { id: 'reader' } } } })
    supabase.auth.onAuthStateChange = callback => {
      globalThis.changeUploadAccount = async id => {
        await globalThis.switchUploadAccount(id)
        callback('SIGNED_IN', { access_token: 'test-only', user: { id } })
      }
      return { data: { subscription: { unsubscribe() {} } } }
    }
    const { default: React } = await import('/node_modules/.vite/deps/react.js')
    const { default: ReactDOM } = await import('/node_modules/.vite/deps/react-dom_client.js')
    const { default: Library } = await import('/src/components/AtlasMaterialsLibrary.jsx')
    const { default: Attachments } = await import('/src/components/FileAttachmentPanel.jsx')
    const { AuthProvider } = await import('/src/lib/authContext.jsx')
    await import('/src/index.css')
    document.body.innerHTML = '<div id="root"></div>'
    const component = chat
      ? React.createElement(Attachments, { onAttach: () => {}, onRemove: () => {} })
      : React.createElement(Library, { attached: [], onToggleAttach: () => {} })
    ReactDOM.createRoot(document.getElementById('root')).render(React.createElement(AuthProvider, null, component))
  }, chat)
  await expect(page.getByText('50 MB per file', { exact: false })).toBeVisible()
  return errors
}

test('backend formats and limits drive uploads, processing warnings and source previews', async ({ page }) => {
  const errors = await mountLibrary(page)
  await expect(page.locator('input[type=file]')).toHaveAttribute('accept', '.pdf,.docx,.pptx,.xlsx,.txt')
  await page.locator('input[type=file]').setInputFiles({ name: 'textbook.pdf', mimeType: 'application/pdf', buffer: Buffer.from('fixture') })
  await expect(page.getByText('One scanned page needs OCR.', { exact: true }).first()).toBeVisible()
  await page.getByRole('button', { name: 'Preview', exact: true }).click()
  await expect(page.getByRole('region', { name: 'Document extraction preview' })).toContainText('page 120')
  await page.getByLabel('Search document sections').fill('zebrafish regeneration')
  await page.getByRole('button', { name: 'Find sections' }).click()
  await expect(page.getByRole('region', { name: 'Document extraction preview' })).toContainText('progenitor cells')
  expect(errors).toEqual([])
})

test('failed upload remains explicit and retryable without a success record', async ({ page }) => {
  await mountLibrary(page, { uploadFailure: true })
  await page.locator('input[type=file]').setInputFiles({ name: 'textbook.pdf', mimeType: 'application/pdf', buffer: Buffer.from('fixture') })
  await expect(page.getByRole('alert')).toContainText('Private upload quota reached.')
  await expect(page.getByRole('button', { name: 'Retry failed uploads' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Preview', exact: true })).toHaveCount(0)
})

test('indexed review is explicitly paid per batch and recovers saved coverage without a model call', async ({ page }) => {
  const errors = await mountLibrary(page)
  let advances = 0
  page.on('request', request => { if (new URL(request.url()).pathname.endsWith('/advance')) advances += 1 })
  await page.locator('input[type=file]').setInputFiles({ name: 'textbook.pdf', mimeType: 'application/pdf', buffer: Buffer.from('fixture') })
  await page.getByRole('button', { name: 'Preview', exact: true }).click()
  await page.getByLabel('Review goal', { exact: false }).fill('Assess the indexed explanation.')
  await page.getByRole('button', { name: 'Create saved review (no model call)' }).click()
  await expect(page.getByLabel('Saved review coverage')).toContainText('0/4')
  expect(advances).toBe(0)
  await page.getByRole('button', { name: 'Review next batch (uses model credits)' }).click()
  await expect(page.getByLabel('Saved review coverage')).toContainText('3/4')
  await page.getByRole('button', { name: 'Close preview', exact: true }).click()
  await page.getByRole('button', { name: 'Preview', exact: true }).click()
  await expect(page.getByLabel('Saved review coverage')).toContainText('3/4')
  expect(advances).toBe(1)
  await page.getByRole('button', { name: 'Review next batch (uses model credits)' }).click()
  await expect(page.getByLabel('Saved review coverage')).toContainText('4/4')
  await expect(page.getByLabel('Saved review coverage')).toContainText('completed')
  await expect(page.getByRole('button', { name: 'Review next batch (uses model credits)' })).toHaveCount(0)
  await expect(page.getByRole('region', { name: 'Indexed document review' })).toContainText('facts verified')
  expect(advances).toBe(2)
  expect(errors).toEqual([])
})

test('failed review batch requires saved-state reload instead of an automatic paid retry', async ({ page }) => {
  await mountLibrary(page, { reviewFailure: true })
  await page.locator('input[type=file]').setInputFiles({ name: 'textbook.pdf', mimeType: 'application/pdf', buffer: Buffer.from('fixture') })
  await page.getByRole('button', { name: 'Preview', exact: true }).click()
  await page.getByLabel('Review goal', { exact: false }).fill('Assess the indexed explanation.')
  await page.getByRole('button', { name: 'Create saved review (no model call)' }).click()
  await page.getByRole('button', { name: 'Review next batch (uses model credits)' }).click()
  await expect(page.getByRole('alert')).toContainText('Review gateway timeout.')
  await expect(page.getByRole('button', { name: 'Review next batch (uses model credits)' })).toHaveCount(0)
  await page.getByRole('button', { name: 'Reload saved review (no model call)' }).click()
  await expect(page.getByLabel('Saved review coverage')).toContainText('0/4')
})

test('malformed paid review evidence hides mutation controls until a free saved-state reload', async ({ page }) => {
  const errors = await mountLibrary(page, { malformedReview: true })
  let advances = 0
  page.on('request', request => { if (new URL(request.url()).pathname.endsWith('/advance')) advances += 1 })
  await page.locator('input[type=file]').setInputFiles({ name: 'textbook.pdf', mimeType: 'application/pdf', buffer: Buffer.from('fixture') })
  await page.getByRole('button', { name: 'Preview', exact: true }).click()
  await page.getByLabel('Review goal', { exact: false }).fill('Assess the indexed explanation.')
  await page.getByRole('button', { name: 'Create saved review (no model call)' }).click()
  await page.getByRole('button', { name: 'Review next batch (uses model credits)' }).click()
  await expect(page.getByRole('alert')).toContainText('Invalid saved document review')
  await expect(page.getByRole('alert')).not.toContainText('private-body-sentinel')
  await expect(page.getByLabel('Saved review coverage')).toContainText('0/4')
  await expect(page.getByRole('button', { name: 'Review next batch (uses model credits)' })).toHaveCount(0)
  await page.getByRole('button', { name: 'Reload saved review (no model call)' }).click()
  await expect(page.getByLabel('Saved review coverage')).toContainText('3/4')
  expect(advances).toBe(1)
  expect(errors).toEqual([])
})

test('foreign saved review lists block creation until a model-free reload succeeds', async ({ page }) => {
  const errors = await mountLibrary(page, { malformedList: true })
  let mutations = 0
  page.on('request', request => {
    if (new URL(request.url()).pathname.includes('/document-reviews') && request.method() !== 'GET') mutations += 1
  })
  await page.locator('input[type=file]').setInputFiles({ name: 'textbook.pdf', mimeType: 'application/pdf', buffer: Buffer.from('fixture') })
  await page.getByRole('button', { name: 'Preview', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('Invalid saved document review')
  await page.getByLabel('Review goal', { exact: false }).fill('Assess the indexed explanation.')
  await expect(page.getByRole('button', { name: 'Create saved review (no model call)' })).toBeDisabled()
  await page.getByRole('button', { name: 'Reload saved reviews (no model call)' }).click()
  await expect(page.getByRole('alert')).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Create saved review (no model call)' })).toBeEnabled()
  expect(mutations).toBe(0)
  expect(errors).toEqual([])
})

test('cross-section synthesis is explicitly paid and saved source citations reopen without replay', async ({ page }) => {
  const errors = await mountLibrary(page)
  let syntheses = 0
  page.on('request', request => { if (new URL(request.url()).pathname.endsWith('/synthesize')) syntheses += 1 })
  await page.locator('input[type=file]').setInputFiles({ name: 'textbook.pdf', mimeType: 'application/pdf', buffer: Buffer.from('fixture') })
  await page.getByRole('button', { name: 'Preview', exact: true }).click()
  await page.getByLabel('Review goal', { exact: false }).fill('Combine the evidence and limitations.')
  await page.getByRole('button', { name: 'Create saved review (no model call)' }).click()
  await expect(page.getByRole('button', { name: 'Synthesize next batch (uses model credits)' })).toHaveCount(0)
  await page.getByRole('button', { name: 'Review next batch (uses model credits)' }).click()
  await page.getByRole('button', { name: 'Review next batch (uses model credits)' }).click()
  expect(syntheses).toBe(0)
  await page.getByRole('button', { name: 'Synthesize next batch (uses model credits)' }).click()
  const synthesis = page.getByRole('region', { name: 'Saved cross-section synthesis' })
  await expect(synthesis).toContainText('All 4 indexed assessments traversed.')
  await synthesis.getByText('Source section 4', { exact: false }).click()
  await expect(synthesis.locator('details[open] blockquote')).toHaveText('An exact source quote.')
  await page.getByRole('button', { name: 'Close preview' }).click()
  await page.getByRole('button', { name: 'Preview', exact: true }).click()
  await expect(page.getByRole('region', { name: 'Saved cross-section synthesis' })).toContainText('A combined assessment with limitations.')
  expect(syntheses).toBe(1)
  expect(errors).toEqual([])
})

test('budget extension confirms a new total without model calls or usage reset', async ({ page }) => {
  const errors = await mountLibrary(page)
  let modelBatches = 0
  page.on('request', request => { if (/\/(advance|synthesize)$/.test(new URL(request.url()).pathname)) modelBatches += 1 })
  await page.locator('input[type=file]').setInputFiles({ name: 'textbook.pdf', mimeType: 'application/pdf', buffer: Buffer.from('fixture') })
  await page.getByRole('button', { name: 'Preview', exact: true }).click()
  await page.getByLabel('Review goal', { exact: false }).fill('Assess the indexed explanation.')
  await page.getByRole('button', { name: 'Create saved review (no model call)' }).click()
  await page.getByRole('button', { name: 'Review next batch (uses model credits)' }).click()
  await page.getByLabel('New total token ceiling').fill('100000')
  await page.getByRole('button', { name: 'Confirm larger total ceiling (no model call)' }).click()
  await expect(page.getByLabel('Saved review coverage')).toContainText('300 reported tokens / 100000 ceiling')
  expect(modelBatches).toBe(1)
  expect(errors).toEqual([])
})

test('uncertain synthesis blocks replay and budget unlock after saved-state recovery', async ({ page }) => {
  await mountLibrary(page, { synthesisFailure: true })
  await page.locator('input[type=file]').setInputFiles({ name: 'textbook.pdf', mimeType: 'application/pdf', buffer: Buffer.from('fixture') })
  await page.getByRole('button', { name: 'Preview', exact: true }).click()
  await page.getByLabel('Review goal', { exact: false }).fill('Combine saved assessments.')
  await page.getByRole('button', { name: 'Create saved review (no model call)' }).click()
  await page.getByRole('button', { name: 'Review next batch (uses model credits)' }).click()
  await page.getByRole('button', { name: 'Review next batch (uses model credits)' }).click()
  await page.getByRole('button', { name: 'Synthesize next batch (uses model credits)' }).click()
  await expect(page.getByRole('alert')).toContainText('Synthesis gateway timeout.')
  await page.getByRole('button', { name: 'Reload saved review (no model call)' }).click()
  await expect(page.getByRole('region', { name: 'Saved cross-section synthesis' })).toContainText('provider_outcome_unknown')
  await expect(page.getByRole('button', { name: 'Synthesize next batch (uses model credits)' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Confirm larger total ceiling (no model call)' })).toHaveCount(0)
})

test('a stale budget confirmation requires reload and cannot authorize a paid batch', async ({ page }) => {
  await mountLibrary(page, { budgetFailure: true })
  await page.locator('input[type=file]').setInputFiles({ name: 'textbook.pdf', mimeType: 'application/pdf', buffer: Buffer.from('fixture') })
  await page.getByRole('button', { name: 'Preview', exact: true }).click()
  await page.getByLabel('Review goal', { exact: false }).fill('Assess the indexed explanation.')
  await page.getByRole('button', { name: 'Create saved review (no model call)' }).click()
  await page.getByLabel('New total token ceiling').fill('100000')
  await page.getByRole('button', { name: 'Confirm larger total ceiling (no model call)' }).click()
  await expect(page.getByRole('alert')).toContainText('Budget changed.')
  await expect(page.getByRole('button', { name: 'Review next batch (uses model credits)' })).toHaveCount(0)
  await page.getByRole('button', { name: 'Reload saved review (no model call)' }).click()
  await expect(page.getByLabel('Saved review coverage')).toContainText('0 reported tokens / 64000 ceiling')
})

test('indexed text browsing reaches the final section and keeps coverage distinct from model review', async ({ page }) => {
  const errors = await mountLibrary(page)
  await page.locator('input[type=file]').setInputFiles({ name: 'textbook.pdf', mimeType: 'application/pdf', buffer: Buffer.from('fixture') })
  await page.getByRole('button', { name: 'Preview', exact: true }).click()
  await page.getByRole('button', { name: 'Browse indexed text' }).click()
  const preview = page.getByRole('region', { name: 'Document extraction preview' })
  await expect(preview.getByLabel('Document section coverage')).toContainText('6 of 13')
  await expect(preview).toContainText('Indexed source 1.')
  await page.getByRole('button', { name: 'Next sections' }).click()
  await expect(preview).toContainText('Indexed source 7.')
  await page.getByRole('button', { name: 'Next sections' }).click()
  await expect(preview).toContainText('Indexed source 13.')
  await expect(page.getByRole('button', { name: 'Next sections' })).toHaveCount(0)
  await expect(preview).toContainText('Neither means the model reviewed the entire document.')
  await page.getByRole('button', { name: 'Previous sections' }).click()
  await expect(preview).toContainText('Indexed source 7.')
  expect(errors).toEqual([])
})

test('a failed section page preserves the current source and reports the failure', async ({ page }) => {
  await mountLibrary(page, { pagingFailure: true })
  await page.locator('input[type=file]').setInputFiles({ name: 'textbook.pdf', mimeType: 'application/pdf', buffer: Buffer.from('fixture') })
  await page.getByRole('button', { name: 'Preview', exact: true }).click()
  await page.getByRole('button', { name: 'Browse indexed text' }).click()
  await expect(page.getByText('Indexed source 1.', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Next sections' }).click()
  await expect(page.getByText('Document index temporarily unavailable.', { exact: true })).toBeVisible()
  await expect(page.getByText('Indexed source 1.', { exact: true })).toBeVisible()
})

test('closing a preview cannot be undone by a late section response', async ({ page }) => {
  await mountLibrary(page, { pagingDelay: true })
  await page.locator('input[type=file]').setInputFiles({ name: 'textbook.pdf', mimeType: 'application/pdf', buffer: Buffer.from('fixture') })
  await page.getByRole('button', { name: 'Preview', exact: true }).click()
  await page.getByRole('button', { name: 'Browse indexed text' }).click()
  const response = page.waitForResponse(url => url.url().includes('start=6'))
  await page.getByRole('button', { name: 'Next sections' }).click()
  await page.getByRole('button', { name: 'Close preview' }).click()
  await response
  await expect(page.getByRole('region', { name: 'Document extraction preview' })).toHaveCount(0)
})

test('delete failure retains the actual library record', async ({ page }) => {
  await mountLibrary(page, { deleteFailure: true })
  await page.locator('input[type=file]').setInputFiles({ name: 'textbook.pdf', mimeType: 'application/pdf', buffer: Buffer.from('fixture') })
  await expect(page.getByRole('button', { name: 'Preview', exact: true })).toBeVisible()
  await page.getByTitle('Delete', { exact: true }).click()
  await expect(page.getByText('Storage unavailable.', { exact: false })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Preview', exact: true })).toBeVisible()
})

test('chat attachment upload can be cancelled with explicit uncertainty', async ({ page }) => {
  await mountLibrary(page, { chat: true, delayed: true })
  await page.locator('input[type=file]').setInputFiles({ name: 'textbook.pdf', mimeType: 'application/pdf', buffer: Buffer.from('fixture') })
  await page.getByRole('button', { name: 'Cancel uploads' }).click()
  await expect(page.getByRole('alert')).toContainText('Cancelled')
})

test('portrait previews wrap document text without horizontal overflow', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await mountLibrary(page)
  await page.locator('input[type=file]').setInputFiles({ name: 'textbook.pdf', mimeType: 'application/pdf', buffer: Buffer.from('fixture') })
  await page.getByRole('button', { name: 'Preview', exact: true }).click()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy()
})

test('account changes discard previews, upload status and private records', async ({ page }) => {
  await mountLibrary(page)
  await page.locator('input[type=file]').setInputFiles({ name: 'textbook.pdf', mimeType: 'application/pdf', buffer: Buffer.from('fixture') })
  await page.getByRole('button', { name: 'Preview', exact: true }).click()
  await page.evaluate(() => globalThis.changeUploadAccount('different-reader'))
  await expect(page.getByRole('region', { name: 'Document extraction preview' })).toHaveCount(0)
  await expect(page.getByText('textbook.pdf', { exact: false })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Preview', exact: true })).toHaveCount(0)
})

test('chat files can be reviewed and deleted after removing their attachment', async ({ page }) => {
  await mountLibrary(page, { chat: true })
  await page.locator('input[type=file]').setInputFiles({ name: 'textbook.pdf', mimeType: 'application/pdf', buffer: Buffer.from('fixture') })
  await expect(page.getByText('One scanned page needs OCR.', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Manage saved files' }).click()
  await expect(page.getByText('My Chat Files', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Preview', exact: true }).click()
  await expect(page.getByRole('region', { name: 'Document extraction preview' })).toContainText('page 120')
  await page.getByTitle('Delete', { exact: true }).click()
  await expect(page.getByRole('button', { name: 'Preview', exact: true })).toHaveCount(0)
})
