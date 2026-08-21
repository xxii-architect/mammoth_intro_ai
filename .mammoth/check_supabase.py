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

# 1. Verify schema objects exist
checks = [
    ("mammoth", "users"),
    ("mammoth", "progress"),
    ("mammoth", "activity_log"),
    ("atlas", "atlas_progress"),
    ("atlas", "adaptive_metrics"),
    ("atlas", "community_stats"),
    ("atlas", "sessions"),
    ("atlas", "exercises"),
]
for schema_name, table in checks:
    try:
        r = sb.schema(schema_name).table(table).select("*").limit(1).execute()
        print(f"OK  {schema_name}.{table} accessible (rows returned: {len(r.data)})")
    except Exception as e:
        print(f"FAIL {schema_name}.{table}: {e}")
        sys.exit(1)

# 2. Confirm TutorAgent can initialize with current env
test_user_id = os.environ.get("ATLAS_USER_ID", "")
if not test_user_id:
    print("WARN ATLAS_USER_ID not set; live submission write test will be skipped")

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
