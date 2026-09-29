import asyncio

from mammoth_os import (
    ATLASSession,
    AtlasFAB,
    AtlasFABConfig,
    AtlasFABError,
    AtlasGenerationReport,
    AtlasLessonSnapshot,
    AtlasProgressSnapshot,
    AtlasRuntimeSnapshot,
    AtlasSubmissionReport,
    AtlasUsageSnapshot,
    __version__,
)


class DummySession:
    def __init__(self):
        self.started = None
        self.submitted = None
        self.generated = None
        self.state = "idle"

    def start_lesson(self, topic, **kwargs):
        self.started = {"topic": topic, **kwargs}
        self.state = "active"
        return {
            "status": "ok",
            "topic": topic,
            "learner_context": kwargs.get("learner_context"),
            "lesson": {"title": f"{topic} lesson"},
            "curriculum": {"title": f"{topic} curriculum"},
            "exercise_id": "exercise-1",
            "lesson_id": "lesson-1",
            "curriculum_id": "curriculum-1",
        }

    async def submit(self, files):
        self.submitted = files
        return {
            "status": "ok",
            "passed": True,
            "files": files,
            "recommendation": "same",
            "hint": "Nice work.",
            "result": {"passed": True},
        }

    async def generate_and_test(self, prompt, context=None):
        self.generated = {"prompt": prompt, "context": context or {}}
        return {
            "status": "ok",
            "prompt": prompt,
            "context": context or {},
            "code": "print('hi')",
            "tests": "assert True",
            "docs": "Example docs",
            "passed": True,
            "hint": "Looks good.",
            "result": {"passed": True},
        }

    def next_lesson(self, lesson_idx_delta=1):
        return {"status": "ok", "lesson_idx_delta": lesson_idx_delta, "lesson_id": "lesson-2", "exercise_id": "exercise-2"}

    def status(self):
        return {
            "state": self.state,
            "user_id": "workspace:test",
            "curriculum_title": "Test curriculum",
            "lesson_title": "Test lesson",
            "exercise_title": "Test exercise",
            "curriculum_id": "curriculum-1",
            "lesson_id": "lesson-1",
        }


def test_package_exports_sdk_surface():
    assert ATLASSession is not None
    assert AtlasFAB is not None
    assert AtlasFABConfig is not None
    assert AtlasFABError is not None
    assert AtlasLessonSnapshot is not None
    assert AtlasSubmissionReport is not None
    assert AtlasGenerationReport is not None
    assert AtlasProgressSnapshot is not None
    assert AtlasUsageSnapshot is not None
    assert AtlasRuntimeSnapshot is not None
    assert __version__ == "0.5.0"


def test_atlas_fab_start_lesson_returns_richer_snapshot():
    session = DummySession()
    fab = AtlasFAB(
        AtlasFABConfig(
            user_id="workspace:test",
            metadata={"learner_context": {"goal": "ship embedding", "pace": "steady"}},
        ),
        session=session,
    )

    result = fab.start_lesson("FastAPI auth", learner_context={"pace": "fast"})

    assert result["status"] == "ok"
    assert result["contract_version"] == "v2"
    assert result["product_surface"] == "atlas_fab"
    assert result["progress"]["lesson_starts"] == 1
    assert session.started["topic"] == "FastAPI auth"
    assert session.started["learner_context"] == {"goal": "ship embedding", "pace": "fast"}


def test_atlas_fab_submit_accepts_solution_code_and_updates_usage():
    session = DummySession()
    fab = AtlasFAB(AtlasFABConfig(user_id="workspace:test"), session=session)

    fab.start_lesson("FastAPI auth")
    result = asyncio.run(fab.submit_model(solution_code="def solution():\n    return True\n"))

    assert result.passed is True
    assert result.submission_index == 1
    assert result.progress["submissions"] == 1
    assert result.usage["request_count"] == 2
    assert session.submitted == {"solution.py": "def solution():\n    return True\n"}


def test_atlas_fab_generate_and_test_model_adds_embed_context_and_counts_usage():
    session = DummySession()
    fab = AtlasFAB(AtlasFABConfig(user_id="workspace:test", audience="buyer", mode="embed"), session=session)

    result = asyncio.run(fab.generate_and_test_model("Build a starter lesson"))

    assert result.passed is True
    assert result.context["source"] == "atlas_fab"
    assert result.context["audience"] == "buyer"
    assert result.context["mode"] == "embed"
    assert result.generation_index == 1
    assert result.usage["request_count"] == 1


def test_atlas_fab_progress_resume_and_reset_use_factory():
    sessions = []

    def factory():
        session = DummySession()
        sessions.append(session)
        return session

    fab = AtlasFAB(AtlasFABConfig(user_id="workspace:buyer-1"), session_factory=factory)
    fab.start_lesson("Python packaging")

    progress = fab.get_progress()
    assert progress["session_state"] == "active"
    assert progress["workflow_stage"] == "awaiting_submission"

    resumed = fab.resume()
    assert resumed["lesson_title"] == "Test lesson"

    reset_state = fab.reset()
    assert reset_state["session_state"] == "idle"
    assert len(sessions) == 2
    assert sessions[0] is not sessions[1]


def test_atlas_fab_runtime_state_uses_client_description(monkeypatch):
    class FakeClient:
        def describe_runtime_state(self):
            return {
                "contract_version": "v2",
                "primary_provider": "openai",
                "fallback_provider": "local",
                "last_used_provider": "openai",
                "last_fallback_used": False,
                "last_fallback_reason": "",
                "last_error_type": "",
                "last_error_detail": "",
                "model": "gpt-4o-mini",
            }

    monkeypatch.setattr("mammoth_os.sdk.get_llm_client", lambda config=None: FakeClient())

    fab = AtlasFAB(AtlasFABConfig(user_id="workspace:buyer-1", adapter="openai", metadata={"usage": {"request_limit": 10}}))
    state = fab.runtime_state()

    assert state["product_surface"] == "atlas_fab"
    assert state["user_id"] == "workspace:buyer-1"
    assert state["primary_provider"] == "openai"
    assert state["model"] == "gpt-4o-mini"
    assert state["usage"]["warning_level"] == "idle"


def test_atlas_fab_error_serializes_cleanly():
    error = AtlasFABError("empty_submission", "Need files", context={"hint": "add solution.py"})
    assert str(error) == "empty_submission: Need files"
    assert error.as_dict()["context"]["hint"] == "add solution.py"


def test_atlas_fab_snapshot_exposes_contract_surface():
    fab = AtlasFAB(AtlasFABConfig(user_id="workspace:test", tenant_id="tenant-42", plan="pro"))
    snapshot = fab.snapshot()

    assert snapshot["contract_version"] == "v2"
    assert snapshot["product_surface"] == "atlas_fab"
    assert snapshot["tenant"]["tenant_id"] == "tenant-42"
    assert snapshot["tenant"]["is_bound"] is True
    assert snapshot["usage_policy"]["metering_mode"] == "request_and_token"
    assert snapshot["usage_policy"]["telemetry_enabled"] is True
    assert "config" in snapshot
    assert "runtime" in snapshot
