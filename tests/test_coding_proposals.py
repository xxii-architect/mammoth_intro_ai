import asyncio
import subprocess

import pytest

from mammoth_os.agents.coding_agent import CodingAgent
from mammoth_os.prompt_templates import (
    build_code_gen_prompt,
    parse_structured_code_response,
)


@pytest.fixture
def client(monkeypatch):
    class Client:
        output = "```python\ndef existing_name(value):\n    return value + 2\n```\n```pytest\ndef test_existing_name():\n    assert existing_name(1) == 3\n```\n```docs\nReview before applying.\n```"
        def __init__(self):
            self.calls = []
        async def generate(self, prompt, **kwargs):
            self.calls.append(prompt)
            return self.output
    instance = Client()
    monkeypatch.setattr("mammoth_os.agents.coding_agent.get_llm_client", lambda: instance)
    return instance


def test_health_module_request_cannot_become_unrelated_wrapper(client):
    result = CodingAgent().run({
        "prompt": "Add a nutritional health layer inside the existing Health Module and leave the rest of the file alone.",
        "coding_intent": "generate_code", "host_access": False,
    })
    assert result["status"] == "needs_context"
    assert result["task_kind"] == "patch_existing"
    assert not client.calls


def test_target_name_is_not_original_file_content(client):
    result = CodingAgent().run({"prompt": "Update health.py", "target": "health.py", "coding_intent": "patch_existing", "host_access": False})
    assert result["status"] == "needs_context"
    assert not client.calls


def test_pasted_source_is_in_prompt_and_diff_is_applicable(client, tmp_path):
    original = "def existing_name(value):\n    return value + 1\n"
    result = CodingAgent().run({"prompt": "Fix the existing function", "coding_intent": "patch_existing", "target": "health.py", "context": {"source": original}, "host_access": False})
    assert original in client.calls[0]
    assert "Do not introduce a generic solution()" in client.calls[0]
    assert result["task_kind"] == "patch_existing"
    assert result["status"] == "ok"
    assert result["validation"]["tests"] == "not_run"
    assert result["confidence"] is None
    assert result["evidence"]["original_read"]
    (tmp_path / "health.py").write_bytes(original.encode("utf-8"))
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    checked = subprocess.run(["git", "apply", "--check", "-"], input=result["diff"].encode("utf-8"), cwd=tmp_path, capture_output=True, check=False)
    assert checked.returncode == 0, checked.stderr


def test_fenced_original_and_file_payloads_are_used(client):
    original = "def existing_name(value):\n    return value + 1\n"
    for payload in (
        {"prompt": f"Fix this code:\n```python\n{original}```"},
        {"prompt": "Update health.py", "target": "health.py", "files": [{"path": "health.py", "content": original}]},
    ):
        result = CodingAgent().run({**payload, "coding_intent": "patch_existing", "host_access": False})
        assert result["status"] == "ok"
        assert original in client.calls[-1]


def test_syntax_failure_is_error_not_completed_work(client):
    client.output = "```python\ndef broken(:\n```"
    result = asyncio.run(CodingAgent().generate_code("Create utility.py", {"target": "utility.py"}))
    assert result["status"] == "error"
    assert result["validation"]["checks"][0]["status"] == "failed"
    assert not result["diff"]


def test_prose_and_docs_are_not_implementation():
    assert parse_structured_code_response("I completed the integration.")["code"] == ""
    assert parse_structured_code_response("```docs\nNothing changed.\n```")["code"] == ""


def test_advice_question_does_not_require_or_claim_code(client):
    client.output = "## Recommendation\nKeep blue for focus and brass for primary actions."
    result = CodingAgent().run({
        "prompt": "What do you think of this? We can be a little more loose with the blue. What are your suggestions?",
        "coding_intent": "generate_code", "host_access": False,
    })
    assert result["status"] == "ok"
    assert result["artifact_type"] == result["task_kind"] == "advice"
    assert "Recommendation" in result["content"]
    assert "no code was generated" in result["summary"]
    assert not result.get("code") and not result.get("diff")
    assert len(client.calls) == 1
    import api_server
    policy = api_server._execution_policy_for_run({}, {}, runtime_agent="coding")
    envelope = api_server._normalize_agent_output("coding", result)
    assert api_server._verify_execution_contract(envelope, policy)["passed"]


def test_advice_with_implementation_request_keeps_source_gate(client):
    result = CodingAgent().run({
        "prompt": "What are your suggestions? Patch the existing stylesheet.",
        "coding_intent": "generate_code", "host_access": False,
    })
    assert result["status"] == "needs_context"
    assert result["task_kind"] == "patch_existing"
    assert not client.calls


def test_advice_preserves_supplied_source_without_reading_host(client, monkeypatch):
    client.output = "The supplied colors need a contrast check."
    monkeypatch.setattr(CodingAgent, "_read_file", lambda *args: pytest.fail("Advice must not read host files"))
    result = CodingAgent().run({
        "prompt": "What are your thoughts on these colors?",
        "context": {"source": ".card {color: blue;}"},
        "host_access": False, "coding_intent": "generate_code",
    })
    assert result["status"] == "ok"


@pytest.mark.parametrize("finish_reason", ["length", "refusal", "content_filter"])
def test_incomplete_advice_is_not_success(client, monkeypatch, finish_reason):
    from mammoth_os.llm_completion import Completion

    async def completion(*args, **kwargs):
        return Completion("partial advice", finish_reason=finish_reason)

    monkeypatch.setattr(client, "generate_completion", completion, raising=False)
    result = CodingAgent().run({"prompt": "What are your suggestions?", "host_access": False})
    assert result["status"] == "error"
    assert result["quality"]["status"] == "failed"
    assert "content" not in result


@pytest.mark.parametrize("language, filename, source", [
    ("css", "styles.css", ".card { color: blue; }"),
    ("html", "index.html", "<main>Hello</main>"),
    ("vue", "Card.vue", "<template><p>Hello</p></template>"),
    ("svelte", "Card.svelte", "<p>Hello</p>"),
    ("jsx", "Card.jsx", "export default () => <p>Hello</p>;"),
])
def test_frontend_languages_keep_source_and_explicit_implementation(client, language, filename, source):
    client.output = f"```{language}\n{source}\n```"
    result = CodingAgent().run({
        "prompt": f"Fix this file:\n```{language}\n{source}\n```",
        "target": filename, "coding_intent": "patch_existing", "host_access": False,
    })
    assert result["status"] == "ok"
    assert result["code"] == source
    assert result["validation"]["checks"][0]["status"] == "not_run"
    assert f"```{language}\n{source}\n```" in client.calls[0]
    assert f"```{language}" in build_code_gen_prompt("Create a component", target=filename)


def test_refactor_syntax_failure_does_not_claim_success(client):
    client.output = "```python\ndef broken(:\n```"
    result = asyncio.run(CodingAgent().refactor("def existing_name(value):\n    return value\n", "default"))
    assert result["status"] == "error"
    assert result["validation"]["tests"] == "not_run"
    assert not result["diff"]


def test_patch_diff_handles_original_without_final_newline(client, tmp_path):
    original = "def existing_name(value):\n    return value + 1"
    result = CodingAgent().run({"prompt": "Fix health.py", "coding_intent": "patch_existing", "target": "health.py", "context": {"source": original}, "host_access": False})
    (tmp_path / "health.py").write_bytes(original.encode("utf-8"))
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    checked = subprocess.run(["git", "apply", "--check", "-"], input=result["diff"].encode("utf-8"), cwd=tmp_path, capture_output=True, check=False)
    assert checked.returncode == 0, checked.stderr
