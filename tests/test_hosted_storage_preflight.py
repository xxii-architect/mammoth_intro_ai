import json
import os
from pathlib import Path
import runpy
from types import SimpleNamespace
import subprocess
import sys

import pytest


def test_hosted_storage_preflight_reports_presence_not_values(tmp_path, monkeypatch):
    module = runpy.run_path(str(Path(__file__).parents[1] / "scripts" / "quality" / "inspect_hosted_storage.py"))
    root = tmp_path / "app"
    root.mkdir()
    root.joinpath(".env").write_text(
        "DATABASE_URL=private-fixture-dsn\nSUPABASE_SERVICE_ROLE_KEY=private-fixture-key\n"
        "MAMMOTH_RUN_BACKEND=unexpected-fixture\nMAMMOTH_REPLICA_COUNT=not-numeric\n", encoding="utf-8",
    )
    process = tmp_path / "proc" / "42"
    process.mkdir(parents=True)
    process.joinpath("environ").write_bytes(b"SUPABASE_URL=private-fixture-url\0MAMMOTH_RUN_BACKEND=postgres\0")
    original_resolve = Path.resolve
    original_run = subprocess.run
    commands = []

    def resolve(path, *args, **kwargs):
        return root if path == process / "cwd" else original_resolve(path, *args, **kwargs)

    def run(command, **kwargs):
        commands.append(command)
        if command[0] == "systemctl":
            return SimpleNamespace(stdout="42\n")
        if command[0] == "git":
            return SimpleNamespace(stdout="a" * 40 + "\n")
        kwargs["env"] = {
            **{key: value for key, value in os.environ.items()
               if not key.startswith(("SUPABASE_", "MAMMOTH_", "DATABASE_URL"))},
            **kwargs["env"],
        }
        return original_run([sys.executable, *command[1:]], **kwargs)

    module["inspect"].__globals__["Path"] = lambda value: tmp_path / "proc" if value == "/proc" else Path(value)
    monkeypatch.setattr(Path, "resolve", resolve)
    monkeypatch.setattr(os, "geteuid", lambda: process.stat().st_uid, raising=False)
    monkeypatch.setattr(subprocess, "run", run)
    report = module["inspect"](str(root))
    assert report["writes_performed"] is False
    assert report["migration_access"] == "database_connection_configured"
    assert report["credential_presence"]["DATABASE_URL"] is True
    assert report["credential_presence"]["MAMMOTH_POSTGRES_DSN"] is False
    assert report["configured_backends"]["MAMMOTH_RUN_BACKEND"] == "postgres"
    assert report["configured_backends"]["MAMMOTH_GENERATED_ARTIFACT_BACKEND"] == "local"
    assert report["configured_backends"]["MAMMOTH_CHAT_BACKEND"] == "local"
    assert report["replica_count"] == "invalid"
    assert "private-fixture" not in json.dumps(report)
    assert len(commands) == 3


def test_hosted_storage_preflight_refuses_missing_service(tmp_path, monkeypatch):
    module = runpy.run_path(str(Path(__file__).parents[1] / "scripts" / "quality" / "inspect_hosted_storage.py"))
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: SimpleNamespace(stdout="0\n"))
    with pytest.raises(RuntimeError, match="not found"):
        module["inspect"](str(tmp_path))
