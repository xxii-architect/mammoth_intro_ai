import os
import shutil
import subprocess
from pathlib import Path

import pytest


def test_frontend_publish_retains_previous_chunks_and_replaces_entry_last(tmp_path):
    bash = shutil.which("bash")
    if os.name == "nt":
        git_bash = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Git" / "bin" / "bash.exe"
        bash = str(git_bash) if git_bash.exists() else None
    if not bash:
        pytest.skip("Bash is not installed")
    script = (Path(__file__).parents[1] / "scripts" / "deploy-droplet.sh").read_text(encoding="utf-8")
    publish = script.split("# Step 3: Deploy frontend", 1)[1].split("# Step 4: Restart backend", 1)[0]
    build = tmp_path / "build"
    deployed = tmp_path / "deployed"
    (build / "assets").mkdir(parents=True)
    (deployed / "assets").mkdir(parents=True)
    (deployed / "assets" / "previous-hash.js").write_text("previous chunk", encoding="utf-8")
    (deployed / "index.html").write_text("old entry", encoding="utf-8")
    (build / "assets" / "current-hash.js").write_text("current chunk", encoding="utf-8")
    (build / "index.html").write_text("new entry", encoding="utf-8")
    (build / "favicon.svg").write_text("<svg/>", encoding="utf-8")
    result = subprocess.run(
        [bash, "-c", 'set -e; sudo() { "$@"; }; ' + publish],
        env={**os.environ, "UI_BUILD_DIR": build.as_posix(), "UI_DEPLOY_DIR": deployed.as_posix()},
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stderr
    assert (deployed / "assets" / "previous-hash.js").read_text() == "previous chunk"
    assert (deployed / "assets" / "current-hash.js").read_text() == "current chunk"
    assert (deployed / "favicon.svg").exists()
    assert (deployed / "index.html").read_text() == "new entry"
    assert not (deployed / "index.html.next").exists()
    assert publish.index('cp -r "${UI_BUILD_DIR}/assets"') < publish.index('mv "${UI_DEPLOY_DIR}/index.html.next"')
