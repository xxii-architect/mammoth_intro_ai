import { useState } from 'react';

const useDeleteNote = () => {
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const deleteNote = async (id: string) => {
    setLoading(true);
    try {
      const response = await fetch(`http://localhost:8000/api/notes/${id}`, {
        method: 'DELETE',
      });
      if (!response.ok) throw new Error('Failed to delete note');
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return { deleteNote, loading, error };
};

export { useDeleteNote };
