# tests/test_leaderboard.py

import supabase

from mammoth_os.leaderboard_engine import ( # type: ignore
    add_xp,
    get_leaderboard_record,
    sync_streak_and_xp,
    get_top_leaderboard,
)

TEST_USER = "d6c16bc9-fc2a-4efd-8d9e-a95fb6baa448"

print("\n=== 🧪 LEADERBOARD ENGINE TEST ===\n")

# 1. Add XP
print("Adding XP to:", TEST_USER)
new_xp = add_xp(TEST_USER, 50)
print("New XP:", new_xp)

# 2. Fetch record
print("\nFetching leaderboard record...")
record = get_leaderboard_record(TEST_USER)
print("Record:", record)

# 3. Sync streak + XP
print("\nSyncing streak + XP...")
sync_data = sync_streak_and_xp(TEST_USER)
print("Sync Result:", sync_data)

# 4. Fetch top leaderboard
print("\nFetching top leaderboard...")
top = get_top_leaderboard(10)
print("Top 10 Leaderboard:")
for row in top:
    print(row)

print("\n=== TEST COMPLETE ===\n")


# import uuid
# from leaderboard_engine import add_xp, call_increment_user_xp
#
# TEST_USER_ID = str(uuid.uuid4())   # fresh UUID → guaranteed clean slate
#
# print("=" * 60)
# print(f"Test user: {TEST_USER_ID}")
# print("=" * 60)
#
# # 1. First award — INSERT branch (no prior row)
# r = add_xp(TEST_USER_ID, 75)
# print(f"[+75 XP]  xp={r['xp']:>5}  rank={r['rank']}")
# assert r["xp"] == 75  and r["rank"] == "Novice",      f"FAIL: {r}"
#
# # 2. Cross Pathfinder threshold (75 + 50 = 125)
# r = add_xp(TEST_USER_ID, 50)
# print(f"[+50 XP]  xp={r['xp']:>5}  rank={r['rank']}")
# assert r["xp"] == 125 and r["rank"] == "Pathfinder",  f"FAIL: {r}"
#
# # 3. Large jump — cross Survivor threshold (125 + 400 = 525)
# r = add_xp(TEST_USER_ID, 400)
# print(f"[+400 XP] xp={r['xp']:>5}  rank={r['rank']}")
# assert r["xp"] == 525 and r["rank"] == "Survivor",    f"FAIL: {r}"
#
# # 4. Direct RPC wrapper — zero-increment (idempotency check)
# r = call_increment_user_xp(TEST_USER_ID, 0)
# print(f"[+0 XP]   xp={r['xp']:>5}  rank={r['rank']}  (no-op check)")
# assert r["xp"] == 525 and r["rank"] == "Survivor",    f"FAIL: {r}"
#
# # 5. Penalty XP — should not drop below 0 (0 − 9999 = 0)
# tiny_user = str(uuid.uuid4())
# r = add_xp(tiny_user, -9999)
# print(f"[-9999 XP] xp={r['xp']:>5}  rank={r['rank']}  (clamp-to-zero)")
# assert r["xp"] == 0   and r["rank"] == "Novice",      f"FAIL: {r}"
#
# print("=" * 60)
# print("All assertions passed ✓")
# print("=" * 60)
