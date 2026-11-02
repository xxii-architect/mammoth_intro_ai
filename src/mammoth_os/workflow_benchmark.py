"""Opt-in agent-loop measurements in disposable repositories, never user repos."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable

from mammoth_os.agent_loop import (
    AgentRun,
    AgentRunner,
    RunStore,
    ToolContext,
    ToolRegistry,
)
from mammoth_os.agent_loop.builtin_tools import register_repo_tools
from mammoth_os.coding_benchmark import CASES, summarize
from mammoth_os.owner_execution import (
    ContainerExecutor,
    ExecutionError,
    OwnerExecution,
    fingerprint,
    git,
    head_sha,
    stamp,
)
from mammoth_os.owner_execution_tools import register_owner_execution_tools


async def run_workflow_benchmark(
    storage: Path, executor: ContainerExecutor, llm_factory: Callable[[], Any], *, repetitions: int = 1,
) -> dict[str, Any]:
    if not 1 <= repetitions <= 10:
        raise ValueError("repetitions must be between 1 and 10")
    ready = executor.readiness()
    if not ready["ready"] or not ready.get("profiles", {}).get("python_unittest"):
        raise RuntimeError(ready.get("reason") or "python_unittest is unavailable.")
    records: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="mammoth-workflow-benchmark-") as directory:
        sandbox = Path(directory)
        for repeat in range(repetitions):
            for case in CASES:
                root = sandbox / f"{case['id']}-{repeat}"
                root.mkdir()
                git(root, "init")
                (root / "app.py").write_text(case["source"], encoding="utf-8", newline="")
                (root / "tests").mkdir()
                acceptance = ("import unittest\n" + case["test"]).encode()
                (root / "tests" / "test_acceptance.py").write_bytes(acceptance)
                git(root, "add", ".")
                git(root, "-c", "user.name=Benchmark", "-c", "user.email=benchmark@example.test",
                    "commit", "-m", "Fixed workflow acceptance fixture")
                base = head_sha(root)
                service = OwnerExecution(sandbox / f"jobs-{case['id']}-{repeat}", executor, enabled=True)
                registry = ToolRegistry()
                register_repo_tools(registry)
                register_owner_execution_tools(registry, service)
                run = AgentRun(
                    id=AgentRun.new_id(), user_id="benchmark", agent_id="coding_agent",
                    message=(case["prompt"] + "\nInspect app.py, check actual owner profile availability, prepare "
                             "only app.py against committed HEAD using python_unittest, request isolated validation, "
                             "then separate approval for a new local branch commit. Do not edit tests, push or deploy."),
                    request={"completion_goal": "applied"},
                )
                runner = AgentRunner(registry, llm_factory, RunStore(sandbox / "runs"))
                ctx = ToolContext(user_id="benchmark", is_admin=True, repo_root=root, repo_scope="local_path")
                started = time.monotonic()
                approvals: list[dict[str, Any]] = []
                refusal = ""
                events = [event async for event in runner.start(run, ctx)]
                while run.status == "awaiting_approval" and len(approvals) < 2:
                    pending = run.pending_approval or {}
                    name = pending.get("tool")
                    args = pending.get("args") or {}
                    try:
                        record = service.get(args.get("execution_id", ""), "benchmark") if name in {
                            "owner_execution_run", "owner_execution_apply",
                        } else {}
                        frozen = service._load(args.get("execution_id", ""), "benchmark") if record else {}
                    except ExecutionError as exc:
                        record, frozen = {}, {}
                        refusal = f"Benchmark approval lookup failed: {exc.code}: {exc}"
                    allowed = (
                        name in {"owner_execution_run", "owner_execution_apply"}
                        and frozen.get("root") == str(root.resolve()) and record.get("base_sha") == base
                        and record.get("profile") == "python_unittest"
                        and [change["path"] for change in frozen.get("changes", [])] == ["app.py"]
                        and (root / "tests" / "test_acceptance.py").read_bytes() == acceptance
                    )
                    approvals.append({"tool": name, "approved": allowed})
                    if not allowed:
                        refusal = "Benchmark refuses anything outside app.py and the two scoped owner approvals."
                    events += [event async for event in runner.resume(
                        run, ctx, approval_id=pending["id"], approved=allowed, note=refusal,
                    )]
                    if not allowed:
                        break
                progress = run.progress()
                applied = next((job for job in progress["executions"]
                                if (job.get("application") or {}).get("status") == "applied"), None)
                acceptance_result = None
                preserved = head_sha(root) == base and (root / "app.py").read_text() == case["source"]
                if applied:
                    branch = applied["application"]["branch"]
                    candidate = git(root, "show", f"{branch}:app.py")
                    acceptance_result = await asyncio.to_thread(
                        executor.run, {"app.py": candidate, "tests/test_acceptance.py": acceptance},
                        "python_unittest", threading.Event(),
                        container_name="mammoth-owner-exec-" + uuid.uuid4().hex[:24] + "-candidate",
                    )
                usage = [item.get("usage") or {} for item in run.diagnostics]
                tokens = {key: sum(item[key] for item in usage) if usage and all(
                    isinstance(item.get(key), int) for item in usage) else None
                          for key in ("prompt_tokens", "completion_tokens", "total_tokens")}
                records.append({
                    "case_id": case["id"], "repeat": repeat, "kind": case["kind"],
                    "passed": bool(run.status == "completed" and progress["goal_met"] and applied
                                   and acceptance_result and acceptance_result["passed"] and preserved
                                   and [item["tool"] for item in approvals] == ["owner_execution_run", "owner_execution_apply"]
                                   and all(item["approved"] for item in approvals)),
                    "duration_ms": round((time.monotonic() - started) * 1000), "cost_usd": None,
                    "status": run.status, "failure_code": run.failure_code, "refusal": refusal,
                    "provider": run.provider, "model": run.model, "model_calls": len(run.diagnostics),
                    "reported_usage": tokens, "usage_complete": all(value is not None for value in tokens.values()),
                    "tool_calls": sum(event.type == "tool.call" for event in events), "approvals": approvals,
                    "progress": progress, "independent_acceptance": acceptance_result, "checkout_preserved": preserved,
                    "diagnostics": run.diagnostics,
                    "tool_outcomes": [{"tool": step.get("tool"), "status": (step.get("result") or {}).get("status"),
                                       "code": (step.get("result") or {}).get("code"),
                                       "error": (step.get("result") or {}).get("error")}
                                      for step in run.transcript],
                })
    summary = summarize(records, "model")
    summary["limitations"].append("Real agent loop, two fixture-only approvals and independent acceptance; no UI or arbitrary-repository claims.")
    report: dict[str, Any] = {"id": "workflow-" + uuid.uuid4().hex[:24], "created_at": stamp(),
              "contract": "mammoth.workflow-benchmark.v1", "corpus_sha256": fingerprint(CASES),
              "summary": summary, "records": records}
    storage.mkdir(parents=True, exist_ok=True)
    (storage / (report["id"] + ".json")).write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", action="store_true", required=True, help="Explicit consent to spend model credits.")
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--output-dir", type=Path, default=Path(".mammoth") / "owner_benchmarks")
    args = parser.parse_args()
    from mammoth_os.llm_client import get_llm_client
    result = asyncio.run(run_workflow_benchmark(
        args.output_dir, ContainerExecutor(os.environ.get("MAMMOTH_OWNER_EXEC_IMAGE", "")),
        get_llm_client, repetitions=args.repetitions,
    ))
    print(json.dumps({"id": result["id"], **result["summary"]}, indent=2))


if __name__ == "__main__":
    main()
