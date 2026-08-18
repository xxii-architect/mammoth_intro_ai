import { useState, useEffect, useMemo } from 'react'
import { DollarSign, Plus, Wallet, BriefcaseBusiness, ReceiptText } from 'lucide-react'
import { api } from '../api/client'

export default function LogSalePage() {
  const [sales, setSales] = useState([])
  const [form, setForm] = useState({
    item: '',
    amount: '',
    notes: '',
    ledger: 'personal',
    category: 'general',
    date: new Date().toISOString().split('T')[0],
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    api('/logsale').then(setSales).catch(() => {})
  }, [])

  const submit = async (e) => {
    e.preventDefault()
    if (!form.item || !form.amount) return
    setSaving(true)
    setError('')
    try {
      const entry = await api('/logsale', {
        method: 'POST',
        body: { ...form, amount: parseFloat(form.amount) },
      })
      if (entry?.status === 'error') {
        throw new Error(entry.error || 'Unable to save sale')
      }
      setSales(prev => [...prev, entry])
      setForm({
        item: '',
        amount: '',
        notes: '',
        ledger: form.ledger,
        category: form.category,
        date: new Date().toISOString().split('T')[0],
      })
    } catch (e) {
      setError(e.message || 'Unable to save sale')
    } finally {
      setSaving(false)
    }
  }

  const total = sales.reduce((s, entry) => s + (parseFloat(entry.amount) || 0), 0)
  const personalSales = useMemo(() => sales.filter((entry) => (entry.ledger || 'personal') === 'personal'), [sales])
  const businessSales = useMemo(() => sales.filter((entry) => (entry.ledger || 'personal') === 'business'), [sales])
  const personalTotal = personalSales.reduce((s, entry) => s + (parseFloat(entry.amount) || 0), 0)
  const businessTotal = businessSales.reduce((s, entry) => s + (parseFloat(entry.amount) || 0), 0)
  const recentSales = [...sales].reverse().slice(0, 5)

  const fieldStyle = {
    width: '100%',
    padding: '10px 12px',
    borderRadius: 10,
    border: '1px solid var(--border)',
    background: 'rgba(255,255,255,0.04)',
    color: 'var(--txt-pri)',
    fontSize: '0.85rem',
    outline: 'none',
    boxSizing: 'border-box',
  }

  return (
    <div className="page-enter" style={{ padding: 24 }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap', marginBottom: 20 }}>
        <div>
          <h1 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: 8, display: 'flex', alignItems: 'center', gap: 8 }}>
            <DollarSign size={20} color="var(--cyan)" /> Revenue Ledger
          </h1>
          <p style={{ margin: 0, color: 'var(--txt-sec)', fontSize: '0.84rem', lineHeight: 1.6, maxWidth: 720 }}>
            Track personal and business sales in one operator-ready surface with cleaner ledger summaries, clearer entry capture, and a more branded MammothOS layout.
          </p>
        </div>
        <div className="glass-card-solid" style={{ padding: '12px 14px', minWidth: 240 }}>
          <div style={{ fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-mut)', marginBottom: 5 }}>Latest split</div>
          <div style={{ color: 'var(--txt-pri)', fontSize: '0.84rem', lineHeight: 1.6 }}>
            Personal <span style={{ color: 'var(--photon)', fontFamily: 'JetBrains Mono,monospace' }}>${personalTotal.toFixed(2)}</span> • Business <span style={{ color: 'var(--cyan)', fontFamily: 'JetBrains Mono,monospace' }}>${businessTotal.toFixed(2)}</span>
          </div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(220px,1fr))', gap: 12, marginBottom: 18 }}>
        <div className="glass-card-solid" style={{ padding: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
            <ReceiptText size={15} color="var(--cyan)" />
            <div style={{ fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-mut)' }}>Total revenue</div>
          </div>
          <div style={{ fontSize: '1.5rem', fontWeight: 800, fontFamily: 'JetBrains Mono,monospace', color: 'var(--txt-pri)' }}>${total.toFixed(2)}</div>
          <div style={{ fontSize: '0.74rem', color: 'var(--txt-sec)', marginTop: 6 }}>{sales.length} logged entr{sales.length === 1 ? 'y' : 'ies'}</div>
        </div>
        <div className="glass-card-solid" style={{ padding: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
            <Wallet size={15} color="var(--photon)" />
            <div style={{ fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-mut)' }}>Personal ledger</div>
          </div>
          <div style={{ fontSize: '1.5rem', fontWeight: 800, fontFamily: 'JetBrains Mono,monospace', color: 'var(--photon)' }}>${personalTotal.toFixed(2)}</div>
          <div style={{ fontSize: '0.74rem', color: 'var(--txt-sec)', marginTop: 6 }}>{personalSales.length} personal entr{personalSales.length === 1 ? 'y' : 'ies'}</div>
        </div>
        <div className="glass-card-solid" style={{ padding: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
            <BriefcaseBusiness size={15} color="var(--cyan)" />
            <div style={{ fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-mut)' }}>Business ledger</div>
          </div>
          <div style={{ fontSize: '1.5rem', fontWeight: 800, fontFamily: 'JetBrains Mono,monospace', color: 'var(--cyan)' }}>${businessTotal.toFixed(2)}</div>
          <div style={{ fontSize: '0.74rem', color: 'var(--txt-sec)', marginTop: 6 }}>{businessSales.length} business entr{businessSales.length === 1 ? 'y' : 'ies'}</div>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap', alignItems: 'flex-start' }}>
        <div style={{ flex: '0 0 340px' }}>
          <form onSubmit={submit} className="glass-card-solid" style={{ padding: 20, borderLeft: '2px solid var(--cyan)' }}>
            <div className="eyebrow" style={{ marginBottom: 6 }}>Capture sale</div>
            <h3 style={{ marginBottom: 10 }}>Log a new revenue entry</h3>
            <p style={{ margin: '0 0 16px', color: 'var(--txt-sec)', fontSize: '0.8rem', lineHeight: 1.6 }}>
              Keep the ledger split clean so personal and business totals stay readable from the home dashboard and sales history.
            </p>
            {error ? (
              <div style={{ marginBottom: 14, padding: '10px 12px', borderRadius: 10, border: '1px solid rgba(248,113,113,0.22)', background: 'rgba(127,29,29,0.18)', color: '#fecaca', fontSize: '0.78rem' }}>
                {error}
              </div>
            ) : null}
            <div style={{ display: 'grid', gap: 12 }}>
              {[
                { key: 'item', label: 'Item / Product', placeholder: 'e.g. Tomato Seeds (25lb)' },
                { key: 'amount', label: 'Amount ($)', placeholder: '0.00', type: 'number' },
                { key: 'date', label: 'Date', type: 'date' },
              ].map(({ key, label, placeholder, type = 'text' }) => (
                <div key={key}>
                  <label style={{ fontSize: '0.72rem', color: 'var(--txt-mut)', display: 'block', marginBottom: 4 }}>{label}</label>
                  <input
                    type={type}
                    value={form[key]}
                    onChange={e => setForm(f => ({ ...f, [key]: e.target.value }))}
                    placeholder={placeholder}
                    style={fieldStyle}
                  />
                </div>
              ))}
              <div>
                <label style={{ fontSize: '0.72rem', color: 'var(--txt-mut)', display: 'block', marginBottom: 4 }}>Ledger</label>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                  {[
                    { value: 'personal', label: 'Personal' },
                    { value: 'business', label: 'Business' },
                  ].map((option) => {
                    const active = form.ledger === option.value
                    return (
                      <button
                        key={option.value}
                        type="button"
                        onClick={() => setForm(f => ({ ...f, ledger: option.value }))}
                        style={{
                          padding: '10px 12px',
                          borderRadius: 10,
                          border: `1px solid ${active ? 'rgba(0,245,212,0.28)' : 'var(--border)'}`,
                          background: active ? 'rgba(0,245,212,0.08)' : 'rgba(255,255,255,0.03)',
                          color: active ? 'var(--photon)' : 'var(--txt-sec)',
                          fontSize: '0.82rem',
                          fontWeight: 700,
                          cursor: 'pointer',
                        }}
                      >
                        {option.label}
                      </button>
                    )
                  })}
                </div>
              </div>
              <div>
                <label style={{ fontSize: '0.72rem', color: 'var(--txt-mut)', display: 'block', marginBottom: 4 }}>Category</label>
                <input
                  type="text"
                  value={form.category}
                  onChange={e => setForm(f => ({ ...f, category: e.target.value }))}
                  placeholder={form.ledger === 'business' ? 'e.g. Product Sales' : 'e.g. Household'}
                  style={fieldStyle}
                />
              </div>
              <div>
                <label style={{ fontSize: '0.72rem', color: 'var(--txt-mut)', display: 'block', marginBottom: 4 }}>Notes</label>
                <textarea
                  value={form.notes}
                  onChange={e => setForm(f => ({ ...f, notes: e.target.value }))}
                  rows={3}
                  placeholder="Optional notes…"
                  style={{ ...fieldStyle, color: 'var(--txt-sec)', resize: 'vertical', minHeight: 94 }}
                />
              </div>
              <button
                type="submit"
                disabled={saving}
                style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, padding: '11px', borderRadius: 10, border: 'none', background: 'linear-gradient(90deg,var(--photon),var(--cyan))', color: '#050608', fontWeight: 700, fontSize: '0.85rem', cursor: 'pointer', opacity: saving ? 0.7 : 1 }}
              >
                <Plus size={16} /> {saving ? 'Saving…' : 'Log Sale'}
              </button>
            </div>
          </form>
        </div>

        <div style={{ flex: 1, minWidth: 280 }}>
          <div className="glass-card-solid" style={{ padding: 18, marginBottom: 16 }}>
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
              <div>
                <div className="eyebrow" style={{ marginBottom: 6 }}>Recent sales pulse</div>
                <div style={{ fontSize: '0.96rem', color: 'var(--txt-pri)', fontWeight: 700, marginBottom: 6 }}>Newest entries and ledger split at a glance</div>
                <div style={{ color: 'var(--txt-sec)', fontSize: '0.78rem', lineHeight: 1.6 }}>
                  The most recent items stay visible here before they roll into the full table below.
                </div>
              </div>
              <div style={{ fontSize: '0.74rem', color: 'var(--txt-mut)' }}>
                {sales.length} total entr{sales.length === 1 ? 'y' : 'ies'}
              </div>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(220px,1fr))', gap: 10, marginTop: 14 }}>
              {recentSales.length > 0 ? recentSales.map((entry) => (
                <div key={entry.id} className="glass-card" style={{ padding: '12px 14px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, marginBottom: 6 }}>
                    <div style={{ color: 'var(--txt-pri)', fontSize: '0.82rem', fontWeight: 700 }}>{entry.item}</div>
                    <div style={{ color: entry.ledger === 'business' ? 'var(--cyan)' : 'var(--photon)', fontSize: '0.74rem', textTransform: 'capitalize' }}>
                      {entry.ledger || 'personal'}
                    </div>
                  </div>
                  <div style={{ color: 'var(--txt-sec)', fontSize: '0.74rem', marginBottom: 6 }}>{entry.category || 'general'} • {entry.date}</div>
                  <div style={{ color: 'var(--txt-pri)', fontFamily: 'JetBrains Mono,monospace', fontSize: '0.88rem', fontWeight: 700 }}>${parseFloat(entry.amount).toFixed(2)}</div>
                </div>
              )) : (
                <div style={{ color: 'var(--txt-mut)', fontSize: '0.8rem' }}>No recent sales yet.</div>
              )}
            </div>
          </div>

          <div className="glass-card-solid" style={{ borderRadius: 12, overflow: 'hidden' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10, padding: '14px 16px', borderBottom: '1px solid var(--border)' }}>
              <div>
                <div style={{ fontSize: '0.82rem', color: 'var(--txt-pri)', fontWeight: 700 }}>Revenue history</div>
                <div style={{ fontSize: '0.72rem', color: 'var(--txt-mut)', marginTop: 4 }}>Full ledger table across both personal and business entries</div>
              </div>
              <div style={{ color: 'var(--txt-sec)', fontSize: '0.72rem' }}>
                Total <span style={{ color: 'var(--cyan)', fontFamily: 'JetBrains Mono,monospace' }}>${total.toFixed(2)}</span>
              </div>
            </div>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border)' }}>
                  {['Date', 'Item', 'Ledger', 'Category', 'Amount', 'Notes'].map((heading) => (
                    <th key={heading} style={{ padding: '12px 16px', textAlign: 'left', fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-mut)', fontWeight: 600 }}>{heading}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {[...sales].reverse().map((entry, index) => (
                  <tr key={entry.id} style={{ borderTop: index ? '1px solid var(--border)' : 'none' }}>
                    <td style={{ padding: '11px 16px', fontFamily: 'JetBrains Mono,monospace', color: 'var(--txt-mut)', fontSize: '0.78rem' }}>{entry.date}</td>
                    <td style={{ padding: '11px 16px', color: 'var(--txt-pri)' }}>{entry.item}</td>
                    <td style={{ padding: '11px 16px', color: entry.ledger === 'business' ? 'var(--cyan)' : 'var(--photon)', textTransform: 'capitalize', fontSize: '0.78rem', fontWeight: 700 }}>{entry.ledger || 'personal'}</td>
                    <td style={{ padding: '11px 16px', color: 'var(--txt-sec)', fontSize: '0.78rem' }}>{entry.category || 'general'}</td>
                    <td style={{ padding: '11px 16px', fontFamily: 'JetBrains Mono,monospace', color: 'var(--cyan)', fontWeight: 600 }}>${parseFloat(entry.amount).toFixed(2)}</td>
                    <td style={{ padding: '11px 16px', color: 'var(--txt-sec)', fontSize: '0.78rem' }}>{entry.notes || '–'}</td>
                  </tr>
                ))}
                {sales.length === 0 && (
                  <tr>
                    <td colSpan={6} style={{ padding: '24px 16px', textAlign: 'center', color: 'var(--txt-mut)' }}>No sales logged yet.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  )
}
