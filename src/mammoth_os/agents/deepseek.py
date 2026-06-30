import requests
import json

def ask(prompt: str):
    # Start the request with streaming enabled
    with requests.post(
        "http://localhost:11434/api/generate",
        json={"model": "deepseek-coder", "prompt": prompt},
        stream=True,
    ) as res:
        output = ""
        for line in res.iter_lines():
            if not line:
                continue
            try:
                data = json.loads(line)
                output += data.get("response", "")
                if data.get("done"):
                    break
            except json.JSONDecodeError:
                # Skip malformed lines
                continue
        return output.strip()
