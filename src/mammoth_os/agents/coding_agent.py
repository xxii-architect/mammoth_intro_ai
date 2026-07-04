import os
from typing import Dict, Any

from .base_agent import BaseAgent


class CodingAgent(BaseAgent):
    """
    CodingAgent Level 4 (Registry Auto-Append Edition)
    -------------------------------------------------
    Generates new agents, writes them to disk, and appends registry entries
    directly into agent_registry.py without relying on unified diff context.
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

        if lower.startswith("create a new agent named"):
            return self._handle_create_agent(text)

        if "update the agent registry" in lower:
            return self._handle_registry_update(text)

        if lower == "mammoth engine list":
            return self._handle_engine_list()

        if lower == "mammoth agent list":
            return self._handle_agent_list()

        if lower == "mammoth help":
            return self._handle_help()

        if lower == "mammoth version":
            return self._handle_version()

        if lower == "mammoth health":
            return self._handle_health()

        if lower == "mammoth status":
            return self._handle_status()

        return {
            "status": "intent",
            "agent": self.name,
            "prompt": prompt,
            "message": "CodingAgent received the prompt but no known coding pattern matched."
        }

    # =========================================================================
    # FILE WRITER
    # =========================================================================
    def _write_file(self, filepath: str, content: str):
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

    # =========================================================================
    # REGISTRY AUTO-APPEND (LEVEL 4 BUGFIX)
    # =========================================================================
    def _append_to_registry(self, agent_key: str, class_name: str, module_name: str):
        registry_path = "src/mammoth_os/agent_registry.py"

        load_agent_entry = (
            f"\n    if agent_name == \"{agent_key}\":\n"
            f"        from mammoth_os.agents.{module_name} import {class_name}\n"
            f"        return {class_name}(router)\n"
        )

        agents_entry = (
            f"\n    \"{agent_key}\": lambda prompt: load_agent(\"{agent_key}\", router).run(prompt),\n"
        )

        with open(registry_path, "r", encoding="utf-8") as f:
            registry = f.read()

        # Insert into load_agent()
        if "return CodingAgent(router)" in registry:
            registry = registry.replace(
                "return CodingAgent(router)",
                "return CodingAgent(router)" + load_agent_entry
            )

        # Insert into AGENTS dict
        if "\"coding\": lambda prompt:" in registry:
            registry = registry.replace(
                "\"coding\": lambda prompt:",
                "\"coding\": lambda prompt:" + agents_entry
            )

        with open(registry_path, "w", encoding="utf-8") as f:
            f.write(registry)

    # =========================================================================
    # AGENT CREATION
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

        # Write agent file
        self._write_file(agent_file_path, agent_file_content)

        # Append registry entries
        self._append_to_registry(agent_key, class_name, module_name)

        return {
            "status": "patch_applied",
            "agent": self.name,
            "prompt": prompt,
            "message": f"{class_name} created and registry updated."
        }

    # =========================================================================
    # REGISTRY UPDATE (LEVEL 2)
    # =========================================================================
    def _handle_registry_update(self, prompt: str) -> Dict[str, Any]:
        return {
            "status": "intent",
            "agent": self.name,
            "prompt": prompt,
            "message": "Registry update recognized. Level 4 auto-wiring is active."
        }

    # =========================================================================
    # CLI COMMANDS
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
            "message": "Commands: mammoth engine list, mammoth agent list, mammoth help, mammoth version, mammoth health, mammoth status."
        }

    def _handle_version(self):
        return {
            "status": "cli",
            "command": "mammoth version",
            "version": "0.1.0-dev",
            "message": "Mammoth OS development build."
        }

    def _handle_health(self):
        return {
            "status": "cli",
            "command": "mammoth health",
            "health": "ok",
            "message": "Health checks are stubbed. Core CLI and CodingAgent are responsive."
        }

    def _handle_status(self):
        return {
            "status": "cli",
            "command": "mammoth status",
            "components": {
                "cli": "ok",
                "coding_agent": "ok",
                "registry": "auto-wiring enabled",
                "autonomous_engine": "ok",
                "research_agent": "ok",
                "curriculum_agent": "ok",
                "schema_inspector_agent": "ok",
                "field_ops_agent": "ok"
            },
            "message": "Mammoth OS status report (Level 4 stub)."
        }
