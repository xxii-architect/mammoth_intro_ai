import os
from dotenv import load_dotenv
from supabase_functions import create_client

load_dotenv()

print(os.getenv("OPENAI_API_KEY"))
print(os.getenv("SUPABASE_URL"))
print(os.getenv("SUPABASE_ANON_KEY"))
print("Supabase import works!")

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_ANON_KEY"))