import os
import difflib
from typing import Dict, Any
from .base_agent import BaseAgent


class CodingAgent(BaseAgent):
    """
    CodingAgent Level 3
    -------------------
    Parses natural-language coding instructions, generates unified diff patches,
    and now applies patches directly to the Mammoth OS filesystem.
    """

    name = "CodingAgent"

    def __init__(self, router):
        super().__init__(router)

    # =========================================================================
    # MAIN ENTRY POINT
    # =========================================================================
    def run(self, prompt: str) -> Dict[str, Any]:
        text = prompt.strip()
        lower = text.lower()

        # --- Agent creation ---
        if lower.startswith("create a new agent named"):
            return self._handle_create_agent(text)

        # --- Registry update ---
        if "update the agent registry" in lower:
            return self._handle_registry_update(text)

        # --- CLI commands ---
        if lower == "mammoth engine list":
            return self._handle_engine_list()

        if lower == "mammoth agent list":
            return self._handle_agent_list()

        if lower == "mammoth help":
            return self._handle_help()

        if lower == "mammoth version":
            return self._handle_version()

        # Fallback
        return {
            "status": "intent",
            "agent": self.name,
            "prompt": prompt,
            "message": "CodingAgent received the prompt but no known coding pattern matched."
        }

    # =========================================================================
    # PATCH APPLICATION ENGINE (LEVEL 3)
    # =========================================================================
    def _apply_patch(self, patch_text: str) -> Dict[str, Any]:
        """
        Applies a unified diff patch directly to the filesystem.
        """
        try:
            lines = patch_text.split("\n")
            current_file = None
            new_content = []

            i = 0
            while i < len(lines):
                line = lines[i]

                # Detect file start
                if line.startswith("diff --git"):
                    # Reset for next file
                    new_content = []
                    current_file = None

                # Detect file path
                if line.startswith("+++ b/"):
                    current_file = line.replace("+++ b/", "").strip()

                # Detect patch content start
                if line.startswith("@@"):
                    i += 1
                    while i < len(lines) and not lines[i].startswith("diff --git"):
                        new_content.append(lines[i])
                        i += 1
                    # Apply file content
                    if current_file:
                        self._write_file_from_patch(current_file, new_content)
                    continue

                i += 1

            return {
                "status": "applied",
                "message": "Patch successfully applied to filesystem."
            }

        except Exception as e:
            return {
                "status": "error",
                "message": f"Patch application failed: {e}"
            }

    def _write_file_from_patch(self, filepath: str, patch_lines: list):
        """
        Writes file content extracted from unified diff patch.
        """
        # Extract only added lines (starting with '+')
        content = []
        for line in patch_lines:
            if line.startswith("+") and not line.startswith("+++"):
                content.append(line[1:])

        # Ensure directory exists
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        # Write file
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(content))

    # =========================================================================
    # AGENT CREATION (LEVEL 1 + LEVEL 3 PATCH APPLICATION)
    # =========================================================================
    def _handle_create_agent(self, prompt: str) -> Dict[str, Any]:
        parts = prompt.split("named", 1)
        agent_name = parts[1].strip().split()[0] if len(parts) > 1 else "NewAgent"

        class_name = f"{agent_name}Agent"
        module_name = f"{agent_name.lower()}_agent"
        agent_key = agent_name.lower()

        agent_file_path = f"src/mammoth_os/agents/{module_name}.py"

        agent_file_content = f"""from typing import Dict, Any
from .base_agent import BaseAgent


class {class_name}(BaseAgent):
    \"""
    {class_name}
    ------------
    Auto-generated agent. Extend with specific logic as needed.
    \"""

    name = "{class_name}"

    def __init__(self, router):
        super().__init__(router)

    def run(self, prompt: str) -> Dict[str, Any]:
        return {{
            "status": "intent",
            "agent": self.name,
            "prompt": prompt,
            "message": "{class_name} received the prompt. Implement logic here."
        }}

    def execute_action(self, action_type: str, target: str, details: Dict[str, Any]):
        return {{
            "status": "intent",
            "agent": self.name,
            "action": action_type,
            "target": target,
            "details": details,
        }}
"""

        patch = f"""diff --git a/{agent_file_path} b/{agent_file_path}
new file mode 100644
index 0000000..b1f3abc
--- /dev/null
+++ b/{agent_file_path}
@@ -0,0 +1,40 @@
{agent_file_content}
"""

        # Apply patch automatically
        apply_result = self._apply_patch(patch)

        return {
            "status": "patch_applied",
            "agent": self.name,
            "prompt": prompt,
            "patch": patch,
            "apply_result": apply_result,
            "message": f"{class_name} created and patch applied."
        }

    # =========================================================================
    # REGISTRY UPDATE (LEVEL 2)
    # =========================================================================
    def _handle_registry_update(self, prompt: str) -> Dict[str, Any]:
        return {
            "status": "intent",
            "agent": self.name,
            "prompt": prompt,
            "message": "Registry update recognized. Level 3 focuses on patch application; Level 4 will auto-update registry."
        }

    # =========================================================================
    # CLI COMMANDS (LEVEL 2)
    # =========================================================================
    def _handle_engine_list(self):
        return {
            "status": "cli",
            "command": "mammoth engine list",
            "engines": ["coding", "research", "curriculum", "schema_inspector", "field_ops"],
            "message": "Available inference engines."
        }

    def _handle_agent_list(self):
        return {
            "status": "cli",
            "command": "mammoth agent list",
            "agents": [
                "CodingAgent",
                "ResearchAgent",
                "CurriculumAgent",
                "SchemaInspectorAgent",
                "FieldOpsAgent"
            ],
            "message": "Registered agents."
        }

    def _handle_help(self):
        return {
            "status": "cli",
            "command": "mammoth help",
            "message": "Commands: mammoth engine list, mammoth agent list, mammoth help, mammoth version."
        }

    def _handle_version(self):
        return {
            "status": "cli",
            "command": "mammoth version",
            "version": "0.1.0-dev",
            "message": "Mammoth OS development build."
        }
