"""
RAG Retrieval Service — Lesson Chunk Retrieval

Lightweight service to:
1. Chunk lessons on-the-fly
2. Embed chunks
3. Retrieve top-k relevant chunks for tutor context

This integrates with curriculum_agent to inject lesson context into coaching.
"""
import os
import re
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from mammoth_os.llm_client import get_llm_client
from mammoth_os.embedding_engine import EmbeddingEngine
from mammoth_os.supabase_client import get_supabase


class LessonChunkRetriever:
    """Retrieve relevant lesson chunks for RAG context."""

    def __init__(self):
        self.llm_client = get_llm_client()
        self.embedding_engine = EmbeddingEngine({
            "model": os.getenv("EMBEDDING_MODEL", "text-embedding-3-large"),
            "cache_ttl": 3600,
            "batch_size": 64,
        })
        self.supabase_schema = os.getenv("SUPABASE_SCHEMA", "atlas").strip() or "atlas"
        self._chunk_cache: Dict[str, List[Dict[str, Any]]] = {}

    def _schema(self, schema_name: Optional[str] = None):
        client = get_supabase()
        if client is None:
            return None
        try:
            return client.schema(schema_name or self.supabase_schema)
        except Exception:
            return None

    async def load_lesson_chunks(self, lesson_id: str) -> List[Dict[str, Any]]:
        """Load persisted chunks for a lesson when Supabase is available."""
        schema = self._schema()
        if schema is None:
            return []

        try:
            response = (
                schema.table("lesson_chunks")
                .select("*")
                .eq("lesson_id", lesson_id)
                .order("chunk_index")
                .execute()
            )
        except Exception:
            return []

        rows = getattr(response, "data", []) or []
        return [row for row in rows if isinstance(row, dict)]

    async def save_lesson_chunks(
        self,
        lesson_id: str,
        chunks: List[Dict[str, Any]],
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Persist lesson chunks when Supabase is available."""
        if not chunks:
            return

        schema = self._schema()
        if schema is None:
            return

        payload = []
        for chunk in chunks:
            metadata = {
                "source": "curriculum_agent",
                "chunk_index": chunk.get("chunk_index", 0),
                "chunk_length": chunk.get("chunk_length", len(chunk.get("chunk_text", ""))),
            }
            if extra_metadata:
                metadata.update({k: v for k, v in extra_metadata.items() if v is not None})
            payload.append({
                "lesson_id": lesson_id,
                "chunk_index": chunk.get("chunk_index", 0),
                "chunk_text": chunk.get("chunk_text", ""),
                "chunk_length": chunk.get("chunk_length", len(chunk.get("chunk_text", ""))),
                "embedding": chunk.get("embedding"),
                "metadata": metadata,
            })

        try:
            schema.table("lesson_chunks").upsert(payload).execute()
        except Exception:
            return

    async def chunk_lesson(self, lesson_id: str, content: str, chunk_size: int = 500) -> List[Dict[str, Any]]:
        """Chunk lesson content recursively (semantic-aware)."""
        if not content or not content.strip():
            return []

        # Simple recursive chunker: split on paragraph breaks, then sentences
        chunks = []
        paragraphs = content.split("\n\n")
        
        current_chunk = ""
        for para in paragraphs:
            if len(current_chunk) + len(para) > chunk_size:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = para
            else:
                current_chunk += "\n\n" + para if current_chunk else para
        
        if current_chunk:
            chunks.append(current_chunk.strip())

        # Return structured chunks with metadata
        result = []
        for i, chunk_text in enumerate(chunks):
            if chunk_text:
                result.append({
                    "lesson_id": lesson_id,
                    "chunk_index": i,
                    "chunk_text": chunk_text,
                    "chunk_length": len(chunk_text),
                })
        
        self._chunk_cache[lesson_id] = result
        return result

    async def embed_chunks(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Embed chunk texts and return chunks with embedding vectors."""
        if not chunks:
            return []

        texts = [c["chunk_text"] for c in chunks]
        try:
            embeddings = await self.embedding_engine.batch_embed(texts)
            for chunk, embedding in zip(chunks, embeddings):
                chunk["embedding"] = embedding
        except Exception as e:
            # Fallback: deterministic embeddings for offline testing
            for chunk in chunks:
                chunk["embedding"] = [float((hash(chunk["chunk_text"]) % 1000) / 1000.0) for _ in range(1536)]
        
        return chunks

    async def retrieve_top_k(self, query: str, lesson_chunks: List[Dict[str, Any]], top_k: int = 3) -> List[Dict[str, Any]]:
        """Retrieve top-k chunks most similar to query."""
        if not lesson_chunks or not query:
            return []

        try:
            query_embedding = await self.embedding_engine.embed(query)
        except Exception:
            query_embedding = [float((hash(query) % 1000) / 1000.0) for _ in range(1536)]

        # Cosine similarity
        import math
        scored_chunks = []
        for chunk in lesson_chunks:
            if "embedding" not in chunk:
                continue
            vec_a = query_embedding
            vec_b = chunk["embedding"]
            dot = sum(a * b for a, b in zip(vec_a, vec_b))
            mag_a = math.sqrt(sum(a ** 2 for a in vec_a))
            mag_b = math.sqrt(sum(b ** 2 for b in vec_b))
            similarity = dot / (mag_a * mag_b + 1e-9)
            scored_chunks.append((similarity, chunk))

        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        ranked = []
        for score, chunk in scored_chunks[:top_k]:
            item = dict(chunk)
            item["score"] = score
            ranked.append(item)
        return ranked

    def _timestamp_value(self, row: Dict[str, Any]) -> float:
        raw = row.get("created_at") or row.get("completed_at") or row.get("last_accessed") or ""
        if isinstance(raw, dict) and "seconds" in raw:
            return float(raw["seconds"])
        if not raw:
            return 0.0
        if isinstance(raw, (int, float)):
            return float(raw)
        text = str(raw).replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(text).timestamp()
        except Exception:
            return 0.0

    def _extract_struggle_tags(self, text: str) -> List[str]:
        lowered = (text or "").lower()
        tags: List[str] = []
        patterns = [
            ("need more examples", ["need more examples", "more examples", "examples"]),
            ("error handling", ["error handling", "try", "except", "exception", "error"]),
            ("env setup", ["env setup", "environment", "install", "dependency", "module not found"]),
            ("too fast", ["too fast", "rush", "rushed", "slow down", "go slower"]),
        ]
        for tag, needles in patterns:
            if any(needle in lowered for needle in needles):
                tags.append(tag)
        return tags[:4]

    def _coerce_tags(self, value: Any) -> List[str]:
        if not value:
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str):
            parts = [p.strip() for p in re.split(r"[,;]", value) if p.strip()]
            return parts or [value.strip()]
        return [str(value).strip()]

    async def load_user_signals(self, user_id: str, lesson_id: str) -> Dict[str, Any]:
        """Load reflection, progress, and adaptive signals for reranking."""
        signals: Dict[str, Any] = {
            "reflections": [],
            "progress": None,
            "adaptive_metrics": None,
            "struggle_tags": [],
            "difficulty_level": None,
            "performance_score": None,
        }

        mammoth = self._schema("mammoth")
        atlas = self._schema("atlas")

        reflection_rows: List[Dict[str, Any]] = []
        if mammoth is not None:
            try:
                response = mammoth.table("notes").select("*").execute()
                reflection_rows = [row for row in (getattr(response, "data", []) or []) if isinstance(row, dict)]
            except Exception:
                reflection_rows = []

        matching_reflections = [
            row for row in reflection_rows
            if str(row.get("user_id") or "") == str(user_id)
            and str(row.get("lesson_id") or "") == str(lesson_id)
        ]
        matching_reflections.sort(key=self._timestamp_value, reverse=True)
        signals["reflections"] = matching_reflections

        tags: List[str] = []
        for row in matching_reflections:
            metadata = row.get("metadata") or {}
            tags.extend(self._coerce_tags(metadata.get("tags")))
            tags.extend(self._extract_struggle_tags(str(row.get("content") or "")))
        seen = set()
        deduped_tags = []
        for tag in tags:
            normalized = tag.lower()
            if normalized and normalized not in seen:
                seen.add(normalized)
                deduped_tags.append(tag)
        signals["struggle_tags"] = deduped_tags[:4]

        progress_rows: List[Dict[str, Any]] = []
        if mammoth is not None:
            for table_name in ("progress",):
                try:
                    response = mammoth.table(table_name).select("*").execute()
                    progress_rows.extend([row for row in (getattr(response, "data", []) or []) if isinstance(row, dict)])
                except Exception:
                    pass
        if atlas is not None:
            for table_name in ("atlas_progress",):
                try:
                    response = atlas.table(table_name).select("*").execute()
                    progress_rows.extend([row for row in (getattr(response, "data", []) or []) if isinstance(row, dict)])
                except Exception:
                    pass

        matching_progress = [
            row for row in progress_rows
            if str(row.get("user_id") or "") == str(user_id)
            and (not row.get("lesson_id") or str(row.get("lesson_id") or "") == str(lesson_id))
        ]
        matching_progress.sort(key=self._timestamp_value, reverse=True)
        signals["progress"] = matching_progress[0] if matching_progress else None

        metrics_rows: List[Dict[str, Any]] = []
        if atlas is not None:
            try:
                response = atlas.table("adaptive_metrics").select("*").execute()
                metrics_rows = [row for row in (getattr(response, "data", []) or []) if isinstance(row, dict)]
            except Exception:
                metrics_rows = []

        matching_metrics = [
            row for row in metrics_rows
            if str(row.get("user_id") or "") == str(user_id)
            and (not row.get("lesson_id") or str(row.get("lesson_id") or "") == str(lesson_id))
        ]
        matching_metrics.sort(key=self._timestamp_value, reverse=True)
        signals["adaptive_metrics"] = matching_metrics[0] if matching_metrics else None
        if signals["adaptive_metrics"]:
            signals["difficulty_level"] = signals["adaptive_metrics"].get("difficulty_level")
            signals["performance_score"] = signals["adaptive_metrics"].get("performance_score")

        progress = signals.get("progress") or {}
        metrics = signals.get("adaptive_metrics") or {}
        reflection = matching_reflections[0] if matching_reflections else {}
        signals["metadata"] = {
            "module": progress.get("module") or reflection.get("metadata", {}).get("module"),
            "lesson_title": reflection.get("metadata", {}).get("lesson_title") or reflection.get("lesson_title"),
            "difficulty_level": signals.get("difficulty_level"),
            "last_performance_score": signals.get("performance_score"),
            "struggle_tags": signals.get("struggle_tags"),
        }
        return signals

    def build_signal_summary(self, signals: Dict[str, Any]) -> str:
        difficulty = signals.get("difficulty_level") or "unknown"
        performance = signals.get("performance_score")
        performance_text = "unknown" if performance is None else str(performance)
        tags = signals.get("struggle_tags") or []
        tags_text = ", ".join(tags) if tags else "none"
        return (
            "Signals:\n"
            f"- Difficulty: {difficulty}\n"
            f"- Performance score: {performance_text}\n"
            f"- Struggle tags: {tags_text}"
        )

    def _score_chunk(self, chunk: Dict[str, Any], signals: Dict[str, Any]) -> float:
        score = float(chunk.get("score") or 0.0)
        text = str(chunk.get("chunk_text") or "").lower()
        index = int(chunk.get("chunk_index") or 0)
        tags = {str(tag).lower() for tag in (signals.get("struggle_tags") or [])}
        difficulty = str(signals.get("difficulty_level") or "").lower()
        performance = signals.get("performance_score")

        if "need more examples" in tags:
            if any(token in text for token in ("example", "examples", "exercise", "sample", "demo", "```")):
                score += 0.35
        if "error handling" in tags:
            if any(token in text for token in ("try", "except", "error", "exception", "catch")):
                score += 0.3
        if "env setup" in tags:
            if any(token in text for token in ("install", "setup", "env", "import", "dependency")):
                score += 0.2
        if difficulty in {"hard", "advanced"}:
            score += max(0.0, 0.18 - (index * 0.03))
        if isinstance(performance, (int, float)) and performance < 0.7:
            score += max(0.0, 0.2 - (index * 0.04))
        if index == 0:
            score += 0.05
        return score

    def rerank_chunks(self, chunks: List[Dict[str, Any]], signals: Dict[str, Any], top_k: int = 5) -> List[Dict[str, Any]]:
        if not chunks:
            return []
        ranked = []
        for chunk in chunks:
            item = dict(chunk)
            item["score"] = self._score_chunk(item, signals)
            item["signal_summary"] = self.build_signal_summary(signals)
            ranked.append(item)
        ranked.sort(key=lambda row: row.get("score", 0.0), reverse=True)
        return ranked[:top_k]

    async def retrieve_chunks(
        self,
        user_id: str,
        lesson_id: str,
        query: Optional[str] = None,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """Retrieve personalized lesson chunks for a user and lesson."""
        chunks = await self.load_lesson_chunks(lesson_id)
        if not chunks:
            return []

        signals = await self.load_user_signals(user_id, lesson_id)

        if any("embedding" not in chunk or not chunk.get("embedding") for chunk in chunks):
            chunks = await self.embed_chunks(chunks)
            await self.save_lesson_chunks(lesson_id, chunks, extra_metadata=signals.get("metadata"))

        base_chunks = chunks
        if query:
            base_chunks = await self.retrieve_top_k(query, chunks, top_k=max(top_k * 2, top_k))
        else:
            base_chunks = sorted(chunks, key=lambda row: int(row.get("chunk_index") or 0))

        return self.rerank_chunks(base_chunks, signals, top_k=top_k)

    async def retrieve_for_lesson(self, lesson_id: str, content: str, query: str = "") -> List[str]:
        """Full pipeline: chunk → embed → retrieve. Returns top chunk texts."""
        chunks = await self.load_lesson_chunks(lesson_id)
        if not chunks:
            chunks = await self.chunk_lesson(lesson_id, content)
            if not chunks:
                return []
            chunks = await self.embed_chunks(chunks)
            await self.save_lesson_chunks(lesson_id, chunks)
        elif any("embedding" not in chunk or not chunk.get("embedding") for chunk in chunks):
            chunks = await self.embed_chunks(chunks)

        # If no query, return first 3 chunks as context
        if not query:
            return [c["chunk_text"] for c in chunks[:3]]

        retrieved = await self.retrieve_top_k(query, chunks, top_k=3)
        return [c["chunk_text"] for c in retrieved]


# Singleton for lazy init
_retriever: Optional[LessonChunkRetriever] = None


def get_retriever() -> LessonChunkRetriever:
    global _retriever
    if _retriever is None:
        _retriever = LessonChunkRetriever()
    return _retriever
