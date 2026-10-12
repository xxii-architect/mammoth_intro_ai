import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

import mammoth_os
from mammoth_os import MammothMind, MammothPaths, PathsError
from mammoth_os.paths import RunEvent, iter_sse
from mammoth_os.sdk import AtlasFAB


def _sse(events):
    return "".join(f"event: {e['type']}\ndata: {json.dumps(e)}\n\n" for e in events).encode("utf-8")


def _event(seq, type_, data=None, run_id="run-0123456789abcdef"):
    return {"contract": "mammoth.run.v1", "run_id": run_id, "seq": seq, "type": type_, "ts": "t", "data": data or {}}


class FakeBackend:
    def __init__(self):
        self.requests = []
        self.routes = {}

    def route(self, method, path, status=200, body=None, sse=None):
        self.routes[(method, path)] = (status, body, sse)


@pytest.fixture()
def backend():
    fake = FakeBackend()

    class Handler(BaseHTTPRequestHandler):
        def _handle(self):
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b""
            fake.requests.append({
                "method": self.command,
                "path": self.path,
                "headers": dict(self.headers),
                "body": json.loads(raw) if raw else None,
            })
            path = self.path.split("?", 1)[0]
            status, body, sse = fake.routes.get((self.command, path), (404, {"status": "error", "error": "nope"}, None))
            payload = _sse(sse) if sse is not None else json.dumps(body).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/event-stream" if sse is not None else "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        do_GET = do_POST = do_DELETE = _handle

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    fake.url = f"http://127.0.0.1:{server.server_address[1]}"
    yield fake
    server.shutdown()
    server.server_close()


def test_public_names_and_aliases():
    assert MammothMind is AtlasFAB
    assert "MammothPaths" in mammoth_os.__all__
    assert "MammothMind" in mammoth_os.__all__


def test_rejects_non_http_base_url():
    with pytest.raises(ValueError):
        MammothPaths("ftp://example.com")


def test_task_and_artifact_methods_preserve_contract_and_metering(backend):
    artifact = {"id": "patch #1", "body": "Proposal", "lineage": {"base_sha": "a" * 40}}
    task = {"id": "card", "status": "in_progress"}
    routes = [
        ("GET", "/api/tasks", [task]),
        ("POST", "/api/tasks", task),
        ("GET", "/api/workspace/artifacts", {"artifacts": [artifact], "categories": []}),
        ("POST", "/api/workspace/artifacts", {"status": "ok", "artifact": artifact}),
        ("GET", "/api/workspace/artifacts/patch%20%231/run", {"status": "ok", "task": task}),
        ("DELETE", "/api/workspace/artifacts/patch%20%231", {"status": "ok", "removed": True}),
        ("DELETE", "/api/workspace/artifacts", {"status": "ok", "cleared": 1}),
    ]
    for method, path, response in routes:
        backend.route(method, path, body=response)
    usage = []
    client = MammothPaths(backend.url, token="test-only", usage_hook=usage.append)
    assert client.list_tasks() == [task]
    assert client.save_task(task) == task
    assert client.list_artifacts()["artifacts"] == [artifact]
    assert client.save_artifact(artifact)["artifact"] == artifact
    assert client.get_artifact_run(artifact["id"])["task"] == task
    assert client.delete_artifact(artifact["id"])["removed"] is True
    assert client.clear_artifacts()["cleared"] == 1
    assert [(request["method"], request["path"]) for request in backend.requests] == [(method, path) for method, path, _ in routes]
    assert backend.requests[1]["body"] == task
    assert backend.requests[3]["body"] == artifact
    assert [item["surface"] for item in usage] == ["tasks", "tasks", *["artifacts"] * 5]
    assert all(request["headers"]["X-Mammoth-Contract"] == "mammoth.paths.v1" for request in backend.requests)
    backend.route("POST", "/api/tasks", status=409, body={"status": "error", "error": "Run-backed tasks are read-only."})
    with pytest.raises(PathsError, match="read-only") as error:
        client.save_task(task)
    assert error.value.status == 409


