"""Persistence operations shared by local and database-backed indexed reviews."""

from contextlib import closing, contextmanager
import json

from .documents import DocumentError


class LocalReviewStore:
    def __init__(self, library):
        self.library = library

    def list(self, scope, file_id):
        with closing(self.library._connect()) as connection:
            rows = connection.execute(
                "SELECT payload FROM document_reviews WHERE scope=? AND file_id=? ORDER BY rowid DESC", (scope, file_id),
            ).fetchall()
        return [json.loads(row[0]) for row in rows]

    def get(self, identity):
        with closing(self.library._connect()) as connection:
            row = connection.execute("SELECT payload FROM document_reviews WHERE id=?", (identity,)).fetchone()
        if row is None:
            raise DocumentError("Review not found.", 404)
        return json.loads(row[0])

    def create(self, state):
        with closing(self.library._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            if connection.execute("SELECT count(*) FROM document_reviews").fetchone()[0] >= 20:
                raise DocumentError("Saved review limit reached (20). Delete an unused review first.", 409)
            if not connection.execute(
                "SELECT 1 FROM files WHERE scope=? AND file_id=?", (state["scope"], state["file_id"]),
            ).fetchone():
                raise DocumentError("File not found.", 404)
            connection.execute("INSERT INTO document_reviews VALUES (?,?,?,?)",
                               (state["id"], state["scope"], state["file_id"], json.dumps(state)))

    def delete(self, identity):
        with closing(self.library._connect()) as connection, connection:
            if not connection.execute("DELETE FROM document_reviews WHERE id=?", (identity,)).rowcount:
                raise DocumentError("Review not found.", 404)

    def save(self, state):
        with closing(self.library._connect()) as connection, connection:
            if not connection.execute(
                "UPDATE document_reviews SET payload=? WHERE id=?", (json.dumps(state), state["id"]),
            ).rowcount:
                raise DocumentError("Review or source was deleted. No further work can be saved.", 404)

    @contextmanager
    def edit(self, identity):
        with closing(self.library._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT payload FROM document_reviews WHERE id=?", (identity,)).fetchone()
            if row is None:
                raise DocumentError("Review not found.", 404)
            state = json.loads(row[0])
            yield state
            connection.execute("UPDATE document_reviews SET payload=? WHERE id=?", (json.dumps(state), identity))
