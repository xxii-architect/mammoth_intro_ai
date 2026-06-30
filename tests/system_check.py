from datetime import datetime
from mammoth_os.supabase_client import supabase  # type: ignore
from mammoth_os.leaderboard_engine import add_xp, get_leaderboard_record, get_top_leaderboard  # type: ignore
from mammoth_os.streak_engine import update_streak  # type: ignore

TEST_USER = "d6c16bc9-fc2a-4efd-8d9e-a95fb6baa448"


def section(title: str):
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


def success(msg: str):
    print(f"✅ {msg}")


def failure(msg: str):
    print(f"❌ {msg}")


def main():
    print("🐘 MAMMOTH OS SYSTEM CHECK")
    print(f"Timestamp: {datetime.utcnow().isoformat()}Z")

    # 1) Supabase connectivity
    section("1) Supabase Connectivity")
    try:
        resp = (
            supabase
            .from_("atlas.community_stats")
            .select("count", count="exact") # type: ignore
            .limit(1)
            .execute()
        )
        success("Supabase reachable")
        print("   community_stats rows:", resp.count)
    except Exception as e:
        failure(f"Supabase connectivity FAILED: {e}")
        return

    # 2) Atomic XP engine
    section("2) Atomic XP Engine")
    try:
        before = get_leaderboard_record(TEST_USER)
        before_xp = before.get("xp", 0) if before else 0
        print(f"   XP before: {before_xp}")

        new_xp = add_xp(TEST_USER, 10)
        success(f"XP increment succeeded, new XP: {new_xp}")

        after = get_leaderboard_record(TEST_USER)
        print("   Leaderboard record after:", after)
    except Exception as e:
        failure(f"XP engine FAILED: {e}")

    # 3) Streak engine
    section("3) Streak Engine")
    try:
        new_streak = update_streak(TEST_USER)
        success(f"Streak updated, new streak: {new_streak}")
    except Exception as e:
        failure(f"Streak engine FAILED: {e}")

    # 4) Leaderboard view
    section("4) Leaderboard View")
    try:
        top = get_top_leaderboard(limit=5)
        success(f"Leaderboard query succeeded, top {len(top)} rows:")
        for row in top:
            print("   -", row)
    except Exception as e:
        failure(f"Leaderboard view FAILED: {e}")

    print("\n🐘 System check complete.")


if __name__ == "__main__":
    main()
