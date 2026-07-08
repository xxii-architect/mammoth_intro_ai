# mammoth_os/engine_registry.py
# Unified Engine Registry for Mammoth OS

from __future__ import annotations
import inspect
import pkgutil
import importlib
from typing import Dict, Any, Optional

import mammoth_os  # root package


class EngineRegistry:
    """Discovers and registers all engine classes inside mammoth_os."""

    _engines: Dict[str, Any] = {}

    @classmethod
    def discover_engines(cls) -> None:
        """Auto-import all modules under mammoth_os and register engine classes."""
        package_path = mammoth_os.__path__

        for _, module_name, _ in pkgutil.walk_packages(package_path, prefix="mammoth_os."):
            try:
                module = importlib.import_module(module_name)
            except Exception:
                continue

            for name, obj in inspect.getmembers(module, inspect.isclass):
                # Engines follow naming convention: SomethingEngine
                if name.endswith("Engine"):
                    cls._engines[name] = obj

    @classmethod
    def list_engines(cls) -> Dict[str, str]:
        if not cls._engines:
            cls.discover_engines()
        return {name: engine.__module__ for name, engine in cls._engines.items()}

    @classmethod
    def get_engine(cls, name: str) -> Optional[Any]:
        if not cls._engines:
            cls.discover_engines()
        return cls._engines.get(name)


# Singleton
engine_registry = EngineRegistry()
