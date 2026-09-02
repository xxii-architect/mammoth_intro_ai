from __future__ import annotations

import fnmatch
import time
from typing import Any, Dict

from .base_agent import BaseAgent


class CacheAgent(BaseAgent):# type: ignore
    """Cache agent with Redis-when-available and in-memory fallback."""

    name = "CacheAgent"

    def __init__(self, router: Any = None):
        super().__init__(router)
        self._redis = None
        self._fallback_store: Dict[str, Dict[str, Any]] = {}

    def log(self, level: str, message: str) -> None:
        print(f"[{self.name}:{level}] {message}")

    async def initialize(self) -> None:
        try:
            import redis.asyncio as aioredis  # type: ignore
        except Exception:
            self._redis = None
            return
        host = getattr(self, "get_config", lambda *_: None)("redis_host") or "localhost"
        port = getattr(self, "get_config", lambda *_: None)("redis_port") or 6379
        try:
            self._redis = aioredis.from_url(f"redis://{host}:{port}")
        except Exception:
            self._redis = None

    def _purge_expired(self) -> None:
        now = time.time()
        for key in list(self._fallback_store):
            expires_at = self._fallback_store[key].get("expires_at")
            if isinstance(expires_at, (int, float)) and expires_at <= now:
                self._fallback_store.pop(key, None)

    async def get(self, key: str) -> str | None:
        if self._redis is not None:
            value = await self._redis.get(key)
            if value is None:
                return None
            return value.decode("utf-8") if isinstance(value, bytes) else str(value)
        self._purge_expired()
        entry = self._fallback_store.get(key)
        return str(entry.get("value")) if entry else None

    async def set(self, key: str, value: str, ttl_sec: int = 300) -> None:
        if self._redis is not None:
            await self._redis.set(key, value, ex=ttl_sec)
            return
        self._fallback_store[key] = {"value": value, "expires_at": time.time() + max(1, ttl_sec)}

    async def delete(self, key: str) -> None:
        if self._redis is not None:
            await self._redis.delete(key)
            return
        self._fallback_store.pop(key, None)

    async def invalidate_pattern(self, pattern: str) -> int:
        if self._redis is not None:
            keys = await self._redis.keys(pattern)
            if keys:
                return int(await self._redis.delete(*keys))
            return 0
        self._purge_expired()
        deleted = 0
        for key in list(self._fallback_store):
            if fnmatch.fnmatch(key, pattern):
                self._fallback_store.pop(key, None)
                deleted += 1
        return deleted

    async def run(self, payload: Any) -> Dict[str, Any]:
        body = payload if isinstance(payload, dict) else {"action": "get", "key": str(payload or "").strip()}
        action = str(body.get("action") or "get").strip().lower()
        key = str(body.get("key") or "").strip()
        pattern = str(body.get("pattern") or key or "*").strip()
        ttl_sec = int(body.get("ttl_sec") or 300)
        if action == "set":
            await self.set(key, str(body.get("value") or ""), ttl_sec)
            return {"status": "ok", "agent": self.name, "action": action, "key": key, "ttl_sec": ttl_sec, "summary": f"Cached value for {key}."}
        if action == "delete":
            await self.delete(key)
            return {"status": "ok", "agent": self.name, "action": action, "key": key, "summary": f"Deleted cache key {key}."}
        if action == "invalidate":
            deleted = await self.invalidate_pattern(pattern)
            return {"status": "ok", "agent": self.name, "action": action, "pattern": pattern, "deleted": deleted, "summary": f"Invalidated {deleted} cache entries for {pattern}."}
        if action == "stats":
            self._purge_expired()
            return {"status": "ok", "agent": self.name, "action": action, "backend": "redis" if self._redis is not None else "memory", "entry_count": len(self._fallback_store), "summary": "Cache stats collected."}
        value = await self.get(key)
        return {"status": "ok", "agent": self.name, "action": "get", "key": key, "value": value, "hit": value is not None, "summary": f"Cache lookup {'hit' if value is not None else 'miss'} for {key}."}

    async def emit_event(self, event_type: str, payload: Any) -> None:
        self.log("INFO", f"Emitting {event_type} without a transport")

    async def process(self, event: "MammothEvent") -> None:# type: ignore
        if event.event_type == "CACHE_INVALIDATE":
            result = await self.run({"action": "invalidate", "pattern": event.payload.get("pattern", "*")})
            await self.emit_event("CACHE_RESULT", result)

    async def shutdown(self) -> None:
        if self._redis is not None:
            await self._redis.aclose()
