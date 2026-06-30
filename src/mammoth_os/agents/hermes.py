# mammoth_os/agents/hermes.py
# Hermes agent for Mammoth OS (local Ollama runtime)

import requests

OLLAMA_ENDPOINT = "http://localhost:11434/api/generate"
MODEL = "hermes3:8b"  # adjust if you use nous-hermes or hermes3:70b

def ask(prompt: str) -> str:
    """Send a prompt to local Ollama and return the generated text (handles streaming)."""
    payload = {"model": MODEL, "prompt": prompt, "stream": True}
    try:
        with requests.post(OLLAMA_ENDPOINT, json=payload, stream=True, timeout=120) as response:
            response.raise_for_status()
            output = ""
            for line in response.iter_lines():
                if not line:
                    continue
                try:
                    data = line.decode("utf-8")
                    if '"response":' in data:
                        chunk = data.split('"response":"', 1)[1].split('"', 1)[0]
                        output += chunk
                except Exception:
                    continue
            return output.strip()
    except Exception as e:
        return f"⚠️ Hermes runtime error: {e}"
