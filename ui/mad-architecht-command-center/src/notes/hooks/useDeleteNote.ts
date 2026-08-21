import { useState } from 'react'
import { api } from '../../api/client'

const useDeleteNote = () => {
  const [loading, setLoading] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)

  const deleteNote = async (id: string) => {
    setLoading(true)
    setError(null)
    try {
      await api(`/notes/${id}`, {
        method: 'DELETE',
      })
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to delete note'
      setError(message)
      throw err
    } finally {
      setLoading(false)
    }
  }

  return { deleteNote, loading, error }
}

export { useDeleteNote }
