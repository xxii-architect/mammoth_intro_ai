import { useState, useEffect } from 'react'
import { DollarSign, Plus } from 'lucide-react'
import { api } from '../api/client'

export default function LogSalePage() {
  const [sales, setSales]     = useState([])
  const [form, setForm]       = useState({
    item: '', amount: '', notes: '', ledger: 'personal', category: 'general',
    date: new Date().toISOString().split('T')[0],
  })
  const [saving, setSaving]   = useState(false)

  useEffect(() => {
    api('/logsale').then(setSales).catch(() => {})
  }, [])

  const submit = async (e) => {
    e.preventDefault()
    if (!form.item || !form.amount) return
    setSaving(true)
    try {
      const entry = await api('/logsale', {
        method: 'POST',
        body: { ...form, amount: parseFloat(form.amount) },
      })
      if (entry?.status === 'error') {
        throw new Error(entry.error || 'Unable to save sale')
      }
      setSales(prev => [...prev, entry])
      setForm({ item: '', amount: '', notes: '', ledger: form.ledger, category: form.category, date: new Date().toISOString().split('T')[0] })
    } catch (e) {
      alert('Failed: ' + e.message)
    }
    setSaving(false)
  }

  const total = sales.reduce((s, e) => s + (parseFloat(e.amount) || 0), 0)
  const personalTotal = sales.filter((e) => (e.ledger || 'personal') === 'personal').reduce((s, e) => s + (parseFloat(e.amount) || 0), 0)
  const businessTotal = sales.filter((e) => (e.ledger || 'personal') === 'business').reduce((s, e) => s + (parseFloat(e.amount) || 0), 0)

  return (
    <div className="page-enter" style={{ padding: 24 }}>
      <h1 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: 20, display: 'flex', alignItems: 'center', gap: 8 }}>
        <DollarSign size={20} color="var(--cyan)" /> Log Sale
      </h1>

      <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap' }}>
        {/* Form */}
        <div style={{ flex: '0 0 340px' }}>
          <form onSubmit={submit} className="glass-card-solid" style={{ padding: 20 }}>
            <h3 style={{ marginBottom: 16 }}>Log New Sale</h3>
            <div style={{ display: 'grid', gap: 12 }}>
              {[
                { key: 'item', label: 'Item / Product', placeholder: 'e.g. Tomato Seeds (25lb)' },
                { key: 'amount', label: 'Amount ($)', placeholder: '0.00', type: 'number' },
                { key: 'date', label: 'Date', type: 'date' },
              ].map(({ key, label, placeholder, type = 'text' }) => (
                <div key={key}>
                  <label style={{ fontSize: '0.72rem', color: 'var(--txt-mut)', display: 'block', marginBottom: 4 }}>{label}</label>
                  <input type={type} value={form[key]} onChange={e => setForm(f => ({ ...f, [key]: e.target.value }))}
                    placeholder={placeholder}
                    style={{ width: '100%', padding: '8px 12px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.04)', color: 'var(--txt-pri)', fontSize: '0.85rem', outline: 'none', boxSizing: 'border-box' }} />
                </div>
              ))}
              <div>
                <label style={{ fontSize: '0.72rem', color: 'var(--txt-mut)', display: 'block', marginBottom: 4 }}>Ledger</label>
                <select
                  value={form.ledger}
                  onChange={e => setForm(f => ({ ...f, ledger: e.target.value }))}
                  style={{ width: '100%', padding: '8px 12px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.04)', color: 'var(--txt-pri)', fontSize: '0.85rem', outline: 'none', boxSizing: 'border-box' }}
                >
                  <option value="personal">Personal</option>
                  <option value="business">Business</option>
                </select>
              </div>
              <div>
                <label style={{ fontSize: '0.72rem', color: 'var(--txt-mut)', display: 'block', marginBottom: 4 }}>Category</label>
                <input
                  type="text"
                  value={form.category}
                  onChange={e => setForm(f => ({ ...f, category: e.target.value }))}
                  placeholder={form.ledger === 'business' ? 'e.g. Product Sales' : 'e.g. Household'}
                  style={{ width: '100%', padding: '8px 12px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.04)', color: 'var(--txt-pri)', fontSize: '0.85rem', outline: 'none', boxSizing: 'border-box' }}
                />
              </div>
              <div>
                <label style={{ fontSize: '0.72rem', color: 'var(--txt-mut)', display: 'block', marginBottom: 4 }}>Notes</label>
                <textarea value={form.notes} onChange={e => setForm(f => ({ ...f, notes: e.target.value }))}
                  rows={2} placeholder="Optional notes…"
                  style={{ width: '100%', padding: '8px 12px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.04)', color: 'var(--txt-sec)', fontSize: '0.85rem', resize: 'none', outline: 'none', boxSizing: 'border-box' }} />
              </div>
              <button type="submit" disabled={saving}
                style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, padding: '10px', borderRadius: 8, border: 'none', background: 'linear-gradient(90deg,var(--photon),var(--cyan))', color: '#050608', fontWeight: 700, fontSize: '0.85rem', cursor: 'pointer', opacity: saving ? 0.7 : 1 }}>
                <Plus size={16} /> {saving ? 'Saving…' : 'Log Sale'}
              </button>
            </div>
          </form>
        </div>

        {/* Sales data */}
        <div style={{ flex: 1, minWidth: 280 }}>
          {/* Total */}
          <div className="glass-card-solid" style={{ padding: 20, marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <p style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.14em', color: 'var(--txt-mut)' }}>Total Revenue</p>
              <p style={{ fontSize: '2rem', fontWeight: 700, fontFamily: 'JetBrains Mono,monospace', color: 'var(--cyan)', marginTop: 4 }}>
                ${total.toFixed(2)}
              </p>
            </div>
            <div style={{ textAlign: 'right' }}>
              <p style={{ fontSize: '0.72rem', color: 'var(--txt-mut)' }}>{sales.length} entries</p>
              <p style={{ fontSize: '0.72rem', color: 'var(--txt-sec)' }}>Personal ${personalTotal.toFixed(2)} • Business ${businessTotal.toFixed(2)}</p>
            </div>
          </div>

          {/* Table */}
          <div className="glass-card-solid" style={{ borderRadius: 12, overflow: 'hidden' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border)' }}>
                  {['Date', 'Item', 'Ledger', 'Category', 'Amount', 'Notes'].map(h => (
                    <th key={h} style={{ padding: '12px 16px', textAlign: 'left', fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-mut)', fontWeight: 600 }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {[...sales].reverse().map((s, i) => (
                  <tr key={s.id} style={{ borderTop: i ? '1px solid var(--border)' : 'none' }}>
                    <td style={{ padding: '11px 16px', fontFamily: 'JetBrains Mono,monospace', color: 'var(--txt-mut)', fontSize: '0.78rem' }}>{s.date}</td>
                    <td style={{ padding: '11px 16px', color: 'var(--txt-pri)' }}>{s.item}</td>
                    <td style={{ padding: '11px 16px', color: s.ledger === 'business' ? 'var(--cyan)' : 'var(--txt-sec)', textTransform: 'capitalize', fontSize: '0.78rem' }}>{s.ledger || 'personal'}</td>
                    <td style={{ padding: '11px 16px', color: 'var(--txt-sec)', fontSize: '0.78rem' }}>{s.category || 'general'}</td>
                    <td style={{ padding: '11px 16px', fontFamily: 'JetBrains Mono,monospace', color: 'var(--cyan)', fontWeight: 600 }}>${parseFloat(s.amount).toFixed(2)}</td>
                    <td style={{ padding: '11px 16px', color: 'var(--txt-sec)', fontSize: '0.78rem' }}>{s.notes || '–'}</td>
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
