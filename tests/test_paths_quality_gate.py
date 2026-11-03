"""Verify the bounded SDK gates reject actual lint and type regressions."""

import importlib.util
import os
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module", autouse=True)
def quality_tools():
    missing = [tool for tool in ("ruff", "mypy") if importlib.util.find_spec(tool) is None]
    if missing:
        message = f"SDK quality gate requires: {', '.join(missing)}"
        if os.environ.get("MAMMOTH_REQUIRE_QUALITY_TESTS") == "1":
            pytest.fail(message)
        pytest.skip(message)


def check(tool, source):
    config = ROOT / "scripts" / "quality"
    options = (["check", "--config", str(config / "paths-ruff.toml")]
               if tool == "ruff" else ["--config-file", str(config / "paths-mypy.ini")])
    return subprocess.run(
        [sys.executable, "-m", tool, *options, str(source)],
        cwd=ROOT, capture_output=True, text=True, timeout=60,
    )


@pytest.mark.parametrize(("tool", "source", "diagnostic"), [
    ("ruff", "def broken():\n    return missing_name\n", "F821"),
    ("ruff", "import os\n", "F401"),
    ("mypy", "def broken() -> int:\n    return 'not an integer'\n", "return-value"),
    ("mypy", "def broken(value):\n    return value\n", "no-untyped-def"),
    ("mypy", "def broken() -> list:\n    return []\n", "type-arg"),
])
def test_quality_gates_reject_regressions(tmp_path, tool, source, diagnostic):
    target = tmp_path / "regression.py"
    target.write_text(source, encoding="utf-8")
    result = check(tool, target)
    assert result.returncode == 1, result.stdout + result.stderr
    assert diagnostic in result.stdout, result.stdout + result.stderr


@pytest.mark.parametrize("tool", ["ruff", "mypy"])
def test_quality_gates_accept_valid_typed_source(tmp_path, tool):
    target = tmp_path / "valid.py"
    target.write_text("def increment(value: int) -> int:\n    return value + 1\n", encoding="utf-8")
    result = check(tool, target)
    assert result.returncode == 0, result.stdout + result.stderr


def test_paths_package_keeps_the_recorded_clean_baseline():
    for tool in ("ruff", "mypy"):
        result = check(tool, ROOT / "src" / "mammoth_os" / "paths")
        assert result.returncode == 0, result.stdout + result.stderr


def test_unchecked_dynamic_returns_are_rejected(tmp_path):
    target = tmp_path / "dynamic.py"
    target.write_text(
        "from typing import Any\n\ndef unchecked(value: Any) -> int:\n    return value\n",
        encoding="utf-8",
    )
    result = check("mypy", target)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "no-any-return" in result.stdout
