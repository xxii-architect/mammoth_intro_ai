import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


DEFAULT_LEARNER_MODEL = {
    "version": 1,
    "user_id": "default_user",
    "mastery": {},
    "confidence": {},
    "streak": 0,
    "attempts": 0,
    "error_patterns": {},
    "recent_outcomes": [],
    "onboarding": {
        "experience_level": "unknown",
        "preferred_pacing": "gentle",
        "learning_style": "guided",
        "goals": [],
        "focus_areas": [],
        "completed_at": None,
    },
    "memory_graph": {
        "nodes": [],
        "edges": [],
        "last_updated": None,
    },
    "last_updated": None,
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _default_onboarding_profile() -> Dict[str, Any]:
    return {
        "experience_level": "unknown",
        "preferred_pacing": "gentle",
        "learning_style": "guided",
        "goals": [],
        "focus_areas": [],
        "completed_at": None,
    }


def _default_memory_graph() -> Dict[str, Any]:
    return {"nodes": [], "edges": [], "last_updated": None}


def _normalize_text_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        items = value.split(",")
    elif isinstance(value, (list, tuple, set)):
        items = list(value)
    else:
        items = [value]
    return [str(item).strip() for item in items if str(item).strip()]


def _slugify(value: Optional[str]) -> str:
    if not value:
        return "general"
    text = re.sub(r"[^a-z0-9]+", "-", str(value).strip().lower()).strip("-")
    return text or "general"


def _resolve_concept(lesson: Optional[Dict[str, Any]] = None, exercise: Optional[Dict[str, Any]] = None, topic: Optional[str] = None) -> str:
    lesson_title = (lesson or {}).get("title") or (lesson or {}).get("lesson_title") or ""
    exercise_title = (exercise or {}).get("title") or ""
    candidate = lesson_title or exercise_title or topic or "general"
    return _slugify(candidate)


def _ensure_model_shape(model: Optional[Dict[str, Any]], user_id: str) -> Dict[str, Any]:
    if not isinstance(model, dict):
        model = {}
    state = {**DEFAULT_LEARNER_MODEL, **model}
    state["version"] = 1
    state["user_id"] = user_id or state.get("user_id") or "default_user"
    state["mastery"] = {str(k): float(v) for k, v in (state.get("mastery") or {}).items() if str(k)}
    state["confidence"] = {str(k): float(v) for k, v in (state.get("confidence") or {}).items() if str(k)}
    state["error_patterns"] = {str(k): int(v) for k, v in (state.get("error_patterns") or {}).items() if str(k)}
    state["recent_outcomes"] = list(state.get("recent_outcomes") or [])[-12:]
    state["streak"] = int(state.get("streak") or 0)
    state["attempts"] = int(state.get("attempts") or 0)
    state["last_updated"] = state.get("last_updated") or None
    onboarding = state.get("onboarding") if isinstance(state.get("onboarding"), dict) else {}
    merged_onboarding = {**_default_onboarding_profile(), **onboarding}
    merged_onboarding["goals"] = _normalize_text_list(merged_onboarding.get("goals"))
    merged_onboarding["focus_areas"] = _normalize_text_list(merged_onboarding.get("focus_areas"))
    state["onboarding"] = merged_onboarding
    graph = state.get("memory_graph") if isinstance(state.get("memory_graph"), dict) else {}
    merged_graph = {**_default_memory_graph(), **graph}
    merged_graph["nodes"] = [node for node in (merged_graph.get("nodes") or []) if isinstance(node, dict) and node.get("id")]
    merged_graph["edges"] = [edge for edge in (merged_graph.get("edges") or []) if isinstance(edge, dict) and edge.get("source") and edge.get("target")]
    state["memory_graph"] = merged_graph
    return state


def _graph_sort_key(item: Dict[str, Any]) -> str:
    return str(item.get("updated_at") or item.get("created_at") or "")


def _upsert_graph_node(graph: Dict[str, Any], node: Dict[str, Any]) -> None:
    nodes = {}
    for existing in graph.get("nodes") or []:
        if isinstance(existing, dict) and existing.get("id"):
            nodes[str(existing["id"])] = existing
    node_id = str(node.get("id") or "").strip()
    if not node_id:
        return
    nodes[node_id] = {**nodes.get(node_id, {}), **node}
    graph["nodes"] = sorted(nodes.values(), key=_graph_sort_key)[-200:]


def _upsert_graph_edge(graph: Dict[str, Any], edge: Dict[str, Any]) -> None:
    edges = {}
    for existing in graph.get("edges") or []:
        if isinstance(existing, dict) and existing.get("source") and existing.get("target"):
            key = (str(existing["source"]), str(existing["target"]), str(existing.get("relation") or "related"))
            edges[key] = existing
    source = str(edge.get("source") or "").strip()
    target = str(edge.get("target") or "").strip()
    if not source or not target:
        return
    key = (source, target, str(edge.get("relation") or "related"))
    edges[key] = {**edges.get(key, {}), **edge}
    graph["edges"] = list(edges.values())[-300:]


def _memory_graph_summary(graph: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    graph_state = _default_memory_graph()
    if isinstance(graph, dict):
        graph_state.update(graph)
    nodes = [node for node in (graph_state.get("nodes") or []) if isinstance(node, dict)]
    edges = [edge for edge in (graph_state.get("edges") or []) if isinstance(edge, dict)]
    recent_nodes = sorted(nodes, key=_graph_sort_key)[-6:]
    return {
        "node_count": len(nodes),
        "edge_count": len(edges),
        "recent_nodes": [
            {
                "id": node.get("id"),
                "type": node.get("type"),
                "label": node.get("label") or node.get("title") or node.get("id"),
            }
            for node in recent_nodes
        ],
    }


def _record_memory_graph(
    state: Dict[str, Any],
    *,
    lesson: Optional[Dict[str, Any]] = None,
    exercise: Optional[Dict[str, Any]] = None,
    result: Optional[Dict[str, Any]] = None,
    topic: Optional[str] = None,
) -> Dict[str, Any]:
    graph = state.get("memory_graph") if isinstance(state.get("memory_graph"), dict) else _default_memory_graph()
    lesson = lesson or {}
    exercise = exercise or {}
    onboarding = state.get("onboarding") if isinstance(state.get("onboarding"), dict) else _default_onboarding_profile()
    concept = _resolve_concept(lesson=lesson, exercise=exercise, topic=topic)
    lesson_id = str(lesson.get("lesson_id") or concept or "lesson").strip()
    lesson_title = str(lesson.get("title") or lesson.get("lesson_title") or topic or lesson_id).strip()
    exercise_title = str(exercise.get("title") or exercise.get("description") or "Practice exercise").strip()
    outcome_label = "passed" if bool((result or {}).get("passed")) else "needs-practice"
    now = _now_iso()

    _upsert_graph_node(graph, {
        "id": f"lesson:{lesson_id}",
        "type": "lesson",
        "label": lesson_title,
        "title": lesson_title,
        "created_at": now,
        "updated_at": now,
        "metadata": {
            "lesson_id": lesson_id,
            "difficulty": lesson.get("difficulty"),
            "module": lesson.get("module_title") or lesson.get("module"),
        },
    })
    _upsert_graph_node(graph, {
        "id": f"exercise:{lesson_id}",
        "type": "exercise",
        "label": exercise_title,
        "title": exercise_title,
        "created_at": now,
        "updated_at": now,
        "metadata": {
            "prompt": str(exercise.get("prompt") or "")[:220],
        },
    })
    _upsert_graph_node(graph, {
        "id": f"concept:{concept}",
        "type": "concept",
        "label": concept.replace("-", " "),
        "title": concept.replace("-", " "),
        "created_at": now,
        "updated_at": now,
        "metadata": {
            "topic": topic,
            "goals": onboarding.get("goals") or [],
            "focus_areas": onboarding.get("focus_areas") or [],
        },
    })
    _upsert_graph_node(graph, {
        "id": f"outcome:{lesson_id}",
        "type": "outcome",
        "label": outcome_label,
        "title": outcome_label,
        "created_at": now,
        "updated_at": now,
        "metadata": {
            "passed": bool((result or {}).get("passed")),
            "hint": str((result or {}).get("hint") or "")[:180],
        },
    })

    _upsert_graph_edge(graph, {
        "source": f"lesson:{lesson_id}",
        "target": f"exercise:{lesson_id}",
        "relation": "includes",
        "created_at": now,
    })
    _upsert_graph_edge(graph, {
        "source": f"exercise:{lesson_id}",
        "target": f"outcome:{lesson_id}",
        "relation": "produces",
        "created_at": now,
    })
    _upsert_graph_edge(graph, {
        "source": f"lesson:{lesson_id}",
        "target": f"concept:{concept}",
        "relation": "teaches",
        "created_at": now,
    })
    if onboarding.get("goals"):
        _upsert_graph_node(graph, {
            "id": "onboarding:profile",
            "type": "onboarding",
            "label": onboarding.get("learning_style") or "Learner profile",
            "title": "Learner profile",
            "created_at": now,
            "updated_at": now,
            "metadata": onboarding,
        })
        for goal in onboarding.get("goals")[:4]:
            goal_id = _slugify(goal)
            _upsert_graph_node(graph, {
                "id": f"goal:{goal_id}",
                "type": "goal",
                "label": goal,
                "title": goal,
                "created_at": now,
                "updated_at": now,
            })
            _upsert_graph_edge(graph, {
                "source": "onboarding:profile",
                "target": f"goal:{goal_id}",
                "relation": "goal",
                "created_at": now,
            })
            _upsert_graph_edge(graph, {
                "source": f"goal:{goal_id}",
                "target": f"concept:{concept}",
                "relation": "focuses",
                "created_at": now,
            })

    graph["last_updated"] = now
    state["memory_graph"] = graph
    return graph


def set_onboarding_profile(
    state: Optional[Dict[str, Any]] = None,
    *,
    user_id: str = "default_user",
    onboarding: Optional[Dict[str, Any]] = None,
    storage_path: Optional[str] = None,
) -> Dict[str, Any]:
    learner_state = load_learner_model(user_id, storage_path=storage_path)
    onboarding = onboarding if isinstance(onboarding, dict) else {}
    merged = {**_default_onboarding_profile(), **learner_state.get("onboarding", {}), **onboarding}
    merged["experience_level"] = str(merged.get("experience_level") or "unknown").strip().lower() or "unknown"
    merged["preferred_pacing"] = str(merged.get("preferred_pacing") or "gentle").strip().lower() or "gentle"
    merged["learning_style"] = str(merged.get("learning_style") or "guided").strip().lower() or "guided"
    merged["goals"] = _normalize_text_list(merged.get("goals"))
    merged["focus_areas"] = _normalize_text_list(merged.get("focus_areas"))
    if any(merged.get(key) for key in ("experience_level", "preferred_pacing", "learning_style")):
        merged["completed_at"] = _now_iso()
    learner_state["onboarding"] = merged
    if state is not None:
        state["learner_model"] = learner_state
        state["learner_context"] = build_learner_context(learner_state)
        state["learner_profile"] = {
            "streak": state["learner_context"].get("streak", 0),
            "attempts": state["learner_context"].get("attempts", 0),
            "recommended_difficulty": state["learner_context"].get("recommended_difficulty", "beginner"),
            "preferred_pacing": state["learner_context"].get("preferred_pacing", "gentle"),
        }
    return save_learner_model(learner_state, storage_path=storage_path)


def _model_path(storage_path: Optional[str] = None) -> str:
    if storage_path:
        return os.path.join(storage_path, "atlas_learner_model.json")
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '.mammoth'))
    os.makedirs(root, exist_ok=True)
    return os.path.join(root, "atlas_learner_model.json")


