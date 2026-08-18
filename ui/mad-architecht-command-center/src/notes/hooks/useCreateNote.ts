import { useState } from 'react'
import { api } from '../../api/client'

const useCreateNote = () => {
  const [loading, setLoading] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)

  const createNote = async (content: string) => {
    setLoading(true)
    setError(null)
    try {
      return await api('/notes', {
        method: 'POST',
        body: { content },
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
