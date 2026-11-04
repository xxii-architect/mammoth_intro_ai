import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import runpy

import pytest

import api_server
from mammoth_os.agent_loop import AgentRun
from mammoth_os.agent_loop.events import RunEvent
from mammoth_os.chat_threads import MAX_RECORD_BYTES, PostgresChatThreads
from mammoth_os.shared_state import StateConflict, StateUnavailable
from test_postgres_run_store import postgres as postgres_fixture, stores as run_stores_fixture

postgres = postgres_fixture
stores = run_stores_fixture


@pytest.fixture
def threads(stores):
    store, _ = stores
    return PostgresChatThreads(store.dsn, store.namespace, "Alice+exact")


def exchange(index):
    return [{"role": "user", "message": f"question {index}"},
            {"role": "assistant", "message": f"answer {index}", "run_id": f"run-{index}"}]


def test_threads_preserve_exact_owner_and_thread_identities_across_instances(threads):
    threads.create("Thread+Exact", "Private", "assistant")
    threads.save_exchange("Thread+Exact", exchange(1))
    fresh = PostgresChatThreads(threads.dsn, threads.namespace, threads.user_id)
    assert fresh.get("Thread+Exact")["messages"] == exchange(1)
    assert fresh.list()[0]["message_count"] == 2
    assert fresh.get("thread-exact") is None
    for owner in ("alice-exact", "alice+exact", "Bob"):
        other = PostgresChatThreads(threads.dsn, threads.namespace, owner)
        assert other.get("Thread+Exact") is None and other.list() == []
    assert PostgresChatThreads(threads.dsn, threads.namespace + "-other", threads.user_id).list() == []


def test_thread_revisions_reject_stale_unkeyed_replacements_without_losing_rename(threads):
    threads.create("one", "Initial", "assistant")
    original = threads.get("one")
    threads.rename("one", "Renamed")
    with pytest.raises(StateConflict, match="changed"):
        threads.save_messages("one", exchange(1), revision=original["revision"], title="stale")
    assert threads.get("one")["messages"] == [] and threads.list()[0]["title"] == "Renamed"
    latest = threads.get("one")
    threads.save_messages("one", exchange(2), revision=latest["revision"], title="New")
    record = threads.get("one")
    assert record["messages"] == exchange(2) and record["entry"]["message_count"] == 2


def test_atomic_exchanges_serialize_and_update_existing_run_without_duplicate_prompts(threads):
    threads.create("one", "Initial", "assistant")
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda index: threads.save_exchange("one", exchange(index)), range(24)))
    record = threads.get("one")
    assert len(record["messages"]) == record["entry"]["message_count"] == 48
    assert {row["run_id"] for row in record["messages"] if row["role"] == "assistant"} == {
        f"run-{index}" for index in range(24)
    }
    changed = exchange(0)
    changed[1]["message"] = "continued"
    threads.save_exchange("one", changed)
    assert len(threads.get("one")["messages"]) == 48
    assert next(row for row in threads.get("one")["messages"] if row.get("run_id") == "run-0")["message"] == "continued"


def test_delete_removes_content_and_fences_old_missing_and_repeated_completions(threads):
    threads.create("one", "Private", "assistant")
    original = threads.get("one")
    threads.save_exchange("one", exchange(1))
    threads.delete("one")
    threads.delete("one")
    assert threads.get("one") is None and threads.list() == []
    assert threads.rename("one", "resurrect") is False
    for action in (lambda: threads.create("one", "again", "assistant"),
                   lambda: threads.save_exchange("one", exchange(2)),
                   lambda: threads.save_messages("one", exchange(3), revision=original["revision"], title="again")):
        with pytest.raises(StateConflict):
            action()
    threads.delete("missing")
    with pytest.raises(StateConflict):
        threads.create("missing", "again", "assistant")


def test_thread_quota_is_atomic_and_never_prunes_existing_conversations(threads, monkeypatch):
    monkeypatch.setattr("mammoth_os.chat_threads.MAX_THREADS", 2)

    def create(index):
        try:
            threads.create(str(index), str(index), "assistant")
            return True
        except StateUnavailable as exc:
            assert "limit reached" in str(exc)
            return False

    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(create, range(16))) == 2
    first = threads.list()[0]["id"]
    threads.delete(first)
    threads.create("replacement", "Replacement", "assistant")
    assert len(threads.list()) == 2
    with pytest.raises(StateConflict):
        threads.create(first, "old", "assistant")


