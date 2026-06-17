import supabase_client
import os
print("URL:", os.getenv("SUPABASE_URL"))
print("KEY:", os.getenv("SUPABASE_ANON_KEY")[:12], "...") # type: ignore


module_id = "ccdcc517-99c7-4af7-ba92-c9e59635b554"

lessons = supabase_client.get_lessons_for_module(module_id)

print("MODULE ID:", module_id)
print("RAW RESPONSE:", lessons)
print("DATA:", lessons.data)
