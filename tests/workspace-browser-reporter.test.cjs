const assert = require('node:assert/strict')
const { test } = require('node:test')
const { mkdtempSync, writeFileSync, rmSync } = require('node:fs')
const { tmpdir } = require('node:os')
const path = require('node:path')
const { spawnSync } = require('node:child_process')
const Reporter = require('../scripts/workspace-browser-reporter.cjs')

const files = ['atlas-workspace.spec.js', 'artifact-library.spec.js', 'document-uploads.spec.js', 'workspace-reliability.spec.js']
const passing = () => files.map(file => ({ location: { file }, expectedStatus: 'passed', results: [{ status: 'passed' }] }))
function check(tests, status = 'passed') {
  const reporter = new Reporter()
  reporter.onBegin({}, { allTests: () => tests })
  return reporter.onEnd({ status }).status
}

test('requires a clean single-attempt pass in every required suite', () => {
  assert.equal(check(passing()), 'passed')
})

test('rejects empty or missing suites, even when Playwright reports passed', () => {
  assert.equal(check([]), 'failed')
  assert.equal(check(passing().slice(1)), 'failed')
})

for (const status of ['skipped', 'failed', 'timedOut', 'interrupted']) {
  test(`rejects ${status} tests`, () => {
    const tests = passing()
    tests[0].results[0].status = status
    assert.equal(check(tests), 'failed')
  })
}

test('rejects expected failures and unexpectedly passing tests', () => {
  for (const status of ['failed', 'passed']) {
    const tests = passing()
    tests[0].expectedStatus = 'failed'
    tests[0].results[0].status = status
    assert.equal(check(tests), 'failed')
  }
})

test('rejects retries and tests with no results', () => {
  for (const results of [[], [{ status: 'failed' }, { status: 'passed' }], [{ status: 'passed' }, { status: 'passed' }]]) {
    const tests = passing()
    tests[0].results = results
    assert.equal(check(tests), 'failed')
  }
})

test('cannot turn global errors, timeout or interruption into a pass', () => {
  for (const status of ['failed', 'timedout', 'interrupted']) assert.equal(check(passing(), status), 'failed')
  assert.equal(new Reporter().onEnd({ status: 'passed' }).status, 'failed')
})

test('real Playwright CLI fails closed for skipped, missing, focused, expected-failure and retried coverage', () => {
  const root = mkdtempSync(path.join(tmpdir(), 'mammoth-browser-gate-check-'))
  const config = path.join(root, 'playwright.config.cjs')
  const releaseConfig = path.resolve(__dirname, 'workspace-ci.playwright.config.js')
  const reporter = path.resolve(__dirname, '..', 'scripts', 'workspace-browser-reporter.cjs')
  const playwright = path.join(path.dirname(require.resolve('@playwright/test/package.json')), 'cli.js')
  const preamble = `const { test, expect } = require(${JSON.stringify(require.resolve('@playwright/test'))});\n`
  const pass = "test('verified', () => expect(true).toBe(true))"
  try {
    for (const [name, body, expected, retries] of [
      ['passing', pass, 0, 0],
      ['skipped', "test.skip('not verified', () => {})", 1, 0],
      ['failed', "test('broken', () => expect(false).toBe(true))", 1, 0],
      ['missing', '', 1, 0],
      ['focused', "test.only('focused', () => {})", 1, 0],
      ['expected failure', "test('known failure', () => { test.fail(); expect(false).toBe(true) })", 1, 0],
      ['retry', "test('flaky', ({}, info) => expect(info.retry).toBe(1))", 1, 1],
    ]) {
      for (const [index, file] of files.entries()) {
        writeFileSync(path.join(root, file), preamble + (index === 0 ? body : pass))
      }
      writeFileSync(config, `module.exports = { ...require(${JSON.stringify(releaseConfig)}), testDir: __dirname, webServer: undefined, reporter: [[${JSON.stringify(reporter)}]], retries: ${retries}, globalTimeout: 20000 }`)
      const env = { ...process.env }
      delete env.ATLAS_UI_URL
      const result = spawnSync(process.execPath, [playwright, 'test', '--config', config], {
        encoding: 'utf8', env, timeout: 30000,
      })
      assert.ifError(result.error)
      assert.equal(result.status, expected, `${name}: ${result.stdout}\n${result.stderr}`)
      assert.match(result.stdout + result.stderr, expected === 0 ? /behavior verified/ : /gate failed|test.only/)
    }
  } finally {
    rmSync(root, { recursive: true, force: true })
  }
})

test('release config refuses an externally supplied server before any browser work', () => {
  const config = path.resolve(__dirname, 'workspace-ci.playwright.config.js')
  const result = spawnSync(process.execPath, ['-e', `require(${JSON.stringify(config)})`], {
    encoding: 'utf8',
    env: { ...process.env, ATLAS_UI_URL: 'http://example.invalid' },
    timeout: 10000,
  })
  assert.ifError(result.error)
  assert.equal(result.status, 1)
  assert.match(result.stderr, /must start its own fixture-configured Vite server/)
})
