import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import { createPathsClient, PathsError, validateDocumentReview } from '../src/index.js'

const fixture = JSON.parse(readFileSync(new URL('../../../tests/fixtures/document-review-contract.json', import.meta.url)))
for (const mutation of fixture.invalid) {
  test(`review evidence rejects ${mutation.name}`, () => {
    const review = structuredClone(fixture.review)
    let target = review
    for (const key of mutation.path.slice(0, -1)) target = target[key]
    target[mutation.path.at(-1)] = mutation.value
    assert.throws(() => validateDocumentReview(review), error => error.code === 'invalid_response')
  })
}
for (const mutation of fixture.invalid_node) {
  test(`synthesis evidence rejects ${mutation.name}`, () => {
    const review = structuredClone(fixture.review)
    const node = structuredClone(fixture.node)
    Object.assign(review.synthesis, { status: 'completed', nodes: [node], result: structuredClone(node) })
    assert.equal(validateDocumentReview(review), review)
    let target = node
    for (const key of mutation.path.slice(0, -1)) target = target[key]
    target[mutation.path.at(-1)] = mutation.value
    assert.throws(() => validateDocumentReview(review), error => error.code === 'invalid_response')
  })
}

test('review evidence preserves additions, overrun and unknown paid work', () => {
  const review = structuredClone(fixture.review)
  assert.equal(validateDocumentReview(review), review)
  Object.assign(review, { status: 'blocked', review_complete: false, synthesis: null })
  review.usage.tokens = 130000
  assert.equal(validateDocumentReview(review), review)
  Object.assign(review, { status: 'active', inflight_section: 0, assessments: [] })
  assert.equal(validateDocumentReview(review), review)
  Object.assign(review, { status: 'ready', inflight_section: null })
  assert.equal(validateDocumentReview(review), review)
  Object.assign(review, { status: 'completed', review_complete: true, assessments: structuredClone(fixture.review.assessments),
    synthesis: structuredClone(fixture.review.synthesis), inflight_section: 'synthesis' })
  review.synthesis.status = 'blocked'
  assert.equal(validateDocumentReview(review), review)
  Object.assign(review, { max_tokens: 128000, budget_extensions: [
    { previous_max_tokens: 64000, max_tokens: 128000, reported_tokens: 200, confirmed_at: 't' },
  ] })
  assert.equal(validateDocumentReview(review), review)
  review.budget_extensions[0].reported_tokens = true
  assert.throws(() => validateDocumentReview(review), /Invalid saved/)
})

test('review client rejects malformed paid evidence once and recovers by GET only', async () => {
  const calls = []
  let payload = { review: { private: 'private-body-sentinel' } }
  const client = createPathsClient({ baseUrl: 'https://x.test', fetch: async (url, init) => {
    calls.push(init.method)
    return new Response(JSON.stringify(payload), { status: 200 })
  } })
  await assert.rejects(client.advanceDocumentReview(fixture.review.id, { confirmModelUsage: true }), error =>
    error instanceof PathsError && error.code === 'invalid_response' && !error.message.includes('private-body-sentinel')
    && Object.keys(error.payload).length === 0)
  assert.deepEqual(calls, ['POST'])
  payload = { review: fixture.review }
  assert.deepEqual((await client.getDocumentReview(fixture.review.id)).review, fixture.review)
  assert.deepEqual(calls, ['POST', 'GET'])
  payload = { reviews: [fixture.review] }
  await assert.rejects(client.listDocumentReviews('wrong-file', { scope: 'atlas' }), error => error.code === 'invalid_response')
  payload = { review: { ...fixture.review, id: `review-${'c'.repeat(24)}` } }
  await assert.rejects(client.getDocumentReview(fixture.review.id), error => error.code === 'invalid_response')
  payload = { deleted: 'wrong-id' }
  await assert.rejects(client.deleteDocumentReview(fixture.review.id), error => error.code === 'invalid_response')
  payload = { reviews: [] }
  assert.deepEqual((await client.listDocumentReviews('file-one')).reviews, [])
})
