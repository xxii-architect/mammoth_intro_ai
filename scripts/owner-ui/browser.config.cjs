const { defineConfig } = require('/opt/mammoth-ui/tests/node_modules/@playwright/test')

module.exports = defineConfig({
  testDir: '/work/tests',
  testMatch: ['atlas-workspace.spec.js', 'artifact-library.spec.js', 'document-uploads.spec.js', 'workspace-reliability.spec.js'],
  workers: 1,
  retries: 0,
  maxFailures: 1,
  forbidOnly: true,
  timeout: 30000,
  globalTimeout: 540000,
  reporter: [['dot'], ['json', { outputFile: '/tmp/browser-results.json' }]],
  outputDir: '/tmp/browser-output',
  use: { launchOptions: { chromiumSandbox: false } },
  webServer: {
    command: 'node /opt/mammoth-ui/ui/node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5194 --strictPort',
    cwd: '/work/ui/mad-architecht-command-center',
    url: 'http://127.0.0.1:5194',
    reuseExistingServer: false,
    env: {
      VITE_SUPABASE_URL: 'http://127.0.0.1:5194',
      VITE_SUPABASE_ANON_KEY: 'test-only-ui-key',
      VITE_MAMMOTH_API_BASE_URL: 'http://127.0.0.1:5194',
      VITE_MONACO_BASE_URL: 'http://127.0.0.1:5194/node_modules/monaco-editor/min/vs',
    },
  },
})
