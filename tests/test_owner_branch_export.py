import base64
import hashlib
import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from fastapi.testclient import TestClient

from mammoth_os.owner_execution import OwnerExecution, ExecutionError, git, head_sha
from test_owner_execution import repository, FakeExecutor, validated  # noqa: F401
from test_paths_backend_contract import packaged_clients  # noqa: F401


def applied(service, root):
    job = validated(service, root)
    return service.apply(job["id"], "owner", root, job["application"]["approval_digest"])


def test_bundle_transfers_only_approved_commit_without_touching_checkout(repository, tmp_path):  # noqa: F811
    service = OwnerExecution(tmp_path / "jobs", FakeExecutor(), enabled=True)
    base = head_sha(repository)
    recipient = tmp_path / "recipient"
    git(repository, "clone", "--no-hardlinks", str(repository), str(recipient))
    job = applied(service, repository)
    commit = job["application"]["commit_sha"]
    before_index = git(repository, "write-tree")
    (repository / "app.py").write_text("private uncommitted text", encoding="utf-8")
    receipt = service.export_branch(job["id"], "owner", repository, commit)
    data = base64.b64decode(receipt["bundle_base64"], validate=True)
    assert hashlib.sha256(data).hexdigest() == receipt["sha256"]
    assert receipt["base_sha"] == base and receipt["size_bytes"] == len(data)
    assert data.startswith(b"# v2 git bundle\n") and base.encode() in data.split(b"\n\n")[0]
    bundle = tmp_path / receipt["filename"]
    bundle.write_bytes(data)
    git(recipient, "bundle", "verify", str(bundle))
    ref = f"refs/heads/{receipt['branch']}"
    git(recipient, "fetch", "--no-tags", str(bundle), f"{ref}:{ref}")
    assert git(recipient, "rev-parse", ref).decode().strip() == commit
    assert git(recipient, "rev-list", f"{base}..{ref}").decode().splitlines() == [commit]
    assert git(recipient, "show", f"{commit}:app.py") == b"def add(a, b):\n    return a + b\n"
    assert head_sha(recipient) == base and head_sha(repository) == base
    assert git(repository, "write-tree") == before_index
    assert (repository / "app.py").read_text() == "private uncommitted text"
    assert not git(repository, "remote").strip()
    empty = tmp_path / "empty"
    empty.mkdir()
    git(empty, "init")
    with pytest.raises(ExecutionError):
        git(empty, "bundle", "verify", str(bundle))
    # Unchanged secret blob is a prerequisite, never transported in the delta pack.
    pack = data[data.index(b"\n\n") + 2:]
    git(empty, "index-pack", "--stdin", input_bytes=pack)
    secret = git(repository, "rev-parse", f"{base}:.env").decode().strip()
    with pytest.raises(ExecutionError):
        git(empty, "cat-file", "-e", secret)


