# src/mammoth_os/supabase_client.py

import os
from dotenv import load_dotenv
from supabase.client import create_client, ClientOptions
from typing import Any, Dict, List
from postgrest import exceptions as postgrest_exceptions

load_dotenv()

# --- Environment helpers ----------------------------------------------------
def _env_or_none(name: str) -> str | None:
    return os.getenv(name) or None

# --- Lazy client factory ---------------------------------------------------
_client_singleton = None

def _create_client():
    url = _env_or_none("SUPABASE_URL")
    key = _env_or_none("SUPABASE_ANON_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_ANON_KEY must be set to create a real Supabase client")
    return create_client(url, key, options=ClientOptions())

def get_supabase():
    """
    Return a Supabase client. Lazily creates and caches a client instance.
    Raises RuntimeError if environment variables are missing.
    """
    global _client_singleton
    if _client_singleton is None:
        _client_singleton = _create_client()
    return _client_singleton

# --- Backwards compatible lazy proxy ---------------------------------------
class _LazyProxy:
    """
    A tiny proxy that defers creation of the real client until first attribute access.
    This lets existing code that does `from mammoth_os.supabase_client import supabase`
    continue to work without immediate import-time RPCs or crashes.
    """
    def __getattr__(self, name):
        client = None
        try:
            client = get_supabase()
        except RuntimeError as e:
            # If no real client is configured, raise a clear error when used.
            raise RuntimeError("Supabase client not configured in this environment") from e
        return getattr(client, name)

# Export a lazy proxy named `supabase` for backward compatibility.
supabase = _LazyProxy()

# --- Safe helpers used by tests and code -----------------------------------
def get_lessons_for_module(module_id: str) -> List[Dict[str, Any]]:
    """
    Return lessons for a module. If no real client is configured or the table is missing,
    return an empty list instead of raising at import time.
    """
    try:
        client = get_supabase()
    except RuntimeError:
        return []

    try:
        resp = client.table("lessons").select("*").eq("module_id", module_id).execute()
        return getattr(resp, "data", []) or []
    except postgrest_exceptions.APIError:
        return []
    except Exception:
        return []

def table(name: str):
    """Convenience: return a table object from the real client (raises if not configured)."""
    return get_supabase().table(name)
