"""Installed clients, actual socket timeouts and a killed/restarted SQLite worker."""

import asyncio
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from contextlib import contextmanager

import pytest
from fastapi import UploadFile

from mammoth_os.document_review import DocumentReviews
from mammoth_os.documents import DocumentLibrary
from test_paths_backend_contract import packaged_clients  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]

PYTHON_DRIVER = """
import json, sys
from mammoth_os import MammothPaths, PathsError
client = MammothPaths(sys.argv[1], timeout=0.8 if sys.argv[3] == 'timeout' else 10)
try:
    if sys.argv[3] == 'get':
        result = client.get_document_review(sys.argv[2])
    elif sys.argv[3] == 'budget':
        result = client.extend_document_review_budget(sys.argv[2], expected_max_tokens=64000,
                    max_tokens=128000, confirm_budget_extension=True)
    else:
        result = client.advance_document_review(sys.argv[2], confirm_model_usage=True)
except (PathsError, TimeoutError, ConnectionError) as error:
    print(json.dumps({'error': type(error).__name__, 'status': getattr(error, 'status', 0)}))
else:
    print(json.dumps(result))
"""

JS_DRIVER = """
import { createPathsClient } from '@mammothos/paths'
const [url, id, action] = process.argv.slice(1)
const client = createPathsClient({ baseUrl: url, fetch: (url, init) =>
    fetch(url, { ...init, signal: AbortSignal.timeout(action === 'timeout' ? 800 : 10000) }) })
try {
    const result = action === 'get' ? await client.getDocumentReview(id)
      : action === 'budget' ? await client.extendDocumentReviewBudget(id, {
          expectedMaxTokens: 64000, maxTokens: 128000, confirmBudgetExtension: true })
      : await client.advanceDocumentReview(id, { confirmModelUsage: true })
    console.log(JSON.stringify(result))
} catch (error) {
    console.log(JSON.stringify({ error: error.name, status: error.status || 0 }))
}
"""


def wait_for_file(path, process):
    deadline = time.monotonic() + 15
    while not path.exists():
        assert process.poll() is None, f"Worker exited ({process.returncode})"
        assert time.monotonic() < deadline, f"Worker did not produce {path.name}"
        time.sleep(0.02)


@contextmanager
def worker(root, blocked_index=-1):
    ready = root / "ready.json"
    ready.unlink(missing_ok=True)
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    with (root / "worker.log").open("a", encoding="utf-8") as log:
        process = subprocess.Popen([sys.executable, str(ROOT / "tests" / "support" / "document_review_worker.py"),
                                    str(root), str(ready), str(blocked_index)], cwd=ROOT, env=env,
                                   stdout=log, stderr=log)
        try:
            wait_for_file(ready, process)
            yield json.loads(ready.read_text())["url"], process
        finally:
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=10)


def client_call(packages, language, url, review_id, action):
    install, node, python_install = packages
    env = {**os.environ, "PYTHONPATH": str(python_install)}
    args = [sys.executable, "-c", PYTHON_DRIVER] if language == "python" else [node, "--input-type=module", "-e", JS_DRIVER]
    result = subprocess.run([*args, url, review_id, action], cwd=install, env=env,
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


@pytest.fixture
def saved_review(tmp_path):
    library = DocumentLibrary(tmp_path / "documents", {})
    asyncio.run(library.upload(UploadFile(filename="source.txt", file=io.BytesIO(b"Original source.")), "chat"))
    entry = library.list("chat")[0]
    Path(entry["chunks_path"]).write_text(json.dumps([
        {"text": f"Original section {index}.", "location": f"section {index}"} for index in range(4)
    ]), encoding="utf-8")
    reviews = DocumentReviews(library)
    return tmp_path, reviews.create("chat", entry["file_id"], "Assess every indexed section.")["id"]


def indices(root):
    return [json.loads(line)["chunk_index"] for line in (root / "calls.jsonl").read_text().splitlines()]


@pytest.mark.parametrize("language", ["python", "javascript"])
def test_real_timeout_then_process_restart_never_replays_unknown_call(packaged_clients, saved_review, language):  # noqa: F811
    root, review_id = saved_review
    with worker(root, blocked_index=1) as (url, process):
        outcome = client_call(packaged_clients, language, url, review_id, "timeout")
        assert outcome["error"] in {"TimeoutError", "PathsError"} and outcome["status"] == 0
        wait_for_file(root / "inflight", process)
        saved = client_call(packaged_clients, language, url, review_id, "get")["review"]
        assert saved["status"] == "active" and saved["inflight_section"] == 1
        assert [item["chunk_index"] for item in saved["assessments"]] == [0]
        assert saved["usage"]["tokens"] == 100
        assert indices(root) == [0, 1]
    with worker(root) as (url, _):
        assert client_call(packaged_clients, language, url, review_id, "get")["review"] == saved
        assert client_call(packaged_clients, language, url, review_id, "advance")["status"] == 409
        assert client_call(packaged_clients, language, url, review_id, "budget")["status"] == 409
        assert indices(root) == [0, 1]


@pytest.mark.parametrize("language", ["python", "javascript"])
def test_process_restart_resumes_only_next_confirmed_checkpoint(packaged_clients, saved_review, language):  # noqa: F811
    root, review_id = saved_review
    with worker(root) as (url, _):
        saved = client_call(packaged_clients, language, url, review_id, "advance")["review"]
        assert saved["status"] == "partial" and len(saved["assessments"]) == 3
        assert indices(root) == [0, 1, 2]
    with worker(root) as (url, _):
        assert client_call(packaged_clients, language, url, review_id, "get")["review"] == saved
        assert indices(root) == [0, 1, 2]
        completed = client_call(packaged_clients, language, url, review_id, "advance")["review"]
        assert completed["review_complete"] and completed["usage"]["tokens"] == 400
        assert indices(root) == [0, 1, 2, 3]
