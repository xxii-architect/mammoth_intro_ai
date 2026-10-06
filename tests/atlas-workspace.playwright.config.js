const { defineConfig } = require('@playwright/test')
const path = require('node:path')
const os = require('node:os')

module.exports = defineConfig({
  testDir: __dirname,
  testMatch: ['atlas-workspace.spec.js', 'artifact-library.spec.js', 'document-uploads.spec.js'],
  workers: 1,
  reporter: 'line',
  outputDir: path.join(os.tmpdir(), `mammoth-atlas-ui-${process.pid}`),
  webServer: process.env.ATLAS_UI_URL ? undefined : {
    command: `node "${path.join('node_modules', 'vite', 'bin', 'vite.js')}" --host 127.0.0.1 --port 5194 --strictPort`,
    cwd: path.resolve(__dirname, '..', 'ui', 'mad-architecht-command-center'),
    url: 'http://127.0.0.1:5194',
    reuseExistingServer: false,
    env: {
      VITE_SUPABASE_URL: 'http://127.0.0.1:5194',
      VITE_SUPABASE_ANON_KEY: 'test-only-ui-key',
      VITE_MAMMOTH_API_BASE_URL: 'http://127.0.0.1:5194',
    },
  },
})
