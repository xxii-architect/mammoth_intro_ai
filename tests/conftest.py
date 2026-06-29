# tests/conftest.py
import pytest
from types import SimpleNamespace

# Minimal fake objects to satisfy leaderboard/streak/lessons calls
class FakeTable:
    def __init__(self, rows=None):
        self._rows = rows or []
        self._filter = None

    def select(self, *args, **kwargs):
        return self

    def eq(self, key, value):
        self._filter = (key, value)
        return self

    def insert(self, payload):
        # simulate insert response
        return SimpleNamespace(data=[payload], status_code=201)

    def update(self, payload):
        # simulate update response
        return SimpleNamespace(data=[payload], status_code=200)

    def execute(self):
        # return rows matching eq filter if present
        if self._filter:
            key, val = self._filter
            rows = [r for r in self._rows if r.get(key) == val]
        else:
            rows = self._rows
        return SimpleNamespace(data=rows, status_code=200)

class FakeSupabase:
    def __init__(self):
        # seed with a sample leaderboard record for tests
        self._leaderboard = [{"user_id": "d6c16bc9-fc2a-4efd-8d9e-a95fb6baa448", "xp": 0}]
        self._streaks = [{"user_id": "d6c16bc9-fc2a-4efd-8d9e-a95fb6baa448", "streak": 1}]

    def schema(self, name):
        # ignore schema name, return self for chaining
        return self

    def table(self, name):
        if name == "leaderboard":
            return FakeTable(rows=self._leaderboard)
        if name == "streaks":
            return FakeTable(rows=self._streaks)
        # default empty table
        return FakeTable(rows=[])

# Provide a fake get_supabase function that your code can call
def fake_get_supabase():
    return FakeSupabase()

@pytest.fixture(autouse=True)
def mock_supabase(monkeypatch):
    """
    Replace the real get_supabase() with a fake client for tests.
    Adjust the import path below to match your project structure.
    """
    monkeypatch.setattr("mammoth_os.supabase_client.get_supabase", lambda: fake_get_supabase())
    # If your code imports a module-level `supabase` variable instead of calling get_supabase(),
    # also patch that name:
    try:
        monkeypatch.setattr("mammoth_os.supabase_client.supabase", fake_get_supabase())
    except Exception:
        pass
    yield
