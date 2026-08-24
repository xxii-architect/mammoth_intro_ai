from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any, Dict, List, Tuple
from urllib.parse import urljoin, urlparse

import requests

from .base_agent import BaseAgent


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
    """Structured browser snapshot agent for web page inspection."""

    name = "BrowserAgent"

    def _normalize_request(self, prompt: Any) -> Dict[str, Any]:
        if isinstance(prompt, dict):
            raw = dict(prompt)
            url = str(raw.get("url") or raw.get("target") or raw.get("href") or "").strip()
            prompt_text = str(raw.get("prompt") or raw.get("query") or raw.get("content") or "").strip()
            if not url and prompt_text.lower().startswith(("http://", "https://")):
                url = prompt_text
            return {
                "url": url,
                "prompt": prompt_text,
                "mode": str(raw.get("mode") or "snapshot").strip() or "snapshot",
                "follow_links": bool(raw.get("follow_links", True)),
                "max_links": max(1, min(25, int(raw.get("max_links") or 10))),
            }

        text = str(prompt or "").strip()
        if text.lower().startswith(("http://", "https://")):
            return {"url": text, "prompt": text, "mode": "snapshot", "follow_links": True, "max_links": 10}
        return {"url": "", "prompt": text, "mode": "snapshot", "follow_links": True, "max_links": 10}

    def _load_page(self, url: str) -> Dict[str, Any]:
        headers = {
            "User-Agent": "MammothOS/1.0 BrowserAgent",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        response = requests.get(url, headers=headers, timeout=12, allow_redirects=True)
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

    def run(self, prompt: Any) -> Dict[str, Any]:
        request = self._normalize_request(prompt)
        url = request.get("url", "")
        if not url:
            query = str(request.get("prompt") or "").strip()
            return {
                "status": "needs_context",
                "agent": self.name,
                "mode": "browser_snapshot_v1",
                "message": "Provide a URL to inspect so I can snapshot the page.",
                "prompt": query,
                "url": "",
                "links": [],
                "headings": [],
                "text": "",
                "summary": "BrowserAgent needs a URL before it can fetch a page snapshot.",
            }

        try:
            page = self._load_page(url)
        except requests.RequestException as exc:
            return {
                "status": "error",
                "agent": self.name,
                "mode": "browser_snapshot_v1",
                "url": url,
                "message": f"Unable to load page: {exc}",
            }

        links = page.get("links") if isinstance(page.get("links"), list) else []
        limited_links = [
            {
                "href": str(link.get("href") or "").strip(),
                "text": str(link.get("text") or "").strip(),
            }
            for link in links[: int(request.get("max_links") or 10)]
            if str(link.get("href") or "").strip()
        ]
        headings = [str(item).strip() for item in (page.get("headings") or []) if str(item).strip()]
        text = str(page.get("text") or "").strip()
        title = str(page.get("title") or url).strip() or url
        description = str(page.get("description") or "").strip()
        summary_bits = [title]
        if description:
            summary_bits.append(description)
        if headings:
            summary_bits.append(f"{len(headings)} heading(s)")
        if limited_links:
            summary_bits.append(f"{len(limited_links)} link(s)")

        return {
            "status": "ok",
            "agent": self.name,
            "mode": "browser_snapshot_v1",
            "prompt": str(request.get("prompt") or url),
            "url": url,
            "final_url": page.get("final_url") or url,
            "status_code": int(page.get("status_code") or 0),
            "content_type": str(page.get("content_type") or ""),
            "title": title,
            "description": description,
            "headings": headings,
            "links": limited_links,
            "text_excerpt": text[:1200],
            "word_count": int(page.get("word_count") or len(text.split())),
            "summary": " • ".join(summary_bits),
            "observations": [
                f"Captured {len(headings)} heading(s).",
                f"Captured {len(limited_links)} link(s).",
                f"Text length: {len(text)} characters.",
            ],
        }

    def execute_action(self, action_type: str, target: str, details: Dict[str, Any]):
        payload = dict(details or {})
        payload.setdefault("url", target)
        payload.setdefault("prompt", target)
        if action_type in {"open", "navigate", "snapshot", "inspect", "load"}:
            return self.run(payload)
        return {
            "status": "unknown_action",
            "agent": self.name,
            "action": action_type,
            "target": target,
        }
