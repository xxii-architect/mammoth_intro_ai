import re
import json
from typing import Dict, Any


def extract_code_and_files(text: str) -> Dict[str, Any]:
    """Parse LLM text for code blocks and structured outputs.

    Returns a dict with optional keys:
    - 'code': concatenated code from first language block (string)
    - 'files': dict of filename -> content if LLM returned JSON with a 'files' key
    - 'all_code_blocks': list of code block strings
    """
    if not text:
        return {"code": "", "all_code_blocks": []}

    # First, try to detect JSON payload with files
    try:
        # Find a JSON blob in the text
        m = re.search(r"\{[\s\S]*\}", text)
        if m:
            maybe_json = m.group(0)
            parsed = json.loads(maybe_json)
            if isinstance(parsed, dict) and "files" in parsed and isinstance(parsed["files"], dict):
                return {"files": parsed["files"], "all_code_blocks": []}
    except Exception:
        pass

    # Extract fenced code blocks
    blocks = re.findall(r"```(?:[\w+-]*)\n([\s\S]*?)```", text)
    blocks = [b.strip() for b in blocks]

    result = {"all_code_blocks": blocks}
    if blocks:
        # Pick the first code block as primary code
        result["code"] = blocks[0]
    else:
        # No fenced blocks; return the whole text as code fallback
        result["code"] = text.strip()

    return result
