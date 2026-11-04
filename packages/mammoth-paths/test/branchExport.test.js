import assert from 'node:assert/strict'
import { createHash, webcrypto } from 'node:crypto'
import { test } from 'node:test'
import { createPathsClient, decodeOwnerBranchExport, PathsError } from '../src/index.js'

// Node 18's Web Crypto global may require an embedder-supplied implementation.
if (!globalThis.crypto) globalThis.crypto = webcrypto
const id = `exec-${'a'.repeat(24)}`
const commit = 'b'.repeat(40)
const data = Buffer.from('# v2 git bundle\nfixture')
const receipt = { contract: 'mammoth.owner-branch-export.v1', execution_id: id, repo: 'owner/repo',
  branch: `mammoth/owner/${id}`, filename: `${id}.bundle`, base_sha: 'c'.repeat(40), commit_sha: commit,
  requires_base: true, automatic_push: false, encoding: 'base64', size_bytes: data.length,
  sha256: createHash('sha256').update(data).digest('hex'), bundle_base64: data.toString('base64') }

test('branch export requires explicit confirmation, validates checksum, and never retries', async () => {
  const calls = []
  let payload = { status: 'ok', export: receipt }
  const client = createPathsClient({ baseUrl: 'https://x.test', fetch: async (url, init) => {
    calls.push({ url, init })
    return new Response(JSON.stringify(payload))
  } })
  await assert.rejects(client.exportOwnerBranch(id, { repo: 'owner/repo', expectedCommit: commit }), /confirmation/)
  assert.equal(calls.length, 0)
  assert.deepEqual(await client.exportOwnerBranch(id, { repo: 'owner/repo', expectedCommit: commit, confirmPrivateExport: true }), payload)
  assert.deepEqual(Buffer.from(await decodeOwnerBranchExport(receipt, { executionId: id, expectedCommit: commit })), data)
  assert.deepEqual(JSON.parse(calls[0].init.body), { repo_context: { root: 'owner/repo' }, expected_commit: commit, confirm_private_export: true })
  for (const change of [{ sha256: 'f'.repeat(64) }, { size_bytes: true }, { size_bytes: 8388609 },
    { commit_sha: 'd'.repeat(40) }, { branch: 'another' }, { bundle_base64: 'private-body-sentinel' },
    { bundle_base64: '====' }, { requires_base: false }, { automatic_push: true }]) {
    payload = { export: { ...receipt, ...change } }
    const before = calls.length
    await assert.rejects(client.exportOwnerBranch(id, { repo: 'owner/repo', expectedCommit: commit, confirmPrivateExport: true }),
      error => error instanceof PathsError && error.code === 'invalid_response' && !error.message.includes('private-body-sentinel'))
    assert.equal(calls.length, before + 1)
  }
})

test('bundle verification requires Web Crypto and accepts the SHA-256 bundle header', async () => {
  const descriptor = Object.getOwnPropertyDescriptor(globalThis, 'crypto')
  Object.defineProperty(globalThis, 'crypto', { value: undefined, configurable: true })
  try {
    await assert.rejects(decodeOwnerBranchExport(receipt, { executionId: id, expectedCommit: commit }),
      error => error.code === 'verification_unavailable')
  } finally {
    Object.defineProperty(globalThis, 'crypto', descriptor)
  }
  const bytes = Buffer.from('# v3 git bundle\nfixture')
  const sha256Commit = 'b'.repeat(64)
  const v3 = { ...receipt, commit_sha: sha256Commit, base_sha: 'c'.repeat(64), size_bytes: bytes.length,
    bundle_base64: bytes.toString('base64'), sha256: createHash('sha256').update(bytes).digest('hex') }
  assert.deepEqual(Buffer.from(await decodeOwnerBranchExport(v3, { executionId: id, expectedCommit: sha256Commit })), bytes)
})
