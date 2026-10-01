"""HTTP client for the Mammoth Paths workspace SDK.

Standard library only so it can be embedded anywhere Python runs. Every call is
scoped server-side to the caller's token: the client never sees another user's
runs, repositories, notes, or build log.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, Iterator, List, Mapping, Optional, Union

PATHS_CONTRACT_VERSION = "mammoth.paths.v1"
RUN_CONTRACT_VERSION = "mammoth.run.v1"

TERMINAL_RUN_EVENTS = frozenset({"run.completed", "run.failed", "run.cancelled", "run.awaiting_approval"})

UsageHook = Callable[[Dict[str, Any]], None]
ApprovalPolicy = Callable[["RunEvent"], Union[bool, str]]


class PathsError(Exception):
    """Raised for non-2xx responses or ``status: error`` payloads."""

    def __init__(self, message: str, *, status: int = 0, code: str = "", payload: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.code = code
        self.payload = payload or {}

    def __str__(self) -> str:
        prefix = f"[{self.status}{' ' + self.code if self.code else ''}] " if self.status or self.code else ""
        return f"{prefix}{self.message}"


@dataclass(frozen=True)
class RunEvent:
    """One ``mammoth.run.v1`` event."""

    type: str
    seq: int
    run_id: str
    ts: str
    data: Dict[str, Any]
    contract: str = RUN_CONTRACT_VERSION

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "RunEvent":
        return cls(
            type=str(raw.get("type") or ""),
            seq=int(raw.get("seq") or 0),
            run_id=str(raw.get("run_id") or ""),
            ts=str(raw.get("ts") or ""),
            data=dict(raw.get("data") or {}),
            contract=str(raw.get("contract") or RUN_CONTRACT_VERSION),
        )

    @property
    def is_terminal(self) -> bool:
        return self.type in TERMINAL_RUN_EVENTS


@dataclass
class RunResult:
    """Outcome of :meth:`MammothPaths.run`."""

    run_id: str
    status: str
    reply: str = ""
    error: str = ""
    events: List[RunEvent] = field(default_factory=list)
    pending_approval: Optional[Dict[str, Any]] = None

    @property
    def tool_calls(self) -> List[Dict[str, Any]]:
        return [e.data for e in self.events if e.type == "tool.call"]

    @property
    def diffs(self) -> List[Dict[str, Any]]:
        return [e.data for e in self.events if e.type == "diff.proposed"]


def iter_sse(lines: Iterable[bytes]) -> Iterator[Dict[str, Any]]:
    """Parse a Server-Sent Events byte stream into decoded JSON ``data`` payloads."""
    data_lines: List[str] = []

    def _flush() -> Optional[Dict[str, Any]]:
        if not data_lines:
            return None
        payload = "\n".join(data_lines)
        data_lines.clear()
        try:
            decoded = json.loads(payload)
        except json.JSONDecodeError:
            return None
        return decoded if isinstance(decoded, dict) else None

    for raw in lines:
        line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
        if not line:
            decoded = _flush()
            if decoded is not None:
                yield decoded
        elif line.startswith("data:"):
            data_lines.append(line[5:].lstrip())
    decoded = _flush()
    if decoded is not None:
        yield decoded


class MammothPaths:
    """Client for the Mammoth Paths workspace surfaces.

    Surfaces: Mammoth Mind agent runs, tool catalog, repository sources,
    notes, build log, and (owner-only) terminal.

    Args:
        base_url: Backend origin, e.g. ``https://app.example.com``. ``/api`` is appended.
        token: Bearer token (Supabase access token today; tenant API keys later).
        token_provider: Callable returning a fresh token per request; overrides ``token``.
        timeout: Socket timeout in seconds for each request.
        usage_hook: Called after every request with ``{surface, method, path, status, duration_ms}``.
            Use it for client-side metering until server-side tenant metering lands.
        headers: Extra headers sent with every request.
    """

    def __init__(
        self,
        base_url: str,
        *,
        token: Optional[str] = None,
        token_provider: Optional[Callable[[], Optional[str]]] = None,
        timeout: float = 120.0,
        usage_hook: Optional[UsageHook] = None,
        headers: Optional[Mapping[str, str]] = None,
        opener: Optional[urllib.request.OpenerDirector] = None,
    ):
        base = str(base_url or "").strip().rstrip("/")
        if not base.startswith(("http://", "https://")):
            raise ValueError("base_url must start with http:// or https://")
        if base.endswith("/api"):
            base = base[: -len("/api")]
        self.base_url = base
        self._token = token
        self._token_provider = token_provider
        self.timeout = float(timeout)
        self.usage_hook = usage_hook
        self._headers = dict(headers or {})
        self._opener = opener or urllib.request.build_opener()

    # ── transport ──────────────────────────────────────────────────────────

    def _url(self, path: str, query: Optional[Mapping[str, Any]] = None) -> str:
        url = f"{self.base_url}/api{path}"
        params = {k: v for k, v in (query or {}).items() if v is not None and v != ""}
        if params:
            url += "?" + urllib.parse.urlencode(params)
        return url

    def _build_request(self, method: str, path: str, body: Any, query: Optional[Mapping[str, Any]], accept: str) -> urllib.request.Request:
        headers = {
            "Accept": accept,
            "User-Agent": "mammoth-paths-python/1",
            "X-Mammoth-Contract": PATHS_CONTRACT_VERSION,
            **self._headers,
        }
        token = self._token_provider() if self._token_provider else self._token
        if token:
            headers["Authorization"] = f"Bearer {token}"
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        return urllib.request.Request(self._url(path, query), data=data, headers=headers, method=method)

    def _meter(self, surface: str, method: str, path: str, status: int, started: float) -> None:
        if self.usage_hook is None:
            return
        try:
            self.usage_hook({
                "surface": surface,
                "method": method,
                "path": path,
                "status": status,
                "duration_ms": round((time.monotonic() - started) * 1000, 1),
            })
        except Exception:
            # Metering must never break the caller's workflow.
            pass

    @staticmethod
    def _error_from_http(exc: urllib.error.HTTPError) -> PathsError:
        try:
            payload = json.loads(exc.read().decode("utf-8") or "{}")
        except Exception:
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        message = str(payload.get("error") or payload.get("detail") or exc.reason or "Request failed")
        return PathsError(message, status=exc.code, code=str(payload.get("code") or ""), payload=payload)

    def _json(self, surface: str, method: str, path: str, body: Any = None, query: Optional[Mapping[str, Any]] = None) -> Any:
        request = self._build_request(method, path, body, query, "application/json")
        started = time.monotonic()
        status = 0
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                status = int(getattr(response, "status", 200) or 200)
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            status = exc.code
            raise self._error_from_http(exc) from None
        except urllib.error.URLError as exc:
            raise PathsError(f"Could not reach {self.base_url}: {exc.reason}") from None
        finally:
            self._meter(surface, method, path, status, started)
        payload = json.loads(raw) if raw.strip() else {}
        if isinstance(payload, dict) and payload.get("status") == "error":
            raise PathsError(str(payload.get("error") or "Request failed"), status=status, code=str(payload.get("code") or ""), payload=payload)
        return payload

    def _stream(self, path: str, body: Any) -> Iterator[RunEvent]:
        request = self._build_request("POST", path, body, None, "text/event-stream")
        started = time.monotonic()
        status = 0
        try:
            try:
                response = self._opener.open(request, timeout=self.timeout)
            except urllib.error.HTTPError as exc:
                status = exc.code
                raise self._error_from_http(exc) from None
            except urllib.error.URLError as exc:
                raise PathsError(f"Could not reach {self.base_url}: {exc.reason}") from None
            status = int(getattr(response, "status", 200) or 200)
            with response:
                for raw in iter_sse(response):
                    yield RunEvent.from_dict(raw)
        finally:
            self._meter("mind", "POST", path, status, started)

    @staticmethod
    def _seg(value: str) -> str:
        return urllib.parse.quote(str(value), safe="")

    # ── Mammoth Mind: agent runs ───────────────────────────────────────────

    def tools(self, repo: Optional[str] = None) -> Dict[str, Any]:
        """Tool catalog visible to the caller for ``repo`` (source id or ``owner/repo``)."""
        return self._json("mind", "GET", "/mammoth/tools", query={"repo": repo})

    def stream_run(
        self,
        message: str,
        *,
        agent_id: str = "assistant",
        repo: Optional[str] = None,
        approval_mode: str = "tools",
        thread_id: Optional[str] = None,
    ) -> Iterator[RunEvent]:
        """Start a run and yield events until it completes, fails, is cancelled, or awaits approval."""
        if approval_mode not in {"tools", "always"}:
            raise ValueError("approval_mode must be 'tools' or 'always'")
        body: Dict[str, Any] = {"message": message, "agent_id": agent_id, "approval_mode": approval_mode}
        if repo:
            body["repo_context"] = {"root": repo}
        if thread_id:
            body["thread_id"] = thread_id
        return self._stream("/mammoth/runs", body)

    def decide(self, run_id: str, approval_id: str, decision: str, note: str = "") -> Iterator[RunEvent]:
        """Approve or reject a pending tool call and yield the resumed events."""
        if decision not in {"approve", "reject"}:
            raise ValueError("decision must be 'approve' or 'reject'")
        return self._stream(
            f"/mammoth/runs/{self._seg(run_id)}/approval",
            {"approval_id": approval_id, "decision": decision, "note": note},
        )

    def run(
        self,
        message: str,
        *,
        on_event: Optional[Callable[[RunEvent], None]] = None,
        approve: Optional[ApprovalPolicy] = None,
        max_approvals: int = 10,
        **options: Any,
    ) -> RunResult:
        """Drive a run to a terminal state.

        ``approve`` receives each ``approval.requested`` event and returns ``True``/``"approve"``
        or ``False``/``"reject"``. Without a policy the run stops at the first approval and
        :attr:`RunResult.pending_approval` is set so a human can decide later via :meth:`decide`.
        """
        events: List[RunEvent] = []
        result = RunResult(run_id="", status="running")
        stream = self.stream_run(message, **options)
        approvals_used = 0
        while True:
            pending: Optional[RunEvent] = None
            for event in stream:
                events.append(event)
                result.run_id = result.run_id or event.run_id
                if on_event is not None:
                    on_event(event)
                if event.type == "approval.requested":
                    pending = event
                elif event.type == "run.completed":
                    result.status, result.reply = "completed", str(event.data.get("reply") or "")
                elif event.type == "run.failed":
                    result.status, result.error = "failed", str(event.data.get("error") or "")
                elif event.type == "run.cancelled":
                    result.status = "cancelled"
                elif event.type == "run.awaiting_approval":
                    result.status = "awaiting_approval"
            if result.status != "awaiting_approval" or pending is None:
                break
            result.pending_approval = dict(pending.data)
            if approve is None or approvals_used >= max(0, int(max_approvals)):
                break
            approvals_used += 1
            verdict = approve(pending)
            decision = "approve" if verdict is True or verdict == "approve" else "reject"
            result.pending_approval = None
            result.status = "running"
            stream = self.decide(result.run_id, str(pending.data.get("id") or ""), decision)
        result.events = events
        return result

    def cancel_run(self, run_id: str) -> Dict[str, Any]:
        return self._json("mind", "POST", f"/mammoth/runs/{self._seg(run_id)}/cancel", body={})

    def get_run(self, run_id: str, *, after: int = 0) -> Dict[str, Any]:
        payload = self._json("mind", "GET", f"/mammoth/runs/{self._seg(run_id)}", query={"after": after or None})
        return payload.get("run") or {}

    def list_runs(self) -> List[Dict[str, Any]]:
        return list(self._json("mind", "GET", "/mammoth/runs").get("runs") or [])

    # ── Repositories (bring your own) ─────────────────────────────────────

    def list_repos(self) -> Dict[str, Any]:
        return self._json("repos", "GET", "/mammoth/repo-sources")

    def connect_repo(self, repo: str) -> Dict[str, Any]:
        """Connect a public GitHub repository (``owner/repo``) to the caller's private sandbox."""
        return self._json("repos", "POST", "/mammoth/repo-sources", body={"repo": repo})

    def sync_repo(self, source_id: str) -> Dict[str, Any]:
        return self._json("repos", "POST", f"/mammoth/repo-sources/{self._seg(source_id)}/sync", body={})

    def remove_repo(self, source_id: str) -> Dict[str, Any]:
        return self._json("repos", "DELETE", f"/mammoth/repo-sources/{self._seg(source_id)}")

    def propose_change(self, source_id: str, changes: List[Dict[str, Any]], *, title: str = "") -> Dict[str, Any]:
        """Create a local branch + git patch in the sandbox. Nothing is ever pushed."""
        return self._json(
            "repos", "POST", f"/mammoth/repo-sources/{self._seg(source_id)}/propose",
            body={"changes": changes, "title": title},
        )

    # ── Notes ─────────────────────────────────────────────────────────────

    def list_notes(self) -> List[Dict[str, Any]]:
        return list(self._json("notes", "GET", "/notes") or [])

    def save_note(self, content: str, *, title: Optional[str] = None, note_id: Optional[str] = None, **fields: Any) -> Dict[str, Any]:
        body: Dict[str, Any] = {**fields, "content": content}
        if title is not None:
            body["title"] = title
        if note_id:
            body["id"] = note_id
        return self._json("notes", "POST", "/notes", body=body)

    def delete_note(self, note_id: str) -> Dict[str, Any]:
        return self._json("notes", "DELETE", f"/notes/{self._seg(note_id)}")

    # ── Build log ─────────────────────────────────────────────────────────

    def list_build_log(self) -> List[Dict[str, Any]]:
        return list(self._json("buildlog", "GET", "/buildlog") or [])

    def log_build(self, title: str, *, description: str = "", **fields: Any) -> Dict[str, Any]:
        return self._json("buildlog", "POST", "/buildlog", body={**fields, "title": title, "description": description})

    # ── Terminal (owner/admin only) ───────────────────────────────────────

    def exec_terminal(self, cmd: str) -> Dict[str, Any]:
        """Run an allow-listed command on the backend host. Owner/admin accounts only."""
        return self._json("terminal", "POST", "/terminal/exec", body={"cmd": cmd})


__all__ = [
    "PATHS_CONTRACT_VERSION",
    "RUN_CONTRACT_VERSION",
    "MammothPaths",
    "PathsError",
    "RunEvent",
    "RunResult",
    "iter_sse",
]
