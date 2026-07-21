from typing import List, Dict

CODE_GEN_TEMPLATE = """
You are an expert software engineer. Given the user's request and the following context, produce a concise, runnable code snippet and any accompanying tests.

User request:
{user_prompt}

Context snippets (most relevant first):
{context}

Requirements:
- Return code in a fenced ```python``` block.
- Include at least one minimal test (pytest) in a fenced block labeled ```pytest```.
- Keep code focused and minimal.

Output:
- A python code block (```python) containing the implementation.
- A pytest block (```pytest) containing tests for the implementation.

If no context is available, still produce an implementation based on the prompt.
"""


def build_code_gen_prompt(user_prompt: str, context_snippets: List[Dict[str, str]] = None) -> str:
    if not context_snippets:
        context_text = "(no context available)"
    else:
        lines = []
        for i, s in enumerate(context_snippets[:5], start=1):
            title = s.get("metadata", {}).get("title") or s.get("id")
            snippet = s.get("text") or s.get("content") or ""
            lines.append(f"[{i}] {title}: {snippet[:500].strip()}")
        context_text = "\n".join(lines)

    return CODE_GEN_TEMPLATE.format(user_prompt=user_prompt, context=context_text)
