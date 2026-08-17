// src/pages/NotesPanel.tsx
import React, { useState } from 'react';

interface Note {
  id: number;
  content: string;
}

const NotesPanel: React.FC = () => {
  const [notes, setNotes] = useState<Note[]>([]);
  const [newNote, setNewNote] = useState<string>('');

  const addNote = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter' && newNote.trim()) {
      const newId = notes.length ? notes[notes.length - 1].id + 1 : 1;
      setNotes([...notes, { id: newId, content: newNote }]);
      setNewNote('');
    }
  };

  return (
    <div className="p-4">
      <h1 className="text-2xl font-bold mb-4">Notes</h1>
      <input
        type="text"
        value={newNote}
        onChange={(e) => setNewNote(e.target.value)}
        onKeyDown={addNote}
        placeholder="Add a new note..."
        className="border p-2 rounded mb-4 w-full"
      />
      <ul className="list-disc pl-5">
        {notes.map((note) => (
          <li key={note.id} className="mb-2">
            {note.content}
          </li>
        ))}
      </ul>
    </div>
  );
};

export default NotesPanel;

// src/components/Sidebar.tsx (Assuming this is where the sidebar is defined)
import React from 'react';
import { Link } from 'react-router-dom';

const Sidebar: React.FC = () => {
  return (
    <div className="sidebar">
      {/* Other sidebar items */}
      <Link to="/notes" className="text-neon-green">
        Notes
      </Link>
    </div>
  );
};

export default Sidebar;

// src/App.tsx (or wherever the router is defined)
import React from 'react';
import { BrowserRouter as Router, Route, Switch } from 'react-router-dom';
import NotesPanel from './pages/NotesPanel';
import CommandCenterLayout from './layouts/CommandCenterLayout'; // Assuming this is the layout component

const App: React.FC = () => {
  return (
    <Router>
      <CommandCenterLayout>
        <Switch>
          {/* Other routes */}
          <Route path="/notes" component={NotesPanel} />
        </Switch>
      </CommandCenterLayout>
    </Router>
  );
};

export default App;

// src/styles/tailwind.css (Ensure neon-green is defined in your Tailwind CSS config)
@tailwind base;
@tailwind components;
@tailwind utilities;

.text-neon-green {
  color: #39ff14; /* Neon green color */
}