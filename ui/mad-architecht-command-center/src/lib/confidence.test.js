import assert from 'node:assert/strict'
import { test } from 'node:test'
import { normalizeConfidence, responseConfidence } from './confidence.js'

test('only explicit finite scores are normalized, zero is preserved', () => {
  for (const value of [undefined, null, '', ' ', false, true, {}, [], NaN, Infinity, -1, 101]) {
    assert.equal(normalizeConfidence(value), null)
  }
  for (const [value, expected] of [[0, 0], ['0', 0], [.91, .91], [91, .91], ['30', .3], [100, 1]]) {
    assert.equal(normalizeConfidence(value), expected)
  }
})

test('legacy heuristics and runtime health cannot become answer correctness', () => {
  assert.equal(responseConfidence({ confidence: .74, runtime_status: { confidence: .8 } }), null)
  assert.equal(responseConfidence({ trust_metadata: { confidence: .74 } }), null)
  assert.equal(responseConfidence({ trust_metadata: { confidence_status: 'not_assessed', confidence: .99 } }), null)
  assert.equal(responseConfidence({ trust_metadata: { confidence_status: 'unverified', confidence: 0 } }), 0)
})
