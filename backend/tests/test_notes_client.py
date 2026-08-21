# pytest test functions — import solution from solution module
import pytest
from solution import solution
from backend.notes_client import NotesClient
import httpx

@pytest.mark.asyncio
async def test_list_notes(mocker):
    mock_response = [{"id": "1", "agent_id": "agent_1", "type": "text", "content": "Note 1", "priority": 1, "subsystem": "general", "metadata": {}}]
    
    async def mock_request(method, url, *args, **kwargs):
        return httpx.Response(200, json=mock_response)

    mocker.patch('httpx.AsyncClient.__aenter__', return_value=httpx.AsyncClient(transport=httpx.MockTransport(mock_request)))
    
    client = NotesClient("http://localhost:8000")
    notes = await client.list_notes()
    assert len(notes) == 1
    assert notes[0].content == "Note 1"

@pytest.mark.asyncio
async def test_create_note():
    client = NotesClient("http://localhost:8000")
    note = await client.create_note("agent_1", "text", "New Note", 1, "general")
    assert note.content == "New Note"

@pytest.mark.asyncio
async def test_delete_note():
    client = NotesClient("http://localhost:8000")
    await client.delete_note("1")
    # You would typically check if the note was deleted, possibly by trying to list notes again.