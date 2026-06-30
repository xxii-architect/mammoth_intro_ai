# tests/test_router_integration.py

import pytest
from mammoth_os.cortex import build_cortex
from mammoth_os.core_types import ExecutionConfig, ApprovalResult

def always_allow(_: object) -> ApprovalResult:
    return ApprovalResult(approved=True)

def always_deny(_: object) -> ApprovalResult:
    return ApprovalResult(approved=False, reason="denied-by-test")

@pytest.fixture
def cortex(tmp_path):
    cfg = ExecutionConfig(default_timeout=2.0, default_retries=0, risk_threshold=0.5)
    c = build_cortex(approval_mode="vs_code_webview", approval_handler=always_allow, execution_config=cfg)
    c.log_path = str(tmp_path / "cortex.log")
    return c

def test_allowed_action_runs(cortex):
    res = cortex.handle_task("BrandVoiceAgent", "generate_copy", "out.txt", {"x": 1})
    assert isinstance(res, dict)
    assert res.get("status") == "ok"

def test_forbidden_action_denied(cortex):
    res = cortex.handle_task("ReflectionAgent", "write_file", "out.txt", {})
    assert isinstance(res, dict)
    assert res["status"] == "denied"

def test_requires_approval_uses_handler(tmp_path):
    cfg = ExecutionConfig()
    c = build_cortex(approval_mode="vs_code_webview", approval_handler=always_deny, execution_config=cfg)
    c.log_path = str(tmp_path / "cortex.log")
    res = c.handle_task("CodingAgent", "delete_file", "out.txt", {})
    assert isinstance(res, dict)
    assert res["status"] == "denied"
    assert res.get("reason") in ("denied-by-test", "Denied via console")
