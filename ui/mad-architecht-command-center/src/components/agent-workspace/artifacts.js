// Shared normalizers for agent run payloads (artifact lives at result.output).

export function normalizeResearchArtifact(runResult) {
  if (!runResult || typeof runResult !== 'object') return null
  let output = runResult?.result?.output ?? runResult?.output ?? null
  if (typeof output === 'string') {
    try { output = JSON.parse(output) } catch { output = null }
  }
  if (!output || typeof output !== 'object' || Array.isArray(output)) return null
  if (!Array.isArray(output.citations) && !Array.isArray(output.sources) && !Array.isArray(output.references)) return null
  const normalizeList = (value) => (Array.isArray(value) ? value.map(item => String(item).trim()).filter(Boolean) : [])
  return {
    status: String(output.status || runResult.status || 'ok'),
    agent: String(output.agent || runResult.agent || 'ResearchAgent'),
    mode: String(output.mode || runResult.mode || 'research'),
    prompt: String(output.prompt || runResult.prompt || ''),
    focus: String(output.focus || ''),
    summary: String(output.summary || ''),
    executive_summary: String(output.executive_summary || output.tldr || ''),
    key_facts: Array.isArray(output.key_facts) ? output.key_facts : [],
    recommended_next_steps: Array.isArray(output.recommended_next_steps) ? output.recommended_next_steps : [],
    knowledge_gaps: String(output.knowledge_gaps || ''),
    confidence_assessment: String(output.confidence_assessment || ''),
    unverified_findings: Array.isArray(output.unverified_findings) ? output.unverified_findings : [],
    quality: output.quality || {},
    findings: Array.isArray(output.findings) ? output.findings : [],
    citations: Array.isArray(output.citations) ? output.citations : [],
    references: Array.isArray(output.references) ? output.references : [],
    sources: Array.isArray(output.sources) ? output.sources : [],
    sourceCoverage: output.source_coverage && typeof output.source_coverage === 'object' ? output.source_coverage : null,
    qualityFlags: normalizeList(output.quality_flags),
    retrievalErrors: normalizeList(output.retrieval_errors),
    workflowHints: output.workflow_hints && typeof output.workflow_hints === 'object' ? output.workflow_hints : null,
    confidence: typeof output.confidence === 'number' ? output.confidence : null,
    artifact_type: output.artifact_type || '',
    title: output.title || '',
    abstract: output.abstract || output.executive_summary || '',
    sections: Array.isArray(output.sections) ? output.sections : [],
    conclusion: output.conclusion || '',
    docx_filename: output.docx_filename || '',
    word_count: output.word_count || 0,
    raw: output,
  }
}

export function normalizeCodingArtifact(runResult) {
  if (!runResult || typeof runResult !== 'object') return null
  let output = runResult?.result?.output ?? runResult?.output ?? null
  if (typeof output === 'string') {
    try { output = JSON.parse(output) } catch { output = null }
  }
  if (!output || typeof output !== 'object' || Array.isArray(output)) return null
  const normalizeList = (value) => (Array.isArray(value) ? value.map(item => String(item).trim()).filter(Boolean) : [])
  const taskPlan = output.task_plan && typeof output.task_plan === 'object' ? output.task_plan : null
  return {
    status: String(output.status || runResult.status || 'ok'),
    agent: String(output.agent || runResult.agent || 'CodingAgent'),
    mode: String(output.mode || runResult.mode || 'coding'),
    taskKind: String(output.task_kind || runResult.task_kind || runResult.intent || 'generate_code'),
    target: String(output.target || runResult.target || ''),
    prompt: String(output.prompt || runResult.prompt || ''),
    summary: String(output.summary || ''),
    code: String(output.code || output.refactored || ''),
    tests: String(output.tests || ''),
    docs: String(output.docs || ''),
    diff: String(output.diff || ''),
    confidence: typeof output.confidence === 'number' ? output.confidence : null,
    warnings: normalizeList(output.warnings),
    qualityChecks: normalizeList(output.quality_checks),
    qualityFlags: normalizeList(output.quality_flags),
    taskPlan,
    evidence: output.evidence && typeof output.evidence === 'object' ? output.evidence : null,
    validation: output.validation && typeof output.validation === 'object' ? output.validation : null,
    raw: output,
  }
}
