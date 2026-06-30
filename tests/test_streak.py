# tests/test_streak.py

from mammoth_os.streak_engine import update_streak, get_user_streak

TEST_USER = "d6c16bc9-fc2a-4efd-8d9e-a95fb6baa448"

print("Updating streak for:", TEST_USER)
new_streak = update_streak(TEST_USER)
print("New streak value:", new_streak)

print("Fetching streak record...")
record = get_user_streak(TEST_USER)
print("Record:", record)
