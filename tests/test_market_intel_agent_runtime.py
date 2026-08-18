from mammoth_os.agents.market_intel_agent import MarketIntelAgent


def test_market_intel_agent_builds_source_aware_brief():
    agent = MarketIntelAgent(user_id="analyst-1")

    result = agent.run(
        {
            "topic": "AI engineering",
            "focus": "job market",
            "depth": "full",
            "sources": [
                {"label": "Hiring notes", "summary": "Teams want product-minded integration skills."},
                {"label": "Tooling notes", "summary": "Orchestration and retrieval are common stack pieces."},
            ],
        }
    )

    assert result["status"] == "ok"
    assert result["signal_confidence"] >= 0.7
    assert len(result["sources"]) == 2
    assert "AI engineering" in result["summary"]
    assert result["opportunities"]
    assert result["risks"]
    assert result["next_actions"]


def test_market_intel_agent_falls_back_to_prompt_driven_sources():
    agent = MarketIntelAgent(user_id="analyst-2")

    result = agent.run({"topic": "software engineering", "focus": "trends", "depth": "quick"})

    assert result["status"] == "ok"
    assert result["sources"][0]["label"] == "Direct prompt"
    assert "software engineering" in result["summary"].lower()
    assert "practical production" in result["summary"].lower()
