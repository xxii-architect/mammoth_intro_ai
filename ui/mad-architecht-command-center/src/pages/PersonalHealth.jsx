import React, { useEffect, useMemo, useState } from 'react';
import { api } from '../api/client'

const save = async (payload) => {
  return await api('/operator/health', {
    method: 'POST',
    body: payload
  })
}

const clamp = (value) => Math.max(0, Math.min(100, Math.round(value)))

const scoreTone = (value, invert = false) => {
  const effective = invert ? 100 - value : value
  if (effective >= 70) return '#22c55e'
  if (effective >= 45) return '#eab308'
  return '#f87171'
}

const formatTimestamp = (raw) => {
  if (!raw) return 'Not saved yet'
  const parsed = new Date(raw)
  return Number.isNaN(parsed.getTime()) ? 'Not saved yet' : parsed.toLocaleString()
}

const sliderCardStyle = {
  padding: 14,
  borderRadius: 14,
  border: '1px solid rgba(255,255,255,0.08)',
  background: 'linear-gradient(180deg, rgba(13,17,23,0.96), rgba(13,17,23,0.82))',
  boxShadow: '0 10px 28px rgba(0,0,0,0.22)',
}

const rangeStyle = {
  width: '100%',
  appearance: 'none',
  height: 8,
  borderRadius: 999,
  outline: 'none',
  background: 'linear-gradient(90deg, rgba(0,245,212,0.26), rgba(77,166,255,0.4))',
}

const SLIDERS = [
  { key: 'energy', label: 'Energy', help: 'How much fuel you have for the next focused push.', invert: false },
  { key: 'focus', label: 'Focus', help: 'How easy it is to keep attention locked on one slice.', invert: false },
  { key: 'mood', label: 'Mood', help: 'General steadiness and confidence during the session.', invert: false },
  { key: 'stress', label: 'Stress', help: 'Current pressure load. Higher values mean more strain.', invert: true },
  { key: 'sleep', label: 'Sleep quality', help: 'How restorative your recent sleep felt.', invert: false },
  { key: 'fatigue', label: 'Fatigue', help: 'Accumulated drag from a long session.', invert: true },
]

