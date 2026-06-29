# src/mammoth_os/supabase_client.py

import os
from dotenv import load_dotenv
from supabase.client import create_client, ClientOptions
from typing import Any, List, Dict, Optional

load_dotenv()

def _env_or_raise(name: str) -> str:
    val = os.getenv(name) or ""
    if not val:
        raise RuntimeError(f"Environment variable {name} is not set")
    return val

def get_supabase():
    """
    Lazily create and return a Supabase client.
    Raises RuntimeError if required environment variables are missing.
    """
    url = _env_or_raise("SUPABASE_URL")
    key = _env_or_raise("SUPABASE_ANON_KEY")
    # create_client is cheap enough here; if you prefer a singleton, wrap this in a module-level cache
    return create_client(url, key, options=ClientOptions())

def get_lessons_for_module(module_id: str) -> List[Dict[str, Any]]:
    """
    Convenience wrapper used by tests and application code.
    Returns a list of lesson records for the given module_id.
    """
    supabase = get_supabase()
    resp = supabase.table("lessons").select("*").eq("module_id", module_id).execute()
    # postgrest client returns .data on success; adapt if your client differs
    return getattr(resp, "data", []) or []

# Optional: small helper to obtain a table object for callers that prefer chaining
def table(name: str):
    return get_supabase().table(name)
