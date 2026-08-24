import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().lower()


def _tokenize(value: str) -> List[str]:
    text = _normalize_text(value)
    if not text:
        return []
    return [token for token in re.findall(r"[a-z0-9]+", text) if len(token) > 1]


class MemoryEngine:
    """
    Lightweight durable memory store for agent context and learning traces.
    It persists a JSON-backed store so the app continues to function without a
    vector backend while still offering semantic-style ranking and consolidation.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        config = config or {}
        self.backend = str(config.get("backend") or "json").strip().lower() or "json"
        self.embedding_model = str(config.get("embedding_model") or "text-embedding-3-large").strip()
        self.max_entries = int(config.get("max_entries") or 10000)
        self.storage_path = Path(str(config.get("storage_path") or ".mammoth/memory_store.json")).resolve()
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._entries: List[Dict[str, Any]] = self._load_entries()

    def _load_entries(self) -> List[Dict[str, Any]]:
        if not self.storage_path.exists():
            return []
        try:
            payload = json.loads(self.storage_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        if not isinstance(payload, list):
            return []
        return [item for item in payload if isinstance(item, dict)]

    def _save_entries(self) -> None:
        self.storage_path.write_text(json.dumps(self._entries, indent=2, default=str), encoding="utf-8")

    def _score_match(self, query: str, content: str, memory_type: str = "semantic") -> float:
        q_tokens = set(_tokenize(query))
        c_tokens = set(_tokenize(content))
        if not q_tokens or not c_tokens:
            return 0.0
        overlap = len(q_tokens & c_tokens)
        if not overlap:
            return 0.0
        base = overlap / max(1, len(q_tokens | c_tokens))
        type_bonus = 0.15 if memory_type == "semantic" else 0.05
        return round(base + type_bonus, 4)

    def store(self, content: str, memory_type: str = "semantic", metadata: Optional[Dict[str, Any]] = None) -> str:
        if content is None:
            raise ValueError("Memory content cannot be None")
        cleaned = str(content).strip()
        if not cleaned:
            raise ValueError("Memory content cannot be empty")
        entry = {
            "id": f"mem-{len(self._entries) + 1}-{abs(hash(cleaned)) & 0xFFFFFFFF:08x}",
            "content": cleaned,
            "memory_type": str(memory_type or "semantic").strip() or "semantic",
            "metadata": metadata or {},
            "created_at": _utc_now(),
            "updated_at": _utc_now(),
        }
        self._entries.append(entry)
        if len(self._entries) > self.max_entries:
            self._entries = self._entries[-self.max_entries:]
        self._save_entries()
        return entry["id"]

    def retrieve(self, query: str, top_k: int = 5, memory_type: Optional[str] = None) -> List[Dict[str, Any]]:
        if not query or not str(query).strip():
            return []
        query_text = str(query).strip()
        scored: List[Dict[str, Any]] = []
        for entry in self._entries:
            type_name = str(entry.get("memory_type") or "semantic")
            if memory_type and type_name != memory_type:
                continue
            score = self._score_match(query_text, str(entry.get("content") or ""), type_name)
            if score <= 0 and query_text.lower() in str(entry.get("content") or "").lower():
                score = 0.2
            if score > 0:
                scored.append({
                    "id": entry.get("id"),
                    "content": entry.get("content"),
                    "memory_type": type_name,
                    "score": score,
                    "metadata": entry.get("metadata") or {},
                    "updated_at": entry.get("updated_at") or entry.get("created_at"),
                })
        scored.sort(key=lambda item: item["score"], reverse=True)
        return scored[: max(1, int(top_k))]

    def forget(self, memory_id: str) -> bool:
        before = len(self._entries)
        self._entries = [entry for entry in self._entries if str(entry.get("id") or "") != str(memory_id)]
        if len(self._entries) != before:
            self._save_entries()
            return True
        return False

    def consolidate(self, namespace: str) -> int:
        namespace_name = str(namespace or "").strip()
        if not namespace_name:
            return 0
        matches = []
        for entry in self._entries:
            metadata = entry.get("metadata") or {}
            specific_namespace = str(metadata.get("namespace") or "").strip()
            if specific_namespace and specific_namespace != namespace_name:
                continue
            matches.append(entry)
        if not matches:
            return 0
        merged_count = 0
        survivors: List[Dict[str, Any]] = []
        seen_ids = set()
        for entry in matches:
            entry_id = str(entry.get("id") or "")
            if entry_id in seen_ids:
                continue
            group = [entry]
            base_tokens = set(_tokenize(str(entry.get("content") or "")))
            for other in matches:
                other_id = str(other.get("id") or "")
                if other_id == entry_id or other_id in seen_ids:
                    continue
                other_tokens = set(_tokenize(str(other.get("content") or "")))
                if not base_tokens or not other_tokens:
                    continue
                similarity = len(base_tokens & other_tokens) / max(1, len(base_tokens | other_tokens))
                if similarity >= 0.75:
                    group.append(other)
                    seen_ids.add(other_id)
            if len(group) > 1:
                merged_count += len(group) - 1
                primary = dict(group[0])
                primary["content"] = "\n".join(str(item.get("content") or "") for item in group if str(item.get("content") or "").strip())
                primary["metadata"] = {
                    **(group[0].get("metadata") or {}),
                    "namespace": namespace_name,
                    "merged_from": [str(item.get("id") or "") for item in group[1:]],
                }
                primary["updated_at"] = _utc_now()
                survivors.append(primary)
                seen_ids.add(entry_id)
            else:
                survivors.append(dict(entry))
                seen_ids.add(entry_id)
        self._entries = [entry for entry in self._entries if str(entry.get("id") or "") not in {str(item.get("id") or "") for item in matches}]
        self._entries.extend(survivors)
        self._save_entries()
        return merged_count

    async def store_async(self, content: str, memory_type: str = "semantic", metadata: Optional[Dict[str, Any]] = None) -> str:
        return self.store(content, memory_type=memory_type, metadata=metadata)

    async def retrieve_async(self, query: str, top_k: int = 5, memory_type: Optional[str] = None) -> List[Dict[str, Any]]:
        return self.retrieve(query, top_k=top_k, memory_type=memory_type)

    async def forget_async(self, memory_id: str) -> bool:
        return self.forget(memory_id)

    async def consolidate_async(self, namespace: str) -> int:
        return self.consolidate(namespace)

    def __len__(self) -> int:
        return len(self._entries)

    def snapshot(self) -> Dict[str, Any]:
        return {
            "backend": self.backend,
            "embedding_model": self.embedding_model,
            "total_entries": len(self._entries),
            "entries": self._entries[-10:],
        }
