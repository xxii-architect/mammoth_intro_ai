"""HTTP client for the Mammoth Paths workspace SDK.

Standard library only so it can be embedded anywhere Python runs. Every call is
scoped server-side to the caller's token: the client never sees another user's
runs, repositories, notes, or build log.
"""

from __future__ import annotations

import codecs
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    Iterator,
    List,
    Literal,
    Mapping,
    Optional,
    Union,
    overload,
)

from .document_review import validate_document_review
from .branch_export import decode_branch_export

PATHS_CONTRACT_VERSION = "mammoth.paths.v1"
RUN_CONTRACT_VERSION = "mammoth.run.v1"

TERMINAL_RUN_EVENTS = frozenset({"run.completed", "run.failed", "run.cancelled", "run.awaiting_approval", "run.partial"})

UsageHook = Callable[[Dict[str, Any]], None]
ApprovalPolicy = Callable[["RunEvent"], Union[bool, str]]


class PathsError(Exception):
    """Raised for backend errors, invalid responses, or interrupted run streams."""

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
        if (not isinstance(raw, Mapping) or raw.get("contract") != RUN_CONTRACT_VERSION
                or any(not isinstance(raw.get(key), str) or not raw[key].strip() for key in ("type", "run_id", "ts"))
                or type(raw.get("seq")) is not int or not 0 < raw["seq"] <= 9007199254740991
                or not isinstance(raw.get("data"), dict)):
            raise PathsError("Invalid run event envelope", code="invalid_event")
        return cls(
            type=raw["type"], seq=raw["seq"], run_id=raw["run_id"],
            ts=raw["ts"], data=dict(raw["data"]), contract=raw["contract"],
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
    snapshot: Optional[Dict[str, Any]] = None

    @property
    def tool_calls(self) -> List[Dict[str, Any]]:
        return [e.data for e in self.events if e.type == "tool.call"]

    @property
    def diffs(self) -> List[Dict[str, Any]]:
        return [e.data for e in self.events if e.type == "diff.proposed"]

    @property
    def progress(self) -> Optional[Dict[str, Any]]:
        """Latest evidence inventory supplied by the backend, if supported."""
        if self.snapshot is not None:
            return self.snapshot.get("progress")
        for event in reversed(self.events):
            progress = event.data.get("progress")
            if isinstance(progress, dict):
                return progress
        return None


def iter_sse(lines: Iterable[bytes]) -> Iterator[Dict[str, Any]]:
    """Parse UTF-8 SSE chunks; malformed data frames fail without exposing their body."""
    data_lines: List[str] = []
    line_chars: List[str] = []
    decoder = codecs.getincrementaldecoder("utf-8-sig")()
    skip_lf = False

    def _flush() -> Optional[Dict[str, Any]]:
        if not data_lines:
            return None
        payload = "\n".join(data_lines)
        data_lines.clear()
        try:
            decoded = json.loads(payload)
        except json.JSONDecodeError:
            raise PathsError("Stream data is not valid JSON", code="invalid_stream") from None
        if not isinstance(decoded, dict):
            raise PathsError("Stream data must be a JSON object", code="invalid_stream")
        return decoded

    def _line(line: str) -> Optional[Dict[str, Any]]:
        if not line:
            return _flush()
        if line == "data" or line.startswith("data:"):
            value = line[5:]
            data_lines.append(value[1:] if value.startswith(" ") else value)
        return None

    def _decode(raw: bytes, *, final: bool = False) -> str:
        try:
            return decoder.decode(raw, final=final)
        except UnicodeDecodeError:
            raise PathsError("Stream is not valid UTF-8", code="invalid_stream") from None

    def _chunks() -> Iterator[str]:
        for raw in lines:
            yield _decode(raw)
        yield _decode(b"", final=True)

    for chunk in _chunks():
        for char in chunk:
            if skip_lf and char == "\n":
                skip_lf = False
                continue
            skip_lf = char == "\r"
            if char in "\r\n":
                decoded = _line("".join(line_chars))
                line_chars.clear()
                if decoded is not None:
                    yield decoded
            else:
                line_chars.append(char)
    if line_chars:
        decoded = _line("".join(line_chars))
        if decoded is not None:
            yield decoded
    decoded = _flush()
    if decoded is not None:
        yield decoded


class MammothPaths:
    """Client for the Mammoth Paths workspace surfaces.

    Surfaces: Mammoth Mind agent runs, tool catalog, repository sources,
    tasks, saved artifacts, notes, build log, and (owner-only) terminal.

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
        message = str(payload.get("error") or payload.get("detail") or payload.get("message") or exc.reason or "Request failed")
        return PathsError(message, status=exc.code, code=str(payload.get("code") or ""), payload=payload)

    @overload
    def _json(self, surface: str, method: str, path: str, body: Any = None,
              query: Optional[Mapping[str, Any]] = None, *, list_response: Literal[False] = False,
              member: Optional[str] = None) -> Dict[str, Any]: ...

    @overload
    def _json(self, surface: str, method: str, path: str, body: Any = None,
              query: Optional[Mapping[str, Any]] = None, *, list_response: Literal[True],
              member: Optional[str] = None) -> List[Dict[str, Any]]: ...

    def _json(self, surface: str, method: str, path: str, body: Any = None,
              query: Optional[Mapping[str, Any]] = None, *, list_response: bool = False,
              member: Optional[str] = None) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        request = self._build_request(method, path, body, query, "application/json")
        started = time.monotonic()
        status = 0
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                status = int(getattr(response, "status", 200) or 200)
                raw = response.read()
        except urllib.error.HTTPError as exc:
            status = exc.code
            raise self._error_from_http(exc) from None
        except urllib.error.URLError as exc:
            raise PathsError(f"Could not reach {self.base_url}: {exc.reason}") from None
        finally:
            self._meter(surface, method, path, status, started)
        try:
            payload: object = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise PathsError("Response is not valid UTF-8 JSON", status=status, code="invalid_response") from None
        if isinstance(payload, dict) and payload.get("status") == "error":
            raise PathsError(str(payload.get("error") or payload.get("detail") or payload.get("message") or "Request failed"),
                             status=status, code=str(payload.get("code") or ""), payload=payload)
        if member is not None:
            if not isinstance(payload, dict):
                raise PathsError("Response envelope must be a JSON object", status=status, code="invalid_response")
            payload = payload.get(member)
        if list_response:
            if isinstance(payload, list) and all(isinstance(item, dict) for item in payload):
                return payload
        elif isinstance(payload, dict):
            return payload
        raise PathsError("Response must be an array of objects" if list_response else "Response must be a JSON object",
                         status=status, code="invalid_response")

    def _stream(self, path: str, body: Any, *, run_id: Optional[str] = None) -> Iterator[RunEvent]:
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
            terminal = False
            previous: Optional[int] = None
            with response:
                for raw in iter_sse(response):
                    event = RunEvent.from_dict(raw)
                    if ((run_id is not None and event.run_id != run_id)
                            or (previous is not None and event.seq != previous + 1)):
                        raise PathsError("Run stream identity or sequence changed; recover the saved snapshot",
                                         code="invalid_event", status=status)
                    run_id, previous = event.run_id, event.seq
                    terminal = event.is_terminal
                    yield event
                    if terminal:
                        break
            if not terminal:
                raise PathsError(
                    "The run stream ended before a terminal event. Check the saved run before starting again.",
                    code="stream_interrupted", status=status,
                )
        except PathsError as exc:
            if not exc.status:
                exc.status = status
            raise
        finally:
            self._meter("mind", "POST", path, status, started)

    @staticmethod
    def _seg(value: str) -> str:
        return urllib.parse.quote(str(value), safe="")

    # ── Mammoth Mind: agent runs ───────────────────────────────────────────

    def tools(self, repo: Optional[str] = None) -> Dict[str, Any]:
        """Tool catalog visible to the caller for ``repo`` (source id or ``owner/repo``)."""
        return self._json("mind", "GET", "/mammoth/tools", query={"repo": repo})

    def runtime_usage(self) -> Dict[str, Any]:
        """Durable private token admission; excludes invoices and uninstrumented calls."""
        return self._json("usage", "GET", "/runtime/usage")

    def runtime_tenants(self) -> Dict[str, Any]:
        """Active backend-verified billing memberships; disabled on local-only hosts."""
        return self._json("usage", "GET", "/runtime/tenants")

    def tenant_runtime_usage(self, tenant_id: str) -> Dict[str, Any]:
        return self._json("usage", "GET", "/runtime/tenant-usage", query={"tenant_id": tenant_id})

    def set_tenant_runtime_limits(self, tenant_id: str, *, daily_token_limit: Optional[int],
                                  daily_usd_limit_micros: Optional[int]) -> Dict[str, Any]:
        for value, maximum in ((daily_token_limit, 1_000_000_000), (daily_usd_limit_micros, 1_000_000_000_000)):
            if value is not None and (type(value) is not int or not 0 <= value <= maximum):
                raise ValueError("Tenant limits must be null or bounded non-negative whole numbers.")
        return self._json("usage", "PUT", "/runtime/tenant-usage/policy", body={
            "tenant_id": tenant_id, "daily_token_limit": daily_token_limit,
            "daily_usd_limit_micros": daily_usd_limit_micros,
        })

    def set_runtime_token_limit(self, daily_token_limit: Optional[int]) -> Dict[str, Any]:
        """Set a UTC daily user ceiling; null removes the ceiling without erasing usage."""
        if daily_token_limit is not None and (
            type(daily_token_limit) is not int or not 0 <= daily_token_limit <= 100_000_000
        ):
            raise ValueError("daily_token_limit must be null or an integer from 0 to 100000000")
        return self._json("usage", "PUT", "/runtime/usage/policy", {"daily_token_limit": daily_token_limit})

    def stream_run(
        self,
        message: str,
        *,
        agent_id: str = "assistant",
        repo: Optional[str] = None,
        approval_mode: str = "tools",
        thread_id: Optional[str] = None,
        completion_goal: Optional[str] = None,
        recursive: Union[bool, Mapping[str, int]] = False,
        surface: Optional[str] = None,
        task: Optional[str] = None,
        history: Optional[List[Mapping[str, Any]]] = None,
        attached_file_ids: Optional[List[str]] = None,
    ) -> Iterator[RunEvent]:
        """Start a run and yield events until it completes, fails, is cancelled, or awaits approval."""
        if approval_mode not in {"tools", "always"}:
            raise ValueError("approval_mode must be 'tools' or 'always'")
        body: Dict[str, Any] = {"message": message, "agent_id": agent_id, "approval_mode": approval_mode}
        if surface is not None:
            if surface not in {"mind", "agent_workspace"}:
                raise ValueError("surface must be 'mind' or 'agent_workspace'")
            body["surface"] = surface
        if task is not None:
            if not isinstance(task, str):
                raise ValueError("task must be a task key string")
            body["task"] = task
        if history is not None:
            if not isinstance(history, list) or any(not isinstance(turn, Mapping) for turn in history):
                raise ValueError("history must be a list of conversation objects")
            body["history"] = [dict(turn) for turn in history]
        if attached_file_ids is not None:
            if not isinstance(attached_file_ids, list) or any(not isinstance(item, str) for item in attached_file_ids):
                raise ValueError("attached_file_ids must be a list of strings")
            body["attached_file_ids"] = list(attached_file_ids)
        if recursive is not False:
            if recursive is not True and not isinstance(recursive, Mapping):
                raise ValueError("recursive must be a boolean or budget mapping")
            body["recursive"] = True if recursive is True else dict(recursive)
        if completion_goal is not None:
            if completion_goal not in {"answer", "proposal", "validated", "applied"}:
                raise ValueError("Invalid completion_goal")
            body["completion_goal"] = completion_goal
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
            run_id=run_id,
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
                elif event.type == "run.partial":
                    result.status, result.reply = "partial", str(event.data.get("reply") or "")
                elif event.type == "run.failed":
                    result.status, result.error = "failed", str(event.data.get("error") or "")
                    result.reply = str(event.data.get("reply") or "")
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

    def continue_run(self, run_id: str) -> Iterator[RunEvent]:
        """Continue saved work with a bounded additional budget; may incur model usage."""
        return self._stream(f"/mammoth/runs/{self._seg(run_id)}/continue", {}, run_id=run_id)

    def cancel_run(self, run_id: str) -> Dict[str, Any]:
        return self._json("mind", "POST", f"/mammoth/runs/{self._seg(run_id)}/cancel", body={})

    def get_run(self, run_id: str, *, after: int = 0) -> Dict[str, Any]:
        return self._json("mind", "GET", f"/mammoth/runs/{self._seg(run_id)}",
                          query={"after": after or None}, member="run")

    def list_runs(self) -> List[Dict[str, Any]]:
        return self._json("mind", "GET", "/mammoth/runs", member="runs", list_response=True)

    def recover_run(self, run_id: str) -> RunResult:
        """Read a full saved snapshot; never execute, continue or approve work."""
        saved = self.get_run(run_id)
        if (not isinstance(saved, dict) or saved.get("id") != run_id
                or not isinstance(saved.get("status"), str) or saved["status"] not in {
            "running", "awaiting_approval", "completed", "failed", "cancelled", "partial",
        } or not isinstance(saved.get("events"), list)
                or any(saved.get(key) is not None and not isinstance(saved[key], kind)
                       for key, kind in (("plan", list), ("diagnostics", list), ("reply", str),
                                         ("progress", dict), ("pending_approval", dict), ("recursive", dict)))
                or any(saved.get(key) is not None and any(not isinstance(item, dict) for item in saved[key])
                       for key in ("plan", "diagnostics"))
                or ("failure_code" in saved and not isinstance(saved["failure_code"], str))
                or ("can_continue" in saved and type(saved["can_continue"]) is not bool)):
            raise PathsError("Invalid saved run snapshot", code="invalid_snapshot")
        previous = 0
        events = []
        for raw in saved["events"]:
            try:
                event = RunEvent.from_dict(raw)
            except PathsError:
                raise PathsError("Invalid saved run event envelope", code="invalid_snapshot") from None
            if event.run_id != run_id or event.seq != previous + 1:
                raise PathsError("Saved run events must belong to this run and form a complete sequence starting at one",
                                 code="invalid_snapshot")
            previous = event.seq
            events.append(event)
        return RunResult(
            run_id=run_id, status=saved["status"], reply=str(saved.get("reply") or ""),
            error=str(saved.get("reply") or "") if saved["status"] in {"failed", "partial"} else "",
            events=events, pending_approval=saved.get("pending_approval") if saved["status"] == "awaiting_approval" else None,
            snapshot=saved,
        )

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

    def list_tasks(self) -> List[Dict[str, Any]]:
        return self._json("tasks", "GET", "/tasks", list_response=True)

    def save_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        return self._json("tasks", "POST", "/tasks", body=task)

    def list_artifacts(self) -> Dict[str, Any]:
        return self._json("artifacts", "GET", "/workspace/artifacts")

    def save_artifact(self, artifact: Dict[str, Any]) -> Dict[str, Any]:
        return self._json("artifacts", "POST", "/workspace/artifacts", body=artifact)

    def get_artifact_run(self, artifact_id: str) -> Dict[str, Any]:
        return self._json("artifacts", "GET", f"/workspace/artifacts/{self._seg(artifact_id)}/run")

    def delete_artifact(self, artifact_id: str) -> Dict[str, Any]:
        return self._json("artifacts", "DELETE", f"/workspace/artifacts/{self._seg(artifact_id)}")

    def clear_artifacts(self) -> Dict[str, Any]:
        return self._json("artifacts", "DELETE", "/workspace/artifacts")

    def read_document(self, file_id: str, *, scope: str = "chat", start: int = 0, count: int = 6) -> Dict[str, Any]:
        """Read a bounded page of private indexed text, not a model review."""
        if scope not in {"chat", "atlas"}:
            raise ValueError("Document scope must be chat or atlas")
        surface = "mammoth" if scope == "chat" else "atlas"
        return self._json("documents", "GET", f"/{surface}/files/{self._seg(file_id)}/content",
                          query={"start": start, "count": count})

    def create_document_review(self, file_id: str, goal: str, *, scope: str = "chat") -> Dict[str, Any]:
        """Create a saved review without running a model."""
        return self._review_json("POST", "/mammoth/document-reviews",
                                 body={"file_id": file_id, "scope": scope, "goal": goal}, file_id=file_id, scope=scope)

    def list_document_reviews(self, file_id: str, *, scope: str = "chat") -> Dict[str, Any]:
        payload = self._json("documents", "GET", "/mammoth/document-reviews", query={"file_id": file_id, "scope": scope})
        try:
            reviews = payload.get("reviews")
            if not isinstance(reviews, list):
                raise ValueError("Invalid saved document reviews")
            for review in reviews:
                validate_document_review(review, file_id=file_id, scope=scope)
        except ValueError:
            raise PathsError("Invalid saved document reviews; reload authoritative state",
                             code="invalid_response", status=200) from None
        return payload

    def get_document_review(self, review_id: str) -> Dict[str, Any]:
        return self._review_json("GET", f"/mammoth/document-reviews/{self._seg(review_id)}", review_id=review_id)

    def _review_json(self, method: str, path: str, *, body: Any = None, review_id: Optional[str] = None,
                     file_id: Optional[str] = None, scope: Optional[str] = None) -> Dict[str, Any]:
        payload = self._json("documents", method, path, body=body)
        try:
            validate_document_review(payload.get("review"), review_id=review_id, file_id=file_id, scope=scope)
        except ValueError:
            raise PathsError("Invalid saved document review; reload authoritative state before further work",
                             code="invalid_response", status=200) from None
        return payload

    def advance_document_review(self, review_id: str, *, confirm_model_usage: bool = False) -> Dict[str, Any]:
        """Explicit paid next batch, never an automatic retry or budget extension."""
        if confirm_model_usage is not True:
            raise ValueError("Explicit model-usage confirmation is required")
        return self._review_json("POST", f"/mammoth/document-reviews/{self._seg(review_id)}/advance",
                                 body={"confirm_model_usage": True}, review_id=review_id)

    def delete_document_review(self, review_id: str) -> Dict[str, Any]:
        payload = self._json("documents", "DELETE", f"/mammoth/document-reviews/{self._seg(review_id)}")
        if payload.get("deleted") != review_id:
            raise PathsError("Invalid review deletion receipt; reload authoritative state", code="invalid_response", status=200)
        return payload

    def synthesize_document_review(self, review_id: str, *, confirm_model_usage: bool = False) -> Dict[str, Any]:
        """Explicit paid synthesis batch over saved assessments, not a full-source reread."""
        if confirm_model_usage is not True:
            raise ValueError("Explicit model-usage confirmation is required")
        return self._review_json("POST", f"/mammoth/document-reviews/{self._seg(review_id)}/synthesize",
                                 body={"confirm_model_usage": True}, review_id=review_id)

    def extend_document_review_budget(self, review_id: str, *, expected_max_tokens: int, max_tokens: int,
                                     confirm_budget_extension: bool = False) -> Dict[str, Any]:
        """Raise the lifetime ceiling without spending tokens or resetting usage."""
        if confirm_budget_extension is not True:
            raise ValueError("Explicit budget-extension confirmation is required")
        return self._review_json("POST", f"/mammoth/document-reviews/{self._seg(review_id)}/budget",
                                 body={"expected_max_tokens": expected_max_tokens, "max_tokens": max_tokens,
                                       "confirm_budget_extension": True}, review_id=review_id)

    def owner_execution_capabilities(self, repo: str = "") -> Dict[str, Any]:
        return self._json("owner_execution", "GET", "/owner-executions/capabilities", query={"repo": repo})

    def prepare_owner_execution(self, repo: str, changes: List[Dict[str, Any]], *, base_sha: str, profile: str,
                                acceptance: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        body = {
            "repo_context": {"root": repo}, "changes": changes, "base_sha": base_sha, "profile": profile,
        }
        if acceptance is not None:
            body["acceptance"] = acceptance
        return self._json("owner_execution", "POST", "/owner-executions", body=body)

    def get_owner_execution(self, execution_id: str) -> Dict[str, Any]:
        return self._json("owner_execution", "GET", f"/owner-executions/{self._seg(execution_id)}")

    def export_owner_branch(self, execution_id: str, *, repo: str, expected_commit: str,
                            confirm_private_export: bool = False) -> Dict[str, Any]:
        """Export the applied commit, never push, import or execute it."""
        if confirm_private_export is not True:
            raise ValueError("Explicit private source export confirmation is required")
        payload = self._json("owner_execution", "POST", f"/owner-executions/{self._seg(execution_id)}/export",
                             body={"repo_context": {"root": repo}, "expected_commit": expected_commit,
                                   "confirm_private_export": True})
        try:
            decode_branch_export(payload.get("export"), execution_id, expected_commit)
        except ValueError:
            raise PathsError("Invalid branch export receipt, checksum or size",
                             code="invalid_response", status=200) from None
        return payload

    def approve_owner_execution(self, execution_id: str, *, repo: str, approval_digest: str) -> Dict[str, Any]:
        return self._json("owner_execution", "POST", f"/owner-executions/{self._seg(execution_id)}/approve",
                          body={"repo_context": {"root": repo}, "approval_digest": approval_digest})

    def cancel_owner_execution(self, execution_id: str) -> Dict[str, Any]:
        return self._json("owner_execution", "POST", f"/owner-executions/{self._seg(execution_id)}/cancel", body={})

    def apply_owner_execution(self, execution_id: str, *, repo: str, approval_digest: str) -> Dict[str, Any]:
        return self._json("owner_execution", "POST", f"/owner-executions/{self._seg(execution_id)}/apply",
                          body={"repo_context": {"root": repo}, "approval_digest": approval_digest})

    # ── Notes ─────────────────────────────────────────────────────────────

    def list_notes(self) -> List[Dict[str, Any]]:
        return self._json("notes", "GET", "/notes", list_response=True)

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
        return self._json("buildlog", "GET", "/buildlog", list_response=True)

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
