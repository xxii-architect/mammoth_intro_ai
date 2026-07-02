# mammoth_os/agents/coding_agent.py

import os
from typing import Dict, Any

from .base_agent import BaseAgent


class CodingAgent(BaseAgent):
    """
    CodingAgent (Wednesday persona)
    - Writes and refactors code
    - Creates and deletes files (delete is approval-gated via Cortex)
    - Can request schema-related actions (always high-risk)
    """

    name = "CodingAgent"

    def __init__(self, router):
        super().__init__(router)

    def execute_action(self, action_type: str, target: str, details: Dict[str, Any]):
        if action_type == "write_code":
            return self._write_code(target, details)

        if action_type == "refactor_code":
            return self._refactor_code(target, details)

        if action_type == "create_file":
            return self._create_file(target, details)

        if action_type == "delete_file":
            return self._delete_file(target)

        if action_type in ("modify_schema", "run_migration", "modify_rls"):
            return self._schema_operation(action_type, target, details)

        return {
            "status": "unknown_action",
            "agent": self.name,
            "action": action_type,
            "target": target,
        }

    # --- Core file/code operations -----------------------------------------

    def _write_code(self, target: str, details: Dict[str, Any]):
        """
        Write or overwrite code in a file.
        details:
            - content: str (required)
        """
        content = details.get("content")
        if content is None:
            return {"status": "error", "reason": "Missing 'content' in details"}

        os.makedirs(os.path.dirname(target), exist_ok=True)

        with open(target, "w", encoding="utf-8") as f:
            f.write(content)

        return {
            "status": "ok",
            "agent": self.name,
            "action": "write_code",
            "target": target,
        }

    def _refactor_code(self, target: str, details: Dict[str, Any]):
        """
        Simple refactor placeholder.
        For now: append a comment or transformation marker.
        Later: call DeepSeek / LLM to perform real refactors.
        """
        if not os.path.exists(target):
            return {"status": "error", "reason": f"File not found: {target}"}

        transformation_note = details.get("note", "# Refactored by CodingAgent\n")

        with open(target, "a", encoding="utf-8") as f:
            f.write("\n" + transformation_note)

        return {
            "status": "ok",
            "agent": self.name,
            "action": "refactor_code",
            "target": target,
        }

    def _create_file(self, target: str, details: Dict[str, Any]):
        """
        Create a new file if it does not exist.
        Optionally seed with content.
        """
        if os.path.exists(target):
            return {"status": "exists", "target": target}

        os.makedirs(os.path.dirname(target), exist_ok=True)

        content = details.get("content", "")
        with open(target, "w", encoding="utf-8") as f:
            f.write(content)

        return {
            "status": "ok",
            "agent": self.name,
            "action": "create_file",
            "target": target,
        }

    def _delete_file(self, target: str):
        """
        Delete a file.
        This is high-risk and approval-gated by CortexRouter.
        """
        if not os.path.exists(target):
            return {"status": "error", "reason": f"File not found: {target}"}

        os.remove(target)

        return {
            "status": "ok",
            "agent": self.name,
            "action": "delete_file",
            "target": target,
        }

    # --- Schema / migration operations -------------------------------------

    def _schema_operation(self, action_type: str, target: str, details: Dict[str, Any]):
        """
        Placeholder for schema-related operations.
        These are always high-risk and go through Cortex approval.
        For now, we just return a structured intent.
        Later, this will call your Supabase / migration tooling.
        """
        return {
            "status": "intent",
            "agent": self.name,
            "action": action_type,
            "target": target,
            "details": details,
        }
    
    def run(self, prompt: str):
        """
        Main entry point for CodingAgent.
        Accepts a natural-language prompt and returns a structured intent
        describing what coding action should be taken.
        """
        return {
            "status": "intent",
            "agent": self.name,
            "prompt": prompt,
            "message": "CodingAgent received the prompt. Implement LLM-driven intent parsing here."
        }

