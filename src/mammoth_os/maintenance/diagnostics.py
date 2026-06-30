from datetime import datetime
from typing import Dict, Any
from mammoth_os.supabase_client import supabase
from mammoth_os.leaderboard_engine import get_top_leaderboard
from mammoth_os.streak_engine import update_streak


def run_system_check(test_user: str) -> Dict[str, Any]:
    report: Dict[str, Any] = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "supabase_ok": False,
        "xp_engine_ok": False,
        "streak_engine_ok": False,
        "leaderboard_ok": False,
        "errors": [],
    }

    # 1) Supabase connectivity
    try:
        resp = (
            supabase
            .schema("atlas")
            .from_("community_stats")
            .select("count", count="exact") # type: ignore
            .limit(1)
            .execute()
        )
        report["supabase_ok"] = True
        report["community_stats_count"] = resp.count
    except Exception as e:
        report["errors"].append(f"Supabase connectivity failed: {e}")
        return report

    # 2) XP engine (simple sanity: leaderboard reachable)
    try:
        top = get_top_leaderboard(limit=1)
        report["xp_engine_ok"] = True
        report["leaderboard_sample"] = top
    except Exception as e:
        report["errors"].append(f"XP/leaderboard failed: {e}")

    # 3) Streak engine (non-destructive test)
    try:
        _ = update_streak(test_user)
        report["streak_engine_ok"] = True
    except Exception as e:
        report["errors"].append(f"Streak engine failed: {e}")

    # 4) Leaderboard view
    try:
        top = get_top_leaderboard(limit=5)
        report["leaderboard_ok"] = True
        report["leaderboard_top"] = top
    except Exception as e:
        report["errors"].append(f"Leaderboard view failed: {e}")

    return report
