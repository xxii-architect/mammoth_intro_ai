from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from .base_agent import BaseAgent


class SearchAgent(BaseAgent):# type: ignore
    """
    Unified search agent combining lightweight workspace search with optional
    caller-provided web results.
    """

    name = "SearchAgent"

    def __init__(self, router: Any = None):
        super().__init__(router)
        self._repo_root = Path(__file__).resolve().parents[3]

    def log(self, level: str, message: str) -> None:
        print(f"[{self.name}:{level}] {message}")

    async def web_search(self, query: str, limit: int = 10) -> list[dict]:
        return [{
            "title": "External web search not configured",
            "snippet": f"Provide fetched sources for '{query}' or integrate a search provider.",
            "source": "web",
            "url": "",
            "score": 0.15,
        }][: max(1, limit)]

    async def internal_search(self, query: str, limit: int = 10) -> list[dict]:
        lowered = str(query or "").strip().lower()
        if not lowered:
            return []
        results: List[Dict[str, Any]] = []
        for path in self._repo_root.rglob("*.py"):
            try:
                text = path.read_text(encoding="utf-8")
            except Exception:
                continue
            hit_count = text.lower().count(lowered)
            if not hit_count:
                continue
            first_line = next((line.strip() for line in text.splitlines() if lowered in line.lower()), "")
            results.append({
                "title": path.name,
                "snippet": first_line[:220],
                "source": "workspace",
                "path": str(path.relative_to(self._repo_root)),
                "score": min(0.95, 0.4 + (hit_count * 0.08)),
            })
        results.sort(key=lambda item: float(item.get("score") or 0), reverse=True)
        return results[: max(1, limit)]

    async def rank(self, results: list[dict], query: str) -> list[dict]:
        lowered = str(query or "").lower()
        ranked = []
        for item in results:
            snippet = str(item.get("snippet") or "").lower()
            title = str(item.get("title") or "").lower()
            score = float(item.get("score") or 0)
            if lowered and lowered in title:
                score += 0.2
            if lowered and lowered in snippet:
                score += 0.1
            ranked.append({**item, "score": round(min(score, 0.99), 2)})
        ranked.sort(key=lambda item: float(item.get("score") or 0), reverse=True)
        return ranked

    async def summarize(self, results: list[dict], query: str) -> str:
        if not results:
            return f"No search evidence found for {query}."
        top = results[0]
        return f"Top match for {query}: {top.get('title')} from {top.get('source')}."

    async def search(self, query: str, sources: list[str] = None) -> dict:# type: ignore
        provided = []
        for item in sources or []:
            text = str(item or "").strip()
            if text:
                provided.append({"title": "Provided source", "snippet": text[:220], "source": "provided", "score": 0.55})
        internal = await self.internal_search(query, limit=8)
        results = await self.rank([*provided, *internal], query)
        summary = await self.summarize(results[:8], query)
        return {
            "query": query,
            "results": results[:8],
            "summary": summary,
            "sources": sorted({str(item.get("source") or "unknown") for item in results[:8]}),
            "quality_flags": ["grounded_search"] if results else ["no_results"],
        }

    async def run(self, payload: Any) -> Dict[str, Any]:
        if isinstance(payload, dict):
            query = str(payload.get("query") or payload.get("prompt") or "").strip()
            sources = payload.get("sources") if isinstance(payload.get("sources"), list) else []
        else:
            query = str(payload or "").strip()
            sources = []
        if not query:
            return {"status": "needs_context", "agent": self.name, "summary": "Provide a search query.", "results": [], "quality_flags": ["missing_query"]}
        result = await self.search(query, sources=sources)
        return {"status": "ok", "agent": self.name, **result}

    async def emit_event(self, event_type: str, payload: Any) -> None:
        self.log("INFO", f"Emitting {event_type} without a transport")

    async def process(self, event: "MammothEvent") -> None:# type: ignore
        if event.event_type == "SEARCH_REQUEST":
            result = await self.search(event.payload["query"], event.payload.get("sources"))
            await self.emit_event("SEARCH_RESULT", result)

    async def shutdown(self) -> None:
        self.log("INFO", "SearchAgent shutting down.")
