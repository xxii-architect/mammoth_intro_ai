class FileSystemAgent(BaseAgent):# type: ignore
    """
    Abstracts all file system operations. Provides a virtual file
    layer that can be backed by local disk, S3, or GCS. Emits
    FILESYSTEM_CHANGED events when watched paths are modified.
    """

    async def initialize(self) -> None:
        self._watchers: dict[str, any] = {}# type: ignore
        self._base_path = self.get_config("base_path") or "/mammoth/workspace"

    async def read(self, path: str) -> str:
        full = self._resolve(path)
        with open(full, "r", encoding="utf-8") as f:
            return f.read()

    async def write(self, path: str, content: str) -> None:
        import os
        full = self._resolve(path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(content)
        await self.emit_event("FILESYSTEM_CHANGED", {"path": path, "action": "write"})

    async def delete(self, path: str) -> None:
        import os
        os.remove(self._resolve(path))
        await self.emit_event("FILESYSTEM_CHANGED", {"path": path, "action": "delete"})

    async def index_directory(self, path: str, recursive: bool = True) -> list[str]:
        import os
        files = []
        for root, dirs, filenames in os.walk(self._resolve(path)):
            for fn in filenames:
                files.append(os.path.join(root, fn))
            if not recursive:
                break
        return files

    async def watch(self, path: str) -> None:
        """Register a path for filesystem change notifications."""
        self._watchers[path] = True
        self.log("INFO", "Watching path: %s", path)

    def _resolve(self, path: str) -> str:
        import os
        return os.path.join(self._base_path, path.lstrip("/"))

    async def process(self, event: "MammothEvent") -> None:# type: ignore
        if event.event_type == "FILESYSTEM_OP":
            op = event.payload.get("operation")
            path = event.payload.get("path")
            if op == "read":
                return await self.read(path)# type: ignore
            elif op == "write":
                return await self.write(path, event.payload.get("content", ""))

    async def shutdown(self) -> None:
        self.log("INFO", "FileSystemAgent shutting down.")
