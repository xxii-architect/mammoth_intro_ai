import { useCallback, useEffect, useState } from 'react'
import { api } from '../../api/client'
import { NoteRecord } from '../types/NoteRecord'

const useAgentNotes = () => {
  const [notes, setNotes] = useState<NoteRecord[]>([])
  const [loading, setLoading] = useState<boolean>(true)
  const [error, setError] = useState<string | null>(null)

  const reload = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await api('/notes')
      setNotes(Array.isArray(data) ? data : [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch notes')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void reload()
  }, [reload])

  return { notes, setNotes, loading, error, reload }
}

export { useAgentNotes }
