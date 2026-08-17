import React, { useState } from 'react';

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
    <div className="mt-4 gap-4 flex flex-col md:flex-row items-start md:items-center">
      <div className="bg-mammoth-dark/60 border border-mammoth-accent/30 rounded-lg shadow-neon-sm p-4">
        <input
          type="text"
          value={content}
          onChange={(e) => setContent(e.target.value)}
          onKeyDown={handleKeyDown}
          className="bg-mammoth-dark/40 border border-mammoth-accent/40 rounded-md text-mammoth-light p-2 w-full focus:ring-2 focus:ring-mammoth-accent shadow-neon-xs"
          placeholder="Write a new note..."
          disabled={isSubmitting}
        />
      </div>
      <button
        className="bg-mammoth-accent hover:bg-mammoth-accent-light text-black font-semibold rounded-md px-3 py-1 shadow-neon-sm"
        onClick={async () => {
          if (content.trim()) {
            setIsSubmitting(true);
            await onCreate(content);
            setContent('');
            setIsSubmitting(false);
          }
        }}
        disabled={isSubmitting}
      >
        Create Note
      </button>
    </div>
  );
};

export { NotesComposer };