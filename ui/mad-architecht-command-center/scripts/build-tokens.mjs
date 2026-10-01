// Compiles src/design/tokens.json (DTCG) into src/design/tokens.css custom properties.
// Usage: npm run tokens
import { readFileSync, writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const src = resolve(here, '../src/design/tokens.json')
const out = resolve(here, '../src/design/tokens.css')

const tokens = JSON.parse(readFileSync(src, 'utf8'))
const lines = []

function formatValue(type, value) {
  if (type === 'cubicBezier' && Array.isArray(value)) return `cubic-bezier(${value.join(', ')})`
  return String(value)
}

function walk(node, path, inheritedType) {
  const type = node.$type || inheritedType
  if (Object.prototype.hasOwnProperty.call(node, '$value')) {
    lines.push(`  --mm-${path.join('-')}: ${formatValue(type, node.$value)};`)
    return
  }
  for (const [key, child] of Object.entries(node)) {
    if (key.startsWith('$') || typeof child !== 'object' || child === null) continue
    walk(child, [...path, key], type)
  }
}

walk(tokens, [], undefined)

const css = `/* AUTO-GENERATED from tokens.json by scripts/build-tokens.mjs. Do not edit by hand. */
:root {
${lines.join('\n')}
}

@media (prefers-reduced-motion: reduce) {
  :root {
    --mm-motion-duration-fast: 0ms;
    --mm-motion-duration-base: 0ms;
    --mm-motion-duration-slow: 0ms;
  }
}
`

writeFileSync(out, css)
console.log(`tokens: wrote ${lines.length} custom properties -> ${out}`)
