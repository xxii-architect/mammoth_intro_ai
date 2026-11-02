from mammoth_os.agents.community_engine_agent import CommunityEngineAgent
import json
import pytest


@pytest.fixture(autouse=True)
def generated_challenge(monkeypatch):
    class Model:
        async def generate(self, prompt, **kwargs):
            return json.dumps({
                "challenge": "Build one small example, explain the result and share progress with the team.",
                "prompt": "Post your example and one question for a partner to review.",
                "social_callout": "Join at your own pace and compare one concrete result.",
            })
    monkeypatch.setattr("mammoth_os.llm_client.get_llm_client", lambda: Model())


def test_community_engine_agent_uses_team_context_and_signals():
    agent = CommunityEngineAgent(user_id="community-1")

    result = agent.run(
        {
            "theme": "ai_learning",
            "difficulty": "hard",
            "group_size": 12,
            "team_context": "crew alpha",
            "learner_context": "week 4",
            "engagement_goal": "share progress",
            "learner_signals": ["need examples", "slow pace"],
        }
    )

    assert result["status"] == "ok"
    assert "crew alpha" in result["social_callout"].lower()
    assert result["reward"]["xp_bonus"] >= 40
    assert "share progress" in result["challenge"].lower()
    assert "engagement goal" in result["engagement_checkpoints"][1].lower()
    assert "need_examples" in result["tags"]
    assert result["signal_confidence"] < 0.9


def test_community_engine_agent_supports_open_challenges():
    agent = CommunityEngineAgent(user_id="community-2")

    result = agent.run({"theme": "mindset", "difficulty": "easy", "group_size": "open"})

    assert result["status"] == "ok"
    assert "open challenge" in result["social_callout"].lower()
    assert result["prompt"]
    assert result["next_actions"]


def test_community_engine_agent_flags_public_high_effort_runs_for_review():
    agent = CommunityEngineAgent(user_id="community-3")

    result = agent.run({"theme": "ai_learning", "difficulty": "hard", "group_size": "open", "constraints": ["external publish"]})

    assert result["status"] == "ok"
    assert result["approval_gate"]["requires_review"] is True
    assert "community-feed" == result["delivery_plan"]["primary_channel"]
