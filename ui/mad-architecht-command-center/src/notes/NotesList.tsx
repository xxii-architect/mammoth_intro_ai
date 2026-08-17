import React from 'react';
import { NoteRecord } from './types/NoteRecord';

// NotesList Component
const NotesList: React.FC<{ notes: NoteRecord[]; onDelete: (id: string) => void }> = ({ notes, onDelete }) => {
  return (
    <ul className="bg-mammoth-dark/60 border border-mammoth-accent/30 rounded-lg shadow-neon-sm p-3 md:p-4 flex flex-col gap-4">
      {notes.map((note) => (
        <li
          key={note.id}
          className="border-l-4 border-mammoth-accent/60 pl-3 hover:bg-mammoth-accent/10 text-mammoth-light font-mammoth-ui p-3 rounded-md shadow-neon-xs bg-mammoth-dark/40 flex justify-between items-center"
        >
          <span>{note.content}</span>
          <button
            onClick={() => onDelete(note.id)}
            className="text-red-400 hover:text-red-300 font-semibold"
          >
            Delete
          </button>
        </li>
      ))}
    </ul>
  );
};

export { NotesList };
