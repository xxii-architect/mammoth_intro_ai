# main.py
# Python 3.11+ required

import os
from dotenv import load_dotenv
from openai import OpenAI
from supabase import create_client, Client  


load_dotenv()
# 1. Load API key from environment variable
#    Never hardcode secrets.
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_ANON_KEY")
supabase = create_client(url, key) # type: ignore

# 2. Simple inference call
response = client.chat.completions.create(
    model="gpt-4o-mini",  # [VERIFY] Replace with available model in your environment
    messages=[
        {"role": "user", "content": "Explain tokens in one sentence."}
    ]
)

print(response.choices[0].message.content)
# 3. Streaming response
print("Streaming response:")
for chunk in client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "user", "content": "Explain tokens in one sentence."}
    ],
    stream=True
):
    print(chunk.choices[0].delta.content or "")