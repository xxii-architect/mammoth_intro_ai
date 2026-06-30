import os
from dotenv import load_dotenv
from supabase.client import create_client, ClientOptions

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL") or ""
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY") or ""

print(os.getenv("OPENAI_API_KEY"))
print(SUPABASE_URL)
print(SUPABASE_ANON_KEY)
print("Supabase import works!")

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_ANON_KEY,
    options=ClientOptions()
)
