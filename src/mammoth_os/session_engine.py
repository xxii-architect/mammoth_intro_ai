# src/mammoth_os/session_engine.py

import logging
from typing import Any, Dict, Optional

from mammoth_os.supabase_client import get_supabase

logger = logging.getLogger(__name__)

def create_session(user_id: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Create a session record for a user. Returns a dict with status and session id.
    """
    supabase = get_supabase()
    try:
        payload = {"user_id": user_id, "metadata": metadata or {}}
        resp = supabase.schema("atlas").table("sessions").insert(payload).execute()
        data = getattr(resp, "data", None) or []
        return {"status": "ok", "session": data[0] if data else payload}
    except Exception as e:
        logger.error("Failed to create session for user %s", user_id, exc_info=True)
        raise

def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    supabase = get_supabase()
    try:
        resp = supabase.schema("atlas").table("sessions").select("*").eq("id", session_id).execute()
        rows = getattr(resp, "data", []) or []
        return rows[0] if rows else None
    except Exception as e:
        logger.error("Failed to read session %s", session_id, exc_info=True)
        raise

def delete_session(session_id: str) -> Dict[str, Any]:
    supabase = get_supabase()
    try:
        resp = supabase.schema("atlas").table("sessions").delete().eq("id", session_id).execute()
        return {"status": "ok"}
    except Exception as e:
        logger.error("Failed to delete session %s", session_id, exc_info=True)
        raise
