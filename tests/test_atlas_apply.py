import asyncio
from pathlib import Path

import api_server


def test_atlas_apply_patch_writes_target_file(tmp_path, monkeypatch):
    # Bypass the admin API guard so the function body can be tested directly
    monkeypatch.setattr(api_server, "_AUTH_REQUIRED", False)

    target = tmp_path / "artifact.txt"
    target.write_text("before\n", encoding="utf-8")

    result = asyncio.run(api_server.atlas_apply(
        {
            "operation": "apply_patch",
            "file_path": str(target),
            "new_content": "after\n",
            "approval_mode": False,
        }
    ))

    assert result["status"] == "ok"
    assert result["operation"] == "apply_patch"
    assert result["result"]["status"] == "success"
    assert result["result"]["action"] == "apply_patch"
    assert Path(result["result"]["path"]) == target
    assert target.read_text(encoding="utf-8") == "after\n"
