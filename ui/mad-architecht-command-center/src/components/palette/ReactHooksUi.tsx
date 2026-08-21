import React, { useEffect, useState } from 'react';

// TypeScript interface for NoteRecord
interface NoteRecord {
  id: number;
  content: string;
  createdAt: string;
}

// Custom Hook to fetch notes
const useAgentNotes = () => {
  const [notes, setNotes] = useState<NoteRecord[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchNotes = async () => {
      try {
        const response = await fetch('http://localhost:8000/notes');
        if (!response.ok) throw new Error('Failed to fetch notes');
        const data = await response.json();
        setNotes(data);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchNotes();
  }, []);

  return { notes, loading, error };
};

// Custom Hook to create a note
const useCreateNote = () => {
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const createNote = async (content: string) => {
    setLoading(true);
    try {
      const response = await fetch('http://localhost:8000/notes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content }),
      });
      if (!response.ok) throw new Error('Failed to create note');
      return await response.json();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return { createNote, loading, error };
};

// Custom Hook to delete a note
const useDeleteNote = () => {
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const deleteNote = async (id: number) => {
    setLoading(true);
    try {
      const response = await fetch(`http://localhost:8000/notes/${id}`, {
        method: 'DELETE',
      });
      if (!response.ok) throw new Error('Failed to delete note');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return { deleteNote, loading, error };
};

// NotesPanel Component
const NotesPanel: React.FC = () => {
  const { notes, loading, error } = useAgentNotes();
  const { createNote } = useCreateNote();
  const { deleteNote } = useDeleteNote();

  return (
    <div className="p-4 bg-gray-900 rounded-lg shadow-lg">
      <h2 className="text-2xl text-neon-green mb-4">Notes</h2>
      {loading && <p className="text-yellow-400">Loading...</p>}
      {error && <p className="text-red-500">{error}</p>}
      <NotesList notes={notes} onDelete={deleteNote} />
      <NotesComposer onCreate={createNote} />
    </div>
  );
};

// NotesList Component
const NotesList: React.FC<{ notes: NoteRecord[]; onDelete: (id: number) => void }> = ({ notes, onDelete }) => {
  return (
    <ul className="space-y-2">
      {notes.map((note) => (
        <li key={note.id} className="p-2 bg-gray-800 rounded flex justify-between items-center">
          <span className="text-white">{note.content}</span>
          <button
            onClick={() => onDelete(note.id)}
            className="text-red-500 hover:text-red-300"
          >
            Delete
          </button>
        </li>
      ))}
    </ul>
  );
};

// NotesComposer Component
const NotesComposer: React.FC<{ onCreate: (content: string) => Promise<void> }> = ({ onCreate }) => {
  const [content, setContent] = useState<string>('');
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  const handleKeyDown = async (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter' && content.trim()) {
      setIsSubmitting(true);
      await onCreate(content);
      setContent('');
      setIsSubmitting(false);
    }
  };

  return (
    <div className="mt-4">
      <input
        type="text"
        value={content}
        onChange={(e) => setContent(e.target.value)}
        onKeyDown={handleKeyDown}
        className="w-full p-2 bg-gray-700 rounded text-white"
        placeholder="Write a new note..."
        disabled={isSubmitting}
      />
    </div>
  );
};

// Main Component
const Reacthooksui: React.FC = () => {
  return (
    <div className="min-h-screen bg-gray-900 flex items-center justify-center">
      <NotesPanel />
    </div>
  );
};

export default Reacthooksui;