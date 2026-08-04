from mammoth_os import agent_registry as agent_registry_mod


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

    assert curriculum_result["payload"] == "build lesson"
    assert tutor_result["payload"]["topic"] == "coach"
    assert plant_result["payload"]["topic"] == "hello"
