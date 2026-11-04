import { useEffect, useRef, useState } from 'react'
import { api, getTenantScope, setTenantScope } from '../api/client'
import { useAuth } from '../lib/authContext'

export default function TenantUsageControls() {
  const { user } = useAuth()
  const generation = useRef(0)
  const [tenants, setTenants] = useState([])
  const [selected, setSelected] = useState('')
  const [enabled, setEnabled] = useState(null)
  const [snapshot, setSnapshot] = useState(null)
  const [tokens, setTokens] = useState('')
  const [dollars, setDollars] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const admin = ['owner', 'admin'].includes(tenants.find(item => item.tenant_id === selected)?.role)

  const apply = data => {
    setSnapshot(data)
    setTokens(data.daily_token_limit == null ? '' : String(data.daily_token_limit))
    setDollars(data.daily_usd_limit_micros == null ? '' : (data.daily_usd_limit_micros / 1000000).toFixed(6))
  }
  const load = async (tenantId, reloadMemberships = false) => {
    const request = ++generation.current
    setBusy(true)
    setError('')
    setSnapshot(null)
    try {
      if (reloadMemberships) {
        const data = await api('/runtime/tenants')
        if (request !== generation.current) return
        if (typeof data?.enabled !== 'boolean' || !Array.isArray(data.tenants)) throw new Error('Tenant membership response is invalid.')
        setEnabled(data.enabled)
        setTenants(data.tenants)
        if (!data.enabled) return
        const saved = getTenantScope(user?.id)
        tenantId = data.tenants.some(item => item.tenant_id === saved) ? saved
          : data.tenants.length === 1 ? data.tenants[0].tenant_id : ''
      }
      if (request !== generation.current) return
      setSelected(tenantId)
      setTenantScope(user?.id, tenantId)
      if (tenantId) {
        const data = await api(`/runtime/tenant-usage?tenant_id=${encodeURIComponent(tenantId)}`)
        if (request === generation.current) apply(data)
      }
    } catch (err) {
      if (request === generation.current) setError(err.message || 'Tenant usage could not be loaded.')
    } finally {
      if (request === generation.current) setBusy(false)
    }
  }
  useEffect(() => {
    setEnabled(null)
    setTenants([])
    setSelected('')
    setSnapshot(null)
    setError('')
    load('', true)
    return () => { generation.current++ }
  }, [user?.id])

  const save = async event => {
    event.preventDefault()
    const request = ++generation.current
    setBusy(true)
    setError('')
    try {
      const dailyTokens = tokens.trim() === '' ? null : Number(tokens)
      if (dailyTokens !== null && (!Number.isSafeInteger(dailyTokens) || dailyTokens < 0 || dailyTokens > 1000000000)) {
        throw new Error('Use whole tokens from 0 to 1000000000, or leave empty.')
      }
      let micros = null
      if (dollars.trim() !== '') {
        if (!/^\d+(?:\.\d{1,6})?$/.test(dollars.trim())) throw new Error('Use non-negative USD with at most six decimal places.')
        const [whole, fraction = ''] = dollars.trim().split('.')
        micros = Number(whole) * 1000000 + Number(fraction.padEnd(6, '0'))
        if (!Number.isSafeInteger(micros) || micros > 1000000000000) throw new Error('The maximum daily USD ceiling is 1000000.')
      }
      const data = await api('/runtime/tenant-usage/policy', { method: 'PUT', body: {
        tenant_id: selected, daily_token_limit: dailyTokens, daily_usd_limit_micros: micros,
      } })
      if (request === generation.current) apply(data)
    } catch (err) {
      if (request === generation.current) setError(err.message || 'Tenant policy could not be saved.')
    } finally {
      if (request === generation.current) setBusy(false)
    }
  }

  return <section className="glass-card-solid" style={{ padding: 20, marginBottom: 20 }} aria-label="Tenant usage controls">
    <h2 style={{ fontSize: '1rem' }}>Tenant usage controls</h2>
    <p>Shared UTC-day admission across tenant members. Estimated USD is not a provider invoice or Copilot credits.
      The private login ceiling remains additive.</p>
    {enabled === false && <p>Shared tenant admission is not enabled on this deployment. Private login limits do not enforce a tenant budget.</p>}
    {enabled && <>
      <label>Active billing tenant
        <select aria-label="Active billing tenant" disabled={busy} value={selected} onChange={event => load(event.target.value)}>
          <option value="">Select a tenant</option>
          {tenants.map(item => <option key={item.tenant_id} value={item.tenant_id}>{item.name} ({item.role})</option>)}
        </select>
      </label>
      {!selected && <p>Select a tenant before starting covered model calls. Membership is checked by the backend.</p>}
      {snapshot && <p role="status">Estimated USD: {(snapshot.estimated_usd_micros / 1000000).toFixed(6)}.
        {' '}Unknown-price attempts: {snapshot.unknown_price_attempts}. Unknown-usage attempts: {snapshot.unknown_attempts}.
        {' '}Reported tokens: {snapshot.reported_tokens}. Reserved unresolved tokens: {snapshot.unresolved_reserved_tokens}.</p>}
      <form onSubmit={save} style={{ display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'center' }}>
        <label>Daily tenant token ceiling
          <input aria-label="Daily tenant token ceiling" type="number" min="0" max="1000000000" step="1"
            disabled={busy || !snapshot || !admin} value={tokens} onChange={event => setTokens(event.target.value)} />
        </label>
        <label>Daily estimated USD ceiling
          <input aria-label="Daily estimated USD ceiling" type="text" inputMode="decimal"
            disabled={busy || !snapshot || !admin} value={dollars} onChange={event => setDollars(event.target.value)} />
        </label>
        <button type="submit" disabled={busy || !snapshot || !admin}>Save tenant ceilings</button>
      </form>
      <p>Only tenant owners/admins can change policy. Empty means uncapped; zero blocks new covered calls.
        Dollar-capped calls need a current exact provider/model price. Unknown outcomes retain the full reservation.
        Prices are operator-reviewed, not editable here. Embeddings and other uninstrumented paid services are outside coverage.</p>
    </>}
    <button type="button" disabled={busy} onClick={() => load(selected, true)}>Reload tenant usage</button>
    {error && <p role="alert">{error}</p>}
  </section>
}
