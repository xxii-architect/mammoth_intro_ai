"""
doc_rag_pipeline.py
Post-generation pipeline fired after any document is produced.

Three independent, non-fatal stages:
  1. RAG seeding   — chunk + embed + upsert into VectorStoreAgent (collection="documents")
  2. ATLAS lessons — extract key-finding sentences and upsert into atlas.atlas_lessons
  3. Library save  — POST artifact record to /api/workspace/artifacts

Usage (fire-and-forget):
    import asyncio
    from mammoth_os.doc_rag_pipeline import seed_document
    asyncio.create_task(seed_document(title, content, source_url, tenant_id))
"""
import asyncio, os, re, uuid
from datetime import datetime, timezone

CHUNK_SIZE = 512
CHUNK_OVERLAP = 64
_SIGNAL_RE = re.compile(
    r"\b(key|finding|conclusion|insight|recommend|result|takeaway|summary|highlight|discover)\b",
    re.IGNORECASE,
)

def _chunk(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list:
    chunks, i, step = [], 0, max(size - overlap, 1)
    while i < len(text):
        chunks.append(text[i : i + size])
        i += step
    return chunks

async def _embed_and_upsert(title: str, content: str, source_url: str, tenant_id: str) -> None:
    from mammoth_os.embedding_engine import EmbeddingEngine
    from mammoth_os.agents.vector_store_agent import VectorStoreAgent
    engine = EmbeddingEngine({
        "model": os.getenv("EMBEDDING_MODEL", "text-embedding-3-large"),
        "cache_ttl": 3600, "batch_size": 64,
    })
    vs = VectorStoreAgent(router=None)
    try:
        await vs.initialize()
    except Exception:
        pass
    chunks = _chunk(content)
    if not chunks:
        return
    vectors = await engine.batch_embed([f"{title}\n\n{c}" for c in chunks])
    base_id = uuid.uuid5(uuid.NAMESPACE_URL, source_url or title).hex
    now = datetime.now(timezone.utc).isoformat()
    for i, (vec, chunk_text) in enumerate(zip(vectors, chunks)):
        await vs.upsert("documents", f"{base_id}:{i}", vec, {
            "title": title, "chunk_index": i, "total_chunks": len(chunks),
            "text": chunk_text, "source_url": source_url,
            "tenant_id": tenant_id, "indexed_at": now,
        })

def _extract_lessons(title: str, content: str, source_url: str) -> list:
    lessons = []
    for sent in re.split(r"(?<=[.!?])\s+", content):
        sent = sent.strip()
        if _SIGNAL_RE.search(sent) and 30 < len(sent) < 500:
            lessons.append({
                "lesson_id": uuid.uuid4().hex,
                "module": "auto_extracted",
                "title": sent[:80],
                "content": sent,
                "source": source_url or title,
                "source_type": "document",
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
        if len(lessons) >= 10:
            break
    return lessons

def _upsert_lessons_sync(lessons: list) -> None:
    if not lessons:
        return
    from mammoth_os.atlas_sync import supabase
    for lesson in lessons:
        supabase.schema("atlas").table("atlas_lessons").upsert(lesson).execute()

def _save_to_library_sync(title: str, content: str, source_url: str, artifact_type: str) -> None:
    import requests as _req
    base = os.getenv("MAMMOTH_API_BASE", "http://localhost:8000")
    payload = {
        "id": uuid.uuid5(uuid.NAMESPACE_URL, source_url or title).hex,
        "title": title,
        "content": content[:4000],
        "artifact_type": artifact_type,
        "source_url": source_url,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _req.post(f"{base}/api/workspace/artifacts", json=payload, timeout=5)

async def seed_document(
    title: str,
    content: str,
    source_url: str = "",
    tenant_id: str = "default",
    artifact_type: str = "document",
    *,
    skip_rag: bool = False,
    skip_atlas: bool = False,
    skip_library: bool = False,
) -> None:
    """Full post-generation pipeline. All stages are non-fatal."""
    if not title or not content:
        return
    if not skip_rag:
        try:
            await _embed_and_upsert(title, content, source_url, tenant_id)
        except Exception as exc:
            print(f"[doc_rag_pipeline] RAG failed: {exc}")
    if not skip_atlas:
        try:
            lessons = _extract_lessons(title, content, source_url)
            await asyncio.to_thread(_upsert_lessons_sync, lessons)
        except Exception as exc:
            print(f"[doc_rag_pipeline] ATLAS failed: {exc}")
    if not skip_library:
        try:
            await asyncio.to_thread(_save_to_library_sync, title, content, source_url, artifact_type)
        except Exception as exc:
            print(f"[doc_rag_pipeline] Library save failed: {exc}")
