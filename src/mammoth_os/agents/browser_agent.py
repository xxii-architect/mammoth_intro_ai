from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib.parse import urljoin, urlparse

import requests

from .base_agent import BaseAgent


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class _PageSnapshotParser(HTMLParser):
    def __init__(self, base_url: str):
        super().__init__()
        self.base_url = base_url
        self.title = ""
        self.description = ""
        self.headings: List[str] = []
        self.links: List[Dict[str, str]] = []
        self._chunks: List[str] = []
        self._skip_depth = 0
        self._capture_title = False
        self._capture_heading: str | None = None
        self._current_heading_text: List[str] = []
        self._current_link: Dict[str, str] | None = None
        self._current_link_text: List[str] = []
        self._seen_description = False

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, str | None]]):
        tag = tag.lower()
        attr_map = {str(key).lower(): (value or "") for key, value in attrs}
        if tag in {"script", "style", "noscript"}:
            self._skip_depth += 1
            return
        if tag == "title":
            self._capture_title = True
            return
        if tag in {"h1", "h2", "h3"}:
            self._capture_heading = tag
            self._current_heading_text = []
            return
        if tag == "meta" and not self._seen_description:
            name = str(attr_map.get("name") or attr_map.get("property") or "").lower()
            if name in {"description", "og:description"}:
                content = str(attr_map.get("content") or "").strip()
                if content:
                    self.description = content
                    self._seen_description = True
            return
        if tag == "a":
            href = str(attr_map.get("href") or "").strip()
            if href:
                self._current_link = {"href": urljoin(self.base_url, href)}
                self._current_link_text = []

    def handle_endtag(self, tag: str):
        tag = tag.lower()
        if tag in {"script", "style", "noscript"} and self._skip_depth:
            self._skip_depth -= 1
            return
        if tag == "title":
            self._capture_title = False
            return
        if tag in {"h1", "h2", "h3"} and self._capture_heading:
            heading = re.sub(r"\s+", " ", "".join(self._current_heading_text).strip()).strip()
            if heading:
                self.headings.append(heading)
            self._capture_heading = None
            self._current_heading_text = []
            return
        if tag == "a" and self._current_link is not None:
            link_text = re.sub(r"\s+", " ", "".join(self._current_link_text)).strip()
            if link_text:
                self._current_link["text"] = link_text
            self.links.append(self._current_link)
            self._current_link = None
            self._current_link_text = []

    def handle_data(self, data: str):
        if self._skip_depth:
            return
        text = str(data or "")
        if not text.strip():
            return
        if self._capture_title:
            self.title += text
        if self._capture_heading:
            self._current_heading_text.append(text)
        self._chunks.append(text)
        if self._current_link is not None:
            self._current_link_text.append(text)

    def snapshot(self) -> Dict[str, Any]:
        text = re.sub(r"\s+", " ", " ".join(self._chunks)).strip()
        if not self.title and self.headings:
            self.title = self.headings[0]
        return {
            "title": re.sub(r"\s+", " ", self.title).strip(),
            "description": re.sub(r"\s+", " ", self.description).strip(),
            "headings": [re.sub(r"\s+", " ", h).strip() for h in self.headings if h.strip()],
            "links": self.links,
            "text": text,
            "word_count": len(text.split()),
        }


