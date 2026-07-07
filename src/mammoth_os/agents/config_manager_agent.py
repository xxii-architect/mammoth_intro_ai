class ConfigManagerAgent(BaseAgent):# type: ignore
    """
    Manages global and per-agent configuration. Supports hot-reload —
    agents receive CONFIG_UPDATED events when their config changes.
    Scopes: global, per-agent, per-environment.
    """

    async def initialize(self) -> None:
        self._configs: dict[str, dict] = {"global": {}}
        self._versions: dict[str, int] = {}
        await self._load_from_disk()

    async def get(self, scope: str, key: str, default=None):
        return self._configs.get(scope, {}).get(key, default)

    async def set(self, scope: str, key: str, value) -> None:
        if scope not in self._configs:
            self._configs[scope] = {}
        self._configs[scope][key] = value
        self._versions[scope] = self._versions.get(scope, 0) + 1
        await self.emit_event("CONFIG_UPDATED", {"scope": scope, "key": key, "value": value})

    async def hot_reload(self, scope: str) -> None:
        """Re-read config from disk and notify relevant agents."""
        await self._load_from_disk(scope=scope)
        await self.emit_event("CONFIG_RELOADED", {"scope": scope})

    async def validate(self, scope: str, schema: dict) -> bool:
        # Validate config against a JSON schema
        import jsonschema# type: ignore
        try:
            jsonschema.validate(self._configs.get(scope, {}), schema)
            return True
        except jsonschema.ValidationError:
            return False

    async def _load_from_disk(self, scope: str = None) -> None:# type: ignore
        import yaml
        import os
        config_path = self.get_config("config_path") or "/etc/mammoth/config.yaml"
        if os.path.exists(config_path):
            with open(config_path) as f:
                self._configs.update(yaml.safe_load(f) or {})

    async def process(self, event: "MammothEvent") -> None:# type: ignore
        pass

    async def shutdown(self) -> None:
        self.log("INFO", "ConfigManagerAgent shutting down.")