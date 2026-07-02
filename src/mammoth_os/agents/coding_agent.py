from typing import Dict, Any
from .base_agent import BaseAgent


class CodingAgent(BaseAgent):
    """
    CodingAgent
    -----------
    Parses natural-language coding instructions and generates unified diff patches
    or structured responses for Mammoth OS (agents, registry, CLI commands).
    """

    name = "CodingAgent"

    def __init__(self, router):
        super().__init__(router)

    def run(self, prompt: str) -> Dict[str, Any]:
        """
        Main entry point for CodingAgent.
        Detects intent and returns either a patch or a structured response.
        """
        text = prompt.strip()
        lower = text.lower()

        # --- Agent creation pattern ---
        if lower.startswith("create a new agent named"):
            return self._handle_create_agent(text)

        # --- Registry update pattern ---
        if "update the agent registry" in lower:
            return self._handle_registry_update(text)

        # --- CLI command: engine list ---
        if lower == "mammoth engine list":
            return self._handle_engine_list()

        # --- CLI command: agent list ---
        if lower == "mammoth agent list":
            return self._handle_agent_list()

        # --- CLI command: help ---
        if lower == "mammoth help":
            return self._handle_help()

        # --- CLI command: version ---
        if lower == "mammoth version":
            return self._handle_version()

        # Fallback
        return {
            "status": "intent",
            "agent": self.name,
            "prompt": prompt,
            "message": "CodingAgent received the prompt but no known coding pattern matched."
        }

    # -------------------------------------------------------------------------
    # Agent creation
    # -------------------------------------------------------------------------
    def _handle_create_agent(self, prompt: str) -> Dict[str, Any]:
        parts = prompt.split("named", 1)
        if len(parts) < 2:
            agent_name = "NewAgent"
        else:
            agent_name = parts[1].strip().split()[0]

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
diff --git a/src/mammoth_os/agent_registry.py b/src/mammoth_os/agent_registry.py
--- a/src/mammoth_os/agent_registry.py
+++ b/src/mammoth_os/agent_registry.py
@@ -45,6 +45,12 @@ def load_agent(agent_name: str, router=None):
         from mammoth_os.agents.coding_agent import CodingAgent
         return CodingAgent(router)

+    if agent_name == "{agent_key}":
+        from mammoth_os.agents.{module_name} import {class_name}
+        return {class_name}(router)
+
@@ -80,6 +86,7 @@ AGENTS = {{
     "coding": lambda prompt: load_agent("coding", router).run(prompt),
     "research": lambda prompt: load_agent("research", router).run(prompt),
     "curriculum": lambda prompt: load_agent("curriculum", router).run(prompt),
+    "{agent_key}": lambda prompt: load_agent("{agent_key}", router).run(prompt),
 }}
"""

        return {
            "status": "patch",
            "agent": self.name,
            "prompt": prompt,
            "message": f"Generated unified diff patch to create {class_name} and wire it into the registry.",
            "patch": patch,
        }

    # -------------------------------------------------------------------------
    # Registry update (simple echo for now)
    # -------------------------------------------------------------------------
    def _handle_registry_update(self, prompt: str) -> Dict[str, Any]:
        return {
            "status": "intent",
            "agent": self.name,
            "prompt": prompt,
            "message": "Registry update requested. For now, use the agent-creation pattern to wire new agents."
        }

    # -------------------------------------------------------------------------
    # CLI commands
    # -------------------------------------------------------------------------
    def _handle_engine_list(self) -> Dict[str, Any]:
        engines = ["coding", "research", "curriculum", "schema_inspector", "field_ops"]
        return {
            "status": "cli",
            "agent": self.name,
            "command": "mammoth engine list",
            "engines": engines,
            "message": "Available inference engines."
        }

    def _handle_agent_list(self) -> Dict[str, Any]:
        agents = [
            "CodingAgent",
            "ResearchAgent",
            "CurriculumAgent",
            "SchemaInspectorAgent",
            "FieldOpsAgent",
            "HouseKeepingAgentAgent",
        ]
        return {
            "status": "cli",
            "agent": self.name,
            "command": "mammoth agent list",
            "agents": agents,
            "message": "Registered agents (static list for now)."
        }

    def _handle_help(self) -> Dict[str, Any]:
        return {
            "status": "cli",
            "agent": self.name,
            "command": "mammoth help",
            "message": "Commands: mammoth engine list, mammoth agent list, mammoth help, mammoth version. Use 'set engine: coding' then natural-language instructions like 'Create a new agent named X...'."
        }

    def _handle_version(self) -> Dict[str, Any]:
        return {
            "status": "cli",
            "agent": self.name,
            "command": "mammoth version",
            "version": "0.1.0-dev",
            "message": "Mammoth OS development build."
        }
