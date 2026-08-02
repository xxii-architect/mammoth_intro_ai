from typing import List, Dict

# ──────────────────────────────────────────────────────────────
# MammothOS-context code generation prompt
# ──────────────────────────────────────────────────────────────

_CODE_GEN_TEMPLATE = """\
You are the CodingAgent inside MammothOS — an expert Python software engineer.
Produce clean, production-ready code for the following request.

User request:
{user_prompt}

Context snippets (most relevant first, may be empty):
{context}

IMPORTANT: Name your main function exactly `solution` so the test runner can import it.

Return exactly three fenced blocks in this order (no other text):

```python
# implementation here — main function MUST be named `solution`
def solution(*args, **kwargs):
    ...
```

```pytest
# pytest test functions — import solution from solution module
from solution import solution

def test_example():
    ...
```

```docs
# short docstring / usage example
```
"""

_REFACTOR_TEMPLATE = """\
You are the CodingAgent inside MammothOS.
Refactor the Python code below for readability and simplicity. Preserve all behaviour.

Original code:
```python
{original}
```

Return ONLY the refactored code in a single ```python block.
Add brief inline comments where the logic is non-obvious.
Do NOT change function signatures or return types.
"""

_EXPLAIN_TEMPLATE = """\
You are the CodingAgent inside MammothOS, acting as a teaching assistant.
Explain the Python code below to a learner in 3-5 plain-English sentences.
Highlight what it does, any gotchas, and one improvement idea.
Return plain text only (no fenced blocks).

Code:
```python
{code}
```
"""


def build_code_gen_prompt(user_prompt: str, context_snippets: List[Dict] = None) -> str:
    """Build a structured code generation prompt with optional RAG context."""
    if not context_snippets:
        context_text = "(no context available)"
    else:
        lines = []
        for i, s in enumerate(context_snippets[:5], start=1):
            title = s.get("metadata", {}).get("title") or s.get("id") or f"snippet-{i}"
            snippet = s.get("text") or s.get("content") or ""
            lines.append(f"[{i}] {title}: {snippet[:500].strip()}")
        context_text = "\n".join(lines)

    return _CODE_GEN_TEMPLATE.format(user_prompt=user_prompt, context=context_text)


def build_refactor_prompt(original_code: str) -> str:
    """Build a prompt asking the LLM to refactor code while preserving behaviour."""
    return _REFACTOR_TEMPLATE.format(original=original_code)


def build_explain_prompt(code: str) -> str:
    """Build a prompt asking the LLM to explain code to a learner."""
    return _EXPLAIN_TEMPLATE.format(code=code)


def parse_structured_code_response(raw: str) -> Dict:
    """Parse the three-block LLM response into code / tests / docs.

    Returns a dict with keys: code, tests, docs.
    """
    import re

    result = {"code": "", "tests": "", "docs": ""}

    patterns = {
        "code":  r"```python\s*\n([\s\S]*?)```",
        "tests": r"```pytest\s*\n([\s\S]*?)```",
        "docs":  r"```docs\s*\n([\s\S]*?)```",
    }
    for key, pat in patterns.items():
        m = re.search(pat, raw)
        if m:
            result[key] = m.group(1).strip()

    if not result["code"]:
        m = re.search(r"```[\w+-]*\s*\n([\s\S]*?)```", raw)
        if m:
            result["code"] = m.group(1).strip()

    if not result["code"]:
        result["code"] = raw.strip()

    return result


# Legacy alias kept so existing imports do not break
CODE_GEN_TEMPLATE = _CODE_GEN_TEMPLATE
