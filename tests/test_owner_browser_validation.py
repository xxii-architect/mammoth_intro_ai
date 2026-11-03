import os
import json
import threading
import uuid
from pathlib import Path

import pytest

from mammoth_os.owner_execution import (
    BROWSER_TESTS,
    ContainerExecutor,
    ExecutionError,
    acceptance_contract,
    git,
    head_sha,
    snapshot,
    validation_evidence,
)


UI = "ui/mad-architecht-command-center/src/pages/SettingsPage.jsx"
TEST = "tests/workspace-reliability.spec.js"
ACCEPTANCE = {"expected_behavior": ["Keyboard toggles texture without losing preference."], "regression_tests": [TEST]}


def test_interaction_requires_expected_behavior_and_regression_edit():
    changes = [{"path": UI, "content": "export default function Settings() {}"}]
    with pytest.raises(ExecutionError, match="require acceptance"):
        acceptance_contract(None, changes, {TEST: b"test()"}, "ui_build")
    with pytest.raises(ExecutionError, match="regression-test edit"):
        acceptance_contract(ACCEPTANCE, changes, {TEST: b"test()"}, "ui_build")
    changes.append({"path": TEST, "content": "test('keyboard', () => {})"})
    assert acceptance_contract(ACCEPTANCE, changes, {}, "ui_browser") == ACCEPTANCE


@pytest.mark.parametrize("value", [
    {}, {"expected_behavior": [""], "regression_tests": [TEST]},
    {"expected_behavior": ["Works"], "regression_tests": ["tests/unrelated.spec.js"]},
    {"expected_behavior": ["Works"], "regression_tests": [TEST], "extra": True},
])
def test_invalid_acceptance_is_explicitly_rejected(value):
    with pytest.raises(ExecutionError):
        acceptance_contract(value, [{"path": UI, "content": ""}, {"path": TEST, "content": ""}], {}, "ui_browser")


def test_non_ui_legacy_proposals_remain_supported():
    assert acceptance_contract(None, [{"path": "app.py", "content": "pass"}], {}, "python_unittest") == {}


@pytest.mark.parametrize(("profile", "passed", "build", "behavior"), [
    ("ui_build", True, "passed", "not_tested"),
    ("ui_component", True, "not_tested", "not_tested"),
    ("ui_browser", True, "passed", "verified"),
    ("ui_browser", False, "failed", "failed"),
    ("python_unittest", True, "not_tested", "not_tested"),
])
def test_evidence_never_calls_a_build_behavioral_verification(profile, passed, build, behavior):
    evidence = validation_evidence({"profile": profile, "candidate": {"passed": passed}, "acceptance": ACCEPTANCE})
    assert evidence["build"] == build
    assert evidence["behavior"] == behavior
    assert evidence["expected_behavior"] == ACCEPTANCE["expected_behavior"]


def test_pending_browser_evidence_does_not_claim_success():
    assert validation_evidence({"profile": "ui_browser"})["behavior"] == "not_tested"


def test_failed_browser_suite_preserves_build_pass_evidence():
    evidence = validation_evidence({"profile": "ui_browser", "candidate": {"passed": False, "build_passed": True}})
    assert evidence["build"] == "passed" and evidence["behavior"] == "failed"


@pytest.mark.skipif(not os.environ.get("MAMMOTH_TEST_OWNER_BROWSER_IMAGE"), reason="Reviewed browser image opt-in")
def test_real_browser_profile_rejects_failing_skipped_empty_and_changed_dependencies():
    root = Path(__file__).parents[1]
    files = snapshot(root, head_sha(root))
    for rel in git(root, "diff", "--name-only").decode().splitlines():
        files[rel] = (root / rel).read_bytes()
    executor = ContainerExecutor(os.environ["MAMMOTH_TEST_OWNER_BROWSER_IMAGE"], timeout=120)

    def run(test_body, extra=None):
        content = dict(files)
        for path in BROWSER_TESTS:
            content[path] = test_body
        content.update(extra or {})
        return executor.run(content, "ui_browser", threading.Event(),
                            container_name="mammoth-owner-exec-" + uuid.uuid4().hex[:24] + "-candidate")

    passing = run(b"const {test,expect}=require('@playwright/test'); test('browser works',async({page})=>{await page.goto('http://127.0.0.1:5194/'); await expect(page.locator('body')).toBeVisible()});")
    assert passing["passed"], passing
    assert passing["tests_detected"] and passing["build_passed"]
    assert len(passing["test_results"]) == 4 and set(passing["test_results"].values()) == {"ok"}
    failing = run(b"const {test,expect}=require('@playwright/test'); test('behavior fails',()=>expect(false).toBe(true));")
    assert not failing["passed"] and failing["build_passed"], failing
    assert validation_evidence({"profile": "ui_browser", "candidate": failing})["behavior"] == "failed"
    skipped = run(b"const {test}=require('@playwright/test'); test.skip('not verified',()=>{});")
    assert not skipped["passed"] and not skipped["tests_detected"], skipped
    empty = run(b"// No tests\n")
    assert not empty["passed"] and not empty["tests_detected"], empty
    manifest = json.loads(files["package.json"])
    manifest["version"] = "0.0.0-unreviewed"
    mismatch = run(b"const {test}=require('@playwright/test'); test('runs',()=>{});",
                   {"package.json": json.dumps(manifest).encode()})
    assert not mismatch["passed"] and "Browser test dependency manifest changed" in mismatch["log"], mismatch
