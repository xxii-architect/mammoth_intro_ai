const path = require('node:path')

const REQUIRED_SUITES = [
  'atlas-workspace.spec.js',
  'artifact-library.spec.js',
  'document-uploads.spec.js',
  'workspace-reliability.spec.js',
]

class WorkspaceBrowserReporter {
  onBegin(_config, suite) {
    this.suite = suite
  }

  onEnd(result) {
    const tests = this.suite?.allTests() || []
    const covered = new Set(tests.map(test => path.basename(test.location.file)))
    const missing = REQUIRED_SUITES.filter(file => !covered.has(file))
    const unverified = tests.filter(test => test.expectedStatus !== 'passed'
      || test.results.length !== 1 || test.results[0].status !== 'passed')
    if (result.status !== 'passed' || missing.length || unverified.length) {
      console.error(`Workspace browser gate failed: run=${result.status}; missing suites=${missing.join(', ') || 'none'}; unverified tests=${unverified.length}. Skips, expected failures and retries do not count as verification.`)
      return { status: 'failed' }
    }
    console.log(`Workspace browser behavior verified: ${tests.length} tests across all ${REQUIRED_SUITES.length} required suites; no skips, retries or expected failures. Fixture-backed Chromium coverage only, not production acceptance.`)
    return { status: 'passed' }
  }
}

module.exports = WorkspaceBrowserReporter
