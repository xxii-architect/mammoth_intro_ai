import { useEffect, useState } from 'react'
import { api } from '../api/client'

export default function AtlasLearningProfile({ state, loadState }) {
  const profile = state?.learner_model?.onboarding
  const [editing, setEditing] = useState(false)
  const [deferred, setDeferred] = useState(false)
  const [draft, setDraft] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  useEffect(() => {
    if (editing) return
    setDraft({
      experience_level: profile?.experience_level === 'unknown' ? 'beginner' : profile?.experience_level || 'beginner',
      preferred_pacing: profile?.preferred_pacing || 'gentle', learning_style: profile?.learning_style || 'guided',
      goals: (profile?.goals || []).join(', '), focus_areas: (profile?.focus_areas || []).join(', '),
    })
  }, [profile, editing])
  if (!state || !draft) return null
  const open = editing || (!profile?.completed_at && !deferred)
  const update = event => { setEditing(true); setDraft(current => ({ ...current, [event.target.name]: event.target.value })) }
  const save = async event => {
    event.preventDefault()
    setBusy(true)
    setError('')
    setNotice('')
    try {
      const result = await api('/atlas/onboard', { method: 'POST', body: draft })
      if (result.approval) {
        setNotice('Profile update is pending approval; your current profile is unchanged.')
        return
      }
      await loadState(true)
      setEditing(false)
      setDeferred(true)
      setNotice('Learning profile saved. It applies to new lessons and exercises, not a rewrite of your current lesson.')
    } catch (cause) { setError(cause.message || 'Could not save your learning profile.') }
    finally { setBusy(false) }
  }
  return (
    <section aria-label="Learning profile" className="atlas-learning-profile">
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, justifyContent: 'space-between' }}>
        <strong>{profile?.completed_at ? 'Your learning profile' : 'Set up your learning experience'}</strong>
        <button type="button" onClick={() => { if (open) { setEditing(false); setDeferred(true) } else setEditing(true) }}>{open ? 'Close profile' : 'Edit learning profile'}</button>
      </div>
      <p>Starting level: {state.learner_context?.starting_level || 'beginner'} · Current recommendation: {state.learner_context?.recommended_difficulty || 'beginner'}</p>
      <p>{state.learner_context?.adaptation_reason || 'Choose a starting level; ATLAS adapts from your practice outcomes.'}</p>
      {open && <form onSubmit={save} className="atlas-profile-form">
        <p>Tell ATLAS what you already know and what you want to learn. Pacing is a preference, not proof of mastery. Expert study is not professional certification.</p>
        <label>Starting level<select name="experience_level" value={draft.experience_level} onChange={update}>
          <option value="beginner">Beginner - no prior knowledge</option><option value="intermediate">Intermediate</option><option value="advanced">Advanced</option><option value="expert">Expert study</option>
        </select></label>
        <label>Pacing<select name="preferred_pacing" value={draft.preferred_pacing} onChange={update}><option value="gentle">Gentle</option><option value="steady">Steady</option><option value="challenge">Challenge</option></select></label>
        <label>Learning preference<select name="learning_style" value={draft.learning_style} onChange={update}>
          <option value="guided">Guided explanations</option><option value="hands-on">Hands-on</option><option value="exploratory">Exploratory</option><option value="examples">Worked examples</option><option value="practice">Practice</option><option value="visual">Visual explanations</option><option value="independent">Independent</option>
        </select></label>
        <label>Goals<input name="goals" value={draft.goals} onChange={update} placeholder="What would you like to be able to do?" /></label>
        <label>Focus areas<input name="focus_areas" value={draft.focus_areas} onChange={update} placeholder="Topics to emphasize, separated by commas" /></label>
        <div><button disabled={busy} type="submit">{busy ? 'Saving profile...' : 'Save learning profile'}</button> <button type="button" disabled={busy} onClick={() => { setDeferred(true); setEditing(false) }}>Not now</button></div>
      </form>}
      {notice && <p role="status">{notice}</p>}
      {error && <p role="alert">{error}</p>}
    </section>
  )
}
