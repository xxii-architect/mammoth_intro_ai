"""
RAG Context Store — User-scoped reusable AI context with privacy enforcement.

Stores AI-generated insights, lesson summaries, struggle patterns, and
learning signals that can be safely reused across sessions for the same user.

Privacy model:
- User personal data is NEVER mixed across user scopes.
- AI-generated context (summaries, topic maps, struggle tags) is stored and reused.
- Raw user messages are NOT stored; only derived/structured signals are.
- Each context entry is tagged with: user_id, topic, source_agent, ttl, reusable flag.
"""
from __future__ import annotations

import datetime
import json
import uuid
from typing import Any, Dict, List, Optional


class ContextEntry:
    """A single reusable context record derived from AI processing."""

    def __init__(
        self,
        entry_id: str,
        user_id: str,
        topic: str,
        content_type: str,
        content: Any,
        source_agent: str,
        tags: Optional[List[str]] = None,
        ttl_hours: int = 72,
        reusable: bool = True,
    ):
        self.entry_id = entry_id
        self.user_id = user_id
        self.topic = topic
        self.content_type = content_type
        self.content = content
        self.source_agent = source_agent
        self.tags = tags or []
        self.created_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self.expires_at = (
            datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=ttl_hours)
        ).isoformat()
        self.reusable = reusable
        self.access_count = 0

    def is_expired(self) -> bool:
        try:
            return datetime.datetime.fromisoformat(self.expires_at) < datetime.datetime.now(datetime.timezone.utc)
        except Exception:
            return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "user_id": self.user_id,
            "topic": self.topic,
            "content_type": self.content_type,
            "content": self.content,
            "source_agent": self.source_agent,
            "tags": self.tags,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "reusable": self.reusable,
            "access_count": self.access_count,
        }


class RAGContextStore:
    """
    User-scoped in-process context store for reusable AI-derived insights.
    Designed to complement Supabase persistent storage with fast local access.
    """

    def __init__(self):
        # user_id -> list of ContextEntry
        self._store: Dict[str, List[ContextEntry]] = {}

    def _user_store(self, user_id: str) -> List[ContextEntry]:
        if user_id not in self._store:
            self._store[user_id] = []
        return self._store[user_id]

    def store(
        self,
        user_id: str,
        topic: str,
        content_type: str,
        content: Any,
        source_agent: str,
        tags: Optional[List[str]] = None,
        ttl_hours: int = 72,
        reusable: bool = True,
    ) -> str:
        """Store a new AI-derived context entry for a user. Returns entry_id."""
        entry_id = str(uuid.uuid4())
        entry = ContextEntry(
            entry_id=entry_id,
            user_id=user_id,
            topic=topic,
            content_type=content_type,
            content=content,
            source_agent=source_agent,
            tags=tags,
            ttl_hours=ttl_hours,
            reusable=reusable,
        )
        store = self._user_store(user_id)
        # Deduplicate by topic + content_type (keep latest)
        store = [e for e in store if not (e.topic == topic and e.content_type == content_type)]
        store.append(entry)
        self._store[user_id] = store
        return entry_id

    def retrieve(
        self,
        user_id: str,
        topic: Optional[str] = None,
        content_type: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Retrieve reusable context for a user, filtered by topic/type/tags."""
        store = self._user_store(user_id)
        results = []
        for entry in store:
            if entry.is_expired():
                continue
            if not entry.reusable:
                continue
            if topic and entry.topic.lower() != topic.lower():
                continue
            if content_type and entry.content_type != content_type:
                continue
            if tags and not any(t in entry.tags for t in tags):
                continue
            entry.access_count += 1
            results.append(entry.to_dict())
        results.sort(key=lambda e: e.get("access_count", 0), reverse=True)
        return results[:limit]

    def purge_expired(self, user_id: Optional[str] = None) -> int:
        purged = 0
        targets = [user_id] if user_id else list(self._store.keys())
        for uid in targets:
            before = len(self._store.get(uid, []))
            self._store[uid] = [e for e in self._store.get(uid, []) if not e.is_expired()]
            purged += before - len(self._store[uid])
        return purged

    def delete_user_data(self, user_id: str) -> int:
        """Remove ALL context for a user (GDPR/privacy wipe)."""
        count = len(self._store.pop(user_id, []))
        return count

    def summary(self) -> Dict[str, Any]:
        total = sum(len(v) for v in self._store.values())
        return {
            "user_count": len(self._store),
            "total_entries": total,
        }

    # ------------------------------------------------------------------
    # Privacy-safe RAG summariser
    # ------------------------------------------------------------------
    _PII_PATTERNS = [
        r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b",  # email
        r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b",  # phone
        r"\b(?:https?://\S+)",                                         # URLs
    ]

    def _strip_pii(self, text: str) -> str:
        """Remove obvious PII tokens from a text string."""
        import re
        for pat in self._PII_PATTERNS:
            text = re.sub(pat, "[REDACTED]", text, flags=re.IGNORECASE)
        return text

    def summarize_for_rag(self, user_id: str, raw_session_data: Dict[str, Any]) -> str:
        """
        Extract AI-derived signals from raw session data and store them.

        Strips PII (names, emails, phone numbers, URLs) before storing.
        Returns the new entry_id.
        """
        # Pull out safe, AI-derived signals only
        topics: List[str] = []
        for t in raw_session_data.get("topics", []):
            topics.append(self._strip_pii(str(t)))

        struggle_indicators: List[str] = []
        for s in raw_session_data.get("struggle_indicators", []):
            struggle_indicators.append(self._strip_pii(str(s)))

        mastery_signals: List[str] = []
        for m in raw_session_data.get("mastery_signals", []):
            mastery_signals.append(self._strip_pii(str(m)))

        difficulty = raw_session_data.get("difficulty", "intermediate")
        agent_name = self._strip_pii(str(raw_session_data.get("agent", "system")))

        content = {
            "topics": topics,
            "struggle_indicators": struggle_indicators,
            "mastery_signals": mastery_signals,
            "difficulty": difficulty,
        }
        tags = ["rag_summary"] + topics[:5]

        return self.store(
            user_id=user_id,
            topic="session_summary",
            content_type="rag_signal",
            content=content,
            source_agent=agent_name,
            tags=tags,
            ttl_hours=72,
        )


# Process-level singleton
_rag_context_store: Optional[RAGContextStore] = None


def get_rag_context_store() -> RAGContextStore:
    global _rag_context_store
    if _rag_context_store is None:
        _rag_context_store = RAGContextStore()
    return _rag_context_store

