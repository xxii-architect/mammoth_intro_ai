const { defineConfig } = require('@playwright/test')
const path = require('node:path')
const os = require('node:os')
const base = require('./atlas-workspace.playwright.config')

if (process.env.ATLAS_UI_URL) {
  throw new Error('The workspace release gate must start its own fixture-configured Vite server; unset ATLAS_UI_URL.')
}

const output = process.env.MAMMOTH_BROWSER_REPORT_DIR || path.join(os.tmpdir(), `mammoth-workspace-gate-${process.pid}`)

module.exports = defineConfig({
  ...base,
  forbidOnly: true,
  retries: 0,
  failOnFlakyTests: true,
  globalTimeout: 540000,
  outputDir: path.join(output, 'test-results'),
  reporter: [
    ['line'],
    [path.resolve(__dirname, '..', 'scripts', 'workspace-browser-reporter.cjs')],
    ['json', { outputFile: path.join(output, 'results.json') }],
    ['html', { outputFolder: path.join(output, 'html'), open: 'never' }],
  ],
  use: {
    browserName: 'chromium',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  webServer: {
    ...base.webServer,
    env: {
      ...base.webServer.env,
      VITE_MONACO_BASE_URL: 'http://127.0.0.1:5194/node_modules/monaco-editor/min/vs',
    },
  },
})
