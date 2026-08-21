# implementation here — main function MUST be named `solution`
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from supabase import create_client, Client
from typing import List, Optional
import uuid
import os

    # Initialize FastAPI app
app = FastAPI()

    # Supabase client initialization
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")

def get_supabase() -> Client:
    return create_client(url, key)

    # NotesRecord model
class NotesRecord(BaseModel):
    id: uuid.UUID
    agent_id: str
    type: str
    content: str
    priority: str
    created_at: str
    subsystem: str
    metadata: dict

    # Service functions
async def list_notes(supabase: Client) -> List[NotesRecord]:
    response = supabase.table("atlas_agent_notes").select("*").execute()
    if response.error:
        raise HTTPException(status_code=500, detail="Error fetching notes")
    return [NotesRecord(**note) for note in response.data]

async def create_note(note: NotesRecord, supabase: Client) -> NotesRecord:
    response = supabase.table("atlas_agent_notes").insert(note.dict()).execute()
    if response.error:
        raise HTTPException(status_code=500, detail="Error creating note")
    return NotesRecord(**response.data[0])

async def delete_note(note_id: uuid.UUID, supabase: Client) -> None:
    response = supabase.table("atlas_agent_notes").delete().eq("id", note_id).execute()
    if response.error:
        raise HTTPException(status_code=500, detail="Error deleting note")

    # API routes
@app.get("/notes", response_model=List[NotesRecord])
async def get_notes():
    supabase = get_supabase()
    return await list_notes(supabase)

@app.post("/notes", response_model=NotesRecord)
async def post_note(note: NotesRecord):
    supabase = get_supabase()
    return await create_note(note, supabase)

@app.delete("/notes/{id}")
async def remove_note(id: uuid.UUID):
    supabase = get_supabase()
    await delete_note(id, supabase)
    return {"detail": "Note deleted successfully"}

def solution(*args, **kwargs):
    return app