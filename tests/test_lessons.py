import pytest  # type: ignore

pytestmark = pytest.mark.xfail(reason="Module not yet implemented", strict=False)

import os
print("CWD:", os.getcwd())

from mammoth_os.supabase_client import get_lessons_for_module  # type: ignore

module_id = "ccdcc517-99c7-4af7-ba92-c9e59635b554"

lessons = get_lessons_for_module(module_id)

print("MODULE ID:", module_id)
print("RAW RESPONSE:", lessons)

# Correct: lessons is a list, not an object with .data
print("DATA:", lessons)
