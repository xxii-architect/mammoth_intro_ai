from mammoth_os.agents.base_agent import BaseAgent  # type: ignore

class VectorStoreAgent(BaseAgent):# type: ignore
    """
    Manages embedding storage and semantic search using pgvector.
    Supports namespaced collections for isolation between agent contexts.
    """

    async def initialize(self) -> None:
        self._backend = self.get_config("backend") or "pgvector"
        self._embedding_dim = self.get_config("embedding_dim") or 1536
        self._collections: dict[str, list] = {}

    async def upsert(self, collection: str, doc_id: str, vector: list[float], metadata: dict = None) -> None:# type: ignore
        if collection not in self._collections:
            self._collections[collection] = []
        self._collections[collection].append({
            "id": doc_id, "vector": vector, "metadata": metadata or {}
        })

    async def search(
        self, collection: str, query_vector: list[float], top_k: int = 10
    ) -> list[dict]:
        import math
        store = self._collections.get(collection, [])

        def cosine_sim(a, b):
            dot = sum(x * y for x, y in zip(a, b))
            mag_a = math.sqrt(sum(x ** 2 for x in a))
            mag_b = math.sqrt(sum(x ** 2 for x in b))
            return dot / (mag_a * mag_b + 1e-9)

        scored = [(cosine_sim(query_vector, d["vector"]), d) for d in store]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [{"score": s, **d} for s, d in scored[:top_k]]

    async def delete(self, collection: str, doc_id: str) -> None:
        if collection in self._collections:
            self._collections[collection] = [
                d for d in self._collections[collection] if d["id"] != doc_id
            ]

    async def process(self, event: "MammothEvent") -> None:# type: ignore
        pass

    async def shutdown(self) -> None:
        self.log("INFO", "VectorStoreAgent shutting down.")