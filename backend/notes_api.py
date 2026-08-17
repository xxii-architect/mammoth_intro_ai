from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from supabase import create_client, Client
from supabase.lib.client import APIResponse
from typing import List
import uuid
import os

app = FastAPI()

def get_supabase() -> Client:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    return create_client(url, key)

class NotesRecord(BaseModel):
    id: uuid.UUID
    agent_id: str
    type: str
    content: str
    priority: str
    created_at: str
    subsystem: str
    metadata: dict

async def list_notes(supabase: Client) -> List[NotesRecord]:
    response: APIResponse = (
        supabase
        .schema("mammoth")
        .table("agent_notes")
        .select("*")
        .execute()
    )

    if response.error:
        raise HTTPException(status_code=500, detail="Error fetching notes")

    return [NotesRecord.model_validate(note) for note in response.data]

async def create_note(note: NotesRecord, supabase: Client) -> NotesRecord:
    response: APIResponse = (
        supabase
        .schema("mammoth")
        .table("agent_notes")
        .insert(note.dict())
        .execute()
    )

    if response.error:
        raise HTTPException(status_code=500, detail="Error creating note")

    return NotesRecord.model_validate(response.data[0])

async def delete_note(note_id: uuid.UUID, supabase: Client) -> None:
    note_id_str = str(note_id)

    response: APIResponse = (
        supabase
        .schema("mammoth")
        .table("agent_notes")
        .delete()
        .eq("id", note_id_str)
        .execute()
    )

    if response.error:
        raise HTTPException(status_code=500, detail="Error deleting note")

@app.get("/notes", response_model=List[NotesRecord])
async def get_notes(supabase: Client = Depends(get_supabase)):
    return await list_notes(supabase)

@app.post("/notes", response_model=NotesRecord)
async def post_note(note: NotesRecord, supabase: Client = Depends(get_supabase)):
    return await create_note(note, supabase)

@app.delete("/notes/{id}")
async def remove_note(id: uuid.UUID, supabase: Client = Depends(get_supabase)):
    await delete_note(id, supabase)
    return {"detail": "Note deleted successfully"}

def solution(*args, **kwargs):
    return app