def test_sha256_repository_bundle_preserves_commit_identity(tmp_path):
    root = tmp_path / "sha256"
    root.mkdir()
    git(root, "init", "--object-format=sha256")
    (root / "app.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
    git(root, "add", "app.py")
    git(root, "-c", "user.name=Test", "-c", "user.email=test@example.test", "commit", "-m", "Base")
    service = OwnerExecution(tmp_path / "jobs", FakeExecutor(), enabled=True)
    job = applied(service, root)
    receipt = service.export_branch(job["id"], "owner", root, job["application"]["commit_sha"])
    from mammoth_os.paths import decode_owner_branch_export
    data = decode_owner_branch_export(receipt, job["id"], job["application"]["commit_sha"])
    assert data.startswith(b"# v3 git bundle\n") and len(receipt["commit_sha"]) == 64
    bundle = tmp_path / "sha256.bundle"
    bundle.write_bytes(data)
    git(root, "bundle", "verify", str(bundle))


def test_export_ignores_local_replace_refs(repository, tmp_path):  # noqa: F811
    service = OwnerExecution(tmp_path / "jobs", FakeExecutor(), enabled=True)
    job = applied(service, repository)
    commit = job["application"]["commit_sha"]
    git(repository, "replace", commit, job["base_sha"])
    receipt = service.export_branch(job["id"], "owner", repository, commit)
    assert receipt["commit_sha"] == commit
    assert git(repository, "rev-parse", f"{commit}^").decode().strip() == job["base_sha"]


@pytest.mark.parametrize("mutation", ["owner", "root", "expected", "moved", "tree", "proposal", "status", "disabled", "oversize"])
def test_export_rejects_mismatched_or_unapproved_work(repository, tmp_path, monkeypatch, mutation):  # noqa: F811
    import mammoth_os.owner_execution as module
    service = OwnerExecution(tmp_path / "jobs", FakeExecutor(), enabled=True)
    job = applied(service, repository)
    commit = job["application"]["commit_sha"]
    user, root, expected = "owner", repository, commit
    if mutation == "owner":
        user = "another-owner"
    elif mutation == "root":
        root = tmp_path
    elif mutation == "expected":
        expected = "f" * 40
    elif mutation == "moved":
        git(root, "update-ref", f"refs/heads/{job['application']['branch']}", job["base_sha"])
    elif mutation == "disabled":
        service.enabled = False
    elif mutation == "oversize":
        monkeypatch.setattr(module, "MAX_BUNDLE_BYTES", 1)
    else:
        record = service._load(job["id"], "owner")
        if mutation == "proposal":
            record["changes"][0]["content"] = "changed"
        elif mutation == "status":
            record["application"]["status"] = "ready"
        elif mutation == "tree":
            # A same-parent commit with the wrong tree must not be exportable.
            wrong = git(root, "-c", "user.name=Test", "-c", "user.email=test@example.test",
                        "commit-tree", f"{record['base_sha']}^{{tree}}", "-p", record["base_sha"],
                        input_bytes=b"Wrong tree\n").decode().strip()
            record["application"]["commit_sha"] = wrong
            git(root, "update-ref", f"refs/heads/{record['application']['branch']}", wrong)
            expected = wrong
        service._save(record)
    with pytest.raises(ExecutionError):
        service.export_branch(job["id"], user, root, expected)


def test_export_route_rechecks_auth_repo_confirmation_identity_and_no_store(repository, tmp_path, monkeypatch, packaged_clients):  # noqa: F811
    import api_server
    from mammoth_os.repo_access import RepoAccessPolicy
    service = OwnerExecution(tmp_path / "jobs", FakeExecutor(), enabled=True)
    job = applied(service, repository)
    monkeypatch.setattr(api_server, "_OWNER_EXECUTION", service)
    monkeypatch.setattr(api_server, "_REPO_POLICY", RepoAccessPolicy(
        platform_root=repository, tenant_base=tmp_path / "tenants", registry_dir=tmp_path / "registry",
        platform_slugs={"explicit/repo"}))
    monkeypatch.setattr(api_server, "_AUTH_REQUIRED", True)
    monkeypatch.setattr(api_server, "_resolve_supabase_user", lambda token: {
        "id": token, "is_admin": token in {"owner", "other-admin"}, "email": "",
    } if token in {"owner", "tenant", "other-admin"} else None)
    activity = []
    monkeypatch.setattr(api_server, "_append_activity", lambda title, **kwargs: activity.append(kwargs))
    client = TestClient(api_server.app)
    path = f"/api/owner-executions/{job['id']}/export"
    body = {"repo_context": {"root": "explicit/repo"}, "expected_commit": job["application"]["commit_sha"],
            "confirm_private_export": True}
    assert client.post(path, json=body).status_code == 401
    assert client.post(path, json=body, headers={"Authorization": "Bearer tenant"}).status_code == 403
    assert client.post(path, json=body, headers={"Authorization": "Bearer other-admin"}).status_code == 404
    headers = {"Authorization": "Bearer owner"}
    assert client.post(path, json={**body, "repo_context": {}}, headers=headers).status_code == 403
    assert client.post(path, json={**body, "confirm_private_export": "true"}, headers=headers).status_code == 400
    assert client.post(path, json={**body, "expected_commit": "f" * 40}, headers=headers).status_code == 409
    response = client.post(path, json=body, headers=headers)
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    assert len(activity) == 1 and activity[0]["kind"] == "owner_branch_exported"
    assert "bundle_base64" not in json.dumps(activity)
    assert "root" not in response.json()["export"]
    # Exercise the actual installed wheel and npm tarball against these loaded routes.
    class Bridge(BaseHTTPRequestHandler):
        def do_POST(self):
            payload = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            response = client.post(self.path, content=payload, headers={
                "Authorization": self.headers.get("Authorization", ""), "Content-Type": "application/json",
            })
            self.send_response(response.status_code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(response.content)))
            self.end_headers()
            self.wfile.write(response.content)

        def log_message(self, *args):
            pass

    installed, node, python_install = packaged_clients
    with ThreadingHTTPServer(("127.0.0.1", 0), Bridge) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f"http://127.0.0.1:{server.server_port}"
        try:
            python = """
import sys
from mammoth_os import MammothPaths
from mammoth_os.paths import decode_owner_branch_export
value = MammothPaths(sys.argv[1], token='owner').export_owner_branch(
    sys.argv[2], repo='explicit/repo', expected_commit=sys.argv[3], confirm_private_export=True)['export']
assert decode_owner_branch_export(value, sys.argv[2], sys.argv[3]).startswith(b'# v2 git bundle\\n')
"""
            javascript = """
import { createPathsClient, decodeOwnerBranchExport } from '@mammothos/paths'
const [url, id, commit] = process.argv.slice(1)
const value = (await createPathsClient({ baseUrl: url, token: 'owner' }).exportOwnerBranch(
    id, { repo: 'explicit/repo', expectedCommit: commit, confirmPrivateExport: true })).export
const data = await decodeOwnerBranchExport(value, { executionId: id, expectedCommit: commit })
if (!new TextDecoder().decode(data.slice(0, 15)).startsWith('# v2 git bundle')) throw new Error('Bad bundle')
"""
            env = {**os.environ, "PYTHONPATH": str(python_install)}
            for args in ([sys.executable, "-c", python], [node, "--input-type=module", "-e", javascript]):
                result = subprocess.run([*args, url, job["id"], body["expected_commit"]], cwd=installed,
                                        env=env, capture_output=True, text=True, timeout=30)
                assert result.returncode == 0, result.stdout + result.stderr
        finally:
            server.shutdown()
            thread.join(timeout=5)
