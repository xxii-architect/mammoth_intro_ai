# mammoth_os/agents/coding_agent.py

from typing import Dict, Any
from .base_agent import BaseAgent


class CodingAgent(BaseAgent):
    """
    CodingAgent
    -----------
    Parses natural-language coding instructions and generates unified diff patches
    to modify the Mammoth OS codebase (add agents, update registry, etc.).
    """

    name = "CodingAgent"

    def __init__(self, router):
        super().__init__(router)

    def run(self, prompt: str) -> Dict[str, Any]:
        """
        Main entry point for CodingAgent.
        Detects intent and returns either a patch or a simple intent description.
        """
        prompt_stripped = prompt.strip()

        # Simple pattern: "Create a new agent named X inside src/mammoth_os/agents."
        if prompt_stripped.lower().startswith("create a new agent named"):
            return self._handle_create_agent(prompt_stripped)

        # Fallback: just echo intent
        return {
            "status": "intent",
            "agent": self.name,
            "prompt": prompt,
            "message": "CodingAgent received the prompt but no known coding pattern matched."
        }

    def _handle_create_agent(self, prompt: str) -> Dict[str, Any]:
        """
        Parse 'Create a new agent named X...' and generate a unified diff patch
        for a new agent file and registry wiring.
        """
        # Very simple name extraction: assume "Create a new agent named X"
        parts = prompt.split("named", 1)
        if len(parts) < 2:
            agent_name = "NewAgent"
        else:
            agent_name = parts[1].strip().split()[0]

        class_name = f"{agent_name}Agent"
        module_name = f"{agent_name.lower()}_agent"

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

        # Minimal unified diff patch: new file + registry wiring
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

+    if agent_name == "{agent_name.lower()}":
+        from mammoth_os.agents.{module_name} import {class_name}
+        return {class_name}(router)
+
@@ -80,6 +86,7 @@ AGENTS = {{
     "coding": lambda prompt: load_agent("coding", router).run(prompt),
     "research": lambda prompt: load_agent("research", router).run(prompt),
     "curriculum": lambda prompt: load_agent("curriculum", router).run(prompt),
+    "{agent_name.lower()}": lambda prompt: load_agent("{agent_name.lower()}", router).run(prompt),
 }}
"""

        return {
            "status": "patch",
            "agent": self.name,
            "prompt": prompt,
            "message": f"Generated unified diff patch to create {class_name} and wire it into the registry.",
            "patch": patch,
        }
