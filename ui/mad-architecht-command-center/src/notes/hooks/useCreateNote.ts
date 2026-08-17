import { useState } from 'react';

const useCreateNote = () => {
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const createNote = async (content: string) => {
    setLoading(true);
    try {
      const response = await fetch('http://localhost:8000/api/notes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content }),
      });
      if (!response.ok) throw new Error('Failed to create note');
      return await response.json();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return { createNote, loading, error };
};

export { useCreateNote };