def test_iter_sse_handles_multiline_and_trailing_block():
    lines = [b"event: x\n", b'data: {"a":\n', b"data: 1}\n", b"\n", b'data: {"b": 2}\n']
    assert list(iter_sse(lines)) == [{"a": 1}, {"b": 2}]


def test_run_completes_and_sends_auth_and_contract_headers(backend):
    backend.route("POST", "/api/mammoth/runs", sse=[
        _event(1, "run.started"),
        _event(2, "tool.call", {"tool": "docs_search", "call_id": "c1"}),
        _event(3, "run.completed", {"reply": "Hello"}),
    ])
    usage = []
    client = MammothPaths(backend.url + "/api", token="tok-1", usage_hook=usage.append)
    seen = []
    result = client.run("hi", repo="owner/repo", on_event=seen.append)

    assert result.status == "completed"
    assert result.reply == "Hello"
    assert result.run_id == "run-0123456789abcdef"
    assert [c["tool"] for c in result.tool_calls] == ["docs_search"]
    assert [e.type for e in seen] == ["run.started", "tool.call", "run.completed"]
    request = backend.requests[0]
    assert request["headers"]["Authorization"] == "Bearer tok-1"
    assert request["headers"]["X-Mammoth-Contract"] == "mammoth.paths.v1"
    assert request["body"] == {"message": "hi", "agent_id": "assistant", "approval_mode": "tools", "repo_context": {"root": "owner/repo"}}
    assert usage and usage[0]["surface"] == "mind" and usage[0]["status"] == 200


def test_run_stops_at_approval_without_policy(backend):
    backend.route("POST", "/api/mammoth/runs", sse=[
        _event(1, "approval.requested", {"id": "apr-1", "tool": "mcp__x__write"}),
        _event(2, "run.awaiting_approval", {"approval_id": "apr-1"}),
    ])
    result = MammothPaths(backend.url).run("do it")
    assert result.status == "awaiting_approval"
    assert result.pending_approval["id"] == "apr-1"
    assert len(backend.requests) == 1


def test_partial_result_and_explicit_continuation(backend):
    run_id = "run-0123456789abcdef"
    backend.route("POST", "/api/mammoth/runs", sse=[
        _event(1, "run.partial", {"reply": "Saved progress", "code": "step_limit", "can_continue": True}),
    ])
    backend.route("POST", f"/api/mammoth/runs/{run_id}/continue", sse=[
        _event(2, "run.continued"), _event(3, "run.completed", {"reply": "Finished"}),
    ])
    client = MammothPaths(backend.url)
    result = client.run("do work")
    assert result.status == "partial" and result.reply == "Saved progress"
    assert result.events[-1].is_terminal
    events = list(client.continue_run(run_id))
    assert events[-1].data["reply"] == "Finished"
    assert backend.requests[-1]["body"] == {}

def test_premature_stream_end_is_not_a_success(backend):
    backend.route("POST", "/api/mammoth/runs", sse=[_event(1, "run.started")])
    with pytest.raises(PathsError) as error:
        MammothPaths(backend.url).run("help")
    assert error.value.code == "stream_interrupted"


def test_run_resumes_through_approval_policy(backend):
    run_id = "run-0123456789abcdef"
    backend.route("POST", "/api/mammoth/runs", sse=[
        _event(1, "approval.requested", {"id": "apr-1", "tool": "t"}),
        _event(2, "run.awaiting_approval", {"approval_id": "apr-1"}),
    ])
    backend.route("POST", f"/api/mammoth/runs/{run_id}/approval", sse=[
        _event(3, "approval.resolved", {"decision": "reject"}),
        _event(4, "run.completed", {"reply": "Worked around it"}),
    ])
    decisions = []
    result = MammothPaths(backend.url).run("do it", approve=lambda ev: decisions.append(ev.data["tool"]) or False)
    assert decisions == ["t"]
    assert result.status == "completed"
    assert result.reply == "Worked around it"
    assert backend.requests[1]["body"] == {"approval_id": "apr-1", "decision": "reject", "note": ""}


