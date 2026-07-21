import asyncio

from mammoth_os.agents.coding_agent import CodingAgent


class DummyClient:
    async def generate(self, prompt, **kwargs):
        # Return a fenced code block as typical LLM output
        return """Here is the implementation:
```python
def add(a, b):
    return a + b
```
"""

    async def embed(self, texts, **kwargs):
        # return a dummy vector
        return [[0.1] * 1536 for _ in texts]


async def _run_test():
    agent = CodingAgent()

    # Monkeypatch get_llm_client used inside generate_code by replacing attribute on module
    import mammoth_os.agents.coding_agent as ca_mod
    ca_mod.get_llm_client = lambda: DummyClient()

    # Monkeypatch _retrieve_context to avoid hitting a real vector store
    async def fake_retrieve(query, collection="default"):
        return [{"id": "doc1", "text": "snippet", "metadata": {"path": "docs/guide.md"}, "score": 0.9}]

    agent._retrieve_context = fake_retrieve

    result = await agent.generate_code("Write a simple add function", context={})
    assert "def add" in result["code"]
    print("Test passed: code contains add function")


if __name__ == "__main__":
    asyncio.run(_run_test())
