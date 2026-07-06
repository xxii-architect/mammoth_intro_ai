class EventBusEngine:
    """
    Central pub/sub event routing using Redis Streams or Kafka.
    All inter-agent communication flows through this engine.
    Supports event replay for crash recovery.
    """

    def __init__(self, config: dict):
        self.backend = config.get("backend", "redis")
        self.retention_ms = config.get("retention_ms", 86400000)
        self._subscribers: dict[str, list[callable]] = {}# type: ignore

    async def publish(self, event: "MammothEvent") -> str:# type: ignore
        """Publish an event. Returns the event stream ID."""
        ...

    async def subscribe(self, event_type: str, handler: callable) -> None:# type: ignore
        """Subscribe a handler function to an event type pattern."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)

    async def unsubscribe(self, event_type: str, handler: callable) -> None:# type: ignore
        if event_type in self._subscribers:
            self._subscribers[event_type].remove(handler)

    async def replay(self, event_type: str, from_timestamp: str, to_timestamp: str = None) -> list:# type: ignore
        """Replay events from a time range for recovery or audit."""
        ...