def test_http_errors_become_paths_error(backend):
    backend.route("GET", "/api/buildlog", status=403, body={"status": "error", "error": "Needs pro", "code": "tier_required"})
    with pytest.raises(PathsError) as info:
        MammothPaths(backend.url).list_build_log()
    assert info.value.status == 403
    assert info.value.code == "tier_required"


def test_status_error_payload_raises(backend):
    backend.route("POST", "/api/mammoth/repo-sources", body={"status": "error", "error": "Platform repo is private", "code": "platform_denied"})
    with pytest.raises(PathsError) as info:
        MammothPaths(backend.url).connect_repo("xxii-architect/mammoth_intro_ai")
    assert info.value.code == "platform_denied"


def test_notes_and_path_segments_are_escaped(backend):
    backend.route("POST", "/api/notes", body={"id": "n1", "content": "c"})
    backend.route("DELETE", "/api/notes/a%2Fb", body={"status": "ok"})
    client = MammothPaths(backend.url, token_provider=lambda: "fresh")
    assert client.save_note("c", title="T")["id"] == "n1"
    client.delete_note("a/b")
    assert backend.requests[0]["body"] == {"content": "c", "title": "T"}
    assert backend.requests[1]["path"] == "/api/notes/a%2Fb"
    assert backend.requests[1]["headers"]["Authorization"] == "Bearer fresh"


def test_usage_hook_failures_do_not_break_calls(backend):
    backend.route("GET", "/api/mammoth/runs", body={"status": "ok", "runs": [{"id": "run-1"}]})

    def broken(_):
        raise RuntimeError("meter down")

    assert MammothPaths(backend.url, usage_hook=broken).list_runs() == [{"id": "run-1"}]


def test_run_event_from_dict_defaults():
    event = RunEvent.from_dict({"type": "run.completed", "seq": "3"})
    assert event.seq == 3 and event.is_terminal and event.contract == "mammoth.run.v1"


def test_owner_execution_sdk_explicit_payloads_and_error_preservation(backend):
    job_id = "exec-" + "a" * 24
    changes = [{"path": "app.py", "content": "pass\n"}]
    for method, path in [
        ("GET", "/api/owner-executions/capabilities"), ("POST", "/api/owner-executions"),
        ("GET", f"/api/owner-executions/{job_id}"), ("POST", f"/api/owner-executions/{job_id}/approve"),
        ("POST", f"/api/owner-executions/{job_id}/cancel"),
    ]:
        backend.route(method, path, body={"status": "ok", "execution": {"id": job_id}})
    client = MammothPaths(backend.url, timeout=300)
    client.owner_execution_capabilities("owner/repo")
    client.prepare_owner_execution("owner/repo", changes, base_sha="b" * 40, profile="python_unittest")
    client.get_owner_execution(job_id)
    client.approve_owner_execution(job_id, repo="owner/repo", approval_digest="c" * 64)
    client.cancel_owner_execution(job_id)
    assert backend.requests[0]["path"].endswith("?repo=owner%2Frepo")
    assert backend.requests[1]["body"] == {"repo_context": {"root": "owner/repo"}, "changes": changes,
                                           "base_sha": "b" * 40, "profile": "python_unittest"}
    assert backend.requests[3]["body"]["approval_digest"] == "c" * 64
    backend.route("GET", "/api/owner-executions/capabilities", status=403, body={"error": "Owner only", "code": "admin_required"})
    with pytest.raises(PathsError) as error:
        client.owner_execution_capabilities()
    assert error.value.status == 403 and error.value.code == "admin_required"
