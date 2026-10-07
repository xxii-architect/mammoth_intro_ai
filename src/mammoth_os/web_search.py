"""Licensed web-search providers for MammothOS (contract ``mammoth.websearch.v1``).

Stdlib only. Picks a provider from the environment:

- ``BRAVE_SEARCH_API_KEY``  → Brave Search API
- ``TAVILY_API_KEY``        → Tavily Search API
- ``MAMMOTH_WEB_SEARCH_PROVIDER`` = ``brave`` | ``tavily`` | ``auto`` (default ``auto``: Brave, then Tavily)

Every call is bounded: short timeout, a small TTL cache so repeated queries cost nothing,
a minimum interval between upstream calls, and a per-process daily cap
(``MAMMOTH_WEB_SEARCH_DAILY_LIMIT``, default 1000). API keys never leave the server and are
never included in results or errors.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from mammoth_os.research_quality import filter_search_sources, search_quality

CONTRACT = "mammoth.websearch.v1"
PROVIDERS = ("brave", "tavily")
MAX_RESULTS = 10
DEFAULT_TIMEOUT = 8.0
CACHE_TTL_SECONDS = 600
CACHE_SIZE = 128
MIN_INTERVAL_SECONDS = 1.0
USER_AGENT = "MammothOS/1.0 (+https://command.truexxiisupply.com)"

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")

Transport = Callable[[urllib.request.Request, float], Dict[str, Any]]


def _clean(text: Any, limit: int = 600) -> str:
    value = _WS_RE.sub(" ", _TAG_RE.sub("", str(text or ""))).strip()
    for entity, char in (("&amp;", "&"), ("&quot;", '"'), ("&#39;", "'"), ("&#x27;", "'"), ("&lt;", "<"), ("&gt;", ">"), ("&nbsp;", " ")):
        value = value.replace(entity, char)
    return value[:limit]


def _public_http_url(url: Any) -> str:
    text = str(url or "").strip()
    parsed = urllib.parse.urlparse(text)
    return text if parsed.scheme in {"http", "https"} and parsed.netloc else ""


def _default_transport(request: urllib.request.Request, timeout: float) -> Dict[str, Any]:
    with urllib.request.urlopen(request, timeout=timeout) as resp:  # noqa: S310 - fixed provider hosts only
        return json.loads(resp.read(1_000_000).decode("utf-8", errors="replace"))


def resolve_provider(env: Optional[Dict[str, str]] = None) -> Optional[Dict[str, str]]:
    """Return ``{"name", "key"}`` for the configured provider, or ``None``."""
    source = env if env is not None else os.environ
    keys = {
        "brave": str(source.get("BRAVE_SEARCH_API_KEY") or "").strip(),
        "tavily": str(source.get("TAVILY_API_KEY") or "").strip(),
    }
    wanted = str(source.get("MAMMOTH_WEB_SEARCH_PROVIDER") or "auto").strip().lower()
    order = [wanted] if wanted in PROVIDERS else list(PROVIDERS)
    for name in order:
        if keys.get(name):
            return {"name": name, "key": keys[name]}
    return None


def _brave_request(query: str, limit: int, key: str) -> urllib.request.Request:
    params = urllib.parse.urlencode({"q": query, "count": limit, "safesearch": "moderate"})
    return urllib.request.Request(
        f"https://api.search.brave.com/res/v1/web/search?{params}",
        headers={"Accept": "application/json", "X-Subscription-Token": key, "User-Agent": USER_AGENT},
    )


def _brave_results(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    items = ((payload.get("web") or {}).get("results")) if isinstance(payload, dict) else None
    out: List[Dict[str, Any]] = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        url = _public_http_url(item.get("url"))
        snippet = _clean(item.get("description"))
        if not url or not snippet:
            continue
        publisher = (item.get("profile") or {}).get("name") or (item.get("meta_url") or {}).get("hostname") or urllib.parse.urlparse(url).netloc
        out.append({"title": _clean(item.get("title"), 200) or url, "url": url, "snippet": snippet, "publisher": _clean(publisher, 120)})
    return out


def _tavily_request(query: str, limit: int, key: str) -> urllib.request.Request:
    body = json.dumps({"query": query, "max_results": limit, "search_depth": "basic", "include_answer": False}).encode("utf-8")
    return urllib.request.Request(
        "https://api.tavily.com/search",
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}", "User-Agent": USER_AGENT},
    )


def _tavily_results(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    items = payload.get("results") if isinstance(payload, dict) else None
    out: List[Dict[str, Any]] = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        url = _public_http_url(item.get("url"))
        snippet = _clean(item.get("content"))
        if not url or not snippet:
            continue
        out.append({"title": _clean(item.get("title"), 200) or url, "url": url, "snippet": snippet, "publisher": urllib.parse.urlparse(url).netloc})
    return out


_ADAPTERS = {
    "brave": (_brave_request, _brave_results),
    "tavily": (_tavily_request, _tavily_results),
}


class WebSearch:
    """Bounded, cached client over the configured provider. Thread-safe."""

    def __init__(
        self,
        *,
        env: Optional[Dict[str, str]] = None,
        transport: Optional[Transport] = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self._env = env
        self._transport = transport or _default_transport
        self._clock = clock
        self._sleep = sleep
        self._lock = threading.Lock()
        self._cache: "OrderedDict[tuple, tuple[float, Dict[str, Any]]]" = OrderedDict()
        self._last_call = 0.0
        self._day = ""
        self._count = 0

    def _daily_limit(self) -> int:
        source = self._env if self._env is not None else os.environ
        try:
            return max(0, int(str(source.get("MAMMOTH_WEB_SEARCH_DAILY_LIMIT") or "1000")))
        except ValueError:
            return 1000

    def status(self) -> Dict[str, Any]:
        provider = resolve_provider(self._env)
        return {
            "contract": CONTRACT,
            "configured": provider is not None,
            "provider": provider["name"] if provider else None,
            "daily_limit": self._daily_limit(),
            "used_today": self._count if self._day == datetime.now(timezone.utc).date().isoformat() else 0,
        }

    def configured(self) -> bool:
        return resolve_provider(self._env) is not None

    def search(self, query: str, limit: int = 5, *, timeout: float = DEFAULT_TIMEOUT) -> Dict[str, Any]:
        q = _WS_RE.sub(" ", str(query or "")).strip()[:300]
        limit = max(1, min(int(limit or 5), MAX_RESULTS))
        provider = resolve_provider(self._env)
        base = {"contract": CONTRACT, "query": q, "provider": provider["name"] if provider else None}
        if not q:
            return {**base, "status": "error", "code": "empty_query", "error": "Search query is required.", "results": []}
        if provider is None:
            return {**base, "status": "not_configured", "code": "not_configured",
                    "error": "Web search is not configured. Set BRAVE_SEARCH_API_KEY or TAVILY_API_KEY.", "results": []}

        cache_key = (provider["name"], q.lower(), limit)
        now = self._clock()
        with self._lock:
            hit = self._cache.get(cache_key)
            if hit and now - hit[0] < CACHE_TTL_SECONDS:
                self._cache.move_to_end(cache_key)
                return {**hit[1], "cached": True}
            today = datetime.now(timezone.utc).date().isoformat()
            if today != self._day:
                self._day, self._count = today, 0
            if self._count >= self._daily_limit():
                return {**base, "status": "error", "code": "daily_limit", "error": "Daily web-search limit reached.", "results": []}
            self._count += 1
            wait = MIN_INTERVAL_SECONDS - (now - self._last_call)
            self._last_call = now + max(0.0, wait)
        if wait > 0:
            self._sleep(wait)

        build_request, parse = _ADAPTERS[provider["name"]]
        try:
            payload = self._transport(build_request(q, limit, provider["key"]), timeout)
        except urllib.error.HTTPError as exc:
            code = "rate_limited" if exc.code == 429 else "auth_failed" if exc.code in {401, 403} else "provider_error"
            return {**base, "status": "error", "code": code, "error": f"Search provider returned HTTP {exc.code}.", "results": []}
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            return {**base, "status": "error", "code": "unreachable", "error": "Search provider could not be reached.", "results": []}

        kept, dropped = filter_search_sources(parse(payload), q)
        selected = kept[:limit]
        result = {
            **base, "status": "ok", "results": selected, "cached": False,
            "quality": search_quality(selected, dropped),
        }
        with self._lock:
            self._cache[cache_key] = (now, result)
            while len(self._cache) > CACHE_SIZE:
                self._cache.popitem(last=False)
        return result


_DEFAULT: Optional[WebSearch] = None
_DEFAULT_LOCK = threading.Lock()


def default_web_search() -> WebSearch:
    global _DEFAULT
    with _DEFAULT_LOCK:
        if _DEFAULT is None:
            _DEFAULT = WebSearch()
        return _DEFAULT


def web_search(query: str, limit: int = 5) -> Dict[str, Any]:
    return default_web_search().search(query, limit)


def web_search_status() -> Dict[str, Any]:
    return default_web_search().status()
