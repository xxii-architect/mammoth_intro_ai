import os

import pytest

from mammoth_os.coding_benchmark import CASES, run_benchmark, summarize
from mammoth_os.owner_execution import ContainerExecutor


class FakeExecutor:
    image = "python@sha256:" + "0" * 64
    timeout = 20
    def readiness(self):
        return {"ready": True}
    def run(self, files, profile, cancelled, **kwargs):
        assert b"class Acceptance" in files["tests/test_acceptance.py"]
        return {"passed": True, "test_results": {}, "duration_ms": 1}


@pytest.mark.parametrize("failure", ["no_code", "no_op", "exception", "invalid_shape"])
def test_failed_generation_is_counted_and_reported_not_an_aborted_suite(tmp_path, failure):
    def generator(case):
        assert set(case) == {"id", "kind", "prompt", "source"}
        if failure == "exception":
            raise RuntimeError("Provider unavailable")
        if failure == "no_op":
            return {"code": case["source"]}
        if failure == "invalid_shape":
            return None
        return {"status": "error", "error": "No response"}
    report = run_benchmark(tmp_path / "reports", FakeExecutor(), generate=generator)
    assert report["summary"]["sample_count"] == 3
    assert report["summary"]["success_count"] == 0
    assert report["summary"]["mode"] == "model"
    assert report["summary"]["cost_usd"] is None
    assert len(report["records"]) == 3
    assert (tmp_path / "reports" / (report["id"] + ".json")).exists()
    if failure == "no_op":
        assert all(record["execution"]["failure_code"] == "empty_patch" for record in report["records"])
    else:
        assert all(record["error"] for record in report["records"])


def test_reference_success_is_not_a_model_reliability_score():
    records = [{"case_id": case["id"], "passed": True, "duration_ms": 10, "cost_usd": None}
               for _ in range(7) for case in CASES]
    result = summarize(records, "reference")
    assert result["success_rate"] == 1
    assert result["coding_thresholds_met"] is False
    assert result["autonomous_execution_enabled"] is False
    assert result["cost_per_success_usd"] is None
    assert result["safety_suite"] == "not_assessed_by_this_report"
    model = summarize(records, "model")
    assert model["coding_thresholds_met"] is True
    records[0]["regression"] = True
    assert summarize(records, "model")["coding_thresholds_met"] is False


def test_p95_and_cost_are_measured_without_invented_defaults():
    records = [{"case_id": "bug-add", "passed": True, "duration_ms": value, "cost_usd": .01} for value in range(1, 21)]
    result = summarize(records, "model")
    assert result["p95_duration_ms"] == 19
    assert result["cost_per_success_usd"] == pytest.approx(.01)
    assert result["coding_thresholds_met"] is False  # Insufficient task diversity.
    assert summarize([], "model")["p95_duration_ms"] is None
    assert summarize([], "model")["success_rate"] == 0


def test_failed_proposal_does_not_become_success_and_nonfinite_cost_is_not_json_evidence(tmp_path):
    report = run_benchmark(tmp_path / "reports", FakeExecutor(),
                           generate=lambda case: {"status": "error", "code": "pass\n", "cost_usd": float("nan")})
    assert report["summary"]["success_count"] == 0
    assert all(record["cost_usd"] is None for record in report["records"])


@pytest.mark.skipif(os.environ.get("MAMMOTH_TEST_OWNER_DOCKER") != "1", reason="Explicit Docker integration opt-in")
def test_reference_benchmark_persists_real_fixed_acceptance_evidence(tmp_path):
    image = os.environ.get("MAMMOTH_OWNER_EXEC_IMAGE", "")
    report = run_benchmark(tmp_path / "reports", ContainerExecutor(image, timeout=20))
    assert report["summary"]["success_count"] == 3, report
    assert report["summary"]["mode"] == "reference"
    assert report["summary"]["coding_thresholds_met"] is False
    assert (tmp_path / "reports" / (report["id"] + ".json")).exists()
    assert all(record["execution"]["baseline"]["passed"] is False for record in report["records"])
    assert all(record["execution"]["candidate"]["passed"] is True for record in report["records"])
