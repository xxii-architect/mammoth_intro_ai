"""Opt-in reproducible coding measurements using fixed, independent acceptance tests."""
from __future__ import annotations

import argparse
import json
import math
import os
import tempfile
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

from mammoth_os.owner_execution import (
    ContainerExecutor,
    ExecutionError,
    OwnerExecution,
    fingerprint,
    git,
    head_sha,
    stamp,
)

CASES = (
    {"id": "bug-add", "kind": "bugfix", "prompt": "Fix add so it returns the sum, preserving the function signature. Support negative and zero values; do not introduce new input restrictions.",
     "source": "def add(a, b):\n    return a - b\n", "solution": "def add(a, b):\n    return a + b\n",
     "test": "from app import add\nclass Acceptance(unittest.TestCase):\n def test_values(self):\n  self.assertEqual(add(2,3),5)\n  self.assertEqual(add(-4,7),3)\n def test_preserved(self):\n  self.assertEqual(add(0,0),0)\n"},
    {"id": "feature-unique", "kind": "feature", "prompt": "Implement unique(values) to preserve order without duplicates, including unhashable list elements. Do not mutate input.",
     "source": "def unique(values):\n    return values\n",
     "solution": "def unique(values):\n    result = []\n    for value in values:\n        if value not in result:\n            result.append(value)\n    return result\n",
     "test": "from app import unique\nclass Acceptance(unittest.TestCase):\n def test_values(self):\n  values=[1,2,1,[3],[3]]\n  self.assertEqual(unique(values),[1,2,[3]])\n  self.assertEqual(values,[1,2,1,[3],[3]])\n def test_preserved(self):\n  self.assertEqual(unique([]),[])\n"},
    {"id": "refactor-normalize", "kind": "refactor", "prompt": "Refactor normalize(value): return an empty string for None; otherwise return str(value).strip().lower(). Preserve the function signature and integer string conversion without adding decimal places.",
     "source": "def normalize(value):\n    return value.strip().lower()\n",
     "solution": "def normalize(value):\n    return '' if value is None else str(value).strip().lower()\n",
     "test": "from app import normalize\nclass Acceptance(unittest.TestCase):\n def test_values(self):\n  self.assertEqual(normalize(None),'')\n  self.assertEqual(normalize(42),'42')\n def test_preserved(self):\n  self.assertEqual(normalize(' A '),'a')\n"},
)


def summarize(records: list[dict[str, Any]], mode: str) -> dict[str, Any]:
    count = len(records)
    successes = sum(item.get("passed") is True for item in records)
    times = sorted(item["duration_ms"] for item in records)
    known_costs = [item.get("cost_usd") for item in records]
    valid_costs = [float(value) for value in known_costs
                   if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0]
    costs_reported = bool(count) and len(valid_costs) == count
    success_rate = successes / count if count else 0
    p95 = times[math.ceil(count * .95) - 1] if times else None
    regressions = sum(item.get("regression") is True for item in records)
    enough = count >= 20 and len({item["case_id"] for item in records}) >= 3
    return {
        "contract": "mammoth.coding-benchmark.v1", "mode": mode, "sample_count": count,
        "success_count": successes, "success_rate": success_rate, "regressions": regressions,
        "p95_duration_ms": p95,
        "cost_usd": sum(valid_costs) if costs_reported else None,
        "cost_per_success_usd": sum(valid_costs) / successes if costs_reported and successes else None,
        "thresholds": {"minimum_samples": 20, "minimum_success_rate": .9, "maximum_regressions": 0, "maximum_p95_duration_ms": 120000},
        "coding_thresholds_met": mode == "model" and enough and success_rate >= .9 and regressions == 0 and p95 is not None and p95 <= 120000,
        "safety_suite": "not_assessed_by_this_report",
        "autonomous_execution_enabled": False,
        "limitations": ["Three synthetic Python tasks only; not evidence for arbitrary repositories.",
                       "Reference mode tests the harness, not model reliability.",
                       "Safety, cancellation/recovery and stale approval tests are separate; all must pass before considering broader autonomy.",
                       "No spend estimate is invented when the provider does not report cost."],
    }


