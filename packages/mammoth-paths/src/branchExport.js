/** Verify bounded transport evidence; local Git must still verify/import the bundle. */
export async function decodeOwnerBranchExport(value, { executionId, expectedCommit }) {
  const invalid = () => {
    const error = new Error('Invalid branch export receipt, checksum or size')
    error.code = 'invalid_response'
    return error
  }
  const hex = (item, lengths) => typeof item === 'string' && lengths.includes(item.length) && /^[a-f0-9]+$/.test(item)
  if (!value || typeof value !== 'object' || Array.isArray(value)
    || value.contract !== 'mammoth.owner-branch-export.v1'
    || typeof executionId !== 'string' || executionId.length !== 29 || !/^exec-[a-f0-9]{24}$/.test(executionId)
    || value.execution_id !== executionId || value.commit_sha !== expectedCommit || !hex(expectedCommit, [40, 64])
    || !hex(value.base_sha, [40, 64]) || !hex(value.sha256, [64])
    || value.branch !== `mammoth/owner/${executionId}` || value.filename !== `${executionId}.bundle`
    || typeof value.repo !== 'string' || value.requires_base !== true || value.automatic_push !== false
    || value.encoding !== 'base64' || !Number.isSafeInteger(value.size_bytes) || value.size_bytes <= 0 || value.size_bytes > 8 * 1024 * 1024
    || typeof value.bundle_base64 !== 'string' || value.bundle_base64.length > 11184812
    || value.bundle_base64.length % 4 !== 0 || /^[A-Za-z0-9+/]*={0,2}$/.exec(value.bundle_base64)?.[0] !== value.bundle_base64) throw invalid()
  const bytes = Uint8Array.from(atob(value.bundle_base64), character => character.charCodeAt(0))
  const header = new TextDecoder().decode(bytes.slice(0, 16))
  if (bytes.length !== value.size_bytes || !['# v2 git bundle\n', '# v3 git bundle\n'].includes(header)) throw invalid()
  if (!globalThis.crypto?.subtle) {
    const error = new Error('Branch export verification requires Web Crypto in a secure context')
    error.code = 'verification_unavailable'
    throw error
  }
  const digest = new Uint8Array(await globalThis.crypto.subtle.digest('SHA-256', bytes))
  if ([...digest].map(item => item.toString(16).padStart(2, '0')).join('') !== value.sha256) throw invalid()
  return bytes
}
