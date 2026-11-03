import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../api/client'
import { usePageMemory } from '../lib/PageMemory'

const EMPTY = { view: 'lesson', lesson_response: '', tutor_response: '', checklist: {}, tutor_message: '', tutor_mode: 'tutor' }

export default function useLearningWorkspace(snapshot) {
  const [cached, cache] = usePageMemory('atlas:workspace-recovery', null)
  const [values, setValues] = useState(cached?.values || EMPTY)
  const [status, setStatus] = useState(cached ? cached.version === cached.savedVersion ? 'Workspace saved' : 'Unsaved workspace changes' : 'Loading saved workspace...')
  const [error, setError] = useState('')
  const [change, setChange] = useState(0)
  const current = useRef(cached)
  const mounted = useRef(true)
  const saving = useRef(false)
  const timer = useRef(null)
  const saveRef = useRef(null)

  useEffect(() => {
    mounted.current = true
    return () => { mounted.current = false; clearTimeout(timer.current) }
  }, [])

  useEffect(() => {
    if (!snapshot) return
    if (snapshot.contract !== 'mammoth.learning-workspace.v1' || !snapshot.values || !snapshot.exercise_key) {
      setError('Saved workspace returned an invalid response. Reload before editing.')
      return
    }
    if (current.current?.exercise_key === snapshot.exercise_key) return
    clearTimeout(timer.current)
    const restoredValues = { ...snapshot.values, view: current.current?.values.view || snapshot.values.view }
    const version = restoredValues.view !== snapshot.values.view ? 1 : 0
    current.current = { ...snapshot, values: restoredValues, version, savedVersion: 0 }
    cache(current.current)
    setValues(restoredValues)
    setError('')
    setStatus(version ? 'Unsaved workspace changes' : snapshot.saved_at ? 'Saved workspace restored' : 'Ready to save your workspace')
    if (version) setChange(change => change + 1)
  }, [snapshot])

  const save = useCallback(async () => {
    const record = current.current
    if (!record || saving.current) return
    if (record.version === record.savedVersion) {
      if (mounted.current && record.savedVersion > 0) {
        setStatus('Workspace saved')
        setError('')
      }
      return
    }
    if (record.pending) {
      await record.pending
      if (mounted.current) {
        if (current.current === record && record.version === record.savedVersion) {
          setStatus('Workspace saved')
          setError('')
          return
        }
        return saveRef.current()
      }
      return
    }
    saving.current = true
    const version = record.version
    const payload = { exercise_key: record.exercise_key, revision: record.revision, values: record.values }
    setStatus('Saving workspace...')
    try {
      const request = api('/atlas/workspace', { method: 'POST', body: payload })
      record.pending = request.then(() => {}, () => {})
      const result = await request
      if (result?.status !== 'saved' || result.exercise_key !== record.exercise_key || result.revision !== payload.revision + 1) {
        throw new Error('The server did not confirm the workspace save.')
      }
      record.revision = result.revision
      record.savedVersion = version
      if (mounted.current && current.current === record) {
        setError('')
        setStatus(record.version === version ? 'Workspace saved' : 'Unsaved workspace changes')
      }
    } catch (cause) {
      if (mounted.current && current.current === record) {
        setError(cause.message || 'Could not save your workspace.')
        setStatus("Couldn't save workspace")
      }
    } finally {
      saving.current = false
      record.pending = null
      const active = current.current
      if (mounted.current && active && active.version !== active.savedVersion &&
          (active !== record || record.savedVersion === version)) {
        timer.current = setTimeout(() => saveRef.current(), 500)
      }
    }
  }, [])
  saveRef.current = save

  const update = useCallback((field, value) => {
    const record = current.current
    if (!record) return
    const next = typeof value === 'function' ? value(record.values[field]) : value
    if (JSON.stringify(record.values[field]) === JSON.stringify(next)) return
    record.values = { ...record.values, [field]: next }
    record.version += 1
    setValues(record.values)
    setStatus('Unsaved workspace changes')
    setChange(value => value + 1)
  }, [])

  useEffect(() => {
    clearTimeout(timer.current)
    timer.current = setTimeout(save, 600)
    return () => clearTimeout(timer.current)
  }, [change, save])

  useEffect(() => {
    const beforeUnload = event => {
      const record = current.current
      if (record && record.version !== record.savedVersion) {
        event.preventDefault()
        event.returnValue = ''
      }
    }
    const flush = () => { if (document.visibilityState === 'hidden') void save() }
    window.addEventListener('beforeunload', beforeUnload)
    window.addEventListener('online', save)
    document.addEventListener('visibilitychange', flush)
    return () => {
      window.removeEventListener('beforeunload', beforeUnload)
      window.removeEventListener('online', save)
      document.removeEventListener('visibilitychange', flush)
    }
  }, [save])

  return { values, update, status, error, save, ready: Boolean(current.current) }
}
