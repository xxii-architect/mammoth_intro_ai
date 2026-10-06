const { test, expect } = require('@playwright/test')
const baseURL = process.env.ATLAS_UI_URL || 'http://127.0.0.1:5194'

async function mountLibrary(page, { uploadFailure = false, deleteFailure = false, delayed = false, chat = false } = {}) {
  const errors = []
  page.on('pageerror', error => errors.push(error.message))
  let records = []
  let account = 'reader'
  await page.route('**/src/main.jsx', route => route.fulfill({ contentType: 'application/javascript', body: '' }))
  await page.route(url => url.pathname.startsWith('/api/'), async route => {
    const path = new URL(route.request().url()).pathname
    let result = {}
    if (path.endsWith('/capabilities')) result = { extensions: ['.pdf', '.docx', '.pptx', '.xlsx', '.txt'], max_file_bytes: 50 * 1048576, max_storage_bytes: 500 * 1048576, usage: { storage_bytes: 0 } }
    else if (path.endsWith('/upload')) {
      if (delayed) await new Promise(resolve => setTimeout(resolve, 1200))
      if (uploadFailure) return route.fulfill({ status: 413, contentType: 'application/json', body: JSON.stringify({ status: 'error', error: 'Private upload quota reached.' }) })
      result = { status: 'ok', file_id: 'atlas-book', name: 'textbook.pdf', size: 12345, tag: 'textbook', processing_status: 'partial', warnings: ['One scanned page needs OCR.'], chunk_count: 120 }
      records = [result]
    } else if (path.endsWith('/content')) result = { status: 'ok', file_id: 'atlas-book', name: 'textbook.pdf', processing_status: 'partial', sections: [{ location: 'page 120', text: 'Zebrafish cardiac regeneration uses progenitor cells.' }] }
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