def load_learner_model(user_id: str = "default_user", storage_path: Optional[str] = None) -> Dict[str, Any]:
    path = _model_path(storage_path)
    if not os.path.exists(path):
        return _ensure_model_shape(DEFAULT_LEARNER_MODEL, user_id)
    try:
        with open(path, 'r', encoding='utf-8') as fh:
            raw = json.load(fh)
    except Exception:
        return _ensure_model_shape(DEFAULT_LEARNER_MODEL, user_id)
    state = _ensure_model_shape(raw, user_id)
    state["user_id"] = user_id or state.get("user_id") or "default_user"
    return state


def save_learner_model(state: Dict[str, Any], storage_path: Optional[str] = None) -> Dict[str, Any]:
    normalized = _ensure_model_shape(state, state.get("user_id") or "default_user")
    normalized["last_updated"] = _now_iso()
    path = _model_path(storage_path)
    try:
        with open(path, 'w', encoding='utf-8') as fh:
            json.dump(normalized, fh, indent=2)
    except Exception:
        pass
    return normalized


def update_learner_model(
    user_id: str = "default_user",
    *,
    lesson: Optional[Dict[str, Any]] = None,
    exercise: Optional[Dict[str, Any]] = None,
    result: Optional[Dict[str, Any]] = None,
    topic: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    storage_path: Optional[str] = None,
) -> Dict[str, Any]:
    state = load_learner_model(user_id, storage_path=storage_path)
    concept = _resolve_concept(lesson=lesson, exercise=exercise, topic=topic)
    passed = bool((result or {}).get("passed"))
    raw_result = (result or {}).get("result") if isinstance(result, dict) else None
    if not isinstance(raw_result, dict):
        raw_result = result or {}

    state["attempts"] = int(state.get("attempts") or 0) + 1
    prior_mastery = float(state.get("mastery", {}).get(concept, 0.5))
    prior_confidence = float(state.get("confidence", {}).get(concept, 0.5))

    if passed:
        mastery_delta = 0.12 if state["attempts"] <= 2 else 0.06
        confidence_delta = 0.05
        state["streak"] = int(state.get("streak") or 0) + 1
    else:
        mastery_delta = -0.05 - min(0.06, 0.02 * max(0, state["attempts"] - 1))
        confidence_delta = -0.04
        state["streak"] = max(0, int(state.get("streak") or 0) - 1)

    # Repeated error patterns make the learner model more conservative.
    fingerprint = metadata.get("error_fingerprint") if isinstance(metadata, dict) else None
    if not fingerprint:
        fingerprint = _infer_error_fingerprint(raw_result)
    if fingerprint:
        counts = state.setdefault("error_patterns", {})
        counts[fingerprint] = int(counts.get(fingerprint, 0)) + 1
        state["error_patterns"] = counts

    next_mastery = _clamp(prior_mastery + mastery_delta)
    next_confidence = _clamp(prior_confidence + confidence_delta)
    state.setdefault("mastery", {})[concept] = next_mastery
    state.setdefault("confidence", {})[concept] = next_confidence
    _record_memory_graph(state, lesson=lesson, exercise=exercise, result=raw_result, topic=topic)

    state.setdefault("recent_outcomes", []).append({
        "concept": concept,
        "passed": passed,
        "mastery_before": round(prior_mastery, 3),
        "mastery_after": round(next_mastery, 3),
        "mastery_delta": round(next_mastery - prior_mastery, 3),
        "confidence_before": round(prior_confidence, 3),
        "confidence_after": round(next_confidence, 3),
        "confidence_delta": round(next_confidence - prior_confidence, 3),
        "attempts": state["attempts"],
        "streak": state["streak"],
        "timestamp": _now_iso(),
    })
    state["recent_outcomes"] = state["recent_outcomes"][-12:]
    return save_learner_model(state, storage_path=storage_path)


