"""Ingestion script to populate the in-memory VectorStoreAgent with docs and source files.

Usage: python -m mammoth_os.ingest_vector_store --root C:\path\to\repo --collections repo

This script is intended for local testing and will fallback to deterministic embeddings if no
LLM/embedding provider is available.
"""
import os
import argparse
from pathlib import Path
import asyncio
from typing import List

from mammoth_os.llm_client import get_llm_client
from mammoth_os.agents.vector_store_agent import VectorStoreAgent


CHUNK_SIZE = 1024


def chunk_text(text: str, size: int = CHUNK_SIZE) -> List[str]:
    # Simple fixed-size chunker (naive). Prefer semantic chunking later.
    chunks = []
    i = 0
    while i < len(text):
        chunk = text[i : i + size]
        chunks.append(chunk)
        i += size
    return chunks


async def ingest_paths(root: Path, paths: List[Path], collection: str = "repo"):
    client = get_llm_client()
    vs = VectorStoreAgent(router=None)

    for p in paths:
        try:
            text = p.read_text(encoding="utf-8")
        except Exception:
            continue
        title = p.name
        rel = str(p.relative_to(root))
        chunks = chunk_text(text)
        # create embeddings in batches
        for i, chunk in enumerate(chunks):
            metadata = {"path": rel, "title": title, "chunk_index": i, "text": chunk}
            try:
                vecs = await client.embed([chunk], timeout=30)
                vec = vecs[0]
            except Exception:
                # Fallback deterministic vector (hash-based) for testing without API
                vec = [float((hash(chunk) % 1000) / 1000.0) for _ in range(1536)]
            doc_id = f"{rel}:{i}"
            vs.upsert(collection, doc_id, vec, metadata)
    print(f"Ingested {len(paths)} files into collection '{collection}'")


def gather_files(root: Path, include_exts=None):
    if include_exts is None:
        include_exts = {".md", ".py", ".txt"}
    files = []
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in include_exts:
            files.append(p)
    return files


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=False, default=os.getcwd())
    parser.add_argument("--collections", default="repo")
    args = parser.parse_args()
    root = Path(args.root)
    collections = [c.strip() for c in args.collections.split(",") if c.strip()]

    # default to docs and src if present
    paths = []
    docs_dir = root / "docs"
    if docs_dir.exists():
        paths.extend(gather_files(docs_dir))
    src_dir = root / "src"
    if src_dir.exists():
        paths.extend(gather_files(src_dir))

    if not paths:
        print("No files found to ingest")
        return

    asyncio.run(ingest_paths(root, paths, collection=collections[0]))


if __name__ == "__main__":
    main()
