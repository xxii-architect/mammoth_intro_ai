"""Versioned shared JSON records with explicit stale-write conflicts."""

from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import tempfile

from .agent_loop.lease import RunLease


class StateConflict(ValueError):
    pass


class StateUnavailable(RuntimeError):
    pass


_MISSING = object()
_SESSION = ContextVar("shared_state_session", default=None)


@contextmanager
def state_session():
    token = _SESSION.set({})
    try:
        yield
    finally:
        _SESSION.reset(token)


def _snapshots():
    session = _SESSION.get()
    if session is None:
        session = {}
        _SESSION.set(session)
    return session


def _record_snapshot(identity, payload, revision):
    session = dict(_snapshots())
    session[identity] = (deepcopy(payload), revision)
    _SESSION.set(session)


def _merge(base, proposed, current):
    if proposed == base:
        return deepcopy(current)
    if current == base or current == proposed:
        return deepcopy(proposed)
    if all(isinstance(value, dict) for value in (base, proposed, current)):
        merged = {}
        for key in dict.fromkeys([*current, *proposed]):
            old, new, saved = (value.get(key, _MISSING) for value in (base, proposed, current))
            if new is _MISSING and saved == old:
                continue
            if saved is _MISSING and new == old:
                continue
            if new is _MISSING or saved is _MISSING:
                if old is not _MISSING:
                    raise StateConflict("Saved state changed during this request; reload before retrying.")
                merged[key] = deepcopy(saved if new is _MISSING else new)
            else:
                merged[key] = _merge(old, new, saved)
        return merged
    if all(isinstance(value, list) for value in (base, proposed, current)):
        def keyed(values):
            if any(not isinstance(item, dict) or not isinstance(item.get("id"), str) for item in values):
                raise StateConflict("Concurrent changes to an unkeyed collection require a reload.")
            index = {item["id"]: item for item in values}
            if len(index) != len(values):
                raise StateConflict("Duplicate record identities require operator repair.")
            return index

        old, new, saved = map(keyed, (base, proposed, current))
        if old.keys() - new.keys() and new.keys() - old.keys():
            raise StateConflict("Concurrent collection retention changes require a reload.")
        merged = {}
        for key in dict.fromkeys([*saved, *new]):
            before, after, latest = old.get(key, _MISSING), new.get(key, _MISSING), saved.get(key, _MISSING)
            if after == before:
                if latest is not _MISSING:
                    merged[key] = latest
            elif latest == before or latest == after:
                if after is not _MISSING:
                    merged[key] = after
            else:
                raise StateConflict("This record changed in another request; reload before retrying.")
        return deepcopy(list(merged.values()))
    raise StateConflict("Saved state changed during this request; reload before retrying.")


class JsonStateStore:
    def __init__(self, root: Path, rpc=None):
        self.root, self.rpc = root, rpc

    def _identity(self, path):
        try:
            key = Path(path).absolute().relative_to(self.root.absolute()).as_posix()
            if self.rpc:
                namespace = os.environ.get("MAMMOTH_STATE_NAMESPACE", "")
                if not namespace or not namespace.replace("-", "").replace("_", "").isalnum():
                    raise StateUnavailable("Shared state requires an explicit alphanumeric deployment namespace.")
                key = f"{namespace}/{key}"
            return key
        except ValueError as exc:
            if self.rpc is None:
                return str(Path(path).absolute())
            raise StateUnavailable("State path is outside the configured private storage root.") from exc

    def _read(self, path, key, default):
        if self.rpc:
            result = self.rpc("mammoth_state_read", {"p_key": key})
            if not isinstance(result, dict) or type(result.get("revision")) is not int:
                raise StateUnavailable("Shared state backend returned an invalid record.")
            return result.get("payload") if result["revision"] else deepcopy(default), result["revision"]
        try:
            raw = Path(path).read_bytes()
        except FileNotFoundError:
            return deepcopy(default), None
        try:
            return json.loads(raw), hashlib.sha256(raw).hexdigest()
        except (ValueError, UnicodeError) as exc:
            raise StateUnavailable("Saved JSON is corrupt; it has not been reset or overwritten.") from exc

    def read(self, path, default):
        key = self._identity(path)
        try:
            payload, revision = self._read(path, key, default)
        except OSError as exc:
            raise StateUnavailable("Saved state could not be read.") from exc
        if not isinstance(payload, type(default)):
            raise StateUnavailable("Saved JSON has an unexpected shape; operator repair is required.")
        _record_snapshot((str(self.root.absolute()), key), payload, revision)
        return payload

    def write(self, path, proposed, *, strict=False):
        key = self._identity(path)
        identity = (str(self.root.absolute()), key)
        snapshot = _snapshots().get(identity)
        if snapshot is None:
            current, revision = self._read(path, key, type(proposed)())
            if revision is not None and revision != 0:
                raise StateConflict("Read the current saved record before updating it.")
            snapshot = (current, revision)
        base, _ = snapshot

        def reconcile(current):
            if strict and current != base and current != proposed:
                raise StateConflict("Saved state changed during this request; reload before retrying.")
            return _merge(base, proposed, current)

        if self.rpc:
            for _ in range(8):
                current, revision = self._read(path, key, type(proposed)())
                merged = reconcile(current)
                result = self.rpc("mammoth_state_cas", {"p_key": key, "p_revision": revision, "p_payload": merged})
                if result.get("saved") is True:
                    _record_snapshot(identity, merged, result["revision"])
                    return
            raise StateConflict("Shared state is busy; reload before retrying.")
        folder = Path(path).parent
        folder.mkdir(parents=True, exist_ok=True)
        lease = RunLease(Path(path).with_suffix(".transaction.lock"), blocking=True)
        temporary = None
        try:
            current, _ = self._read(path, key, type(proposed)())
            merged = reconcile(current)
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=folder, delete=False) as stream:
                temporary = Path(stream.name)
                json.dump(merged, stream, indent=2, default=str)
                stream.flush()
                os.fsync(stream.fileno())
            temporary.replace(path)
            _record_snapshot(identity, merged, hashlib.sha256(Path(path).read_bytes()).hexdigest())
        except OSError as exc:
            raise StateUnavailable("Saved state could not be written; no save was confirmed.") from exc
        finally:
            if temporary:
                temporary.unlink(missing_ok=True)
            lease.close()


def service_rpc(name, params):
    """Service-only RPCs; never silently fall back to a local store."""
    from .supabase_client import get_supabase

    if not os.environ.get("SUPABASE_SERVICE_ROLE_KEY"):
        raise StateUnavailable("Shared storage requires SUPABASE_SERVICE_ROLE_KEY and the reviewed migration.")
    client = get_supabase()
    if client is None:
        raise StateUnavailable("Shared storage client is unavailable.")
    try:
        response = client.rpc(name, params).execute()
    except Exception as exc:
        raise StateUnavailable("Shared storage RPC failed; no local fallback was used.") from exc
    data = getattr(response, "data", None)
    if not isinstance(data, dict):
        raise StateUnavailable("Shared storage RPC returned an invalid response.")
    return data
