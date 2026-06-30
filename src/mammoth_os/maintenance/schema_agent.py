from typing import List, Dict, Any
from mammoth_os.supabase_client import supabase


def describe_schema(schema: str = "atlas") -> List[Dict[str, Any]]:
    """
    Returns a list of tables + basic info for the given schema.
    Non-destructive, read-only.
    """
    query = """
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema = %s
    ORDER BY table_name;
    """
    # Supabase doesn't expose raw SQL directly via Python client,
    # so for now we just query known tables/views.
    # Later we can move this to a SQL function.
    result = (
        supabase
        .schema(schema)
        .from_("community_stats")
        .select("*")
        .limit(1)
        .execute()
    )

    return [{"schema": schema, "table": "community_stats", "sample": result.data}]
