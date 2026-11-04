"""Bounded production migration preflight. Never outputs credential values."""

import json
import os
from pathlib import Path
import subprocess
import sys


def inspect(app_path):
    root = Path(app_path).resolve(strict=True)
    report = {"contract": "mammoth.storage-preflight.v1", "writes_performed": False}
    pid = subprocess.run(
        ["systemctl", "show", "mammothos", "--property=MainPID", "--value"],
        check=True, capture_output=True, text=True, timeout=15,
    ).stdout.strip()
    if not pid.isdigit() or int(pid) < 1:
        raise RuntimeError("The live backend service was not found.")
    process = Path("/proc") / pid
    if process.stat().st_uid != os.geteuid() or (process / "cwd").resolve() != root:
        raise RuntimeError("Preflight must use the live service UID and checkout.")
    report["deployed_commit"] = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"], check=True, capture_output=True, text=True, timeout=15,
    ).stdout.strip()
    environment = dict(item.decode().split("=", 1) for item in (process / "environ").read_bytes().split(b"\0") if b"=" in item)
    code = """
import json,os,sys,importlib.util
from dotenv import dotenv_values
config={**dotenv_values(sys.argv[1]),**os.environ}
keys=['MAMMOTH_POSTGRES_DSN','SUPABASE_DB_URL','DATABASE_URL','SUPABASE_SERVICE_ROLE_KEY','SUPABASE_KEY','SUPABASE_URL']
print(json.dumps({
 'credential_presence':{key:bool(config.get(key)) for key in keys},
 'psycopg_installed':importlib.util.find_spec('psycopg') is not None,
 'configured_backends':{key:config.get(key,'local') if config.get(key,'local') in ['local','postgres','supabase'] else 'invalid' for key in [
  'MAMMOTH_RUN_BACKEND','MAMMOTH_STATE_BACKEND','MAMMOTH_USAGE_BACKEND','MAMMOTH_PRIVATE_USAGE_BACKEND',
  'MAMMOTH_LEARNING_CONTROLS_BACKEND']},
 'replica_count':config.get('MAMMOTH_REPLICA_COUNT','1') if config.get('MAMMOTH_REPLICA_COUNT','1').isdigit() else 'invalid',
}))
"""
    observed = subprocess.run(
        [str(process / "exe"), "-c", code, str(root / ".env")], env=environment,
        check=True, capture_output=True, text=True, timeout=15,
    )
    report.update(json.loads(observed.stdout))
    report["migration_access"] = "database_connection_configured" if any(
        report["credential_presence"][key] for key in ("MAMMOTH_POSTGRES_DSN", "SUPABASE_DB_URL", "DATABASE_URL")
    ) else "database_admin_connection_required"
    return report


if __name__ == "__main__":
    print(json.dumps(inspect(sys.argv[1]), indent=2))
