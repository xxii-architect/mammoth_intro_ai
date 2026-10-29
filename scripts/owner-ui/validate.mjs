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
if (process.argv[2] === 'build') {
  const result = spawnSync('npm', ['run', 'build'], {
    cwd: ui,
    stdio: 'inherit',
    env: { ...process.env, CI: '1' },
  })
  if (result.error) throw result.error
  if (result.status !== 0) process.exit(result.status || 1)
  console.log('MAMMOTH_UI_BUILD_PASSED')
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
      assert.ok(html.includes(`Output confidence: ${expected}`), `Supplied score ${confidence} must render ${expected}.`)
    }
    console.log('MAMMOTH_UI_COMPONENT_PASSED: TrustBadgeRow explicit zero, low and high scores; provider retained.')
  } finally {
    await server.close()
  }
} else {
  throw new Error('Expected build or component profile.')
}
