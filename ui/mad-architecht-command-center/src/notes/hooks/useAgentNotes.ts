import { useState, useEffect } from 'react';
import { NoteRecord } from '../types/NoteRecord';

const useAgentNotes = () => {
  const [notes, setNotes] = useState<NoteRecord[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchNotes = async () => {
      try {
        const response = await fetch('http://localhost:8000/api/notes');
        if (!response.ok) throw new Error('Failed to fetch notes');
        const data = await response.json();
        setNotes(data);
      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchNotes();
  }, []);

  return { notes, loading, error };
};

export { useAgentNotes };