def test_thread_retention_and_actual_record_byte_bound(threads):
    threads.create("one", "Initial", "assistant")
    for index in range(62):
        threads.save_exchange("one", exchange(index))
    assert len(threads.get("one")["messages"]) == 120
    before = threads.get("one")
    with pytest.raises(ValueError, match="4 MiB"):
        threads.save_messages("one", [{"message": "a" * MAX_RECORD_BYTES}], revision=before["revision"], title="")
    assert threads.get("one") == before


def configure(monkeypatch, threads, tmp_path):
    monkeypatch.setenv("MAMMOTH_CHAT_BACKEND", "postgres")
    monkeypatch.setenv("MAMMOTH_POSTGRES_DSN", threads.dsn)
    monkeypatch.setenv("MAMMOTH_STATE_NAMESPACE", threads.namespace)
    monkeypatch.setattr(api_server, "CHAT_THREADS_DIR", tmp_path)
    monkeypatch.setattr(api_server, "_current_request_user_id", lambda *args: threads.user_id)


def test_thread_api_crud_uses_shared_store_not_legacy_paths(threads, tmp_path, monkeypatch):
    configure(monkeypatch, threads, tmp_path)
    result = asyncio.run(api_server.create_chat_thread({"title": "New"}))
    identity = result["thread_id"]
    assert asyncio.run(api_server.list_chat_threads())["threads"][0]["id"] == identity
    assert asyncio.run(api_server.rename_chat_thread(identity, {"title": "Renamed"}))["title"] == "Renamed"
    assert asyncio.run(api_server.get_thread_history(identity))["chat_history"] == []
    assert asyncio.run(api_server.delete_chat_thread(identity))["deleted"] == identity
    assert asyncio.run(api_server.rename_chat_thread(identity, {"title": "Hidden"})).status_code == 404
    assert asyncio.run(api_server.list_chat_threads())["threads"] == []
    assert not list(tmp_path.iterdir())
    with pytest.raises(StateUnavailable, match="atomic"):
        api_server._save_thread_index(threads.user_id, [])
    with pytest.raises(StateUnavailable, match="coordinated"):
        api_server._save_thread_messages(threads.user_id, identity, [])


def test_legacy_stream_reports_late_delete_without_replaying_generated_reply(threads, tmp_path, monkeypatch):
    configure(monkeypatch, threads, tmp_path)
    threads.create("one", "Initial", "assistant")
    calls = []

    async def chat(body):
        calls.append("model")
        threads.delete("one")
        return {"reply": "Already generated", "chat_history": exchange(1)}

    monkeypatch.setattr(api_server, "mammoth_chat", chat)

    async def stream():
        response = await api_server.mammoth_chat_stream({"thread_id": "one"})
        return "".join([chunk async for chunk in response.body_iterator])

    raw = asyncio.run(stream())
    assert calls == ["model"] and "Already generated" in raw
    assert '"error_code": "thread_storage_failed"' in raw and threads.get("one") is None
    assert asyncio.run(api_server.mammoth_chat_stream({"thread_id": "one"})).status_code == 404
    assert calls == ["model"]


def test_run_exchange_and_terminal_event_report_failed_chat_save_without_replay(threads, tmp_path, monkeypatch):
    configure(monkeypatch, threads, tmp_path)
    state = {}
    monkeypatch.setattr(api_server, "_load_atlas_state", lambda: state)
    monkeypatch.setattr(api_server, "_save_atlas_state", lambda state: None)
    threads.create("one", "Initial", "assistant")
    run = AgentRun(AgentRun.new_id(), threads.user_id, "question")
    run.reply, run.status = "Generated reply", "completed"
    assert api_server._persist_agent_run_exchange(run, thread_id="one") == {"status": "saved"}
    assert threads.get("one")["messages"][-1]["run_id"] == run.id
    threads.delete("one")

    async def events():
        yield RunEvent(run.id, 1, "run.completed", {"reply": run.reply})

    async def stream():
        response = api_server._agent_run_stream(run, events(), thread_id="one")
        return "".join([chunk async for chunk in response.body_iterator])

    raw = asyncio.run(stream())
    assert '"chat_save": {"status": "failed"' in raw and "Generated reply" in raw
    assert threads.get("one") is None and not list(tmp_path.iterdir())


def migration():
    return runpy.run_path(str(Path(__file__).parents[1] / "scripts" / "migrate_chat_threads.py"))


