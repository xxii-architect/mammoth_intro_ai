# tests/test_streak.py
import pytest # type: ignore

pytestmark = pytest.mark.xfail(reason="Module not yet implemented", strict=False)


from mammoth_os.streak_engine import update_streak, get_user_streak
from mammoth_os.supabase_client import get_supabase

TEST_USER = "d6c16bc9-fc2a-4efd-8d9e-a95fb6baa448"

print("SUPABASE TYPE:", type(get_supabase()))


print("Updating streak for:", TEST_USER)
new_streak = update_streak(TEST_USER)
print("New streak value:", new_streak)

print("Fetching streak record...")
record = get_user_streak(TEST_USER)
print("Record:", record)