def _derive_adaptive_coaching(
    *,
    onboarding: Dict[str, Any],
    average_mastery: float,
    streak: int,
    recent_failures: int,
    repeated_error_count: int,
) -> Dict[str, Any]:
    learning_style = str(onboarding.get("learning_style") or "guided").strip().lower()
    preferred_pacing = str(onboarding.get("preferred_pacing") or "gentle").strip().lower()

    if recent_failures >= 2 or average_mastery < 0.4:
        hint_depth = "foundational"
    elif average_mastery < 0.7:
        hint_depth = "guided"
    else:
        hint_depth = "strategic"

    if preferred_pacing == "challenge" and streak >= 2 and recent_failures == 0:
        challenge_level = "stretch"
    elif preferred_pacing == "gentle" or recent_failures >= 2:
        challenge_level = "support"
    else:
        challenge_level = "balanced"

    remediation_needed = recent_failures >= 2 or repeated_error_count >= 3
    tone_map = {
        "guided": "step_by_step",
        "hands-on": "nudge_then_practice",
        "exploratory": "question_led",
    }
    return {
        "hint_depth": hint_depth,
        "challenge_level": challenge_level,
        "remediation_needed": remediation_needed,
        "coaching_tone": tone_map.get(learning_style, "step_by_step"),
        "style": learning_style,
        "pacing": preferred_pacing,
    }


