from __future__ import annotations

import math
import uuid
import datetime
from typing import Any, Dict, List, Optional

from mammoth_os.agents.base_agent import BaseAgent  # type: ignore


class VectorStoreAgent(BaseAgent):  # type: ignore
    """
    Manages embedding storage and semantic search using in-process cosine similarity.
    Supports namespaced, privacy-scoped collections with TTL and tagging.
    Designed to be backed by pgvector or a local store.
    """

    name = "VectorStoreAgent"

    def __init__(self, router: Any = None):
        super().__init__(router)
        self._collections: Dict[str, List[Dict[str, Any]]] = {}
        self._privacy_scoped: Dict[str, str] = {}  # collection -> user_id scope

    def log(self, level: str, message: str) -> None:
        print(f"[{self.name}:{level}] {message}")

    async def emit_event(self, event_type: str, payload: Any) -> None:
        self.log("INFO", f"Emitting {event_type}")

    def _cosine_sim(self, a: List[float], b: List[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        mag_a = math.sqrt(sum(x ** 2 for x in a))
        mag_b = math.sqrt(sum(x ** 2 for x in b))
        return dot / (mag_a * mag_b + 1e-9)

    def _is_expired(self, doc: Dict[str, Any]) -> bool:
        expires_at = doc.get("expires_at")
        if not expires_at:
            return False
        try:
            return datetime.datetime.fromisoformat(expires_at) < datetime.datetime.now(datetime.timezone.utc)
        except Exception:
            return False

    def _collection_for_user(self, collection: str, user_id: Optional[str]) -> str:
        if user_id:
            return f"user:{user_id}:{collection}"
        return collection

    async def upsert(
        self,
        collection: str,
        doc_id: str,
        vector: List[float],
        metadata: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
        ttl_sec: Optional[int] = None,
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        scoped = self._collection_for_user(collection, user_id)
        if scoped not in self._collections:
            self._collections[scoped] = []
        expires_at = None
        if ttl_sec and ttl_sec > 0:
            expires_at = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=ttl_sec)).isoformat()
        entry = {
            "id": doc_id,
            "vector": vector,
            "metadata": metadata or {},
            "tags": tags or [],
            "user_id": user_id,
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "expires_at": expires_at,
        }
        self._collections[scoped] = [d for d in self._collections[scoped] if d["id"] != doc_id]
        self._collections[scoped].append(entry)
        return {"status": "ok", "agent": self.name, "action": "upsert", "collection": scoped, "doc_id": doc_id, "summary": f"Upserted {doc_id} into {scoped}."}

    async def search(
        self,
        collection: str,
        query_vector: List[float],
        top_k: int = 10,
        user_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        scoped = self._collection_for_user(collection, user_id)
        store = [d for d in self._collections.get(scoped, []) if not self._is_expired(d)]
        if tags:
            store = [d for d in store if any(t in (d.get("tags") or []) for t in tags)]
        scored = [(self._cosine_sim(query_vector, d["vector"]), d) for d in store if d.get("vector")]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [{"score": round(s, 4), **{k: v for k, v in d.items() if k != "vector"}} for s, d in scored[:top_k]]

    async def delete(self, collection: str, doc_id: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        scoped = self._collection_for_user(collection, user_id)
        before = len(self._collections.get(scoped, []))
        self._collections[scoped] = [d for d in self._collections.get(scoped, []) if d["id"] != doc_id]
        after = len(self._collections.get(scoped, []))
        return {"status": "ok", "agent": self.name, "action": "delete", "collection": scoped, "doc_id": doc_id, "deleted": before - after}

    async def purge_expired(self, collection: Optional[str] = None) -> Dict[str, Any]:
        purged = 0
        keys = [collection] if collection else list(self._collections.keys())
        for key in keys:
            before = len(self._collections.get(key, []))
            self._collections[key] = [d for d in self._collections.get(key, []) if not self._is_expired(d)]
            purged += before - len(self._collections[key])
        return {"status": "ok", "agent": self.name, "action": "purge_expired", "purged": purged, "summary": f"Purged {purged} expired document(s)."}

    async def run(self, payload: Any) -> Dict[str, Any]:
        if isinstance(payload, dict):
            action = str(payload.get("action") or "status").strip().lower()
            collection = str(payload.get("collection") or "default").strip()
            doc_id = str(payload.get("doc_id") or uuid.uuid4()).strip()
            vector = payload.get("vector") or []
            query_vector = payload.get("query_vector") or vector
            top_k = int(payload.get("top_k") or 10)
            metadata = payload.get("metadata") or {}
            user_id = payload.get("user_id")
            tags = payload.get("tags") or []
            ttl_sec = payload.get("ttl_sec")
        else:
            action = "status"
            collection = "default"
            doc_id = str(uuid.uuid4())
            vector = []
            query_vector = []
            top_k = 10
            metadata = {}
            user_id = None
            tags = []
            ttl_sec = None

        if action == "upsert":
            if not vector:
                return {"status": "needs_context", "agent": self.name, "summary": "Provide a vector to upsert."}
            return await self.upsert(collection, doc_id, vector, metadata=metadata, user_id=user_id, ttl_sec=ttl_sec, tags=tags)

        if action == "search":
            if not query_vector:
                return {"status": "needs_context", "agent": self.name, "summary": "Provide a query_vector to search."}
            results = await self.search(collection, query_vector, top_k=top_k, user_id=user_id, tags=tags)
            return {"status": "ok", "agent": self.name, "action": "search", "collection": collection, "results": results, "count": len(results), "summary": f"Found {len(results)} result(s)."}

        if action == "delete":
            return await self.delete(collection, doc_id, user_id=user_id)

        if action == "purge_expired":
            return await self.purge_expired(collection if collection != "default" else None)

        total_docs = sum(len(v) for v in self._collections.values())
        return {
            "status": "ok",
            "agent": self.name,
            "action": "status",
            "collections": list(self._collections.keys()),
            "collection_count": len(self._collections),
            "total_docs": total_docs,
            "summary": f"{total_docs} document(s) across {len(self._collections)} collection(s).",
            "quality_flags": ["cosine_similarity", "privacy_scoped_collections", "ttl_support", "tag_filtering"],
        }

    async def process(self, event: "MammothEvent") -> None:  # type: ignore
        if event is None:
            return
        et = getattr(event, "event_type", None)
        if et in ("VECTOR_UPSERT", "VECTOR_SEARCH"):
            payload = getattr(event, "payload", {}) or {}
            action = "upsert" if et == "VECTOR_UPSERT" else "search"
            await self.run({"action": action, **payload})

    async def shutdown(self) -> None:
        self.log("INFO", f"VectorStoreAgent shutting down. {sum(len(v) for v in self._collections.values())} document(s) in store.")

