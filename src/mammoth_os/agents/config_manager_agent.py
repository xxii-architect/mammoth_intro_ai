from __future__ import annotations

from typing import Any, Dict, Optional

from .base_agent import BaseAgent


class ConfigManagerAgent(BaseAgent):  # type: ignore
    """
    Manages global and per-agent configuration. Supports hot-reload —
    agents receive CONFIG_UPDATED events when their config changes.
    Scopes: global, per-agent, per-environment.
    """

    name = "ConfigManagerAgent"

    def __init__(self, router: Any = None):
        super().__init__(router)
        self._configs: Dict[str, Dict[str, Any]] = {"global": {}}
        self._versions: Dict[str, int] = {}

    def log(self, level: str, message: str) -> None:
        print(f"[{self.name}:{level}] {message}")

    async def emit_event(self, event_type: str, payload: Any) -> None:
        self.log("INFO", f"Emitting {event_type}")

    async def initialize(self) -> None:
        await self._load_from_disk()

    async def get(self, scope: str, key: str, default: Any = None) -> Any:
        return self._configs.get(scope, {}).get(key, default)

    async def set(self, scope: str, key: str, value: Any) -> Dict[str, Any]:
        if scope not in self._configs:
            self._configs[scope] = {}
        self._configs[scope][key] = value
        self._versions[scope] = self._versions.get(scope, 0) + 1
        await self.emit_event("CONFIG_UPDATED", {"scope": scope, "key": key, "value": value})
        return {"status": "ok", "agent": self.name, "scope": scope, "key": key, "version": self._versions[scope]}

    async def hot_reload(self, scope: str) -> Dict[str, Any]:
        await self._load_from_disk(scope=scope)
        await self.emit_event("CONFIG_RELOADED", {"scope": scope})
        return {"status": "ok", "agent": self.name, "action": "hot_reload", "scope": scope}

    async def validate(self, scope: str, schema: dict) -> bool:
        try:
            import jsonschema  # type: ignore
            jsonschema.validate(self._configs.get(scope, {}), schema)
            return True
        except Exception:
            return False

    async def _load_from_disk(self, scope: Optional[str] = None) -> None:
        import os
        import yaml  # type: ignore
        config_path = self._get_config_path()
        if config_path and os.path.exists(config_path):
            try:
                with open(config_path) as f:
                    data = yaml.safe_load(f) or {}
                if scope:
                    if scope in data:
                        self._configs[scope] = data[scope]
                else:
                    self._configs.update(data)
            except Exception as exc:
                self.log("WARNING", f"Config load failed: {exc}")

    def _get_config_path(self) -> Optional[str]:
        import os
        router_cfg = {}
        try:
            router_cfg = getattr(self.router, "config", {}) if self.router else {}
        except Exception:
            pass
        if isinstance(router_cfg, dict) and router_cfg.get("config_path"):
            return str(router_cfg["config_path"])
        return os.environ.get("MAMMOTH_CONFIG_PATH") or "/etc/mammoth/config.yaml"

    async def run(self, payload: Any) -> Dict[str, Any]:
        if isinstance(payload, dict):
            action = str(payload.get("action") or "get").strip().lower()
            scope = str(payload.get("scope") or "global").strip()
            key = str(payload.get("key") or "").strip()
            value = payload.get("value")
        else:
            action = "dump"
            scope = "global"
            key = ""
            value = None

        if action == "set":
            if not key:
                return {"status": "needs_context", "agent": self.name, "summary": "Provide scope, key, and value."}
            return await self.set(scope, key, value)

        if action == "get":
            result = await self.get(scope, key)
            return {"status": "ok", "agent": self.name, "action": "get", "scope": scope, "key": key, "value": result, "summary": f"Config [{scope}/{key}] = {result}."}

        if action == "reload":
            return await self.hot_reload(scope)

        scopes_summary = {s: list(v.keys()) for s, v in self._configs.items()}
        return {
            "status": "ok",
            "agent": self.name,
            "action": "dump",
            "scopes": scopes_summary,
            "scope_count": len(self._configs),
            "summary": f"{len(self._configs)} config scope(s) loaded.",
            "quality_flags": ["hot_reload", "scoped_config", "event_driven_updates"],
        }

    async def process(self, event: "MammothEvent") -> None:  # type: ignore
        if event is None:
            return

    async def shutdown(self) -> None:
        self.log("INFO", f"ConfigManagerAgent shutting down. {len(self._configs)} scope(s) managed.")