def build_learner_context(state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    model = _ensure_model_shape(state, (state or {}).get("user_id") or "default_user")
    mastery = model.get("mastery") or {}
    confidence = model.get("confidence") or {}
    recent_outcomes = list(model.get("recent_outcomes") or [])
    error_patterns = dict(model.get("error_patterns") or {})
    sorted_mastery = sorted(mastery.items(), key=lambda item: item[1])
    sorted_confidence = sorted(confidence.items(), key=lambda item: item[1], reverse=True)
    average_mastery = sum(mastery.values()) / len(mastery) if mastery else 0.5
    onboarding = model.get("onboarding") or _default_onboarding_profile()
    graph_summary = _memory_graph_summary(model.get("memory_graph"))

    if onboarding.get("preferred_pacing") == "challenge":
        recommended_difficulty = "advanced"
        preferred_pacing = "challenge"
    elif onboarding.get("preferred_pacing") == "steady":
        recommended_difficulty = "intermediate" if average_mastery >= 0.45 else "beginner"
        preferred_pacing = "steady"
    elif average_mastery < 0.45:
        recommended_difficulty = "beginner"
        preferred_pacing = "gentle"
    elif average_mastery < 0.7:
        recommended_difficulty = "intermediate"
        preferred_pacing = "steady"
    else:
        recommended_difficulty = "advanced"
        preferred_pacing = "challenge"

    weakest = [{"concept": concept, "mastery": round(value, 3)} for concept, value in sorted_mastery[:3]]
    strongest = [{"concept": concept, "confidence": round(value, 3)} for concept, value in sorted_confidence[:3]]
    recent_failures = sum(1 for item in recent_outcomes[-3:] if isinstance(item, dict) and not bool(item.get("passed")))
    repeated_error_count = max((int(count) for key, count in error_patterns.items() if key != "passed"), default=0)
    adaptive_coaching = _derive_adaptive_coaching(
        onboarding=onboarding,
        average_mastery=average_mastery,
        streak=int(model.get("streak") or 0),
        recent_failures=recent_failures,
        repeated_error_count=repeated_error_count,
    )
    latest_delta = recent_outcomes[-1] if recent_outcomes else None

    return {
        "user_id": model.get("user_id") or "default_user",
        "streak": int(model.get("streak") or 0),
        "attempts": int(model.get("attempts") or 0),
        "mastery": {concept: round(value, 3) for concept, value in mastery.items()},
        "confidence": {concept: round(value, 3) for concept, value in confidence.items()},
        "weakest_concepts": weakest,
        "strongest_concepts": strongest,
        "recommended_difficulty": recommended_difficulty,
        "preferred_pacing": preferred_pacing,
        "adaptive_coaching": adaptive_coaching,
        "latest_mastery_delta": latest_delta.get("mastery_delta") if isinstance(latest_delta, dict) else None,
        "latest_confidence_delta": latest_delta.get("confidence_delta") if isinstance(latest_delta, dict) else None,
        "onboarding": onboarding,
        "memory_graph_summary": graph_summary,
        "error_patterns": error_patterns,
        "recent_outcomes": recent_outcomes,
    }


def build_lesson_plan(state: Optional[Dict[str, Any]] = None, topic: Optional[str] = None) -> Dict[str, Any]:
    learner_context = build_learner_context(state)
    weakest = learner_context.get("weakest_concepts") or []
    onboarding = learner_context.get("onboarding") or {}
    focus_concept = weakest[0].get("concept") if weakest else None
    topic_text = (topic or "the current lesson").strip()
    learning_style = str(onboarding.get("learning_style") or "guided").strip().lower()
    goal_hint = onboarding.get("goals") or []

    if focus_concept:
        suggested_topic = f"{topic_text} + practice on {focus_concept}" if topic_text and topic_text != focus_concept else f"Practice {focus_concept}"
        rationale = f"{focus_concept} is currently your lowest-mastery concept, so ATLAS should emphasize it with a {learning_style} scaffold."
    else:
        suggested_topic = topic_text or "A fresh review lesson"
        rationale = "The learner profile is still emerging, so ATLAS will keep the next lesson broad and supportive."
    if goal_hint:
        rationale = f"{rationale} Primary learner goal: {goal_hint[0]}."

    return {
        "focus_concept": focus_concept,
        "suggested_topic": suggested_topic,
        "difficulty": learner_context.get("recommended_difficulty") or "beginner",
        "pacing": learner_context.get("preferred_pacing") or "gentle",
        "rationale": rationale,
        "weakest_concepts": weakest[:3],
        "onboarding": onboarding,
    }


def _infer_error_fingerprint(raw_result: Optional[Dict[str, Any]]) -> Optional[str]:
    if not isinstance(raw_result, dict):
        return None
    text = f"{raw_result.get('stdout', '')}\n{raw_result.get('stderr', '')}".lower()
    if 'syntaxerror' in text:
        return 'syntax_error'
    if 'indentationerror' in text:
        return 'indentation_error'
    if 'modulenotfounderror' in text or 'importerror' in text:
        return 'import_error'
    if 'assertionerror' in text or 'assert ' in text:
        return 'assertion_error'
    if 'typeerror' in text:
        return 'type_error'
    if 'nameerror' in text:
        return 'name_error'
    if 'timeout' in text:
        return 'timeout'
    if 'notimplementederror' in text:
        return 'not_implemented'
    if raw_result.get('passed'):
        return 'passed'
    return 'unknown_failure'
