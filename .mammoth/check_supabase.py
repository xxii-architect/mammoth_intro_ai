"""
Supabase live wiring smoke test.
Run AFTER applying .mammoth/supabase_schema.sql in the Supabase SQL Editor.

Usage:
    set SUPABASE_URL=https://...
    set SUPABASE_SERVICE_ROLE_KEY=...
    python .mammoth/check_supabase.py
"""
import os, sys, asyncio

url = os.environ.get("SUPABASE_URL") or os.environ.get("SUPABASE_URL")
key = (os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
       or os.environ.get("SUPABASE_KEY")
       or os.environ.get("SUPABASE_ANON_KEY"))

if not url or not key:
    print("SKIP: SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not set")
    sys.exit(0)

try:
    from supabase import create_client
except ImportError:
    print("SKIP: supabase-py not installed (pip install supabase)")
    sys.exit(0)

sb = create_client(url, key)

# 1. Verify tables exist
for table in ("sessions", "exercises", "progress"):
    try:
        r = sb.table(table).select("id").limit(1).execute()
        print(f"OK  table '{table}' accessible (rows returned: {len(r.data)})")
    except Exception as e:
        print(f"FAIL table '{table}': {e}")
        sys.exit(1)

# 2. Insert a test progress row and clean it up
try:
    ins = sb.table("progress").insert({
        "user_id": "_smoke_test",
        "curriculum_id": "test",
        "lesson_id": "test",
        "passed": True,
        "stdout": "OK",
        "stderr": "",
        "duration_ms": 1,
        "error_fingerprint": "passed",
        "attempt_index": 0,
    }).execute()
    row_id = ins.data[0]["id"]
    print(f"OK  insert progress row: {row_id}")
    sb.table("progress").delete().eq("id", row_id).execute()
    print("OK  cleanup smoke row")
except Exception as e:
    print(f"FAIL insert/delete: {e}")
    sys.exit(1)

# 3. Wiring via TutorAgent
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
try:
    from mammoth_os.agents.tutor_agent import TutorAgent
    agent = TutorAgent()
    if agent.supabase is None:
        print("WARN TutorAgent.supabase is None — check env vars")
    else:
        print("OK  TutorAgent.supabase initialised")
except Exception as e:
    print(f"FAIL TutorAgent init: {e}")
    sys.exit(1)

print("\nAll Supabase checks passed.")
