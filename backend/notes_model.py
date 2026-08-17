
    # implementation here — main function MUST be named `solution`
from enum import Enum
from uuid import uuid4
from pydantic import BaseModel, Field
from typing import Optional
import json

class NoteType(str, Enum):
    NOTE = "note"
    RECOMMENDATION = "recommendation"
    REQUEST = "request"

class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class NotesRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    agent_id: str
    type: NoteType
    content: str
    priority: Priority
    created_at: Optional[str] = Field(default=None)
    subsystem: str
    metadata: Optional[dict] = Field(default_factory=dict)

def solution():
    # This function can be used to initialize or test the NotesRecord model
    example_note = NotesRecord(
        agent_id="agent_123",
        type=NoteType.NOTE,
        content="This is a sample note.",
        priority=Priority.MEDIUM,
        subsystem="example_subsystem",
        metadata={"key": "value"}
    )
    print(example_note.json())

# 🧪 Generated tests:

# pytest test functions — import solution from solution module
from solution import solution
from backend.notes_model import NotesRecord, NoteType, Priority
import pytest
from pydantic import ValidationError

def test_notes_record_creation():
    note = NotesRecord(
        agent_id="agent_123",
        type=NoteType.NOTE,
        content="This is a sample note.",
        priority=Priority.MEDIUM,
        subsystem="example_subsystem",
        metadata={"key": "value"}
    )
    assert note.agent_id == "agent_123"
    assert note.type == NoteType.NOTE
    assert note.priority == Priority.MEDIUM

def test_invalid_note_type():
    with pytest.raises(ValidationError):
        NotesRecord(
            agent_id="agent_123",
            type="invalid_type",  # This should raise a validation error
            content="This is a sample note.",
            priority=Priority.MEDIUM,
            subsystem="example_subsystem"
        )

def test_invalid_priority():
    with pytest.raises(ValidationError):
        NotesRecord(
            agent_id="agent_123",
            type=NoteType.NOTE,
            content="This is a sample note.",
            priority="invalid_priority",  # This should raise a validation error
            subsystem="example_subsystem"
        )