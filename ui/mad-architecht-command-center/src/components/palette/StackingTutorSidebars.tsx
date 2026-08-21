import React, { useState } from 'react';

interface Tutor {
  id: number;
  name: string;
  subject: string;
}

interface StackingTutorSidebarsProps {
  tutors: Tutor[];
}

const StackingTutorSidebars: React.FC<StackingTutorSidebarsProps> = ({ tutors }) => {
  const [selectedTutorId, setSelectedTutorId] = useState<number | null>(null);

  const handleTutorSelect = (id: number) => {
    setSelectedTutorId(id);
  };

  const handleKeyPress = (event: React.KeyboardEvent<HTMLDivElement>, id: number) => {
    if (event.key === 'Enter') {
      handleTutorSelect(id);
    }
  };

  return (
    <div className="flex flex-col md:flex-row md:space-x-4">
      <div className="flex flex-col space-y-2 md:w-1/4">
        {tutors.map(tutor => (
          <div
            key={tutor.id}
            className={`p-4 border rounded-lg cursor-pointer transition-colors duration-200 ${
              selectedTutorId === tutor.id ? 'bg-blue-500 text-white' : 'bg-white text-black'
            }`}
            onClick={() => handleTutorSelect(tutor.id)}
            onKeyPress={(event) => handleKeyPress(event, tutor.id)}
            tabIndex={0}
            role="button"
          >
            <h3 className="text-lg font-semibold">{tutor.name}</h3>
            <p className="text-sm">{tutor.subject}</p>
          </div>
        ))}
      </div>
      <div className="md:w-3/4">
        {selectedTutorId !== null && (
          <div className="p-4 border rounded-lg">
            <h2 className="text-xl font-bold">Selected Tutor</h2>
            <p className="text-lg">{tutors.find(tutor => tutor.id === selectedTutorId)?.name}</p>
            <p className="text-md">{tutors.find(tutor => tutor.id === selectedTutorId)?.subject}</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default StackingTutorSidebars;