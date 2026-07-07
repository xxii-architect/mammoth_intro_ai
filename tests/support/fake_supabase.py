from types import SimpleNamespace

class FakeTable:
    def __init__(self, rows=None):
        self._rows = rows or []
        self._filter = None
        self._pending_insert = None
        self._pending_update = None
        self._pending_upsert = None
        self._limit = None
        self._order = None

    def from_(self, name):
        return self

    def select(self, *args, **kwargs):
        return self

    def eq(self, key, value):
        self._filter = (key, value)
        return self

    def limit(self, n):
        self._limit = n
        return self

    def order(self, column, desc=False):
        self._order = (column, desc)
        return self

    def insert(self, payload):
        self._pending_insert = payload
        return self

    def update(self, payload):
        self._pending_update = payload
        return self

    def upsert(self, payload):
        self._pending_upsert = payload
        return self

    def delete(self):
        self._pending_update = {"__delete__": True}
        return self

    def execute(self):
        def matches(row):
            if not self._filter:
                return True
            key, val = self._filter
            return row.get(key) == val

        # UPSERT
        if self._pending_upsert is not None:
            payload = self._pending_upsert
            updated = False
            for r in self._rows:
                if matches(r):
                    r.update(payload)
                    updated = True
            if not updated:
                self._rows.append(payload)
            self._pending_upsert = None
            self._filter = None
            return SimpleNamespace(data=[payload], status_code=200)

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
                self._rows[:] = [r for r in self._rows if not matches(r)]
                self._pending_update = None
                self._filter = None
                return SimpleNamespace(data=[], status_code=200)

            updated_rows = []
            for r in self._rows:
                if matches(r):
                    r.update(self._pending_update)
                    updated_rows.append(r)
            self._pending_update = None
            self._filter = None
            return SimpleNamespace(data=updated_rows, status_code=200)

        # SELECT
        rows = [r for r in self._rows if matches(r)]

        # ORDER
        if self._order:
            col, desc = self._order
            rows = sorted(rows, key=lambda r: r.get(col, 0), reverse=desc)

        # LIMIT
        if self._limit is not None:
            rows = rows[: self._limit]

        self._filter = None
        self._order = None
        self._limit = None

        return SimpleNamespace(data=rows, status_code=200)


class FakeSupabase:
    def __init__(self):
        self._leaderboard = [
            {"user_id": "d6c16bc9-fc2a-4efd-8d9e-a95fb6baa448", "xp": 0, "rank": "Novice"}
        ]
        self._streaks = []
        self._lessons = []  # ← IMPORTANT: lessons stored here
        self._profiles = []

    def schema(self, name):
        return self

    def table(self, name):
        # ALWAYS return FakeTable — NEVER return raw lists
        if name == "leaderboard":
            return FakeTable(self._leaderboard)
        if name == "streaks":
            return FakeTable(self._streaks)
        if name == "lessons":
            return FakeTable(self._lessons)  # ← FIXED
        if name == "profiles":
            return FakeTable(self._profiles)
        return FakeTable([])

    def from_(self, name):
        return self.table(name)

    def rpc(self, name, payload):
        if name in ("increment_user_xp", "public.increment_user_xp"):
            user_id = payload["p_user_id"]
            inc = payload["p_xp_increment"]

            row = next((r for r in self._leaderboard if r["user_id"] == user_id), None)
            if row:
                row["xp"] += inc
            else:
                row = {"user_id": user_id, "xp": inc}
                self._leaderboard.append(row)

            return SimpleNamespace(data=[row], status_code=200)

        if name == "update_streak":
            user_id = payload["p_user_id"]
            row = next((r for r in self._streaks if r["user_id"] == user_id), None)
            if row:
                row["streak"] += 1
            else:
                row = {"user_id": user_id, "streak": 1}
                self._streaks.append(row)

            return SimpleNamespace(data=[row], status_code=200)

        return SimpleNamespace(data=[], status_code=200)


def fake_get_supabase():
    return FakeSupabase()
