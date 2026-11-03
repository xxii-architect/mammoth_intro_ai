"""Installed clients against loaded routes with isolated auth, context and tools."""

import json
import asyncio
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from fastapi import UploadFile
from fastapi.testclient import TestClient

import api_server
from mammoth_os.agent_loop import AgentRunner, RunStore, ToolRegistry, ToolSpec
from mammoth_os.documents import DocumentLibrary


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def packaged_clients(tmp_path_factory):
    root = tmp_path_factory.mktemp("paths-packages")
    node, npm = shutil.which("node"), shutil.which("npm")
    if not node or not npm:
        if os.environ.get("MAMMOTH_REQUIRE_PACKAGED_SDK_TESTS") == "1":
            pytest.fail("Packaged SDK contract tests require Node and npm.")
        pytest.skip("Node/npm unavailable; CI enforces packaged SDK contract tests.")
    source = root / "python-source"
    source.mkdir()
    for name in ("pyproject.toml", "README.md"):
        shutil.copy2(ROOT / name, source / name)
    shutil.copytree(ROOT / "src", source / "src", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    wheels = root / "wheels"
    wheels.mkdir()
    build = subprocess.run(
        [sys.executable, "-c", "import sys; from setuptools.build_meta import build_wheel; build_wheel(sys.argv[1])", str(wheels)],
        cwd=source, capture_output=True, text=True, timeout=120,
    )
    assert build.returncode == 0, build.stdout + build.stderr
    wheel, = wheels.glob("*.whl")
    python_install = root / "python-installed"
    install = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--no-deps", "--no-index", "--target", str(python_install), str(wheel)],
        capture_output=True, text=True, timeout=60,
    )
    assert install.returncode == 0, install.stdout + install.stderr
    pack = subprocess.run([npm, "pack", "--ignore-scripts", "--json", "--pack-destination", str(root)],
                          cwd=ROOT / "packages" / "mammoth-paths", capture_output=True, text=True, timeout=60)
    assert pack.returncode == 0, pack.stdout + pack.stderr
    archive = root / json.loads(pack.stdout)[0]["filename"]
    install_js = subprocess.run(
        [npm, "install", "--offline", "--ignore-scripts", "--no-package-lock", "--no-audit", "--no-fund",
         "--prefix", str(root), str(archive)],
        cwd=root, capture_output=True, text=True, timeout=60,
    )
    assert install_js.returncode == 0, install_js.stdout + install_js.stderr
    return root, node, python_install


