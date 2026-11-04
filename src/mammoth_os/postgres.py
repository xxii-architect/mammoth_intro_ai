"""Private PostgreSQL connections with bounded operations and no fallback."""

from contextlib import contextmanager

from .shared_state import StateUnavailable


def open_database(dsn):
    try:
        import psycopg
    except ImportError as exc:
        raise StateUnavailable("PostgreSQL storage requires the postgres package extra.") from exc
    if not dsn:
        raise StateUnavailable("A private PostgreSQL database connection is required.")
    connection = None
    try:
        connection = psycopg.connect(dsn, autocommit=True, connect_timeout=5)
        connection.execute("SET statement_timeout = '10s'")
        connection.execute("SET lock_timeout = '5s'")
        return connection
    except psycopg.Error as exc:
        if connection is not None:
            connection.close()
        raise StateUnavailable("PostgreSQL storage is unavailable; no disk fallback was used.") from exc


@contextmanager
def database(dsn):
    connection = open_database(dsn)
    import psycopg

    try:
        yield connection
    except psycopg.Error as exc:
        raise StateUnavailable("PostgreSQL storage failed; no save or replay was confirmed.") from exc
    finally:
        connection.close()
