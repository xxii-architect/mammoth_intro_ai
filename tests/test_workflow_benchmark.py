import asyncio

import pytest

from mammoth_os.agent_loop import AgentRunner
from mammoth_os.coding_benchmark import CASES
from mammoth_os.workflow_benchmark import run_workflow_benchmark


class FixtureExecutor:
    image = "python@sha256:" + "0" * 64
    timeout = 20

    def readiness(self):
        return {"ready": True, "profiles": {"python_unittest": True}}

    def run(self, files, profile, cancelled, **kwargs):
        source = files["app.py"].decode()
        assert b"class Acceptance" in files["tests/test_acceptance.py"]
        return {"passed": any(source == case["solution"] for case in CASES), "duration_ms": 1}


@pytest.mark.parametrize("behavior", ["complete", "claim_only", "edit_acceptance"])
def test_workflow_benchmark_requires_both_approvals_branch_and_independent_acceptance(tmp_path, monkeypatch, behavior):
    async def decide(self, run, ctx):
        case = next(case for case in CASES if run.message.startswith(case["prompt"]))
        if behavior == "claim_only":
            return {"final": "Everything is done"}
        tools = [step["tool"] for step in run.transcript]
        if not tools:
            return {"tool": "owner_execution_status", "args": {}}
        if "owner_execution_prepare" not in tools:
            path = "tests/test_acceptance.py" if behavior == "edit_acceptance" else "app.py"
            return {"tool": "owner_execution_prepare", "args": {
                "base_sha": run.transcript[0]["result"]["base_sha"], "profile": "python_unittest",
                "changes": [{"path": path, "content": case["solution"]}],
            }}
        job = next(step["result"]["execution"] for step in reversed(run.transcript)
                   if step["result"].get("execution"))
        if "owner_execution_run" not in tools:
            return {"tool": "owner_execution_run", "args": {
                "execution_id": job["id"], "approval_digest": job["approval_digest"],
            }}
        if "owner_execution_apply" not in tools:
            return {"tool": "owner_execution_apply", "args": {
                "execution_id": job["id"], "approval_digest": job["application"]["approval_digest"],
            }}
        return {"final": "The recorded branch is applied"}
    monkeypatch.setattr(AgentRunner, "_decide", decide)
    report = asyncio.run(run_workflow_benchmark(tmp_path, FixtureExecutor(), lambda: None))
    assert report["summary"]["sample_count"] == 3
    assert report["summary"]["success_count"] == (3 if behavior == "complete" else 0)
    assert report["summary"]["coding_thresholds_met"] is False
    assert report["summary"]["cost_usd"] is None
    assert (tmp_path / (report["id"] + ".json")).is_file()
    for record in report["records"]:
        assert record["checkout_preserved"] is True
        assert record["usage_complete"] is False
        assert all(value is None for value in record["reported_usage"].values())
        if behavior == "complete":
            assert record["independent_acceptance"]["passed"] is True
            assert len(record["approvals"]) == 2
        elif behavior == "edit_acceptance":
            assert record["approvals"] == [{"tool": "owner_execution_run", "approved": False}]
            assert record["refusal"]
