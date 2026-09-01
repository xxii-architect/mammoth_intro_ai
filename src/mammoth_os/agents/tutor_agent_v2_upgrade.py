# tutor_agent_v2_upgrade.py
# Wave 3 improvements: safer context retrieval, adaptive difficulty hints, and quality gates

import asyncio
from typing import Dict, Any, List, Optional


def _extract_difficulty_hint(signal_summary: str) -> str:
    """Parse signal summary to derive adaptive difficulty guidance for coaching."""
    if not isinstance(signal_summary, str):
        return "medium"
    lowered = signal_summary.lower()
    if "difficulty: hard" in lowered or "struggle" in lowered:
        return "easy"
    if "difficulty: easy" in lowered or "fast pass" in lowered:
        return "hard"
    return "medium"


def _safe_retrieve_context(
    retriever,
    lesson_id: str,
    user_id: str,
    topic: str,
    lesson_title: str,
    lesson_chunks: List[str],
    timeout_sec: float = 3.0,
) -> tuple[List[Dict[str, Any]], str]:
    """
    Safely retrieve personalized context with timeout and fallback.
    
    Returns: (personalized_chunks, signal_summary)
    """
    personalized_chunks: List[Dict[str, Any]] = []
    signal_summary = "Signals:\n- Difficulty: unknown\n- Performance score: unknown\n- Struggle tags: none"
    
    if not lesson_id:
        if lesson_chunks:
            personalized_chunks = [
                {"chunk_text": chunk, "chunk_index": idx, "score": 0.0}
                for idx, chunk in enumerate(lesson_chunks)
            ]
        return personalized_chunks, signal_summary
    
    try:
        # Attempt async retrieval with a timeout to avoid blocking coaching
        async def _retrieve():
            try:
                chunks = await retriever.retrieve_chunks(
                    user_id=user_id,
                    lesson_id=lesson_id,
                    query=topic or lesson_title,
                    top_k=5,
                )
                return chunks or []
            except Exception as e:
                return []
        
        # Use asyncio.wait_for to enforce timeout
        loop = asyncio.get_event_loop()
        personalized_chunks = loop.run_until_complete(
            asyncio.wait_for(_retrieve(), timeout=timeout_sec)
        )
    except (asyncio.TimeoutError, Exception):
        personalized_chunks = []
    
    try:
        async def _signals():
            signals = await retriever.load_user_signals(user_id, lesson_id)
            return retriever.build_signal_summary(signals)
        
        loop = asyncio.get_event_loop()
        signal_summary = loop.run_until_complete(
            asyncio.wait_for(_signals(), timeout=timeout_sec)
        ) or signal_summary
    except (asyncio.TimeoutError, Exception):
        pass
    
    # Fallback to lesson_chunks if no personalized context
    if not personalized_chunks and lesson_chunks:
        personalized_chunks = [
            {"chunk_text": chunk, "chunk_index": idx, "score": 0.0}
            for idx, chunk in enumerate(lesson_chunks)
        ]
    
    return personalized_chunks, signal_summary


def _build_adaptive_checkpoints(
    lesson_title: str,
    module_id: str,
    difficulty_hint: str,
) -> List[str]:
    """Build checkpoint list adapted to estimated difficulty level."""
    checkpoints = [
        f"Restate the objective for {lesson_title} in your own words.",
        "Identify one concrete success check before you start.",
        "Record what confused you so the next coaching step can adapt.",
    ]
    
    if module_id:
        checkpoints.insert(1, f"Keep the work aligned with module '{module_id}'.")
    
    if difficulty_hint == "easy":
        checkpoints.append("Push yourself: try adding a constraint or edge case once the basics pass.")
    elif difficulty_hint == "hard":
        checkpoints.insert(0, "Start with the smallest valid structure that compiles or runs.")
    
    return checkpoints


def _build_coaching_summary(
    lesson_title: str,
    difficulty_hint: str,
    has_context: bool,
) -> str:
    """Build a coaching summary that reflects difficulty and context availability."""
    base = f"Tutor guidance for {lesson_title}: focus on one checkpoint, verify the behavior, and reflect before the next step."
    if difficulty_hint == "hard":
        base += " (Build structure first; logic later.)"
    elif difficulty_hint == "easy":
        base += " (You've got this — try pushing the boundaries.)"
    if not has_context:
        base += " (Limited context — break the problem into concrete pieces.)"
    return base


__all__ = [
    "_extract_difficulty_hint",
    "_safe_retrieve_context",
    "_build_adaptive_checkpoints",
    "_build_coaching_summary",
]