def run_benchmark(storage: Path, executor: ContainerExecutor, *, repetitions: int = 1,
                  generate: Callable[[dict[str, str]], dict[str, Any]] | None = None) -> dict[str, Any]:
    if not 1 <= repetitions <= 10:
        raise ValueError("repetitions must be between 1 and 10")
    ready = executor.readiness()
    if not ready["ready"]:
        raise RuntimeError(ready["reason"])
    records = []
    report_id = "benchmark-" + uuid.uuid4().hex[:24]
    with tempfile.TemporaryDirectory(prefix="mammoth-coding-benchmark-") as folder:
        root = Path(folder)
        service = OwnerExecution(root / "executions", executor, enabled=True)
        for repeat in range(repetitions):
            for case in CASES:
                repository = root / f"{case['id']}-{repeat}"
                repository.mkdir()
                git(repository, "init")
                (repository / "app.py").write_text(case["source"], encoding="utf-8", newline="")
                (repository / "tests").mkdir()
                (repository / "tests" / "test_acceptance.py").write_text("import unittest\n" + case["test"], encoding="utf-8", newline="")
                git(repository, "add", ".")
                git(repository, "-c", "user.name=Benchmark", "-c", "user.email=benchmark@example.test", "commit", "-m", "Fixed acceptance fixture")
                started = time.monotonic()
                try:
                    proposal = generate({key: case[key] for key in ("id", "kind", "prompt", "source")}) if generate else {"code": case["solution"]}
                except (RuntimeError, ValueError, TypeError, OSError) as exc:
                    proposal = {"error": f"Generator failed: {type(exc).__name__}: {exc}", "code": ""}
                if not isinstance(proposal, dict):
                    proposal = {"error": "Generator returned a non-object result.", "code": ""}
                code = proposal.get("code")
                if proposal.get("status") in {"error", "failed", "blocked", "needs_context"}:
                    code = None
                cost = proposal.get("cost_usd")
                cost = float(cost) if isinstance(cost, (int, float)) and not isinstance(cost, bool) and math.isfinite(cost) and cost >= 0 else None
                if not isinstance(code, str) or not code.strip():
                    records.append({"case_id": case["id"], "kind": case["kind"], "passed": False,
                                    "error": proposal.get("error") or "Generator produced no source file.", "duration_ms": round((time.monotonic() - started) * 1000),
                                    "cost_usd": cost})
                    continue
                # Acceptance files are never replaced by the generator.
                try:
                    job = service.prepare(repository, case["id"], "benchmark", [{"path": "app.py", "content": code}],
                                          base_sha=head_sha(repository), profile="python_unittest")
                    result = service.execute(job["id"], "benchmark", repository, job["approval_digest"])
                except ExecutionError as exc:
                    result = {"status": "failed", "error": str(exc), "failure_code": exc.code}
                records.append({
                    "case_id": case["id"], "kind": case["kind"], "repeat": repeat,
                    "passed": result["status"] == "validated", "regression": result.get("regression", False),
                    "duration_ms": round((time.monotonic() - started) * 1000), "cost_usd": cost,
                    "provider": proposal.get("provider"), "model": proposal.get("model"),
                    "reported_usage": proposal.get("reported_usage"), "execution": result,
                })
    report = {"id": report_id, "created_at": stamp(), "corpus_sha256": fingerprint(CASES),
              "summary": summarize(records, "model" if generate else "reference"), "records": records}
    storage.mkdir(parents=True, exist_ok=True)
    (storage / f"{report_id}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", action="store_true", help="Opt into CodingAgent calls; consumes provider credits.")
    parser.add_argument("--repetitions", type=int, default=1, help="3 tasks per repetition; 7 repetitions gives 21 samples.")
    parser.add_argument("--output-dir", type=Path, default=Path(".mammoth") / "owner_benchmarks")
    args = parser.parse_args()
    generator = None
    if args.model:
        from mammoth_os.agents.coding_agent import CodingAgent
        agent = CodingAgent()
        def generator(case: dict[str, str]) -> dict[str, Any]:
            return agent.run({"prompt": case["prompt"], "coding_intent": "patch_existing", "host_access": False,
                              "target": "app.py", "context": {"target": "app.py", "source": case["source"]}})
    result = run_benchmark(args.output_dir, ContainerExecutor(os.environ.get("MAMMOTH_OWNER_EXEC_IMAGE", "")),
                           repetitions=args.repetitions, generate=generator)
    print(json.dumps({"id": result["id"], **result["summary"]}, indent=2))


if __name__ == "__main__":
    main()
