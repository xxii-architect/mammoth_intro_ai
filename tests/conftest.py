# tests/conftest.py
import pytest
from types import SimpleNamespace
import importlib

print(">>> tests.conftest.py loaded (early patch)")

# -------------------------
# Chainable fake table
# -------------------------
class FakeTable:
    def __init__(self, rows=None):
        self._rows = rows or []
        self._filter = None
        self._pending_update = None
        self._pending_insert = None
        self._last_select_args = None

    # chain entry points
    def select(self, *args, **kwargs):
        self._last_select_args = (args, kwargs)
        return self

    def eq(self, key, value):
        self._filter = (key, value)
        return self

    def insert(self, payload):
        self._pending_insert = payload
        return self

    def update(self, payload):
        self._pending_update = payload
        return self

    def delete(self):
        self._pending_update = {"__delete__": True}
        return self

    def execute(self):
        """
        Execute the pending operation (select/insert/update/delete) and return
        an object with .data similar to the real client response.
        """
        def _matches_filter(row):
            if not self._filter:
                return True
            key, val = self._filter
            return row.get(key) == val

        # INSERT
        if self._pending_insert is not None:
            payload = self._pending_insert
            if isinstance(payload, list):
                for p in payload:
                    self._rows.append(p)
                data = payload
            else:
                self._rows.append(payload)
                data = [payload]
            self._pending_insert = None
            self._filter = None
            return SimpleNamespace(data=data, status_code=201)

        # UPDATE / DELETE
        if self._pending_update is not None:
            if self._pending_update.get("__delete__"):
                before = len(self._rows)
                self._rows[:] = [r for r in self._rows if not _matches_filter(r)]
                deleted = before - len(self._rows)
                self._pending_update = None
                self._filter = None
                return SimpleNamespace(data=[], status_code=200)
            updated_rows = []
            for r in self._rows:
                if _matches_filter(r):
                    r.update(self._pending_update)
                    updated_rows.append(r)
            self._pending_update = None
            self._filter = None
            return SimpleNamespace(data=updated_rows, status_code=200)

        # SELECT
        if self._last_select_args is not None or self._filter is not None:
            rows = [r for r in self._rows if _matches_filter(r)]
            self._last_select_args = None
            self._filter = None
            return SimpleNamespace(data=rows, status_code=200)

        # default: return all rows
        return SimpleNamespace(data=list(self._rows), status_code=200)


# -------------------------
# Fake Supabase client
# -------------------------
class FakeSupabase:
    def __init__(self):
        self._leaderboard = [{"user_id": "d6c16bc9-fc2a-4efd-8d9e-a95fb6baa448", "xp": 0}]
        self._streaks = [{"user_id": "d6c16bc9-fc2a-4efd-8d9e-a95fb6baa448", "streak": 1}]
        self._sessions = []

    def schema(self, name):
        # keep API shape: supabase.schema("atlas").table("...")...
        return self

    def table(self, name):
        if name == "leaderboard":
            return FakeTable(rows=self._leaderboard)
        if name == "streaks":
            return FakeTable(rows=self._streaks)
        if name == "sessions":
            return FakeTable(rows=self._sessions)
        return FakeTable(rows=[])

    def rpc(self, name, payload):
        """
        Simulate RPCs. If the code calls increment_user_xp, handle it here
        by updating the leaderboard row and returning a response object.
        Otherwise raise to force fallback behavior in code.
        """
        # handle the specific RPC used by the code/tests
        if name in ("increment_user_xp", "public.increment_user_xp"):
            user_id = None
            xp_inc = None
            if isinstance(payload, dict):
                user_id = payload.get("p_user_id") or payload.get("user_id")
                xp_inc = payload.get("p_xp_increment") or payload.get("xp_increment") or payload.get("amount")
            if user_id is None and isinstance(payload, (list, tuple)) and payload:
                first = payload[0]
                if isinstance(first, dict):
                    user_id = first.get("p_user_id") or first.get("user_id")
                    xp_inc = first.get("p_xp_increment") or first.get("xp_increment")
            if not user_id or xp_inc is None:
                raise RuntimeError("RPC increment_user_xp called with unexpected payload in fake client")

            row = next((r for r in self._leaderboard if r.get("user_id") == user_id), None)
            if row:
                row["xp"] = int(row.get("xp", 0)) + int(xp_inc)
            else:
                row = {"user_id": user_id, "xp": int(xp_inc)}
                self._leaderboard.append(row)
            return SimpleNamespace(data=[row], status_code=200)

        # default: not implemented
        raise RuntimeError(f"RPC {name} not available in fake client")


def fake_get_supabase():
    return FakeSupabase()


# -------------------------
# Early pytest patch (runs before collection/import)
# -------------------------
def pytest_configure(config):
    print(">>> pytest_configure: patching mammoth_os.supabase_client.get_supabase and supabase (forcing singleton)")
    sc = importlib.import_module("mammoth_os.supabase_client")

    # create a single fake instance and force the module to use it everywhere
    fake_instance = fake_get_supabase()

    # replace the factory so future calls return the fake instance
    sc.get_supabase = lambda: fake_instance # type: ignore

    # replace the cached singleton if present (ensures import-time uses are covered)
    try:
        sc._client_singleton = fake_instance # type: ignore
        print(">>> conftest: set sc._client_singleton to fake_instance")
    except Exception as e:
        print(">>> conftest: could not set _client_singleton:", e)

    # replace the proxy/attribute so direct imports of `supabase` work immediately
    try:
        sc.supabase = fake_instance  # type: ignore
        print(">>> conftest: replaced sc.supabase with fake_instance")
    except Exception as e:
        print(">>> conftest: could not replace sc.supabase:", e)
