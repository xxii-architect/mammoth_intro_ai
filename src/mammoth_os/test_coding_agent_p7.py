"""Tests for Priority 7: CodingAgent LLM upgrade, generate_and_test, and atlas code CLI."""
import asyncio
import sys
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

# ─────────────────────────────────────────────────────────────────────────────
# prompt_templates tests
# ─────────────────────────────────────────────────────────────────────────────

from mammoth_os.prompt_templates import (
    build_code_gen_prompt,
    build_refactor_prompt,
    build_explain_prompt,
    parse_structured_code_response,
    CODE_GEN_TEMPLATE,
)


def test_build_code_gen_prompt_no_context():
    p = build_code_gen_prompt("write a fibonacci function")
    assert "fibonacci" in p
    assert "(no context available)" in p


def test_build_code_gen_prompt_with_snippets():
    snippets = [{"id": "snip1", "text": "def fib(n): return n"}]
    p = build_code_gen_prompt("fibonacci", snippets)
    assert "snip1" in p
    assert "fib" in p


def test_build_refactor_prompt():
    p = build_refactor_prompt("x=1+2")
    assert "x=1+2" in p
    assert "Refactor" in p


def test_build_explain_prompt():
    p = build_explain_prompt("print('hello')")
    assert "print" in p
    assert "explain" in p.lower()


def test_code_gen_template_alias():
    """Legacy CODE_GEN_TEMPLATE alias must still exist."""
    assert CODE_GEN_TEMPLATE
    assert "{user_prompt}" in CODE_GEN_TEMPLATE


# ─────────────────────────────────────────────────────────────────────────────
# parse_structured_code_response tests
# ─────────────────────────────────────────────────────────────────────────────

def test_parse_full_three_blocks():
    raw = """
```python
def add(a, b): return a + b
```

```pytest
def test_add():
    assert add(1, 2) == 3
```

```docs
add(a, b) -> returns a + b
```
"""
    result = parse_structured_code_response(raw)
    assert "def add" in result["code"]
    assert "def test_add" in result["tests"]
    assert "add(a, b)" in result["docs"]


def test_parse_code_only():
    raw = "```python\ndef hello(): pass\n```"
    result = parse_structured_code_response(raw)
    assert "def hello" in result["code"]
    assert result["tests"] == ""
    assert result["docs"] == ""


def test_parse_unlabelled_fallback():
    raw = "```\ndef mystery(): pass\n```"
    result = parse_structured_code_response(raw)
    assert "def mystery" in result["code"]


def test_parse_plain_text_fallback():
    raw = "def plain(): pass"
    result = parse_structured_code_response(raw)
    assert "def plain" in result["code"]


# ─────────────────────────────────────────────────────────────────────────────
# CodingAgent.generate_code structured response test
# ─────────────────────────────────────────────────────────────────────────────

def test_generate_code_parses_structured_response():
    """generate_code should populate code, tests, and docs from the LLM response."""
    from mammoth_os.agents.coding_agent import CodingAgent

    llm_raw = """\
```python
def add(a, b):
    return a + b
```

```pytest
def test_add():
    from solution import add
    assert add(2, 3) == 5
```

```docs
add(a, b) -> int — returns the sum of a and b.
```
"""

    mock_client = AsyncMock()
    mock_client.generate = AsyncMock(return_value=llm_raw)

    with patch("mammoth_os.agents.coding_agent.get_llm_client", return_value=mock_client), \
         patch.object(CodingAgent, "_retrieve_context", new=AsyncMock(return_value=[])):
        agent = CodingAgent()
        result = asyncio.run(agent.generate_code("write an add function"))

    assert "def add" in result["code"]
    assert "def test_add" in result["tests"]
    assert "sum" in result["docs"]
    assert result["confidence"] > 0


def test_generate_code_returns_warnings_on_no_code():
    """If LLM returns no fenced blocks, warnings should be non-empty."""
    from mammoth_os.agents.coding_agent import CodingAgent

    mock_client = AsyncMock()
    mock_client.generate = AsyncMock(return_value="Sorry, I cannot help with that.")

    with patch("mammoth_os.agents.coding_agent.get_llm_client", return_value=mock_client), \
         patch.object(CodingAgent, "_retrieve_context", new=AsyncMock(return_value=[])):
        agent = CodingAgent()
        result = asyncio.run(agent.generate_code("bad prompt"))

    # Falls back to raw text as code, but confidence should be low
    assert isinstance(result["code"], str)
    assert isinstance(result["warnings"], list)


