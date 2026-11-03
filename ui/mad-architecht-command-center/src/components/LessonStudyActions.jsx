import { useEffect, useRef, useState } from 'react'
import { api } from '../api/client'
import LessonContent from './LessonContent'
import { usePageMemory } from '../lib/PageMemory'
import './lesson-study-actions.css'

const ACTIONS = [
  ['explain', 'Simpler explanation'],
  ['example', 'Worked example'],
  ['practice', 'Practice question'],
  ['remediate', 'Work on this feedback'],
]

export default function LessonStudyActions({ children, source, exerciseKey, fallbackText = '', onRefresh, onOpenTutor }) {
  const memoryKey = `atlas:study:${exerciseKey || 'none'}:${source}`
  const [selection, setSelection] = usePageMemory(`${memoryKey}:selection`, '')
  const [open, setOpen] = useState(false)
  const [action, setAction] = usePageMemory(`${memoryKey}:action`, source === 'feedback' ? 'remediate' : 'explain')
  const [reply, setReply] = usePageMemory(`${memoryKey}:reply`, '')
  const [busy, setBusy] = usePageMemory(`${memoryKey}:busy`, '')
  const [error, setError] = usePageMemory(`${memoryKey}:error`, '')
  const [note, setNote] = usePageMemory(`${memoryKey}:note`, '')
  const [authorship, setAuthorship] = usePageMemory(`${memoryKey}:authorship`, 'learner')
  const [card, setCard] = usePageMemory(`${memoryKey}:card`, null)
  const [cardAuthorship, setCardAuthorship] = usePageMemory(`${memoryKey}:card-authorship`, 'learner')
  const [receipt, setReceipt] = usePageMemory(`${memoryKey}:receipt`, '')
  const [noteSaved, setNoteSaved] = usePageMemory(`${memoryKey}:note-saved`, false)
  const [cardSaved, setCardSaved] = usePageMemory(`${memoryKey}:card-saved`, false)
  const root = useRef(null)
  const dialog = useRef(null)
  const activeKey = useRef(exerciseKey)
  const opener = useRef(null)
  const previousSelection = useRef(selection)
  activeKey.current = exerciseKey

  useEffect(() => {
    setOpen(false)
  }, [exerciseKey])
  useEffect(() => {
    if (previousSelection.current === selection) return
    previousSelection.current = selection
    setReply('')
    setNote('')
    setCard(null)
    setReceipt('')
    setNoteSaved(false)
    setCardSaved(false)
    setAuthorship('learner')
    setError('')
  }, [selection])
  useEffect(() => {
    if (open) dialog.current?.showModal()
    else dialog.current?.close()
  }, [open])

  const capture = event => {
    if (open) return
    if (event.target.closest('button, input, textarea, select, dialog')) return
    const selected = window.getSelection()
    if (!selected?.rangeCount || !root.current?.contains(selected.anchorNode) || !root.current?.contains(selected.focusNode)) return
    const text = selected.toString().trim()
    if (text.length >= 2 && text.length <= 4000) setSelection(text)
  }
  const show = event => {
    opener.current = event.currentTarget
    if (!selection) setSelection(fallbackText)
    setOpen(true)
  }
  const ask = async () => {
    const key = exerciseKey
    let responseReceived = false
    setBusy('help')
    setReply('')
    setError('')
    try {
      const result = await api('/atlas/chat', { method: 'POST', body: {
        contextual_help: { exercise_key: key, source, selection, action },
      } })
      if (result?.status !== 'ok' || typeof result.reply !== 'string' || !result.reply.trim()) {
        throw new Error(result?.error || 'The tutor did not confirm a usable response.')
      }
      if (activeKey.current !== key) return
      setReply(result.reply)
      responseReceived = true
      await onRefresh?.(true)
    } catch (cause) {
      if (activeKey.current === key) setError(responseReceived
        ? `Tutor response received, but the workspace refresh failed: ${cause.message || 'unavailable'}. Do not ask again just to reload.`
        : cause.message || 'Could not get contextual help. Retry explicitly.')
    } finally { setBusy('') }
  }

  const learningSelection = { exercise_key: exerciseKey, source, selection }
  const studyAction = async operation => {
    setBusy(operation)
    setError('')
    setReceipt('')
    const key = exerciseKey
    try {
      if (operation === 'preview') {
        const result = await api('/atlas/study-preview', { method: 'POST', body: { learning_selection: learningSelection } })
        if (result?.status !== 'draft' || !Array.isArray(result.cards)) throw new Error('The server did not confirm a card preview.')
        if (!result.cards.length) throw new Error('This passage does not provide an answered recall card. Choose a teaching statement or write your own card.')
        if (activeKey.current === key) { setCard(result.cards[0]); setCardAuthorship('source-derived'); setCardSaved(false) }
      } else if (operation === 'note') {
        const result = await api('/notes', { method: 'POST', body: {
          body: note.trim(), content: note.trim(), source: 'personal', subsystem: 'atlas',
          learning_selection: learningSelection, reviewed: true, authorship,
        } })
        if (!result?.id || !result.metadata?.learning_context) throw new Error(result?.error || 'The server did not confirm the linked note.')
        if (activeKey.current === key) { setNoteSaved(true); setReceipt('Saved to your private Notes with lesson provenance.') }
      } else {
        const result = await api('/flashcards', { method: 'POST', body: {
          cards: [{ front: card.front.trim(), back: card.back.trim() }],
          learning_selection: learningSelection, reviewed: true, authorship: cardAuthorship,
        } })
        if (result?.status !== 'ok' || result.count !== 1 || !result.cards?.[0]?.learning_context) throw new Error('The server did not confirm the linked card.')
        if (activeKey.current === key) { setCardSaved(true); setReceipt('Saved to your lesson flashcards with provenance.') }
      }
    } catch (cause) {
      if (activeKey.current === key) setError(cause.message || 'Study material could not be saved. Your draft is retained.')
    } finally { setBusy('') }
  }

  return (
    <div ref={root} onMouseUp={capture} onTouchEnd={capture} onKeyUp={capture}>
      {children}
      {(selection || fallbackText) && <button className="lesson-study-trigger" type="button" disabled={!exerciseKey} onClick={show}>
        {source === 'lesson' ? 'Study selection' : source === 'feedback' ? 'Work on feedback' : 'Explain instructions'}
      </button>}
      <dialog ref={dialog} className="lesson-study-dialog" aria-label="Study selected text"
        onCancel={event => { if (busy && busy !== 'help') event.preventDefault(); else setOpen(false) }}
        onClose={() => { setOpen(false); opener.current?.focus() }}>
        {open && <>
        <div className="lesson-study-heading">
          <h2>Study selected text</h2>
          <button type="button" disabled={Boolean(busy && busy !== 'help')} onClick={() => setOpen(false)}>{busy === 'help' ? 'Close view (request continues)' : 'Close'}</button>
        </div>
        <p>Source: {source}. Help uses model credits only when you choose Ask tutor. It does not submit work or change mastery.</p>
        {busy === 'help' && <p>Closing this view does not cancel the request. To request cancellation, close the view and open Edit learning profile, Learning privacy &amp; costs, then Refresh learning request controls.</p>}
        <p>Study drafts stay in this tab for this selection. Selecting different text starts a new draft; refresh does not recover unsaved study notes or cards.</p>
        <blockquote>{selection}</blockquote>
        <label>Help type
          <select value={action} disabled={Boolean(busy)} onChange={event => setAction(event.target.value)}>
            {ACTIONS.filter(([id]) => id !== 'remediate' || source === 'feedback').map(([id, label]) => <option key={id} value={id}>{label}</option>)}
          </select>
        </label>
        <button type="button" disabled={Boolean(busy) || !selection} onClick={ask}>{busy === 'help' ? 'Asking tutor...' : 'Ask tutor'}</button>
        {error && <p role="alert">{error} No automatic retry was made.</p>}
        {reply && <section aria-label="Contextual tutor response">
          <p>AI-generated study help; review it against your lesson and sources.</p>
          <LessonContent content={reply} />
          <button type="button" disabled={Boolean(busy)} onClick={() => { setNote(reply); setAuthorship('ai-assisted'); setNoteSaved(false); setReceipt('') }}>Use help as note draft</button>
          {onOpenTutor && <button type="button" onClick={() => { setOpen(false); onOpenTutor() }}>View tutor conversation</button>}
        </section>}
        <details>
          <summary>Save a linked study note</summary>
          <p>Uses your existing private Notes (Pro/developer access required). Review before saving. No model call.</p>
          <label>Study note
            <textarea rows={5} maxLength={12000} value={note} disabled={Boolean(busy)} onChange={event => { setNote(event.target.value); setNoteSaved(false); setReceipt('') }} />
          </label>
          <p>Authorship: {authorship === 'ai-assisted' ? 'AI-assisted, reviewed by you' : 'Learner-written'}</p>
          <button type="button" disabled={Boolean(busy) || !note.trim() || noteSaved} onClick={() => studyAction('note')}>{busy === 'note' ? 'Saving note...' : 'Save reviewed note'}</button>
        </details>
        <details>
          <summary>Create a linked recall card</summary>
          <p>Drafts use the selected teaching passage without a model call. Review and edit the question and answer; saving does not demonstrate mastery.</p>
          <button type="button" disabled={Boolean(busy)} onClick={() => studyAction('preview')}>Draft recall card</button>
          <button type="button" disabled={Boolean(busy)} onClick={() => { setCard({ front: '', back: selection }); setCardAuthorship('learner'); setCardSaved(false); setReceipt('') }}>Write my own card</button>
          {card && <>
            <label>Recall question<textarea rows={2} maxLength={4000} value={card.front} disabled={Boolean(busy)} onChange={event => { setCard({ ...card, front: event.target.value }); setCardAuthorship('learner'); setCardSaved(false); setReceipt('') }} /></label>
            <label>Recall answer<textarea rows={4} maxLength={12000} value={card.back} disabled={Boolean(busy)} onChange={event => { setCard({ ...card, back: event.target.value }); setCardAuthorship('learner'); setCardSaved(false); setReceipt('') }} /></label>
            <p>Authorship: {cardAuthorship === 'source-derived' ? 'Source-derived draft, reviewed by you' : 'Learner-edited'}</p>
            <button type="button" disabled={Boolean(busy) || !card.front.trim() || !card.back.trim() || cardSaved} onClick={() => studyAction('card')}>{busy === 'card' ? 'Saving card...' : 'Save reviewed card'}</button>
          </>}
        </details>
        {receipt && <p role="status">{receipt}</p>}
        </>}
      </dialog>
    </div>
  )
}
