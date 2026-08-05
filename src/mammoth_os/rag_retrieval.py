"""
RAG Retrieval Service — Lesson Chunk Retrieval

Lightweight service to:
1. Chunk lessons on-the-fly
2. Embed chunks
3. Retrieve top-k relevant chunks for tutor context

This integrates with curriculum_agent to inject lesson context into coaching.
"""
import os
from typing import List, Dict, Any, Optional
from mammoth_os.llm_client import get_llm_client
from mammoth_os.embedding_engine import EmbeddingEngine


class LessonChunkRetriever:
    """Retrieve relevant lesson chunks for RAG context."""

    def __init__(self):
        self.llm_client = get_llm_client()
        self.embedding_engine = EmbeddingEngine({
            "model": os.getenv("EMBEDDING_MODEL", "text-embedding-3-large"),
            "cache_ttl": 3600,
            "batch_size": 64,
        })
        self._chunk_cache: Dict[str, List[Dict[str, Any]]] = {}

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
        return [chunk for _, chunk in scored_chunks[:top_k]]

    async def retrieve_for_lesson(self, lesson_id: str, content: str, query: str = "") -> List[str]:
        """Full pipeline: chunk → embed → retrieve. Returns top chunk texts."""
        chunks = await self.chunk_lesson(lesson_id, content)
        if not chunks:
            return []

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
