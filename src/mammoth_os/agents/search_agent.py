class SearchAgent(BaseAgent):# type: ignore
    """
    Unified search agent combining web search APIs with internal vector
    search of the Mammoth OS workspace. Results are ranked by relevance,
    deduplicated, and summarized via ReasoningEngine.
    """

    async def search(self, query: str, sources: list[str] = None) -> dict:# type: ignore
        """
        Execute a hybrid search across web and internal sources.

        Returns:
            {"results": list[dict], "summary": str, "sources": list[str]}
        """
        ...

    async def web_search(self, query: str, limit: int = 10) -> list[dict]:
        """Execute web search via configured search API."""
        ...

    async def internal_search(self, query: str, limit: int = 10) -> list[dict]:
        """Search the VectorStore for internal documents."""
        ...

    async def rank(self, results: list[dict], query: str) -> list[dict]:
        """Re-rank results using semantic relevance scoring."""
        ...

    async def summarize(self, results: list[dict], query: str) -> str:
        """Summarize results into a concise answer."""
        ...

    async def process(self, event: "MammothEvent") -> None:# type: ignore
        if event.event_type == "SEARCH_REQUEST":
            result = await self.search(event.payload["query"])
            await self.emit_event("SEARCH_RESULT", result)

    async def shutdown(self) -> None:
        self.log("INFO", "SearchAgent shutting down.")