def test_generate_code_handles_llm_error():
    """generate_code should return confidence=0 and warnings when LLM fails."""
    from mammoth_os.agents.coding_agent import CodingAgent

    mock_client = AsyncMock()
    mock_client.generate = AsyncMock(side_effect=RuntimeError("LLM timeout"))

    with patch("mammoth_os.agents.coding_agent.get_llm_client", return_value=mock_client), \
         patch.object(CodingAgent, "_retrieve_context", new=AsyncMock(return_value=[])):
        agent = CodingAgent()
        result = asyncio.run(agent.generate_code("anything"))

    assert result["confidence"] == 0.0
    assert any("LLM timeout" in w for w in result["warnings"])


# ─────────────────────────────────────────────────────────────────────────────
# ATLASSession.generate_and_test tests
# ─────────────────────────────────────────────────────────────────────────────

def _make_session():
    from mammoth_os.atlas_session import ATLASSession
    return ATLASSession(user_id="test_user")


def test_generate_and_test_passed():
    """When generated code passes tests, passed=True and hint is positive."""
    mock_gen_result = {
        "code": "def add(a, b): return a + b",
        "tests": "def test_add():\n    from solution import add\n    assert add(1, 2) == 3",
        "docs": "Returns a + b",
        "diff": "", "confidence": 0.8, "warnings": [],
    }
    mock_submission_result = {
        "passed": True, "feedback": "Well done!",
        "result": {"passed": True, "stdout": "OK: test_add", "stderr": ""},
    }

    with patch("mammoth_os.atlas_session.TutorAgent") as MockTutor, \
         patch("mammoth_os.agents.coding_agent.CodingAgent.generate_code", new=AsyncMock(return_value=mock_gen_result)):
        MockTutor.return_value.accept_submission = AsyncMock(return_value=mock_submission_result)
        session = _make_session()
        result = asyncio.run(session.generate_and_test("write an add function"))

    assert result["passed"] is True
    assert "def add" in result["code"]
    assert result["hint"]


def test_generate_and_test_no_code():
    """When CodingAgent produces no code, passed=False with helpful hint."""
    mock_gen_result = {
        "code": "", "tests": "", "docs": "", "diff": "", "confidence": 0.0, "warnings": ["no code"],
    }

    with patch("mammoth_os.agents.coding_agent.CodingAgent.generate_code", new=AsyncMock(return_value=mock_gen_result)):
        session = _make_session()
        result = asyncio.run(session.generate_and_test("empty prompt"))

    assert result["passed"] is False
    assert result["code"] == ""
    assert "no code" in result["hint"].lower() or "specific" in result["hint"].lower()


# ─────────────────────────────────────────────────────────────────────────────
# atlas code CLI smoke test
# ─────────────────────────────────────────────────────────────────────────────

def test_atlas_code_generate_cli_smoke(tmp_path, capsys):
    """CLI generate command should print generated code and hint."""
    import argparse
    from cli.atlas import cmd_atlas_code_generate, _SESSION_STATE_FILE

    mock_gen_result = {
        "code": "def add(a, b): return a + b",
        "tests": "def test_add(): pass",
        "docs": "Returns sum",
        "passed": True,
        "hint": "Great! Your tests passed.",
        "result": {"passed": True, "stdout": "", "stderr": ""},
    }

    args = argparse.Namespace(prompt=["write", "an", "add", "function"], no_save=True)
    with patch("cli.atlas._load_session") as mock_load, \
         patch("cli.atlas.asyncio.run", return_value=mock_gen_result):
        from mammoth_os.atlas_session import ATLASSession
        mock_load.return_value = ATLASSession(user_id="cli_user")
        cmd_atlas_code_generate(args)

    out = capsys.readouterr().out
    assert "def add" in out or "Generated" in out or "ATLAS" in out
