"""
memory_engine.py — JSON-file-backed MemoryEngine
Replaces the async stub. All methods are synchronous so MemoryAgent
can call them directly. MemoryAgent.store_async / retrieve_async
wrappers continue to work since they just call the sync methods.
"""
from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


class MemoryEngine:
    """
    Unified vector + graph memory store. Combines episodic memory
    (ordered event sequences) with semantic memory (factual knowledge).
    JSON-file backend — suitable for single-node deployments.
    """

    def __init__(self, config: dict):
        self.backend = config.get("backend", "json")
        self.embedding_model = config.get("embedding_model", "text-embedding-3-large")
        self.max_entries = int(config.get("max_entries") or 2500)
        raw_path = config.get("storage_path") or ".mammoth/memory_store.json"
        self._path = Path(raw_path)
        self._lock = threading.Lock()
        # Ensure parent directory exists
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists():
            self._path.write_text("[]", encoding="utf-8")

    # ── private helpers ──────────────────────────────────────────

    def _load(self) -> List[Dict[str, Any]]:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, OSError):
            return []

    def _save(self, entries: List[Dict[str, Any]]) -> None:
        # Enforce max_entries cap (keep newest)
        if len(entries) > self.max_entries:
            entries = entries[-self.max_entries:]
        self._path.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _score(entry: Dict[str, Any], query: str) -> float:
        """Simple keyword overlap score — good enough for JSON backend."""
        q_tokens = set(query.lower().split())
        content = str(entry.get("content") or "").lower()
        if not q_tokens:
            return 0.0
        hits = sum(1 for t in q_tokens if t in content)
        return hits / len(q_tokens)

    # ── public API (synchronous) ─────────────────────────────────

    def store(self, content: str, memory_type: str = "semantic", metadata: Optional[Dict[str, Any]] = None) -> str:
        """Store content. Returns memory_id."""
        memory_id = str(uuid.uuid4())
        entry = {
            "id": memory_id,
            "content": str(content),
            "memory_type": str(memory_type or "semantic"),
            "metadata": metadata if isinstance(metadata, dict) else {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        with self._lock:
            entries = self._load()
            entries.append(entry)
            self._save(entries)
        return memory_id

    def retrieve(self, query: str, top_k: int = 5, memory_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Keyword search across stored memories. Returns top_k results."""
        with self._lock:
            entries = self._load()
        if memory_type:
            entries = [e for e in entries if e.get("memory_type") == memory_type]
        scored = sorted(entries, key=lambda e: self._score(e, query or ""), reverse=True)
        return scored[:max(1, int(top_k))]

    def forget(self, memory_id: str) -> bool:
        """Remove a memory entry by ID. Returns True if found and removed."""
        with self._lock:
            entries = self._load()
            before = len(entries)
            entries = [e for e in entries if e.get("id") != memory_id]
            if len(entries) == before:
                return False
            self._save(entries)
        return True

    def consolidate(self, namespace: str) -> int:
        """
        Merge near-duplicate memories within a namespace.
        For the JSON backend this is a no-op that returns 0
        (embeddings required for true deduplication).
        """
        return 0
