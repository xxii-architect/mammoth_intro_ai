import json

from mammoth_os import agent_registry as agent_registry_mod
from mammoth_os.agents.research_agent import ResearchAgent


class DummyAgent:
    def __init__(self, name: str):
        self.name = name

    def run(self, payload):
        if self.name == "tutor":
            assert isinstance(payload, dict)
            assert payload["topic"] == "coach"
        if self.name == "curriculum":
            assert payload == "build lesson"
        return {"agent": self.name, "payload": payload}


def test_run_agent_normalizes_payloads(monkeypatch):
    monkeypatch.setattr(agent_registry_mod, "load_agent", lambda agent_name, router=None: DummyAgent(agent_name))

    curriculum_result = agent_registry_mod.run_agent("curriculum", {"prompt": "build lesson"})
    tutor_result = agent_registry_mod.run_agent("tutor", {"prompt": "coach"})
    plant_result = agent_registry_mod.run_agent("plant_the_seed", {"prompt": "hello"})
    field_ops_result = agent_registry_mod.run_agent("field_ops", {"topic": "navigation", "environment": "forest", "hazards": ["fog"]})
    browser_result = agent_registry_mod.run_agent("browser", {"url": "https://example.com", "follow_links": False})
    task_queue_result = agent_registry_mod.run_agent("task_queue", {"action": "status", "prompt": "show queue"})

    assert curriculum_result["payload"] == "build lesson"
    assert tutor_result["payload"]["topic"] == "coach"
    assert plant_result["payload"]["topic"] == "hello"
    assert field_ops_result["payload"]["environment"] == "forest"
    assert browser_result["payload"]["url"] == "https://example.com"
    assert task_queue_result["payload"]["action"] == "status"


def test_research_agent_emits_grounded_evidence_fields(monkeypatch):
    class _FakeResponse:
        def __init__(self, payload):
            self._payload = json.dumps(payload).encode("utf-8")

        def read(self):
            return self._payload

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def _fake_urlopen(req, timeout=0):
        url = req.full_url
        if "wikipedia.org" in url:
            return _FakeResponse(
                {
                    "title": "Code review",
                    "extract": "Code review is a systematic examination of source code.",
                    "content_urls": {"desktop": {"page": "https://en.wikipedia.org/wiki/Code_review"}},
                }
            )
        return _FakeResponse(
            {
                "AbstractText": "Verification before moving on reduces regressions and improves confidence.",
                "AbstractURL": "https://duckduckgo.com/code-review",
                "Heading": "Code review",
            }
        )

    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen)
    result = ResearchAgent(router=None).run("Analyze whether the coding lesson should verify the patch before we move on.")

    assert result["focus"] == "curriculum"
    assert result["confidence"] >= 0.6
    assert isinstance(result["findings"], list) and result["findings"]
    assert isinstance(result["citations"], list) and result["citations"]
    assert isinstance(result["references"], list)
    assert result["mode"] == "source_grounded_research_v2"
    assert result["source_coverage"]["total_claims"] == len(result["findings"])
