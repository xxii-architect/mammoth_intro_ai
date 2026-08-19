import asyncio

from mammoth_os import ATLASSession, AtlasFAB, AtlasFABConfig, __version__


class DummySession:
    def __init__(self):
        self.started = None
        self.submitted = None

    def start_lesson(self, topic, **kwargs):
        self.started = {"topic": topic, **kwargs}
        return {"status": "ok", "topic": topic, "learner_context": kwargs.get("learner_context")}

    async def submit(self, files):
        self.submitted = files
        return {"status": "ok", "passed": True, "files": files}

    async def generate_and_test(self, prompt, context=None):
        return {"status": "ok", "prompt": prompt, "context": context or {}}

    def next_lesson(self, lesson_idx_delta=1):
        return {"status": "ok", "lesson_idx_delta": lesson_idx_delta}

    def status(self):
        return {"state": "active", "user_id": "workspace:test"}


def test_package_exports_sdk_surface():
    assert ATLASSession is not None
    assert AtlasFAB is not None
    assert AtlasFABConfig is not None
    assert __version__ == "0.5.0"


def test_atlas_fab_start_lesson_merges_context():
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
    assert session.started["topic"] == "FastAPI auth"
    assert session.started["learner_context"] == {"goal": "ship embedding", "pace": "fast"}


def test_atlas_fab_submit_accepts_solution_code():
    session = DummySession()
    fab = AtlasFAB(AtlasFABConfig(user_id="workspace:test"), session=session)

    result = fab.submit(solution_code="def solution():\n    return True\n")

    assert result["status"] == "ok"
    assert session.submitted == {"solution.py": "def solution():\n    return True\n"}


def test_atlas_fab_generate_and_test_adds_embed_context():
    session = DummySession()
    fab = AtlasFAB(AtlasFABConfig(user_id="workspace:test", audience="buyer", mode="embed"), session=session)

    result = asyncio.run(fab.generate_and_test_async("Build a starter lesson"))

    assert result["status"] == "ok"
    assert result["context"]["source"] == "atlas_fab"
    assert result["context"]["audience"] == "buyer"
    assert result["context"]["mode"] == "embed"


def test_atlas_fab_runtime_state_uses_client_description(monkeypatch):
    class FakeClient:
        def describe_runtime_state(self):
            return {
                "contract_version": "v2",
                "primary_provider": "openai",
                "fallback_provider": "local",
                "model": "gpt-4o-mini",
            }

    monkeypatch.setattr("mammoth_os.sdk.get_llm_client", lambda config=None: FakeClient())

    fab = AtlasFAB(AtlasFABConfig(user_id="workspace:buyer-1", adapter="openai"))
    state = fab.runtime_state()

    assert state["product_surface"] == "atlas_fab"
    assert state["user_id"] == "workspace:buyer-1"
    assert state["primary_provider"] == "openai"
    assert state["model"] == "gpt-4o-mini"