@pytest.fixture
def contract_backend(monkeypatch, tmp_path):
    monkeypatch.setattr(api_server, "_AUTH_REQUIRED", True)
    monkeypatch.setattr(api_server, "_resolve_supabase_user", lambda token: {
        "id": token, "is_admin": False,
    } if token in {"tenant-a", "tenant-b"} else None)
    libraries = {
        user: DocumentLibrary(tmp_path / user / "documents",
                              {"chat": tmp_path / user / "chat", "atlas": tmp_path / user / "atlas"})
        for user in ("tenant-a", "tenant-b")
    }
    uploaded = asyncio.run(libraries["tenant-a"].upload(
        UploadFile(filename="source.txt", file=io.BytesIO(
            ("BEGIN_SOURCE\n" + "middle source material " * 300 + "\nEND_SOURCE").encode())), "chat"))
    monkeypatch.setattr(api_server, "_document_library", lambda user: libraries[user])
    monkeypatch.setattr(api_server, "_load_atlas_state", lambda: {
        "active_account_id": "default", "mammoth_chat_history": [{
            "role": "user", "message": "Mind-only private history",
            "user_id": api_server._current_request_user_id(), "account_id": "default",
        }],
    })
    exchanges, documents, prompts, tool_calls, requests = [], [], [], [], []
    monkeypatch.setattr(api_server, "_persist_agent_run_exchange", lambda run, **kwargs: exchanges.append(run.id))
    def attached(user, ids, message):
        documents.append((user, ids))
        return "Fixture document context." if ids == ["fixture-file"] else ""
    monkeypatch.setattr(api_server, "_attached_chat_document_context", attached)
    store = RunStore(tmp_path / "runs")
    registry = ToolRegistry()
    registry.register(ToolSpec(
        "contract_read", "Fixture read requiring review", {"type": "object", "properties": {}, "additionalProperties": False},
        "read", lambda args, ctx: tool_calls.append(ctx.user_id) or {"status": "ok"},
        requires_approval=True,
    ))
    class Model:
        model = "scripted-contract"
        def __init__(self):
            self.responses = iter([
                {"final": "Context received."},
                {"tool": "contract_read", "args": {}},
                {"final": "Approved read finished."},
                {"tool": "contract_read", "args": {}},
            ])
        async def generate(self, prompt, **kwargs):
            prompts.append(prompt)
            return json.dumps(next(self.responses))
    model = Model()
    monkeypatch.setattr(api_server, "_AGENT_RUNS", store)
    monkeypatch.setattr(api_server, "_AGENT_TOOLS", registry)
    monkeypatch.setattr(api_server, "_AGENT_RUNNER", AgentRunner(registry, lambda: model, store))
    with TestClient(api_server.app) as app:
        class Handler(BaseHTTPRequestHandler):
            def handle_request(self):
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length)
                requests.append((self.command, self.path, json.loads(body) if body else None))
                response = app.request(self.command, self.path, content=body,
                                       headers={key: value for key, value in self.headers.items()
                                                if key.lower() not in {"host", "content-length", "connection"}})
                self.send_response(response.status_code)
                self.send_header("Content-Type", response.headers.get("content-type", "application/json"))
                self.send_header("Content-Length", str(len(response.content)))
                self.end_headers()
                self.wfile.write(response.content)
            do_GET = do_POST = handle_request
            def log_message(self, *args):
                pass
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield {
                "url": f"http://127.0.0.1:{server.server_port}", "store": store,
                "exchanges": exchanges, "documents": documents, "prompts": prompts,
                "tool_calls": tool_calls, "requests": requests,
                "file_id": uploaded["file_id"],
            }
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


@pytest.mark.parametrize("language", ["python", "javascript"])
def test_packaged_clients_follow_loaded_backend_contract(packaged_clients, contract_backend, language):
    root, node, python_install = packaged_clients
    backend = contract_backend
    driver = ROOT / "tests" / "support" / ("paths_contract_driver.py" if language == "python" else "paths_contract_driver.mjs")
    if language == "python":
        command = [sys.executable, str(driver), backend["url"], str(python_install), backend["file_id"]]
    else:
        installed_driver = root / driver.name
        shutil.copy2(driver, installed_driver)
        command = [node, str(installed_driver), backend["url"], backend["file_id"]]
    result = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    data = json.loads(result.stdout)
    saved = backend["store"].get(data["context_run"], "tenant-a")
    assert saved.request["surface"] == "agent_workspace"
    assert saved.request["repo_context"] is None
    assert saved.request["thread_id"] == ""
    assert saved.request["history_text"] == "user: Prior workspace turn\nassistant: Prior answer"
    assert saved.request["extra_context"].startswith("Task: review code.")
    assert "Fixture document context." in saved.request["extra_context"]
    assert "Mind-only private history" not in backend["prompts"][0]
    assert "Prior workspace turn" in backend["prompts"][0]
    assert ("tenant-a", ["fixture-file"]) in backend["documents"]
    assert backend["exchanges"] == []
    assert backend["tool_calls"] == ["tenant-a"]
    assert backend["store"].get(data["cancelled_run"], "tenant-a").status == "cancelled"
    starts = [body for method, path, body in backend["requests"] if method == "POST" and path == "/api/mammoth/runs"]
    assert starts[0]["history"][0]["text"] == "Prior workspace turn"
    assert starts[0]["attached_file_ids"] == ["fixture-file"]
    assert starts[0]["task"] == "analyze_codebase"
    assert len(starts) == 5  # contextual run, denied repo, two approval runs, anonymous request
