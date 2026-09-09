import pytest
from src.mammoth_os.agents.coding_agent import CodingAgent  # Adjust the import based on your structure

def test_coding_agent_initialization():
    # Test the initialization of CodingAgent with the new parameter
    agent = CodingAgent(autonomous_engine=True)  # Change parameters as needed
    assert agent.autonomous_engine is True  # Check if the parameter is set correctly

def test_coding_agent_functionality():
    agent = CodingAgent(autonomous_engine=True)
    result = agent.run({
        "task": "generate a sorting function",
        "target": "unknown",
        "coding_intent": "generate_code",
    })
    assert isinstance(result, dict)
    assert result.get("status") == "needs_context"
    assert result.get("task_kind") == "generate_code"
    assert result.get("agent") == "CodingAgent"
# Add more tests as needed