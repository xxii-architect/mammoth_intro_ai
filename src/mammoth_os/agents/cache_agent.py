class CacheAgent(BaseAgent):# type: ignore
    """Redis-backed cache with TTL management and pattern-based invalidation."""

    async def initialize(self) -> None:
        import redis.asyncio as aioredis# type: ignore
        host = self.get_config("redis_host") or "localhost"
        port = self.get_config("redis_port") or 6379
        self._redis = aioredis.from_url(f"redis://{host}:{port}")

    async def get(self, key: str) -> str | None:
        return await self._redis.get(key)

    async def set(self, key: str, value: str, ttl_sec: int = 300) -> None:
        await self._redis.set(key, value, ex=ttl_sec)

    async def delete(self, key: str) -> None:
        await self._redis.delete(key)

    async def invalidate_pattern(self, pattern: str) -> int:
        keys = await self._redis.keys(pattern)
        if keys:
            return await self._redis.delete(*keys)
        return 0

    async def process(self, event: "MammothEvent") -> None:# type: ignore
        if event.event_type == "CACHE_INVALIDATE":
            await self.invalidate_pattern(event.payload.get("pattern", "*"))

    async def shutdown(self) -> None:
        await self._redis.aclose()