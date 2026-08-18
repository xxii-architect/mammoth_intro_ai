import React, { useState } from 'react';
import { api } from '../api/client'

const save = async (payload) => {
  await api('/operator/health', {
    method: 'POST',
    body: JSON.stringify(payload)
  })
}

export default function PersonalHealth() {
  const [energy, setEnergy] = useState(50);
  const [focus, setFocus] = useState(50);
  const [mood, setMood] = useState(50);
  const [stress, setStress] = useState(50);
  const [sleep, setSleep] = useState(50);
  const [uptime, setUptime] = useState(0);
  const [fatigue, setFatigue] = useState(0);

  return (
    <div className='glass-card-solid neon-card' style={{ padding: 20, borderRadius: 12 }}>
      <h2 style={{ marginBottom: 12, color: 'var(--cyan)' }}>Personal Health</h2>

      <label>Energy: {energy}</label>
      <input type='range' min='0' max='100' value={energy} onChange={e => {
        const v = Number(e.target.value)
        setEnergy(v)
        save({ energy: v })
      }} />

      <label>Focus: {focus}</label>
      <input type='range' min='0' max='100' value={focus} onChange={e => {
        const v = Number(e.target.value)
        setFocus(v)
        save({ focus: v })
      }} />

      <label>Mood: {mood}</label>
      <input type='range' min='0' max='100' value={mood} onChange={e => {
        const v = Number(e.target.value)
        setMood(v)
        save({ mood: v })
      }} />

      <label>Stress: {stress}</label>
      <input type='range' min='0' max='100' value={stress} onChange={e => {
        const v = Number(e.target.value)
        setStress(v)
        save({ stress: v })
      }} />

      <label>Sleep Quality: {sleep}</label>
      <input type='range' min='0' max='100' value={sleep} onChange={e => {
        const v = Number(e.target.value)
        setSleep(v)
        save({ sleep: v })
      }} />

      <label>Operator Uptime: {uptime} hrs</label>
      <input type='number' value={uptime} onChange={e => {
        const v = Number(e.target.value)
        setUptime(v)
        save({ uptime: v })
      }} />

      <label>Fatigue Score: {fatigue}</label>
      <input type='range' min='0' max='100' value={fatigue} onChange={e => {
        const v = Number(e.target.value)
        setFatigue(v)
        save({ fatigue: v })
      }} />
    </div>
  );
}