def test_chat_backup_round_trip_preserves_revisions_and_deletion_fences(threads, tmp_path, monkeypatch):
    module = migration()
    threads.create("thread-one", "One", "assistant")
    threads.save_exchange("thread-one", exchange(1))
    threads.create("thread-two", "Two", "assistant")
    threads.delete("thread-two")
    backup = tmp_path / "backup"
    module["export_backup"](threads, backup)
    target = PostgresChatThreads(threads.dsn, threads.namespace + "-copy", threads.user_id)
    assert module["import_backup"](target, backup) == 2
    assert target.get("thread-one") == threads.get("thread-one")
    with pytest.raises(StateConflict):
        target.create("thread-two", "Resurrect", "assistant")
    exported = tmp_path / "exported"
    module["export_backup"](target, exported)
    assert (exported / "threads.json").read_bytes() == (backup / "threads.json").read_bytes()
    local = tmp_path / "restored"
    assert module["restore_local"](backup, local, threads.user_id) == 2
    assert (local / "restore-complete.json").is_file()
    assert json.loads((local / "_deleted.json").read_text()) == {"thread-two": True}
    monkeypatch.setenv("MAMMOTH_CHAT_BACKEND", "local")
    monkeypatch.setattr(api_server, "_thread_dir", lambda user: local)
    assert api_server._load_thread_messages(threads.user_id, "thread-one") == threads.get("thread-one")["messages"]
    with pytest.raises(StateConflict, match="deleted before rollback"):
        api_server._save_thread_messages(threads.user_id, "thread-two", exchange(4))
    with pytest.raises(StateConflict, match="deleted before rollback"):
        api_server._upsert_thread_index_entry(threads.user_id, "thread-two")
    with pytest.raises(FileExistsError):
        module["restore_local"](backup, local, threads.user_id)


def test_legacy_backup_refuses_collisions_missing_messages_and_unindexed_data(tmp_path):
    module = migration()
    source = tmp_path / "source"
    source.mkdir()
    index = [{"id": "Thread+One"}, {"id": "thread-one"}]
    (source / "_index.json").write_text(json.dumps(index))
    (source / "thread-one.json").write_text("[]")
    with pytest.raises(ValueError, match="Colliding"):
        module["local_backup"](source, tmp_path / "backup", "alice")
    (source / "_index.json").write_text(json.dumps([{"id": "thread-two"}]))
    with pytest.raises(FileNotFoundError):
        module["local_backup"](source, tmp_path / "missing", "alice")
    (source / "thread-two.json").write_text("[]")
    with pytest.raises(ValueError, match="Unindexed"):
        module["local_backup"](source, tmp_path / "extra", "alice")
    (source / "thread-one.json").unlink()
    assert module["local_backup"](source, tmp_path / "valid", "alice")["threads"] == 1


def test_chat_import_refuses_wrong_owner_tamper_existing_state_and_unsafe_rollback(threads, tmp_path):
    module = migration()
    threads.create("Thread+One", "one", "assistant")
    threads.create("thread-one", "two", "assistant")
    backup = tmp_path / "backup"
    module["export_backup"](threads, backup)
    with pytest.raises(ValueError, match="already has"):
        module["import_backup"](threads, backup)
    with pytest.raises(ValueError, match="owner"):
        module["import_backup"](PostgresChatThreads(threads.dsn, threads.namespace, "wrong-owner"), backup)
    with pytest.raises(ValueError, match="collide"):
        module["restore_local"](backup, tmp_path / "unsafe", threads.user_id)
    assert not (tmp_path / "unsafe").exists()
    (backup / "threads.json").write_text("[]")
    with pytest.raises(ValueError, match="checksum"):
        module["import_backup"](PostgresChatThreads(threads.dsn, threads.namespace + "-copy", threads.user_id), backup)


def test_chat_schema_is_service_only(threads, postgres):
    threads.create("one", "private", "assistant")
    for role in ("anon", "authenticated"):
        for table in ("mammoth_chat_owners", "mammoth_chat_threads"):
            result = postgres(f"SET ROLE {role}; SELECT * FROM public.{table}", check=False)
            assert result.returncode != 0 and "permission denied" in result.stderr
    assert postgres("SELECT bool_and(relrowsecurity) FROM pg_class WHERE relname IN "
                    "('mammoth_chat_owners','mammoth_chat_threads')") == "t"


def test_chat_backend_refuses_invalid_configuration(monkeypatch):
    monkeypatch.setenv("MAMMOTH_CHAT_BACKEND", "invalid")
    with pytest.raises(StateUnavailable, match="Invalid chat"):
        api_server._chat_thread_store("alice")
    monkeypatch.setenv("MAMMOTH_CHAT_BACKEND", "postgres")
    monkeypatch.delenv("MAMMOTH_POSTGRES_DSN", raising=False)
    with pytest.raises(StateUnavailable, match="private database"):
        api_server._chat_thread_store("alice")
