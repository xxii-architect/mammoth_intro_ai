# pytest test functions — import solution from solution module
from solution import solution
from fastapi.testclient import TestClient
import uuid

# Mock Supabase client
class MockSupabaseClient:
    def __init__(self):
        self.notes = []

    def insert(self, note):
        self.notes.append(note)
        return {"data": note}

    def delete(self, note_id):
        self.notes = [note for note in self.notes if note["id"] != note_id]
        return {"data": {"detail": "Note deleted successfully"}}

    def select(self):
        return self.notes

mock_supabase = MockSupabaseClient()

def test_get_notes():
    # Populate mock data
    mock_supabase.insert({
        "id": uuid.uuid4(),
        "agent_id": "agent_1",
        "type": "info",
        "content": "This is a test note",
        "priority": "high",
        "created_at": "2023-10-01T12:00:00Z",
        "subsystem": "test_subsystem",
        "metadata": {}
    })
    
    response = client.get("/notes")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_post_note():
    note_data = {
        "id": uuid.uuid4(),
        "agent_id": "agent_1",
        "type": "info",
        "content": "This is a test note",
        "priority": "high",
        "created_at": "2023-10-01T12:00:00Z",
        "subsystem": "test_subsystem",
        "metadata": {}
    }
    response = client.post("/notes", json=note_data)
    assert response.status_code == 200
    assert response.json()["content"] == note_data["content"]

def test_delete_note():
    note_id = uuid.uuid4()  # Replace with a valid UUID from your database
    mock_supabase.insert({
        "id": note_id,
        "agent_id": "agent_1",
        "type": "info",
        "content": "This is a test note",
        "priority": "high",
        "created_at": "2023-10-01T12:00:00Z",
        "subsystem": "test_subsystem",
        "metadata": {}
    })
    
    response = client.delete(f"/notes/{note_id}")
    assert response.status_code == 200
    assert response.json() == {"detail": "Note deleted successfully"}