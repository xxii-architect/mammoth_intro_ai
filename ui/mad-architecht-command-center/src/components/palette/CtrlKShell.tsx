import React, { useState, useEffect, useRef } from 'react';

interface Command {
  id: string;
  name: string;
  execute: () => void;
}

interface CtrlkShellProps {
  commands: Command[];
}

const CtrlkShell: React.FC<CtrlkShellProps> = ({ commands }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [filteredCommands, setFilteredCommands] = useState<Command[]>(commands);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (isOpen) {
      inputRef.current?.focus();
    }
  }, [isOpen]);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.ctrlKey && event.key === 'k') {
        event.preventDefault();
        setIsOpen(prev => !prev);
      }
      if (isOpen) {
        switch (event.key) {
          case 'ArrowDown':
            setSelectedIndex(prev => Math.min(prev + 1, filteredCommands.length - 1));
            break;
          case 'ArrowUp':
            setSelectedIndex(prev => Math.max(prev - 1, 0));
            break;
          case 'Enter':
            if (filteredCommands[selectedIndex]) {
              filteredCommands[selectedIndex].execute();
              setIsOpen(false);
            }
            break;
          case 'Escape':
            setIsOpen(false);
            break;
          default:
            break;
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen, selectedIndex, filteredCommands]);

  useEffect(() => {
    setFilteredCommands(
      commands.filter(command => command.name.toLowerCase().includes(query.toLowerCase()))
    );
    setSelectedIndex(0);
  }, [query, commands]);

  return (
    <>
      {isOpen && (
        <div className="fixed top-0 left-0 right-0 z-50 p-4">
          <div className="bg-white rounded shadow-lg">
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="w-full p-2 border-b border-gray-300 focus:outline-none"
              placeholder="Search commands..."
            />
            <ul className="max-h-60 overflow-y-auto">
              {filteredCommands.map((command, index) => (
                <li
                  key={command.id}
                  onClick={() => {
                    command.execute();
                    setIsOpen(false);
                  }}
                  className={`p-2 cursor-pointer ${index === selectedIndex ? 'bg-blue-500 text-white' : 'hover:bg-gray-200'}`}
                >
                  {command.name}
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </>
  );
};

export default CtrlkShell;