import { useEffect, useRef, useState } from 'react'
import { api } from '../api/client'
import { useAuth } from '../lib/authContext'

export default function RuntimeUsageControls() {
  const { user } = useAuth()
  const generation = useRef(0)
  const [snapshot, setSnapshot] = useState(null)
  const [limit, setLimit] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const load = async () => {
    const request = ++generation.current
    setBusy(true)
    setError('')
    try {
      const data = await api('/runtime/usage')
      if (request !== generation.current) return
      setSnapshot(data)
      setLimit(data.daily_token_limit == null ? '' : String(data.daily_token_limit))
    } catch (err) {
      if (request === generation.current) setError(err.message || 'Could not load runtime usage.')
    } finally {
      if (request === generation.current) setBusy(false)
    }
  }
  useEffect(() => {
    setSnapshot(null)
    setLimit('')
    load()
    return () => { generation.current++ }
  }, [user?.id])

  const save = async (event) => {
    event.preventDefault()
    const request = ++generation.current
    setBusy(true)
    setError('')
    try {
      const value = limit.trim() === '' ? null : Number(limit)
      if (value !== null && (!Number.isSafeInteger(value) || value < 0 || value > 100000000)) {
        throw new Error('Use a whole number from 0 to 100000000, or leave empty for no ceiling.')
      }
      const data = await api('/runtime/usage/policy', { method: 'PUT', body: JSON.stringify({ daily_token_limit: value }) })
      if (request === generation.current) setSnapshot(data)
    } catch (err) {
      if (request === generation.current) setError(err.message || 'Could not save runtime ceiling.')
    } finally {
      if (request === generation.current) setBusy(false)
    }
  }

  return (
    <section className="glass-card-solid" style={{ padding: 20, marginBottom: 20 }} aria-label="Runtime usage controls">
      <h2 style={{ fontSize: '1rem' }}>Runtime usage controls</h2>
      <p>Private to your login across workspace accounts. UTC daily token admission, not dollars or Copilot credits.</p>
      {snapshot && <p role="status">
        Reported: {snapshot.reported_tokens} tokens. Unresolved reservations: {snapshot.unresolved_reserved_tokens}.
        {' '}Accounting: {snapshot.accounting_status}. Completion attempts: {snapshot.attempts}.
      </p>}
      <p>Calls through the shared completion API and standard OpenAI/Ollama text adapters are covered, including agent runs and indexed reviews.
        Embeddings, custom paths, internal SDK retries and provider invoices are not separately covered. Unknown or interrupted calls retain their full reservation.
        No automatic replay, paid health probes, or cancellation of already-started calls.</p>
      <form onSubmit={save} style={{ display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'center' }}>
        <label>Daily token ceiling (empty = no ceiling)
          <input aria-label="Daily runtime token ceiling" type="number" min="0" max="100000000" step="1"
            value={limit} onChange={event => setLimit(event.target.value)} disabled={busy || !snapshot} />
        </label>
        <button type="submit" disabled={busy || !snapshot}>Save runtime ceiling</button>
        <button type="button" onClick={load} disabled={busy}>Reload runtime usage</button>
      </form>
      <p>Zero blocks new covered calls. Full input/output allowance must fit before a call starts.
        Changing the ceiling does not erase usage or release unknown reservations.</p>
      {error && <p role="alert">{error}</p>}
    </section>
  )
}
