from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from .base_agent import BaseAgent


class EvolutionAgent(BaseAgent):# type: ignore
    """
    Monitors agent implementation maturity, suggests upgrades, and provides
    simple comparison scaffolding for iterative improvement work.
    """

    name = "EvolutionAgent"

    def __init__(self, router: Any = None):
        super().__init__(router)
        self._agents_dir = Path(__file__).resolve().parent

    def log(self, level: str, message: str) -> None:
        print(f"[{self.name}:{level}] {message}")

    async def analyze_performance(self) -> dict:
        metrics = []
        for path in sorted(self._agents_dir.glob("*_agent.py")):
            if path.name == "base_agent.py":
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except Exception:
                continue
            metrics.append({
                "agent_id": path.stem,
                "line_count": len(text.splitlines()),
                "has_run": " run(" in text or "async def run" in text or "def run" in text,
                "has_process": "def process" in text,
            })
        healthy = [item for item in metrics if item["has_run"] and item["has_process"]]
        return {
            "agent_count": len(metrics),
            "healthy_surface_count": len(healthy),
            "coverage_ratio": round((len(healthy) / len(metrics)) if metrics else 0.0, 2),
            "metrics": metrics[:20],
        }

    async def suggest_upgrades(self) -> list[dict]:
        performance = await self.analyze_performance()
        suggestions = []
        for metric in performance["metrics"]:
            if not metric["has_run"]:
                suggestions.append({"agent_id": metric["agent_id"], "priority": "high", "upgrade": "add standard run entrypoint"})
            elif metric["line_count"] < 40:
                suggestions.append({"agent_id": metric["agent_id"], "priority": "medium", "upgrade": "expand structured output and observability"})
        return suggestions[:10]

    async def run_ab_test(self, agent_a: str, agent_b: str, traffic_pct: float = 50) -> dict:
        traffic_pct = max(0.0, min(100.0, float(traffic_pct)))
        return {
            "agent_a": agent_a,
            "agent_b": agent_b,
            "traffic_pct": traffic_pct,
            "status": "planned",
            "summary": f"Route {traffic_pct:.0f}% of comparison traffic to {agent_b} while preserving {100 - traffic_pct:.0f}% on {agent_a}.",
        }

    async def detect_regression(self, agent_id: str) -> bool:
        path = self._agents_dir / f"{agent_id}.py"
        if not path.exists():
            return True
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            return True
        return " run(" not in text and "async def run" not in text and "def run" not in text

    async def run(self, payload: Any) -> Dict[str, Any]:
        body = payload if isinstance(payload, dict) else {"action": "analyze"}
        action = str(body.get("action") or "analyze").strip().lower()
        if action == "suggest":
            suggestions = await self.suggest_upgrades()
            return {"status": "ok", "agent": self.name, "action": action, "suggestions": suggestions, "summary": f"Generated {len(suggestions)} upgrade suggestions."}
        if action == "ab_test":
            result = await self.run_ab_test(str(body.get("agent_a") or ""), str(body.get("agent_b") or ""), float(body.get("traffic_pct") or 50))
            return {"status": "ok", "agent": self.name, "action": action, **result}
        if action == "regression":
            agent_id = str(body.get("agent_id") or "").strip()
            regressed = await self.detect_regression(agent_id)
            return {"status": "ok", "agent": self.name, "action": action, "agent_id": agent_id, "regressed": regressed}
        report = await self.analyze_performance()
        return {"status": "ok", "agent": self.name, "action": "analyze", **report}

    async def emit_event(self, event_type: str, payload: Any) -> None:
        self.log("INFO", f"Emitting {event_type} without a transport")

    async def process(self, event: "MammothEvent") -> None:# type: ignore
        if event.event_type == "EVOLUTION_ANALYZE":
            result = await self.analyze_performance()
            await self.emit_event("EVOLUTION_REPORT", result)

    async def shutdown(self) -> None:
        self.log("INFO", "EvolutionAgent shutting down.")
