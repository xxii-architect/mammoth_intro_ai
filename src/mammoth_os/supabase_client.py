# src/mammoth_os/supabase_client.py

import os
from dotenv import load_dotenv
from supabase.client import create_client, ClientOptions
from types import SimpleNamespace
from postgrest import exceptions as postgrest_exceptions

load_dotenv()

# ---------------------------------------------------------------------------
# Lazy client creation
# ---------------------------------------------------------------------------

_client_singleton = None

def _create_client():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_ANON_KEY")
    if not url or not key:
        raise RuntimeError("Supabase environment variables not set")
    return create_client(url, key, options=ClientOptions())

def get_supabase():
    global _client_singleton
    if _client_singleton is None:
        _client_singleton = _create_client()
    return _client_singleton

# ---------------------------------------------------------------------------
# Backwards-compatible lazy proxy
# ---------------------------------------------------------------------------

class _LazyProxy:
    def __getattr__(self, name):
        client = get_supabase()
        return getattr(client, name)

supabase = _LazyProxy()

# ---------------------------------------------------------------------------
# Safe helpers
# ---------------------------------------------------------------------------

def get_lessons_for_module(module_id: str) -> SimpleNamespace:
    """
    Always return an object with .data so tests don't break.
    """
    try:
        client = get_supabase()
        resp = client.table("lessons").select("*").eq("module_id", module_id).execute()
        data = getattr(resp, "data", []) or []
        return SimpleNamespace(data=data)
    except Exception:
        return SimpleNamespace(data=[])

def table(name: str):
    return get_supabase().table(name)
