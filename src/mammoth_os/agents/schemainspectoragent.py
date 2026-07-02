# mammoth_os/agents/schema_inspector_agent.py

from typing import Dict, Any
from .base_agent import BaseAgent


class SchemaInspectorAgent(BaseAgent):
    """
    SchemaInspectorAgent
    --------------------
    Inspects database schemas, validates structure, checks for missing fields,
    and reports inconsistencies across Mammoth OS modules.
    """

    name = "SchemaInspectorAgent"

    def __init__(self, router):
        super().__init__(router)

    def run(self, prompt: str) -> Dict[str, Any]:
        """
        Main entry point for schema inspection tasks.
        """
        return {
            "status": "schema_intent",
            "agent": self.name,
            "prompt": prompt,
            "message": "SchemaInspectorAgent received the prompt. Ready to inspect schemas."
        }

    def inspect_table(self, table_name: str) -> Dict[str, Any]:
        """
        Inspect a Supabase table and return its structure.
        """
        try:
            result = (
                self.router.supabase
                .schema("atlas")
                .from_(table_name)
                .select("*")
                .limit(1)
                .execute()
            )

            if not result.data:
                return {
                    "status": "ok",
                    "agent": self.name,
                    "table": table_name,
                    "message": "Table exists but contains no rows.",
                    "columns": []
                }

            sample_row = result.data[0]
            columns = list(sample_row.keys())

            return {
                "status": "ok",
                "agent": self.name,
                "table": table_name,
                "columns": columns,
                "message": f"Schema inspection complete for table '{table_name}'."
            }

        except Exception as e:
            return {
                "status": "error",
                "agent": self.name,
                "table": table_name,
                "message": f"Schema inspection failed: {e}"
            }

    def execute_action(self, action_type: str, target: str, details: Dict[str, Any]):
        """
        Handle structured schema inspection actions.
        """
        if action_type == "inspect_table":
            return self.inspect_table(target)

        return {
            "status": "unknown_action",
            "agent": self.name,
            "action": action_type,
            "target": target,
            "details": details,
        }
