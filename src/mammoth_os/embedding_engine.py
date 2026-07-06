class EmbeddingEngine:
    """
    Generates and caches text embeddings for semantic operations.
    Supports batched embedding for efficiency and cosine similarity.
    """

    def __init__(self, config: dict):
        self.model = config.get("model", "text-embedding-3-large")
        self.cache_ttl = config.get("cache_ttl", 3600)
        self.batch_size = config.get("batch_size", 64)
        self._cache: dict[str, list[float]] = {}

    async def embed(self, text: str) -> list[float]:
        """Generate embedding for a single text string."""
        if text in self._cache:
            return self._cache[text]
        vector = await self._call_model([text])
        self._cache[text] = vector[0]
        return vector[0]

    async def batch_embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of texts."""
        results = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            vectors = await self._call_model(batch)
            results.extend(vectors)
        return results

    async def similarity(self, vec_a: list[float], vec_b: list[float]) -> float:
        """Compute cosine similarity between two vectors."""
        import math
        dot = sum(a * b for a, b in zip(vec_a, vec_b))
        mag = math.sqrt(sum(a ** 2 for a in vec_a)) * math.sqrt(sum(b ** 2 for b in vec_b))
        return dot / (mag + 1e-9)

    async def _call_model(self, texts: list[str]) -> list[list[float]]:
        """Call the configured embedding model API."""
        ...