# llama_service.py
# Connects Mammoth OS to local Ollama runtime

import requests
import json

OLLAMA_ENDPOINT = "http://localhost:11434/api/generate"
MODEL = "llama3.1:8b"

def query_llama(prompt: str) -> str:
    """Send a prompt to local Ollama and return the generated text."""
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False
    }
    try:
        response = requests.post(OLLAMA_ENDPOINT, json=payload, timeout=120)
        response.raise_for_status()
        data = response.json()
        return data.get("response", "").strip()
    except Exception as e:
        return f"⚠️ Llama runtime error: {e}"

# Alias for Mammoth OS agent registry
def run_llama(prompt: str) -> str:
    return query_llama(prompt)
