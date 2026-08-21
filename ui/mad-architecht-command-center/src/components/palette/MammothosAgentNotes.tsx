import React, { useState, useEffect } from 'react';
import { api } from '../../api/client';

interface Note {
  id: number;
  content: string;
  createdAt: string;
}

const MammothosAgentNotes: React.FC = () => {
  const [notes, setNotes] = useState<Note[]>([]);
  const [newNote, setNewNote] = useState<string>('');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Fetch existing notes from an API or local storage
    const fetchNotes = async () => {
      try {
        const data = await api('/agent-notes');
        setNotes(data);
      } catch (err) {
        setError('Failed to fetch notes');
      }
    };

    fetchNotes();
  }, []);

  const handleInputChange = (event: React.ChangeEvent<HTMLTextAreaElement>) => {
    setNewNote(event.target.value);
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      handleAddNote();
    }
  };

  const handleAddNote = async () => {
    if (newNote.trim() === '') {
      setError('Note cannot be empty');
      return;
    }

    const noteToAdd: Note = {
      id: Date.now(),
      content: newNote,
      createdAt: new Date().toISOString(),
    };

    try {
      await api('/agent-notes', {
        method: 'POST',
        body: noteToAdd,
      });

      setNotes((prevNotes) => [...prevNotes, noteToAdd]);
      setNewNote('');
      setError(null);
    } catch (err) {
      setError('Failed to add note');
    }
  };

  return (
    <div className="p-4 bg-gray-100 rounded-lg shadow-md">
      <h2 className="text-xl font-semibold mb-4">MammothOS Agent Notes</h2>
      {error && <p className="text-red-500">{error}</p>}
      <div className="mb-4">
        <textarea
          value={newNote}
          onChange={handleInputChange}
          onKeyDown={handleKeyDown}
          className="w-full p-2 border border-gray-300 rounded-md"
          rows={3}
          placeholder="Leave a note..."
        />
      </div>
      <button
        onClick={handleAddNote}
        className="px-4 py-2 bg-blue-500 text-white rounded-md hover:bg-blue-600"
      >
        Add Note
      </button>
      <div className="mt-6">
        <h3 className="text-lg font-semibold">Existing Notes</h3>
        <ul className="mt-2">
          {notes.map((note) => (
            <li key={note.id} className="p-2 border-b border-gray-200">
              <p className="text-gray-800">{note.content}</p>
              <span className="text-gray-500 text-sm">{new Date(note.createdAt).toLocaleString()}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
};

export default MammothosAgentNotes;