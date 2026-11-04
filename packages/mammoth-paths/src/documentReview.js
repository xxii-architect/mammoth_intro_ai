/** Structural evidence guards, not authorization or factual verification. */
export function validateDocumentReview(value, { reviewId, fileId, scope } = {}) {
  const require = condition => {
    if (!condition) {
      const error = new Error('Invalid saved document review; reload authoritative state before further work')
      error.code = 'invalid_response'
      throw error
    }
  }
  const object = item => item !== null && typeof item === 'object' && !Array.isArray(item)
  const integer = (item, min = 0) => Number.isSafeInteger(item) && item >= min
  const equal = (a, b) => JSON.stringify(a) === JSON.stringify(b)
  require(object(value))
  require(value.contract === 'mammoth.document-review.v1' && typeof value.id === 'string' && value.id.length === 31 && /^review-[a-f0-9]{24}$/.test(value.id))
  require(typeof value.id === 'string' && typeof value.file_id === 'string' && !!value.file_id)
  require(['chat', 'atlas'].includes(value.scope))
  require(reviewId === undefined || value.id === reviewId)
  require(fileId === undefined || value.file_id === fileId)
  require(scope === undefined || value.scope === scope)
  require(['ready', 'partial', 'active', 'completed', 'blocked'].includes(value.status))
  for (const key of ['goal', 'name', 'stop_reason', 'created_at', 'updated_at']) require(typeof value[key] === 'string')
  const digest = value.source_sha256
  require(typeof digest === 'string' && digest.length === 64 && /^[a-f0-9]{64}$/.test(digest))
  const total = value.total_sections
  require(integer(total, 1) && typeof value.review_complete === 'boolean')
  require(integer(value.max_tokens) && value.max_tokens >= 64000 && value.max_tokens <= 128000)
  require(value.max_extended_tokens === undefined || value.max_extended_tokens === 128000)
  require(value.batch_sections === 3)
  require(object(value.usage) && integer(value.usage.tokens) && typeof value.usage.accounting_status === 'string')
  require(Array.isArray(value.warnings) && value.warnings.every(item => typeof item === 'string'))
  require(value.coverage_basis === 'indexed_sections_not_original_file_or_factual_verification')
  const assessments = value.assessments
  require(Array.isArray(assessments) && assessments.length <= total)
  assessments.forEach((item, index) => {
    require(object(item) && item.chunk_index === index && item.source_sha256 === digest)
    for (const key of ['location', 'summary', 'quote', 'model', 'reasoning_trace']) require(typeof item[key] === 'string')
    require(!!item.summary.trim() && Array.from(item.quote).length >= 1 && Array.from(item.quote).length <= 300)
    require(integer(item.reported_tokens, 1) && object(item.quality) && item.quality.fact_verification === 'not_performed')
  })
  require(!value.review_complete || assessments.length === total)
  require(value.status !== 'completed' || value.review_complete)
  require(value.status !== 'ready' || !assessments.length && !value.review_complete)
  const marker = value.inflight_section
  require(marker === null || marker === undefined || marker === 'synthesis' || integer(marker) && marker === assessments.length && marker < total)
  require(marker == null || ['active', 'blocked'].includes(value.status) || marker === 'synthesis' && value.status === 'completed')
  let previous = 64000
  let retained = 0
  const history = value.budget_extensions === undefined ? [] : value.budget_extensions
  require(Array.isArray(history))
  for (const extension of history) {
    require(object(extension) && extension.previous_max_tokens === previous)
    require(integer(extension.max_tokens) && previous < extension.max_tokens && extension.max_tokens <= 128000)
    require(integer(extension.reported_tokens) && retained <= extension.reported_tokens && extension.reported_tokens <= value.usage.tokens
      && extension.reported_tokens < extension.max_tokens && typeof extension.confirmed_at === 'string')
    previous = extension.max_tokens
    retained = extension.reported_tokens
  }
  require(previous === value.max_tokens)
  const synthesis = value.synthesis
  if (synthesis != null) {
    require(value.review_complete && object(synthesis))
    require(['active', 'partial', 'completed', 'blocked'].includes(synthesis.status) && typeof synthesis.stop_reason === 'string')
    require(synthesis.basis === 'saved_assessments_not_full_source' && synthesis.fact_verification === 'not_performed')
    require(integer(synthesis.level) && Array.isArray(synthesis.levels) && synthesis.level === synthesis.levels.length)
    const nodes = (items, inputs, leaf, complete) => {
      require(Array.isArray(items) && items.length <= Math.ceil(inputs.length / 8))
      require(!complete || items.length === Math.ceil(inputs.length / 8))
      items.forEach((node, index) => {
        const group = inputs.slice(index * 8, (index + 1) * 8)
        const expected = [...new Set(group.flatMap(item => leaf ? [item.chunk_index] : item.section_indices))].sort((a, b) => a - b)
        const allowed = new Set(leaf ? expected : group.flatMap(item => item.citations))
        require(object(node) && node.source_sha256 === digest)
        require(Array.isArray(node.section_indices) && node.section_indices.every(item => integer(item)) && equal(node.section_indices, expected))
        require(Array.isArray(node.citations) && !!node.citations.length && node.citations.every(item => integer(item) && allowed.has(item)))
        require(equal(node.citations, [...new Set(node.citations)].sort((a, b) => a - b)))
        require(typeof node.summary === 'string' && !!node.summary.trim())
        require(typeof node.model === 'string' && typeof node.reasoning_trace === 'string')
        require(integer(node.reported_tokens, 1) && object(node.quality) && node.quality.fact_verification === 'not_performed')
      })
    }
    let inputs = assessments
    synthesis.levels.forEach((items, level) => {
      nodes(items, inputs, level === 0, true)
      require(items.length > 1)
      inputs = items
    })
    nodes(synthesis.nodes, inputs, synthesis.level === 0, false)
    if (synthesis.result != null) {
      require(object(synthesis.result) && synthesis.nodes.length === 1)
      nodes([synthesis.result], inputs, synthesis.level === 0, false)
      for (const key of ['summary', 'citations', 'section_indices', 'source_sha256', 'model', 'reported_tokens', 'reasoning_trace']) {
        require(equal(synthesis.result[key], synthesis.nodes[0][key]))
      }
      require(synthesis.result.section_indices.length === total && synthesis.result.section_indices.every((section, index) => section === index))
    }
    require(synthesis.status !== 'completed' || synthesis.result != null)
  }
  require(marker !== 'synthesis' || synthesis != null)
  return value
}
