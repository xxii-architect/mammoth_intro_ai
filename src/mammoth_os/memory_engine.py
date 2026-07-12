class MemoryEngine:
    """
    Unified vector + graph memory store. Combines episodic memory
    (ordered event sequences) with semantic memory (factual knowledge).
    Supports multiple backends via adapter pattern.
    """

    def __init__(self, config: dict):
        self.backend = config.get("backend", "pgvector")
        self.embedding_model = config.get("embedding_model", "text-embedding-3-large")
        self.max_entries = config.get("max_entries", 100000)

    async def store(self, content: str, memory_type: str = "semantic", metadata: dict = None) -> str:# type: ignore
        """Store content with embedding. Returns memory_id."""
        ...

    async def retrieve(self, query: str, top_k: int = 5, memory_type: str = None) -> list[dict]:# type: ignore
        """Semantic search across stored memories."""
        ...

    async def forget(self, memory_id: str) -> bool:# type: ignore
        """Remove a memory entry by ID."""
        ...

    async def consolidate(self, namespace: str) -> int:# type: ignore
        """Merge near-duplicate memories. Returns count merged."""
