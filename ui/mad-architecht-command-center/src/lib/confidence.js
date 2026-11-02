export function normalizeConfidence(value) {
  if (typeof value !== 'number' && typeof value !== 'string') return null
  if (typeof value === 'string' && !value.trim()) return null
  const numeric = Number(value)
  if (!Number.isFinite(numeric) || numeric < 0 || numeric > 100) return null
  return numeric > 1 ? numeric / 100 : numeric
}

export function responseConfidence(entry) {
  const metadata = entry?.trust_metadata
  if (!metadata?.confidence_status || metadata.confidence_status === 'not_assessed') return null
  return normalizeConfidence(metadata.confidence)
}
