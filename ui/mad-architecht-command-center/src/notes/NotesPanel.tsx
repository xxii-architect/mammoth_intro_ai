import React from 'react';
import { useAgentNotes } from './hooks/useAgentNotes';
import { useCreateNote } from './hooks/useCreateNote';
import { useDeleteNote } from './hooks/useDeleteNote';
import { NotesList } from './NotesList';
import { NotesComposer } from './NotesComposer';

// NotesPanel Component
const NotesPanel: React.FC = () => {
  const { notes, loading, error } = useAgentNotes();
  const { createNote } = useCreateNote();
  const { deleteNote } = useDeleteNote();

  return (
    <div className="bg-mammoth-dark backdrop-blur-md border border-mammoth-accent/40 rounded-xl shadow-neon p-4 md:p-6 flex flex-col gap-6">
      <h2 className="text-xl font-semibold text-mammoth-accent mb-4 md:mb-6">Notes</h2>

      {loading && <p className="text-yellow-400">Loading...</p>}
      {error && <p className="text-red-500">{error}</p>}

      <div className="bg-mammoth-dark/60 border border-mammoth-accent/30 rounded-lg shadow-neon-sm p-4 flex flex-col gap-6">
        <NotesList notes={notes} onDelete={deleteNote} />
        <NotesComposer onCreate={createNote} />
      </div>
    </div>
  );
};

export default NotesPanel;
