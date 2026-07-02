"""
Mammoth OS — Autonomous Engine (Lightweight Version)
Used in Mammoth Intro AI to support file operations and patching.
"""

import difflib
from pathlib import Path
from typing import Any, Dict


class AutonomousEngine:
    """
    Lightweight AutonomousEngine for Mammoth Intro AI.
    Supports:
    - create_file
    - write_file
    - apply_patch
    - generate_patch
    - run_task
    """

    def __init__(self, user_id: str | None = None):
        self.user_id = user_id

    # 🧩 Create a new file
    def create_file(self, path: str, content: str = "") -> Dict[str, Any]:
        file_path = Path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf8")
        return {"status": "success", "action": "create_file", "path": path}

    # 🧩 Write/replace file content
    def write_file(self, path: str, content: str) -> Dict[str, Any]:
        Path(path).write_text(content, encoding="utf8")
        return {"status": "success", "action": "write_file", "path": path}

    # 🧩 Generate unified diff patch
    def generate_patch(self, old: str, new: str, filename: str) -> str:
        diff = difflib.unified_diff(
            old.splitlines(),
            new.splitlines(),
            fromfile=f"{filename} (old)",
            tofile=f"{filename} (new)",
            lineterm=""
        )
        return "\n".join(diff)

    # 🧩 Apply patch directly (simple version)
    def apply_patch(self, path: str, new_content: str) -> Dict[str, Any]:
        Path(path).write_text(new_content, encoding="utf8")
        return {"status": "success", "action": "apply_patch", "path": path}

    # 🧩 Main task router
    def run_task(self, task: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if task == "create_file":
            return self.create_file(payload["file_path"], payload.get("content", ""))

        if task == "write_file":
            return self.write_file(payload["file_path"], payload["content"])

        if task == "apply_patch":
            return self.apply_patch(payload["file_path"], payload["new_content"])

        return {"status": "error", "message": f"Unknown task '{task}'"}
