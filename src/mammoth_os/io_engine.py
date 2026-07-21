class IOEngine:
    """Manages all I/O operations: file, network, and stream. Provides
    buffered reads, async writes, and directory watching."""

    async def read(self, path: str, encoding: str = "utf-8") -> str:
        async with aiofiles.open(path, encoding=encoding) as f:# type: ignore
            return await f.read()

    async def write(self, path: str, content: str, mode: str = "w") -> None:
        import aiofiles
        async with aiofiles.open(path, mode=mode) as f:# type: ignore
            await f.write(content)

    async def stream(self, url: str) -> "AsyncIterator[bytes]":# type: ignore
        """Stream HTTP response bytes."""
        import aiohttp# type: ignore
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                async for chunk in resp.content:
                    yield chunk

    async def watch(self, path: str, callback: callable) -> None:# type: ignore
        """Watch a directory for changes using inotify or polling."""
        ...
