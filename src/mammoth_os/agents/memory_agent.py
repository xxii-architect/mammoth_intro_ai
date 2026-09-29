from __future__ import annotations

from typing import Any, Dict, List, Optional

from mammoth_os.memory_engine import MemoryEngine
from .base_agent import BaseAgent


class MemoryAgent(BaseAgent):
    """A simple persistent memory layer for agent context and recall."""

    name = "MemoryAgent"

    def __init__(self, router: Any = None, storage_root: Optional[str] = None):
        super().__init__(router)
        self.engine = MemoryEngine({
            "backend": "json",
            "storage_path": str(storage_root or ".mammoth/memory_store.json"),
            "max_entries": 2500,
        })

    def store(self, content: str, memory_type: str = "semantic", metadata: Optional[Dict[str, Any]] = None) -> str:
        return self.engine.store(content, memory_type=memory_type, metadata=metadata)

    async def store_async(self, content: str, memory_type: str = "semantic", metadata: Optional[Dict[str, Any]] = None) -> str:
        return self.store(content, memory_type=memory_type, metadata=metadata)

    def retrieve(self, query: str, top_k: int = 5, memory_type: Optional[str] = None) -> List[Dict[str, Any]]:
        return self.engine.retrieve(query, top_k=top_k, memory_type=memory_type)

    async def retrieve_async(self, query: str, top_k: int = 5, memory_type: Optional[str] = None) -> List[Dict[str, Any]]:
        return self.retrieve(query, top_k=top_k, memory_type=memory_type)

    def forget(self, memory_id: str) -> bool:
        return self.engine.forget(memory_id)

    async def forget_async(self, memory_id: str) -> bool:
        return self.forget(memory_id)

    def consolidate(self, namespace: str) -> int:
        return self.engine.consolidate(namespace)

    async def consolidate_async(self, namespace: str) -> int:
        return self.consolidate(namespace)

    async def inject_context(self, prompt: str, user_id: str = "default") -> str:
        memories = self.retrieve(prompt, top_k=3)
        if not memories:
            return str(prompt)
        context = "\n".join(f"- {item['content']}" for item in memories) 
        return f"[Memory context for {user_id}]\n{context}\n\n{prompt}"

    def run(self, prompt: Any) -> Dict[str, Any]:
        if isinstance(prompt, dict):
            action = str(prompt.get("action") or "store").strip().lower()
            if action == "retrieve":
                results = self.retrieve(str(prompt.get("query") or prompt.get("prompt") or ""), top_k=int(prompt.get("top_k") or 5), memory_type=prompt.get("memory_type"))
                return {"status": "ok", "agent": self.name, "action": "retrieve", "results": results}
            if action == "forget":
                memory_id = str(prompt.get("memory_id") or "").strip()
                return {"status": "ok" if self.forget(memory_id) else "not_found", "agent": self.name, "action": "forget", "memory_id": memory_id}
            if action == "consolidate":
                namespace = str(prompt.get("namespace") or "general").strip()
                merged = self.consolidate(namespace)
                return {"status": "ok", "agent": self.name, "action": "consolidate", "namespace": namespace, "merged_count": merged}
            content = str(prompt.get("content") or prompt.get("prompt") or "").strip()
            if not content:
                return {"status": "needs_context", "agent": self.name, "action": "store", "message": "Memory content is required."}
            memory_id = self.store(content, memory_type=str(prompt.get("memory_type") or "semantic"), metadata=prompt.get("metadata") if isinstance(prompt.get("metadata"), dict) else {})
            return {"status": "ok", "agent": self.name, "action": "store", "memory_id": memory_id, "memory_type": str(prompt.get("memory_type") or "semantic")}

        query = str(prompt or "").strip()
        if not query:
            return {"status": "needs_context", "agent": self.name, "message": "Please provide a query or memory payload."}
        return {"status": "ok", "agent": self.name, "results": self.retrieve(query, top_k=5)}

    async def process(self, event: Any) -> Dict[str, Any]:
        if isinstance(event, dict):
            payload = event.get("payload") if isinstance(event.get("payload"), dict) else event
            content = str(payload.get("content") or payload.get("prompt") or "").strip()
            if not content:
                return {"status": "needs_context", "agent": self.name, "message": "Event payload is missing content."}
            memory_id = self.store(content, memory_type=str(payload.get("type") or payload.get("memory_type") or "episodic"), metadata=payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {})
            return {"status": "ok", "agent": self.name, "memory_id": memory_id, "memory_type": str(payload.get("type") or payload.get("memory_type") or "episodic")}
        return {"status": "error", "agent": self.name, "message": "Unsupported event type."}

    async def shutdown(self) -> None:
        return None
