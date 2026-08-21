# implementation here — main function MUST be named `solution`
import httpx
from httpx import AsyncClient, HTTPStatusError
from typing import List, Optional
from pydantic import BaseModel, ValidationError
import asyncio
import time
import uuid  # Import uuid module

    # Assuming NotesRecord is defined in backend/notes_model.py
from backend.notes_model import NotesRecord, NoteType, Priority

class NotesClient:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.client = AsyncClient()

    async def _request_with_retry(self, method: str, url: str, **kwargs) -> httpx.Response:
        retries = 3
        for attempt in range(retries):
            try:
                response = await self.client.request(method, url, **kwargs)
                response.raise_for_status()
                return response
            except HTTPStatusError as e:
                if attempt < retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                else:
                    raise e

    async def list_notes(self) -> List[NotesRecord]:
        url = f"{self.base_url}/notes"
        response = await self._request_with_retry("GET", url)
        return [NotesRecord(**note) for note in response.json()]

    async def create_note(self, agent_id: str, type: NoteType, content: str, priority: Priority, subsystem: str, metadata: Optional[dict] = None) -> NotesRecord:
        note_data = {
            "agent_id": agent_id,
            "type": type.value,
            "content": content,
            "priority": priority.value,
            "subsystem": subsystem,
            "metadata": metadata or {}
        }
        try:
            note = NotesRecord(**note_data)
        except ValidationError as e:
            raise ValueError(f"Invalid note data: {e}")

        url = f"{self.base_url}/notes"
        response = await self._request_with_retry("POST", url, json=note.dict())
        return NotesRecord(**response.json())

    async def delete_note(self, id: uuid.UUID) -> None:  # Change id parameter to uuid.UUID
        url = f"{self.base_url}/notes/{str(id)}"  # Convert to string when building the URL
        await self._request_with_retry("DELETE", url)

async def main():
    client = NotesClient("http://localhost:8000")
    notes = await client.list_notes()
    print(notes)

def solution(*args, **kwargs):
    asyncio.run(main())