class BrowserAgent(BaseAgent):
    """Stateful browser automation agent with replayable action traces."""

    name = "BrowserAgent"

    def __init__(self, router, storage_root: str | None = None):
        super().__init__(router)
        self.storage_root = Path(storage_root) if storage_root else Path(__file__).resolve().parents[3] / ".mammoth"
        self.storage_root.mkdir(parents=True, exist_ok=True)
        self._state_path = self.storage_root / "browser_agent_state.json"

    def _default_state(self) -> Dict[str, Any]:
        return {"sessions": {}, "replays": []}

    def _load_state(self) -> Dict[str, Any]:
        if not self._state_path.exists():
            return self._default_state()
        try:
            data = json.loads(self._state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return self._default_state()
        if not isinstance(data, dict):
            return self._default_state()
        sessions = data.get("sessions") if isinstance(data.get("sessions"), dict) else {}
        replays = data.get("replays") if isinstance(data.get("replays"), list) else []
        return {"sessions": sessions, "replays": replays}

    def _save_state(self, state: Dict[str, Any]) -> None:
        tmp_path = self._state_path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")
        tmp_path.replace(self._state_path)

    def _normalize_request(self, prompt: Any) -> Dict[str, Any]:
        if isinstance(prompt, dict):
            raw = dict(prompt)
            action = str(raw.get("action") or raw.get("mode") or "snapshot").strip().lower() or "snapshot"
            url = str(raw.get("url") or raw.get("target") or raw.get("href") or "").strip()
            prompt_text = str(raw.get("prompt") or raw.get("query") or raw.get("content") or "").strip()
            if not url and prompt_text.lower().startswith(("http://", "https://")):
                url = prompt_text
            actions = raw.get("actions") if isinstance(raw.get("actions"), list) else []
            return {
                "action": action,
                "url": url,
                "prompt": prompt_text,
                "session_id": str(raw.get("session_id") or "").strip(),
                "replay_id": str(raw.get("replay_id") or "").strip(),
                "actions": actions,
                "follow_links": bool(raw.get("follow_links", True)),
                "max_links": max(1, min(25, int(raw.get("max_links") or 10))),
                "method": str(raw.get("method") or "GET").strip().upper(),
                "form": raw.get("form") if isinstance(raw.get("form"), dict) else {},
                "json_payload": raw.get("json") if isinstance(raw.get("json"), (dict, list)) else None,
                "headers": raw.get("headers") if isinstance(raw.get("headers"), dict) else {},
                "rerun": bool(raw.get("rerun")),
            }

        text = str(prompt or "").strip()
        if text.lower().startswith(("http://", "https://")):
            return {
                "action": "snapshot",
                "url": text,
                "prompt": text,
                "session_id": "",
                "replay_id": "",
                "actions": [],
                "follow_links": True,
                "max_links": 10,
                "method": "GET",
                "form": {},
                "json_payload": None,
                "headers": {},
                "rerun": False,
            }
        return {
            "action": "snapshot",
            "url": "",
            "prompt": text,
            "session_id": "",
            "replay_id": "",
            "actions": [],
            "follow_links": True,
            "max_links": 10,
            "method": "GET",
            "form": {},
            "json_payload": None,
            "headers": {},
            "rerun": False,
        }

    def _session_for(self, state: Dict[str, Any], session_id: str) -> requests.Session:
        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": "MammothOS/1.0 BrowserAgent",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
        )
        session_meta = state.get("sessions", {}).get(session_id) if session_id else None
        if isinstance(session_meta, dict):
            stored_headers = session_meta.get("headers")
            if isinstance(stored_headers, dict):
                for key, value in stored_headers.items():
                    if key and isinstance(value, str):
                        session.headers[str(key)] = value
            stored_cookies = session_meta.get("cookies")
            if isinstance(stored_cookies, dict):
                session.cookies.update({str(key): str(value) for key, value in stored_cookies.items()})
        return session

    def _persist_session(self, state: Dict[str, Any], session_id: str, session: requests.Session, *, last_url: str) -> None:
        session_headers = {}
        for key, value in session.headers.items():
            if key.lower() in {"user-agent", "accept", "content-type", "authorization", "x-requested-with"}:
                session_headers[str(key)] = str(value)
        state.setdefault("sessions", {})
        state["sessions"][session_id] = {
            "session_id": session_id,
            "last_url": last_url,
            "headers": session_headers,
            "cookies": requests.utils.dict_from_cookiejar(session.cookies),
            "updated_at": _utc_now(),
        }

    def _fetch_page(
        self,
        session: requests.Session,
        *,
        url: str,
        method: str = "GET",
        form: Dict[str, Any] | None = None,
        json_payload: Any = None,
        headers: Dict[str, str] | None = None,
    ) -> Dict[str, Any]:
        response = session.request(
            method=method,
            url=url,
            headers=headers or None,
            data=form or None,
            json=json_payload,
            timeout=12,
            allow_redirects=True,
        )
        content_type = str(response.headers.get("content-type") or "")
        final_url = str(response.url or url).strip()
        parser = _PageSnapshotParser(final_url)
        body = response.text or ""
        if "html" in content_type.lower() or "xml" in content_type.lower() or body.lstrip().startswith("<"):
            parser.feed(body)
            parser.close()
            snapshot = parser.snapshot()
        else:
            snapshot = {
                "title": urlparse(final_url).netloc or final_url,
                "description": "",
                "headings": [],
                "links": [],
                "text": re.sub(r"\s+", " ", body).strip(),
                "word_count": len(body.split()),
            }
        return {
            "status_code": response.status_code,
            "content_type": content_type,
            "final_url": final_url,
            **snapshot,
        }

    def _record_replay(self, state: Dict[str, Any], *, session_id: str, actions: List[Dict[str, Any]], request_action: str) -> str:
        replay_id = f"replay-{uuid.uuid4().hex[:10]}"
        record = {
            "replay_id": replay_id,
            "session_id": session_id,
            "action": request_action,
            "created_at": _utc_now(),
            "actions": actions,
        }
        replays = state.setdefault("replays", [])
        replays.append(record)
        state["replays"] = replays[-120:]
        return replay_id

    def _find_replay(self, state: Dict[str, Any], replay_id: str) -> Dict[str, Any] | None:
        for item in reversed(state.get("replays", [])):
            if isinstance(item, dict) and str(item.get("replay_id") or "").strip() == replay_id:
                return item
        return None

    def _execute_step(
        self,
        session: requests.Session,
        *,
        step: Dict[str, Any],
        last_url: str,
        max_links: int,
    ) -> Dict[str, Any]:
        action = str(step.get("action") or "snapshot").strip().lower() or "snapshot"
        headers = step.get("headers") if isinstance(step.get("headers"), dict) else {}

        if action in {"set_headers", "headers"}:
            for key, value in headers.items():
                if key and isinstance(value, str):
                    session.headers[str(key)] = value
            return {
                "status": "ok",
                "action": action,
                "message": "Session headers updated.",
                "headers": {str(key): str(value) for key, value in headers.items()},
                "final_url": last_url,
            }

        if action in {"fill", "type", "input", "set_value"}:
            field = str(step.get("field") or step.get("selector") or step.get("name") or step.get("target") or "").strip()
            value = step.get("value")
            if value is None:
                value = step.get("text") or ""
            if not field:
                return {"status": "needs_context", "action": action, "message": "Fill/type action requires a field name or selector."}
            state = getattr(session, "_browser_state", None)
            if state is None:
                state = {}
                setattr(session, "_browser_state", state)
            state.setdefault("form_values", {})[field] = str(value)
            return {
                "status": "ok",
                "action": action,
                "field": field,
                "value": str(value),
                "final_url": last_url,
                "summary": "Prepared field '" + field + "' with the provided value.",
            }

        if action == "extract":
            pattern = str(step.get("pattern") or step.get("selector") or step.get("query") or "").strip()
            source_text = str(step.get("text") or step.get("content") or step.get("value") or "").strip()
            if not source_text and not last_url:
                return {"status": "needs_context", "action": action, "message": "Extract action requires source text or the current page context."}
            extracted = source_text
            if pattern and source_text:
                match = re.search(re.escape(pattern), source_text, flags=re.IGNORECASE)
                if match:
                    extracted = source_text[match.start():match.end() + 80]
            return {
                "status": "ok",
                "action": action,
                "pattern": pattern,
                "final_url": last_url,
                "extracted": extracted,
                "summary": "Extracted the requested field or text snippet.",
            }

        if action == "click":
            href = str(step.get("href") or step.get("target") or "").strip()
            if not href:
                return {"status": "needs_context", "action": action, "message": "click action requires href or target."}
            if not last_url and not href.lower().startswith(("http://", "https://")):
                return {"status": "needs_context", "action": action, "message": "Relative click requires an existing page context."}
            url = urljoin(last_url, href) if last_url else href
            action = "navigate"
        else:
            url = str(step.get("url") or step.get("target") or "").strip()
            if not url and action in {"snapshot", "navigate", "open", "inspect", "load", "submit", "post"}:
                return {"status": "needs_context", "action": action, "message": f"{action} action requires a URL."}

        if action in {"snapshot", "navigate", "open", "inspect", "load"}:
            page = self._fetch_page(session, url=url, method="GET", headers=headers)
        elif action in {"submit", "post"}:
            method = str(step.get("method") or "POST").strip().upper() or "POST"
            form = step.get("form") if isinstance(step.get("form"), dict) else {}
            json_payload = step.get("json") if isinstance(step.get("json"), (dict, list)) else None
            page = self._fetch_page(session, url=url, method=method, form=form, json_payload=json_payload, headers=headers)
        else:
            return {"status": "unknown_action", "action": action, "message": f"Unsupported browser action '{action}'."}

        links = page.get("links") if isinstance(page.get("links"), list) else []
        limited_links = [
            {"href": str(link.get("href") or "").strip(), "text": str(link.get("text") or "").strip()}
            for link in links[:max_links]
            if str(link.get("href") or "").strip()
        ]
        headings = [str(item).strip() for item in (page.get("headings") or []) if str(item).strip()]
        text = str(page.get("text") or "").strip()
        title = str(page.get("title") or url).strip() or url
        description = str(page.get("description") or "").strip()
        summary_bits = [title]
        if description:
            summary_bits.append(description)
        summary_bits.append(f"{len(headings)} heading(s)")
        summary_bits.append(f"{len(limited_links)} link(s)")

        return {
            "status": "ok",
            "action": action,
            "url": url,
            "final_url": str(page.get("final_url") or url),
            "status_code": int(page.get("status_code") or 0),
            "content_type": str(page.get("content_type") or ""),
            "title": title,
            "description": description,
            "headings": headings,
            "links": limited_links,
            "text_excerpt": text[:1200],
            "word_count": int(page.get("word_count") or len(text.split())),
            "summary": " • ".join(summary_bits),
        }

    def _run_actions(
        self,
        *,
        state: Dict[str, Any],
        session_id: str,
        actions: List[Dict[str, Any]],
        max_links: int,
    ) -> Dict[str, Any]:
        session = self._session_for(state, session_id)
        session_meta = state.get("sessions", {}).get(session_id) if isinstance(state.get("sessions"), dict) else {}
        last_url = str((session_meta or {}).get("last_url") or "").strip()
        action_results: List[Dict[str, Any]] = []

        for raw_step in actions:
            step = dict(raw_step) if isinstance(raw_step, dict) else {"action": "snapshot", "url": str(raw_step or "")}
            if not step.get("url") and step.get("target"):
                step["url"] = step.get("target")
            result = self._execute_step(session, step=step, last_url=last_url, max_links=max_links)
            action_results.append(result)
            if str(result.get("status") or "") == "ok":
                maybe_url = str(result.get("final_url") or result.get("url") or "").strip()
                if maybe_url:
                    last_url = maybe_url

        self._persist_session(state, session_id, session, last_url=last_url)
        replay_id = self._record_replay(
            state,
            session_id=session_id,
            actions=action_results,
            request_action="workflow" if len(actions) > 1 else str(actions[0].get("action") or "snapshot"),
        )

        failed = [item for item in action_results if str(item.get("status") or "") not in {"ok"}]
        final = action_results[-1] if action_results else {"status": "error", "message": "No browser actions were executed."}
        checks = [
            {
                "name": "actions_executed",
                "passed": bool(action_results),
                "detail": f"Executed {len(action_results)} action(s).",
            },
            {
                "name": "all_actions_ok",
                "passed": not failed,
                "detail": "All browser actions completed." if not failed else f"{len(failed)} action(s) need attention.",
            },
        ]

        status = "ok" if not failed else "error"
        response: Dict[str, Any] = {
            "status": status,
            "agent": self.name,
            "mode": "browser_automation_v2",
            "session_id": session_id,
            "replay_id": replay_id,
            "action_count": len(action_results),
            "actions": action_results,
            "final": final,
            "execution": {
                "stage": "verify",
                "passed": not failed,
                "checks": checks,
            },
            "summary": str(final.get("summary") or final.get("message") or "Browser workflow complete."),
        }
        if isinstance(final, dict):
            for key in ("url", "final_url", "status_code", "content_type", "title", "description", "headings", "links", "text_excerpt", "word_count"):
                if key in final:
                    response[key] = final[key]
        return response

    def run(self, prompt: Any) -> Dict[str, Any]:
        request = self._normalize_request(prompt)
        state = self._load_state()
        session_id = request.get("session_id") or f"browser-{uuid.uuid4().hex[:10]}"
        action = str(request.get("action") or "snapshot").strip().lower()
        max_links = int(request.get("max_links") or 10)

        if action in {"site_audit", "lighthouse_audit"}:
            url = str(request.get("url") or request.get("prompt") or "").strip()
            return self.run_site_audit(url)

        if action == "replay":
            replay_id = str(request.get("replay_id") or "").strip()
            if not replay_id:
                return {
                    "status": "needs_context",
                    "agent": self.name,
                    "mode": "browser_automation_v2",
                    "message": "replay action requires replay_id.",
                    "session_id": session_id,
                }
            replay_record = self._find_replay(state, replay_id)
            if not replay_record:
                return {
                    "status": "error",
                    "agent": self.name,
                    "mode": "browser_automation_v2",
                    "message": f"Replay '{replay_id}' was not found.",
                    "session_id": session_id,
                    "replay_id": replay_id,
                }
            if not request.get("rerun"):
                return {
                    "status": "ok",
                    "agent": self.name,
                    "mode": "browser_automation_v2",
                    "session_id": str(replay_record.get("session_id") or session_id),
                    "replay_id": replay_id,
                    "replay": replay_record,
                    "summary": "Loaded replay trace.",
                }
            replay_actions = replay_record.get("actions") if isinstance(replay_record.get("actions"), list) else []
            rerun_steps = []
            for item in replay_actions:
                if not isinstance(item, dict):
                    continue
                step = {
                    "action": item.get("action") or "snapshot",
                    "url": item.get("url") or item.get("final_url") or "",
                }
                rerun_steps.append(step)
            response = self._run_actions(state=state, session_id=session_id, actions=rerun_steps, max_links=max_links)
            response["replayed_from"] = replay_id
            self._save_state(state)
            return response

        actions = request.get("actions") if isinstance(request.get("actions"), list) and request.get("actions") else []
        if not actions:
            url = str(request.get("url") or "").strip()
            if action in {"snapshot", "navigate", "open", "inspect", "load"} and not url:
                query = str(request.get("prompt") or "").strip()
                return {
                    "status": "needs_context",
                    "agent": self.name,
                    "mode": "browser_automation_v2",
                    "message": "Provide a URL to inspect so I can run browser actions.",
                    "prompt": query,
                    "url": "",
                    "session_id": session_id,
                }
            actions = [
                {
                    "action": action,
                    "url": url,
                    "method": request.get("method"),
                    "form": request.get("form"),
                    "json": request.get("json_payload"),
                    "headers": request.get("headers"),
                }
            ]

        try:
            response = self._run_actions(state=state, session_id=session_id, actions=actions, max_links=max_links)
        except requests.RequestException as exc:
            return {
                "status": "error",
                "agent": self.name,
                "mode": "browser_automation_v2",
                "session_id": session_id,
                "message": f"Unable to complete browser action: {exc}",
            }

        self._save_state(state)
        return response


    # ─────────────────────────────────────────────────────────────────────
    # Playwright MCP bridge
    # ─────────────────────────────────────────────────────────────────────

    @staticmethod
    def _mcp_config_path() -> Path:
        return Path(__file__).resolve().parents[3] / "mcp" / "playwright.json"

    def _mcp_available(self) -> bool:
        cfg_path = self._mcp_config_path()
        if not cfg_path.exists():
            return False
        try:
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            return bool(cfg.get("enabled", True))
        except (OSError, json.JSONDecodeError):
            return False

    def _run_playwright_mcp(self, request: Dict[str, Any]) -> Dict[str, Any]:
        import subprocess
        import shutil
        cfg_path = self._mcp_config_path()
        try:
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"status": "error", "message": "Playwright MCP config not readable."}
        command = cfg.get("command", "npx")
        args = cfg.get("args", [])
        env_overrides = cfg.get("env", {})
        if shutil.which(command) is None and command == "npx":
            return {"status": "needs_setup", "message": "npx not found. Install Node.js to enable the Playwright MCP bridge.", "summary": "Playwright MCP unavailable — Node.js required."}
        url = str(request.get("url") or "").strip()
        if not url:
            return {"status": "needs_context", "message": "Playwright MCP requires a URL."}
        rpc_request = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "browser_navigate", "arguments": {"url": url}}}
        import os
        proc_env = {**os.environ, **{str(k): str(v) for k, v in env_overrides.items()}}
        try:
            proc = subprocess.run([command] + args, input=json.dumps(rpc_request) + "\n", capture_output=True, text=True, timeout=30, env=proc_env)
            if proc.returncode != 0:
                return {"status": "error", "message": f"Playwright MCP exited {proc.returncode}.", "stderr": proc.stderr[:500]}
            response_text = proc.stdout.strip()
            if not response_text:
                return {"status": "error", "message": "Playwright MCP returned empty response."}
            rpc_response = json.loads(response_text.splitlines()[-1])
            result_content = rpc_response.get("result", {})
            text_parts = [str(item.get("text") or "") for item in (result_content.get("content") or []) if isinstance(item, dict) and item.get("type") == "text"]
            combined = "\n".join(text_parts).strip()
            return {"status": "ok", "mode": "playwright_mcp", "url": url, "content": combined, "summary": combined[:240] if combined else f"Navigated to {url}."}
        except subprocess.TimeoutExpired:
            return {"status": "error", "message": "Playwright MCP timed out (30s)."}
        except Exception as exc:
            return {"status": "error", "message": f"Playwright MCP error: {exc}"}

    def _run_lighthouse(self, url: str) -> Dict[str, Any]:
        import subprocess
        import shutil
        import tempfile
        if not shutil.which("npx"):
            return {"status": "needs_setup", "message": "npx not found.", "summary": "Lighthouse unavailable — Node.js required."}
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_path = Path(tmp_dir) / "lighthouse"
            cmd = ["npx", "lighthouse", url, "--output=json", "--quiet", "--chrome-flags=--headless=new --no-sandbox --disable-gpu", f"--output-path={out_path}"]
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
                json_file = out_path.with_suffix(".report.json")
                if not json_file.exists():
                    return {"status": "error", "message": "Lighthouse produced no output.", "stderr": result.stderr[:400]}
                report = json.loads(json_file.read_text(encoding="utf-8"))
                categories = {k: round((v.get("score") or 0) * 100) for k, v in (report.get("categories") or {}).items()}
                audits = report.get("audits") or {}
                opportunities = []
                for audit_id, audit in audits.items():
                    if audit.get("score") is not None and float(audit.get("score") or 1) < 0.9:
                        savings = audit.get("details", {}).get("overallSavingsMs") or 0
                        opportunities.append({"id": audit_id, "title": audit.get("title", audit_id), "score": round(float(audit.get("score") or 0), 2), "savings_ms": int(savings), "display_value": str(audit.get("displayValue") or "")})
                opportunities.sort(key=lambda x: x["score"])
                score_summary = " | ".join(f"{k}: {v}" for k, v in categories.items())
                return {"status": "ok", "mode": "lighthouse", "url": url, "categories": categories, "top_opportunities": opportunities[:10], "summary": f"Lighthouse scores — {score_summary}"}
            except subprocess.TimeoutExpired:
                return {"status": "error", "message": "Lighthouse timed out (90s)."}
            except Exception as exc:
                return {"status": "error", "message": f"Lighthouse error: {exc}"}

    def run_site_audit(self, url: str) -> Dict[str, Any]:
        request = self._normalize_request({"action": "snapshot", "url": url})
        state = self._load_state()
        session_id = f"audit-{uuid.uuid4().hex[:8]}"
        if self._mcp_available():
            browser_result = self._run_playwright_mcp(request)
        else:
            response = self._run_actions(state=state, session_id=session_id, actions=[{"action": "snapshot", "url": url}], max_links=20)
            self._save_state(state)
            browser_result = response
        lighthouse_result = self._run_lighthouse(url)
        combined_summary = str(browser_result.get("summary") or "")
        if lighthouse_result.get("status") == "ok":
            combined_summary += " | " + str(lighthouse_result.get("summary") or "")
        return {"status": "ok", "agent": self.name, "mode": "site_audit", "url": url, "summary": combined_summary.strip(" |"), "browser": browser_result, "lighthouse": lighthouse_result}

    @staticmethod
    def human_gate(reason: str, *, context: Dict[str, Any] | None = None) -> Dict[str, Any]:
        return {"status": "human_gate", "reason": reason, "context": context or {}, "summary": f"Waiting for human input: {reason}", "instructions": "Complete the required action in the browser window, then resume the workflow."}
    def execute_action(self, action_type: str, target: str, details: Dict[str, Any]):
        payload = dict(details or {})
        payload.setdefault("action", action_type)
        payload.setdefault("url", target)
        payload.setdefault("prompt", target)
        if action_type in {"open", "navigate", "snapshot", "inspect", "load", "submit", "post", "click", "replay"}:
            return self.run(payload)
        return {
            "status": "unknown_action",
            "agent": self.name,
            "action": action_type,
            "target": target,
            "mode": "browser_automation_v2",
        }
