# mammoth_os/maintenance/schema_agent.py
# Mammoth OS — Schema inspection utilities

from __future__ import annotations
from typing import Dict, Any

from mammoth_os.supabase_client import get_supabase


def describe_schema(schema: str) -> Dict[str, Any]:
    """
    Describe a Supabase schema in a CLI-safe way.
    Returns a structured error when Supabase is not configured.
    """
    client = get_supabase()

    if client is None:
        # CLI / local mode fallback
        return {
            "error": "Supabase client not initialized",
            "schema": schema,
            "details": "No SUPABASE_URL / SUPABASE_KEY set. Running in local/CLI mode.",
        }

    try:
        # This assumes the Supabase client supports .schema(schema)
        schema_obj = client.schema(schema)  # type: ignore

        # Try to introspect tables if available
        info: Dict[str, Any] = {
            "schema": schema,
            "tables": [],
        }

        # Some clients expose a list of tables; if not, we just return the schema name
        if hasattr(schema_obj, "list_tables"):
            try:
                tables = schema_obj.list_tables()  # type: ignore
                info["tables"] = tables or []
            except Exception as exc:
                info["tables_error"] = str(exc)

        return info

    except Exception as exc:
        return {
            "error": str(exc),
            "schema": schema,
            "details": "Supabase schema introspection failed.",
        }