export default function PersonalHealth() {
  const [energy, setEnergy] = useState(50);
  const [focus, setFocus] = useState(50);
  const [mood, setMood] = useState(50);
  const [stress, setStress] = useState(50);
  const [sleep, setSleep] = useState(50);
  const [uptime, setUptime] = useState(0);
  const [fatigue, setFatigue] = useState(0);
  const [loaded, setLoaded] = useState(false)
  const [updatedAt, setUpdatedAt] = useState('')
  const [savingLabel, setSavingLabel] = useState('')
  const [saveError, setSaveError] = useState('')

  useEffect(() => {
    api('/operator/health')
      .then((res) => {
        const data = res?.data || {}
        setEnergy(Number(data.energy ?? 50))
        setFocus(Number(data.focus ?? 50))
        setMood(Number(data.mood ?? 50))
        setStress(Number(data.stress ?? 50))
        setSleep(Number(data.sleep ?? 50))
        setUptime(Number(data.uptime ?? 0))
        setFatigue(Number(data.fatigue ?? 0))
        setUpdatedAt(res?.updated_at || '')
        setLoaded(true)
      })
      .catch(() => {
        setLoaded(true)
      })
  }, [])

  const readiness = useMemo(() => clamp((energy + focus + mood + sleep + (100 - stress) + (100 - fatigue)) / 6), [energy, focus, mood, sleep, stress, fatigue])
  const strain = useMemo(() => clamp((stress + fatigue + Math.min(uptime * 4, 100)) / 3), [stress, fatigue, uptime])
  const pacingNote = useMemo(() => {
    if (strain >= 70) return 'High strain detected — polish and validate instead of widening scope.'
    if (readiness >= 70) return 'Healthy enough for another implementation slice with focused validation.'
    return 'Moderate state — keep tasks small and favor tidy, testable changes.'
  }, [readiness, strain])

  const persistField = async (label, payload) => {
    setSaveError('')
    setSavingLabel(label)
    try {
      const response = await save(payload)
      setUpdatedAt(response?.updated_at || new Date().toISOString())
    } catch (error) {
      setSaveError(error instanceof Error ? error.message : 'Failed to save operator health')
    } finally {
      setSavingLabel('')
    }
  }

  const setPercent = (label, setter, payloadKey, value) => {
    const next = clamp(Number(value))
    setter(next)
    void persistField(label, { [payloadKey]: next })
  }

  return (
    <div className='glass-card-solid neon-card' style={{ padding: 20, borderRadius: 12 }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', marginBottom: 12 }}>
        <div>
          <h2 style={{ marginBottom: 6, color: 'var(--cyan)' }}>Personal Health</h2>
          <p style={{ margin: 0, color: 'var(--txt-sec)', fontSize: '0.8rem', lineHeight: 1.6 }}>
            Lightweight operator pacing so the health panel reflects how hard you can push the next slice.
          </p>
        </div>
        <div style={{ fontSize: '0.74rem', color: savingLabel ? 'var(--cyan)' : 'var(--txt-mut)' }}>
          {savingLabel ? `Saving ${savingLabel}…` : `Last saved ${formatTimestamp(updatedAt)}`}
        </div>
      </div>
      {!loaded && <p style={{ color: 'var(--txt-mut)', fontSize: '0.78rem' }}>Loading health profile…</p>}
      {saveError && <p style={{ color: '#fecaca', fontSize: '0.78rem', marginBottom: 12 }}>{saveError}</p>}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(180px,1fr))', gap: 12, marginBottom: 16 }}>
        <div className='glass-card' style={{ padding: 12 }}>
          <div style={{ fontSize: '0.68rem', color: 'var(--txt-mut)', textTransform: 'uppercase', letterSpacing: '0.12em' }}>Readiness</div>
          <div style={{ fontSize: '1.08rem', fontWeight: 800, color: scoreTone(readiness) }}>{readiness}</div>
          <div style={{ fontSize: '0.74rem', color: 'var(--txt-sec)' }}>energy + focus balance</div>
        </div>
        <div className='glass-card' style={{ padding: 12 }}>
          <div style={{ fontSize: '0.68rem', color: 'var(--txt-mut)', textTransform: 'uppercase', letterSpacing: '0.12em' }}>Strain</div>
          <div style={{ fontSize: '1.08rem', fontWeight: 800, color: scoreTone(strain, true) }}>{strain}</div>
          <div style={{ fontSize: '0.74rem', color: 'var(--txt-sec)' }}>stress + fatigue load</div>
        </div>
        <div className='glass-card' style={{ padding: 12 }}>
          <div style={{ fontSize: '0.68rem', color: 'var(--txt-mut)', textTransform: 'uppercase', letterSpacing: '0.12em' }}>Operator uptime</div>
          <div style={{ fontSize: '1.08rem', fontWeight: 800, color: 'var(--txt-pri)' }}>{uptime}h</div>
          <div style={{ fontSize: '0.74rem', color: 'var(--txt-sec)' }}>current session stretch</div>
        </div>
      </div>

      <div className='glass-card' style={{ padding: 14, marginBottom: 16 }}>
        <div style={{ fontSize: '0.7rem', color: 'var(--txt-mut)', textTransform: 'uppercase', letterSpacing: '0.12em', marginBottom: 6 }}>Suggested pacing</div>
        <div style={{ fontSize: '0.82rem', color: 'var(--txt-pri)', lineHeight: 1.6 }}>{pacingNote}</div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(240px,1fr))', gap: 14 }}>
        {SLIDERS.map((item) => {
          const values = { energy, focus, mood, stress, sleep, fatigue }
          const setters = { energy: setEnergy, focus: setFocus, mood: setMood, stress: setStress, sleep: setSleep, fatigue: setFatigue }
          const value = values[item.key]
          const setter = setters[item.key]
          return (
            <div key={item.key} style={sliderCardStyle}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10, marginBottom: 6 }}>
                <label style={{ color: 'var(--txt-pri)', fontWeight: 700, fontSize: '0.86rem' }}>{item.label}</label>
                <span style={{ color: scoreTone(value, item.invert), fontFamily: 'JetBrains Mono,monospace', fontSize: '0.78rem', fontWeight: 700 }}>
                  {value}
                </span>
              </div>
              <div style={{ color: 'var(--txt-sec)', fontSize: '0.74rem', lineHeight: 1.55, marginBottom: 12 }}>
                {item.help}
              </div>
              <input
                type='range'
                min='0'
                max='100'
                value={value}
                onChange={e => setPercent(item.key, setter, item.key, e.target.value)}
                style={rangeStyle}
              />
            </div>
          )
        })}

        <div style={sliderCardStyle}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10, marginBottom: 6 }}>
            <label style={{ color: 'var(--txt-pri)', fontWeight: 700, fontSize: '0.86rem' }}>Operator uptime</label>
            <span style={{ color: 'var(--txt-pri)', fontFamily: 'JetBrains Mono,monospace', fontSize: '0.78rem', fontWeight: 700 }}>
              {uptime} hrs
            </span>
          </div>
          <div style={{ color: 'var(--txt-sec)', fontSize: '0.74rem', lineHeight: 1.55, marginBottom: 12 }}>
            Approximate uninterrupted work stretch so the panel can show when you may be pushing too long.
          </div>
          <input
            type='number'
            value={uptime}
            min='0'
            onChange={e => {
              const v = Math.max(0, Math.round(Number(e.target.value) || 0))
              setUptime(v)
              void persistField('uptime', { uptime: v })
            }}
            style={{ width: '100%', borderRadius: 10, border: '1px solid var(--border)', background: 'rgba(5,6,8,0.8)', color: 'var(--txt-pri)', padding: '10px 12px', fontSize: '0.86rem' }}
          />
        </div>
      </div>

      <style>{`
        input[type="range"]::-webkit-slider-thumb {
          appearance: none;
          width: 18px;
          height: 18px;
          border-radius: 50%;
          background: linear-gradient(180deg, var(--photon), var(--cyan));
          box-shadow: 0 0 0 3px rgba(0, 245, 212, 0.18);
          cursor: pointer;
          border: 0;
        }
        input[type="range"]::-moz-range-thumb {
          width: 18px;
          height: 18px;
          border-radius: 50%;
          background: linear-gradient(180deg, var(--photon), var(--cyan));
          box-shadow: 0 0 0 3px rgba(0, 245, 212, 0.18);
          cursor: pointer;
          border: 0;
        }
      `}</style>
    </div>
  );
}