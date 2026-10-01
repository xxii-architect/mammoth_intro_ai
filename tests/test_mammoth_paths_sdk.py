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
