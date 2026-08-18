from mammoth_os.agents.community_engine_agent import CommunityEngineAgent


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
