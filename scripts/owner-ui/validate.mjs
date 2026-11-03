import { createHash } from 'node:crypto'
import { mkdirSync, readdirSync, readFileSync, symlinkSync } from 'node:fs'
import { spawnSync } from 'node:child_process'
import { createRequire } from 'node:module'
import assert from 'node:assert/strict'

const ui = '/work/ui/mad-architecht-command-center'
for (const [source, locked] of [
  [`${ui}/package.json`, '/opt/mammoth-ui/ui/package.json'],
  [`${ui}/package-lock.json`, '/opt/mammoth-ui/ui/package-lock.json'],
]) {
  const hash = path => createHash('sha256').update(JSON.stringify(JSON.parse(readFileSync(path, 'utf8')))).digest('hex')
  if (hash(source) !== hash(locked)) throw new Error(`Dependency manifest changed: ${source}. Rebuild and review the pinned image before validation.`)
}
mkdirSync(`${ui}/node_modules`)
for (const name of readdirSync('/opt/mammoth-ui/ui/node_modules')) {
  symlinkSync(`/opt/mammoth-ui/ui/node_modules/${name}`, `${ui}/node_modules/${name}`, 'dir')
}
if (['build', 'browser'].includes(process.argv[2])) {
  const result = spawnSync('npm', ['run', 'build'], {
    cwd: ui,
    stdio: 'inherit',
    env: { ...process.env, CI: '1' },
  })
  if (result.error) throw result.error
  if (result.status !== 0) process.exit(result.status || 1)
  console.log('MAMMOTH_UI_BUILD_PASSED')
  if (process.argv[2] === 'browser') {
    for (const name of ['package.json', 'package-lock.json']) {
      const hash = path => createHash('sha256').update(JSON.stringify(JSON.parse(readFileSync(path, 'utf8')))).digest('hex')
      assert.equal(hash(`/work/${name}`), hash(`/opt/mammoth-ui/tests/${name}`), 'Browser test dependency manifest changed; rebuild the pinned image.')
    }
    symlinkSync('/opt/mammoth-ui/tests/node_modules', '/work/node_modules', 'dir')
    const result = spawnSync('node', ['/opt/mammoth-ui/tests/node_modules/@playwright/test/cli.js',
      'test', '--config=/opt/mammoth-ui/browser.config.cjs'], {
      cwd: '/work', stdio: 'inherit', env: { ...process.env, CI: '1' },
    })
    if (result.error) throw result.error
    const report = JSON.parse(readFileSync('/tmp/browser-results.json', 'utf8'))
    const testResults = {}
    const collect = (suite, parents = []) => {
      const titles = [...parents, suite.title]
      for (const spec of suite.specs || []) {
        const id = createHash('sha256').update(JSON.stringify([spec.file, ...titles, spec.title])).digest('hex').slice(0, 24)
        testResults[id] = spec.tests.every(test => test.status === 'expected') ? 'ok' : 'FAIL'
      }
      for (const child of suite.suites || []) collect(child, titles)
    }
    for (const suite of report.suites) collect(suite)
    console.log(`MAMMOTH_UI_BROWSER_TEST_RESULTS:${JSON.stringify(testResults)}`)
    if (result.status !== 0) process.exit(result.status || 1)
    const coveredFiles = new Set(report.suites.filter(suite => (suite.specs?.length || suite.suites?.length))
      .map(suite => suite.file.split(/[\\/]/).pop()))
    for (const name of ['atlas-workspace.spec.js', 'artifact-library.spec.js', 'document-uploads.spec.js', 'workspace-reliability.spec.js']) {
      assert.ok(coveredFiles.has(name), `Required browser suite missing or empty: ${name}`)
    }
    assert.ok(report.stats.expected > 0 && report.stats.unexpected === 0 &&
      report.stats.flaky === 0 && report.stats.skipped === 0, 'Browser validation requires passing tests with no skips or flakes.')
    console.log(`MAMMOTH_UI_BROWSER_PASSED: ${report.stats.expected} tests; no skips, flakes or failures. Workspace suite only, not independent acceptance review.`)
  }
} else if (process.argv[2] === 'component') {
  const require = createRequire('/opt/mammoth-ui/ui/package.json')
  const React = require('react')
  const { renderToStaticMarkup } = require('react-dom/server')
  const { createServer } = await import('/opt/mammoth-ui/ui/node_modules/vite/dist/node/index.js')
  const server = await createServer({ root: ui, server: { middlewareMode: true, hmr: false } })
  try {
    const { TrustBadgeRow } = await server.ssrLoadModule('/src/components/TrustSurfaces.jsx')
    for (const [confidence, expected] of [[0, '0%'], [0.3, '30%'], [0.91, '91%']]) {
      const html = renderToStaticMarkup(React.createElement(TrustBadgeRow, {
        provider: 'openai', confidence, showEvidence: false,
      }))
      assert.ok(html.includes('OpenAI'), 'The provider should render.')
      assert.ok(html.includes(`Reported score (uncalibrated): ${expected}`), `Supplied score ${confidence} must render ${expected}.`)
    }
    for (const confidence of [undefined, null, '', ' ', false, true, 'bad', -1, 101]) {
      const html = renderToStaticMarkup(React.createElement(TrustBadgeRow, { provider: 'openai', confidence, sourceCount: 2 }))
      assert.ok(html.includes('Not assessed') && html.includes('OpenAI') && html.includes('2 sources'))
      assert.ok(!html.includes('74%') && !html.includes('80%'))
    }
    console.log('MAMMOTH_UI_COMPONENT_PASSED: explicit scores, invalid/missing values unassessed, provider and source counts retained.')
  } finally {
    await server.close()
  }
} else {
  throw new Error('Expected build, component or browser profile.')
}
