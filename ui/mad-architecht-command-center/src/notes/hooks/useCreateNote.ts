import { useState } from 'react'
import { api } from '../../api/client'

const useCreateNote = () => {
  const [loading, setLoading] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)

  const createNote = async (content: string) => {
    setLoading(true)
    setError(null)
    try {
      const trimmed = content.trim()
      const title = trimmed.split(/\r?\n/, 1)[0]?.trim().slice(0, 72) || 'Untitled'
      return await api('/notes', {
        method: 'POST',
        body: {
          title,
          body: trimmed,
          content: trimmed,
          source: 'personal',
          type: 'personal_note',
          subsystem: 'general',
          priority: 'normal',
          agent_id: 'operator',
          metadata: { origin: 'notes_panel' },
        },
      })
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to create note'
      setError(message)
      throw err
    } finally {
      setLoading(false)
    }
  }

  return { createNote, loading, error }
}

export { useCreateNote }
