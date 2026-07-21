class MemoryAgent(BaseAgent):# type: ignore
    """
    Provides unified long-term memory for agents. Combines episodic memory
    (event sequences) and semantic memory (factual knowledge) backed
    by VectorStoreAgent. Injects relevant context into agent prompts.
    """

    async def store(self, content: str, memory_type: str, metadata: dict = None) -> str:# type: ignore
        """Store a memory and return its ID."""
        ...

    async def retrieve(self, query: str, top_k: int = 5, memory_type: str = None) -> list[dict]:# type: ignore
        """Retrieve memories most relevant to the query."""
        ...

    async def forget(self, memory_id: str) -> bool:
        """Remove a specific memory entry."""
        ...

    async def consolidate(self, user_id: str) -> None:
        """Merge redundant memories, compress episodic chains."""
        ...

    async def inject_context(self, prompt: str, user_id: str) -> str:
        """Retrieve relevant memories and prepend to prompt as context."""
        memories = await self.retrieve(prompt, top_k=3)
        context = "\n".join(m.get("content", "") for m in memories)
        return f"[Context from memory]:\n{context}\n\n{prompt}"

    async def process(self, event: "MammothEvent") -> None:# type: ignore
        if event.event_type == "MEMORY_STORE":
            await self.store(event.payload["content"], event.payload.get("type", "episodic"))

    async def shutdown(self) -> None:
        self.log("INFO", "MemoryAgent shutting down.")
