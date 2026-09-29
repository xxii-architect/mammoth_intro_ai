from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from .base_agent import BaseAgent


SEARCH_SYSTEM = """You are MammothOS's search synthesizer.
Given a query and search result snippets, write a precise, grounded summary.

Return JSON only:
{\"summary\":\"<2-3 sentence synthesis — specific, grounded in the results>\",\"top_source\":\"<title of most relevant result>\",\"confidence\":0.0}"""

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
    @staticmethod
    def _run_async(coro):
        import asyncio
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)
        else:
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(asyncio.run, coro).result()

    async def _llm_summarize(self, results: list, query: str) -> str:
        import json as _j, re as _re
        from mammoth_os.llm_client import get_llm_client
        snippets = "\n".join(
            f"- [{r.get('title', '?')}]: {r.get('snippet', '')[:180]}"
            for r in results[:6]
        ) if results else "(no local results — synthesize from knowledge)"
        raw = await get_llm_client().generate(
            f"Query: {query}\n\nResults:\n{snippets}",
            system_prompt=SEARCH_SYSTEM,
            max_tokens=400,
            temperature=0.2,
        )
        try:
            parsed = _j.loads(raw) if isinstance(raw, str) else raw
            if isinstance(parsed, dict) and parsed.get("summary"):
                return str(parsed["summary"])
        except Exception:
            pass
        if isinstance(raw, str):
            m = _re.search(r'"summary"\s*:\s*"([^"]+)"', raw)
            if m:
                return m.group(1)
            if len(raw) < 400 and not raw.strip().startswith("{"):
                return raw.strip()
            # raw-text fallback for narrative LLM output
            clean = raw.strip()
            if len(clean) > 40:
                return clean[:500]
        return ""



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
        llm_sum = await self._llm_summarize(results or [], query)
        if llm_sum and len(llm_sum) > 30:
            print("  [SearchAgent] LLM summarize active")
            return llm_sum
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
