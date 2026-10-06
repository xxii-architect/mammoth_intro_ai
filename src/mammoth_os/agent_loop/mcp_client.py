"""Minimal Model Context Protocol (MCP) stdio client and tool bridge.

Implements the open MCP JSON-RPC handshake (``initialize`` →
``notifications/initialized`` → ``tools/list`` / ``tools/call``) over
newline-delimited stdio. Servers come from ``mcp/index.json``.

Access is allowlisted per server:

* ``"access": "admin"`` (default) – owner/admin only. Use this for any server
  rooted at the platform checkout.
* ``"access": "tenant"`` – any signed-in user, but the server is launched with
  its working directory set to that user's resolved repository sandbox, and
  only when a repository is selected.

Only tools listed in a server's ``tools`` / ``approval_required_tools`` are ever
exposed; tools in ``approval_required_tools`` pause the run for approval.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .tools import (
    TIER_EXEC,
    TIER_NETWORK,
    TIER_READ,
    TIER_WRITE,
    ToolContext,
    ToolRegistry,
    ToolSpec,
)

MCP_PROTOCOL_VERSION = "2025-06-18"
CLIENT_INFO = {"name": "mammothos", "version": "1"}
# Agents propose; humans publish. Pushing is never available to a run.
NEVER_EXPOSED_TOOLS = frozenset({"git_push"})
_MUTATING_HINTS = ("write", "create", "move", "delete", "remove", "edit", "commit", "push", "reset", "checkout", "_add", "install", "run", "exec", "evaluate", "click", "fill", "type", "submit", "upload")
_ENV_PASSTHROUGH = ("PATH", "PATHEXT", "SYSTEMROOT", "HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "TEMP", "TMP", "COMSPEC")


@dataclass
class MCPServerConfig:
    id: str
    label: str
    command: str
    args: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)
    tools: List[str] = field(default_factory=list)
    approval_required_tools: List[str] = field(default_factory=list)
    access: str = "admin"
    category: str = ""
    enabled: bool = True

    def exposed_tools(self) -> List[Tuple[str, bool]]:
        seen: Dict[str, bool] = {}
        for name in self.tools:
            # Fail safe: anything that looks mutating needs approval even if
            # the config forgot to list it under approval_required_tools.
            lowered = str(name).lower()
            seen[str(name)] = any(hint in lowered for hint in _MUTATING_HINTS)
        for name in self.approval_required_tools:
            seen[str(name)] = True
        return sorted((name, approval) for name, approval in seen.items() if name not in NEVER_EXPOSED_TOOLS)


def load_mcp_registry(root: Path) -> List[MCPServerConfig]:
    index_path = root / "mcp" / "index.json"
    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    servers: List[MCPServerConfig] = []
    for entry in index.get("servers") or []:
        if not isinstance(entry, dict) or not entry.get("enabled", True):
            continue
        cfg_rel = str(entry.get("config") or "")
        cfg_path = (root / cfg_rel).resolve()
        try:
            cfg_path.relative_to((root / "mcp").resolve())
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not cfg.get("enabled", True) or str(cfg.get("transport") or "stdio") != "stdio":
            continue
        access = str(cfg.get("access") or entry.get("access") or "admin").lower()
        servers.append(MCPServerConfig(
            id=str(entry.get("id") or cfg.get("name") or cfg_path.stem),
            label=str(entry.get("label") or cfg.get("name") or cfg_path.stem),
            command=str(cfg.get("command") or ""),
            args=[str(a) for a in cfg.get("args") or []],
            env={str(k): str(v) for k, v in (cfg.get("env") or {}).items()},
            tools=[str(t) for t in cfg.get("tools") or []],
            approval_required_tools=[str(t) for t in cfg.get("approval_required_tools") or []],
            access="tenant" if access == "tenant" else "admin",
            category=str(entry.get("category") or ""),
        ))
    return servers


class MCPError(RuntimeError):
    pass


class MCPStdioClient:
    def __init__(self, command: List[str], *, cwd: Path, env: Optional[Dict[str, str]] = None, timeout_s: float = 30.0):
        self.command = command
        self.cwd = cwd
        self.env = env or {}
        self.timeout_s = timeout_s
        self._proc: Optional[asyncio.subprocess.Process] = None
        self._next_id = 0
        self._lock = asyncio.Lock()
        self.tools: Dict[str, Dict[str, Any]] = {}
        self.initialized = False
        self.last_error = False

    @property
    def running(self) -> bool:
        return self._proc is not None and self._proc.returncode is None

    async def start(self) -> None:
        if self.running and self.initialized:
            return
        if self.running:
            await self.close()
        self.last_error = False
        exe = shutil.which(self.command[0])
        if not exe:
            raise MCPError(f"MCP server command not found: {self.command[0]}")
        base_env = {k: os.environ[k] for k in _ENV_PASSTHROUGH if k in os.environ}
        self._proc = await asyncio.create_subprocess_exec(
            exe, *self.command[1:],
            cwd=str(self.cwd),
            env={**base_env, **self.env},
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await self._request("initialize", {
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": CLIENT_INFO,
        })
        await self._notify("notifications/initialized", {})
        listing = await self._request("tools/list", {})
        self.tools = {t.get("name"): t for t in listing.get("tools") or [] if isinstance(t, dict)}
        self.initialized = True

    async def _write(self, message: Dict[str, Any]) -> None:
        assert self._proc is not None and self._proc.stdin is not None
        self._proc.stdin.write((json.dumps(message) + "\n").encode("utf-8"))
        await self._proc.stdin.drain()

    async def _notify(self, method: str, params: Dict[str, Any]) -> None:
        await self._write({"jsonrpc": "2.0", "method": method, "params": params})

    async def _request(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if self._proc is None or self._proc.stdout is None:
            raise MCPError("MCP server is not running")
        self._next_id += 1
        request_id = self._next_id
        await self._write({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
        while True:
            line = await asyncio.wait_for(self._proc.stdout.readline(), timeout=self.timeout_s)
            if not line:
                raise MCPError("MCP server closed the connection")
            try:
                message = json.loads(line.decode("utf-8", errors="replace"))
            except ValueError:
                continue
            if message.get("id") != request_id:
                continue
            if "error" in message:
                err = message["error"] or {}
                raise MCPError(str(err.get("message") or err)[:400])
            return message.get("result") or {}

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        async with self._lock:
            await self.start()
            return await self._request("tools/call", {"name": name, "arguments": arguments})

    async def close(self) -> None:
        if self._proc is None:
            return
        if self._proc.returncode is None:
            self._proc.terminate()
            try:
                await asyncio.wait_for(self._proc.wait(), timeout=5)
            except asyncio.TimeoutError:
                self._proc.kill()
        self._proc = None
        self.initialized = False


def _flatten_mcp_result(result: Dict[str, Any]) -> Dict[str, Any]:
    texts: List[str] = []
    for block in result.get("content") or []:
        if isinstance(block, dict) and block.get("type") == "text":
            texts.append(str(block.get("text") or ""))
    out: Dict[str, Any] = {
        "status": "error" if result.get("isError") else "ok",
        "content": "\n".join(texts)[:20_000],
    }
    if isinstance(result.get("structuredContent"), dict):
        out["structured"] = result["structuredContent"]
    return out


class MCPBridge:
    """Exposes allowlisted MCP server tools through a :class:`ToolRegistry`."""

    def __init__(self, platform_root: Path, servers: Optional[List[MCPServerConfig]] = None):
        self.platform_root = platform_root
        self.servers = servers if servers is not None else load_mcp_registry(platform_root)
        self._clients: Dict[Tuple[str, str], MCPStdioClient] = {}

    def _cwd_for(self, server: MCPServerConfig, ctx: ToolContext) -> Optional[Path]:
        if server.access == "tenant":
            return ctx.repo_root
        return self.platform_root

    def _visible(self, server: MCPServerConfig) -> Any:
        def check(ctx: ToolContext) -> bool:
            if server.access == "admin":
                # Repo-category servers are rooted at the platform checkout, so they
                # only appear when the owner explicitly selected the platform repo.
                if server.category == "repo":
                    return bool(ctx.is_admin) and ctx.repo_scope == "platform"
                return bool(ctx.is_admin)
            return ctx.has_repo
        return check

    def _client(self, server: MCPServerConfig, cwd: Path) -> MCPStdioClient:
        key = (server.id, str(cwd))
        client = self._clients.get(key)
        if client is None:
            client = MCPStdioClient([server.command, *server.args], cwd=cwd, env=server.env)
            self._clients[key] = client
        return client

    def register(self, registry: ToolRegistry) -> None:
        for server in self.servers:
            for tool_name, needs_approval in server.exposed_tools():
                registry.register(self._spec(server, tool_name, needs_approval))

    def _spec(self, server: MCPServerConfig, tool_name: str, needs_approval: bool) -> ToolSpec:
        async def handler(args: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
            cwd = self._cwd_for(server, ctx)
            if cwd is None:
                return {"status": "error", "code": "no_repo", "error": "Select a repository first."}
            client = self._client(server, cwd)
            try:
                raw = await client.call_tool(tool_name, args)
            except (MCPError, OSError, asyncio.TimeoutError) as exc:
                client.last_error = True
                await client.close()
                return {"status": "error", "code": "mcp_error", "error": str(exc)}
            return _flatten_mcp_result(raw)

        tier = TIER_WRITE if needs_approval else TIER_READ
        if server.category == "browser":
            tier = TIER_EXEC if needs_approval else TIER_NETWORK
        return ToolSpec(
            name=f"mcp__{server.id}__{tool_name}",
            description=f"[{server.label}] MCP tool '{tool_name}'.",
            input_schema={"type": "object"},
            tier=tier,
            handler=handler,
            trace_kind="tool",
            requires_approval=needs_approval,
            source=f"mcp:{server.id}",
            available=self._visible(server),
        )

    def describe(self, ctx: ToolContext) -> List[Dict[str, Any]]:
        out = []
        for server in self.servers:
            visible = self._visible(server)(ctx)
            if not visible:
                continue
            out.append({
                "id": server.id,
                "label": server.label,
                "category": server.category,
                "access": server.access,
                "installed": bool(shutil.which(server.command)) if server.command else False,
                "tools": [name for name, _ in server.exposed_tools()],
                "approval_required_tools": list(server.approval_required_tools),
                **self.runtime_state(server, ctx),
            })
        return out

    def runtime_state(self, server: MCPServerConfig, ctx: ToolContext) -> Dict[str, Any]:
        installed = bool(server.command and shutil.which(server.command))
        client = self._clients.get((server.id, str(self._cwd_for(server, ctx))))
        visible = self._visible(server)(ctx)
        connected = bool(visible and client and client.running and client.initialized)
        status = (
            "disabled" if not server.enabled else
            "needs_setup" if not installed else
            "needs_context" if not visible else
            "connected" if connected else
            "error" if client and client.last_error else "configured"
        )
        return {
            "status": status,
            "connected": connected,
            "health_verified": connected,
            "workflow_ready": installed and visible and server.enabled,
            "requires_repo": server.access == "tenant" or server.category == "repo",
        }

    async def close(self) -> None:
        for client in list(self._clients.values()):
            await client.close()
        self._clients.clear()
