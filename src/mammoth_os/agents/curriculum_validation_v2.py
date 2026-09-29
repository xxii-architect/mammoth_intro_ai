"""Curriculum validation and grounding hardening for ATLAS.

This module provides strict validation to prevent fabricated content
and ensure curriculum lessons are properly grounded in subject matter.

Key hardening areas:
1. Subject extraction quality gates
2. Lesson content fabrication detection
3. Duration estimate validation
4. Objective/teaching point coherence checks
5. Content depth and specificity validation
"""

import re
from typing import Dict, Any, List, Tuple


def _extract_subject_strict(prompt: str) -> str:
    """Extract subject with strict validation.
    
    Rejects:
    - Overly generic subjects (e.g., "lesson", "topic", "course")
    - Prompts with no clear subject indicator
    - Subjects under 3 characters
    
    Returns: (subject, confidence_score)
    """
    if not prompt or len(prompt) < 10:
        return "", 0.0
    
    # Try specific lesson track pattern first (highest confidence)
    lesson_track_match = re.search(
        r"lesson track for\s+(.+?)(?:\s+with\s+|\s+emphasis\s+on:|[.;]|$)",
        prompt,
        re.IGNORECASE,
    )
    if lesson_track_match:
        subject = lesson_track_match.group(1).strip()
        if len(subject) >= 3 and subject.lower() not in {"lesson", "topic", "course"}:
            return subject, 0.95
    
    # Try "for <subject>" pattern
    match = re.search(r"for\s+([\w\s\-]+?)(?:[\.,]|$)", prompt, re.IGNORECASE)
    if match:
        subject = match.group(1).strip()
        if len(subject) >= 3 and subject.lower() not in {"lesson", "topic", "course", "beginners"}:
            return subject, 0.85
    
    # Try colon-separated pattern
    parts = prompt.split(":", 1)
    if len(parts) > 1:
        subject = parts[0].strip()
        if len(subject) >= 3 and subject.lower() not in {"lesson", "topic", "course"}:
            return subject, 0.75
    
    # Fallback to full prompt if it seems specific enough
    subject = prompt.strip()
    if len(subject) >= 10 and any(word in subject.lower() for word in ["learn", "understand", "teach"]):
        return subject, 0.60
    
    return "", 0.0


def _validate_lesson_content_depth(lesson: Dict[str, Any], subject: str) -> Tuple[bool, List[str]]:
    """Validate that lesson content has sufficient depth and specificity.
    
    Returns: (is_valid, list of validation errors)
    """
    errors = []
    
    # Check title specificity
    title = str(lesson.get("title") or "").strip()
    if not title:
        errors.append("Lesson title is empty")
    elif len(title) < 5:
        errors.append(f"Lesson title too short: '{title}'")
    elif title.lower() in {"lesson", "introduction", "overview", "basics"}:
        errors.append(f"Lesson title too generic: '{title}'")
    
    # Check content length (avoid stubs)
    content = str(lesson.get("content") or "").strip()
    if len(content) < 100:
        errors.append(f"Content too brief ({len(content)} chars, need ≥100)")
    
    # Check for placeholder markers (fabrication indicators)
    placeholder_markers = [
        "implement this",
        "add your own",
        "fill in the blank",
        "tbd",
        "todo",
        "placeholder",
        "example here",
        "insert example",
        "to be determined",
        "[example]",
        "{{",
        "}}",
        "assume",
        "suppose",
    ]
    for marker in placeholder_markers:
        if marker in content.lower():
            errors.append(f"Content contains placeholder marker: '{marker}'")
    
    # Check teaching points exist and are specific
    teaching_points = [str(item).strip() for item in (lesson.get("teaching_points") or []) if str(item).strip()]
    if len(teaching_points) < 2:
        errors.append(f"Insufficient teaching points ({len(teaching_points)}, need ≥2)")
    for tp in teaching_points:
        if len(tp) < 10:
            errors.append(f"Teaching point too brief: '{tp}'")
        if tp.lower() in {"fundamentals", "basics", "overview", "introduction"}:
            errors.append(f"Teaching point too generic: '{tp}'")
    
    # Check examples for specificity
    examples = [str(item).strip() for item in (lesson.get("examples") or []) if str(item).strip()]
    if len(examples) < 1:
        errors.append("No examples provided")
    for ex in examples:
        if len(ex) < 15:
            errors.append(f"Example too brief: '{ex}'")
        if any(generic in ex.lower() for generic in ["example", "for instance", "such as"]):
            # Some generic language is okay, but check it's not ONLY that
            if len(ex) < 30:
                errors.append(f"Example lacks concrete detail: '{ex}'")
    
    # Subject relevance check
    if subject:
        subject_terms = _extract_subject_terms(subject)
        if subject_terms:
            content_blob = f"{title} {content} {' '.join(teaching_points)} {' '.join(examples)}"
            relevance = _text_relevance_score(content_blob, subject_terms)
            # Require at least 1 subject term mention (not 2) and allow fewer for simpler subjects
            if relevance == 0 and len(subject_terms) > 2:
                errors.append(f"Content shows no relevance to subject '{subject}'")
            elif relevance == 0 and len(subject_terms) <= 2:
                # For short subjects like "Variables", one mention might be enough
                if "variable" not in title.lower():
                    errors.append(f"Content shows no relevance to subject '{subject}'")
    
    return len(errors) == 0, errors


def _validate_duration_estimates(lesson: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate that duration estimates are realistic and consistent.
    
    Returns: (is_valid, list of validation errors)
    """
    errors = []
    
    estimated_minutes = lesson.get("estimated_minutes")
    if estimated_minutes is None:
        errors.append("Missing estimated_minutes")
    elif not isinstance(estimated_minutes, int):
        errors.append(f"estimated_minutes not an integer: {type(estimated_minutes)}")
    elif estimated_minutes <= 0:
        errors.append(f"estimated_minutes invalid: {estimated_minutes}")
    elif estimated_minutes > 480:  # 8 hours
        errors.append(f"estimated_minutes unrealistic: {estimated_minutes} (max 480)")
    elif estimated_minutes < 5:
        errors.append(f"estimated_minutes too short: {estimated_minutes} (min 5)")
    else:
        # Heuristic: estimated_minutes should roughly correlate with content length
        content_len = len(str(lesson.get("content") or "").strip())
        expected_minutes = max(10, min(120, content_len // 50))  # ~50 chars per minute of reading
        if estimated_minutes < expected_minutes * 0.5:
            errors.append(f"estimated_minutes seems low ({estimated_minutes}) for content length ({content_len} chars)")
    
    return len(errors) == 0, errors


def _extract_subject_terms(subject: str) -> List[str]:
    """Extract key subject terms for relevance checking."""
    stopwords = {
        "and", "the", "for", "with", "into", "from", "your", "their", "this", "that",
        "basics", "basic", "beginner", "beginners", "fundamentals", "foundation", "foundations",
        "practical", "friendly", "real", "world", "introduction", "intro", "lesson", "course",
        "advanced", "learning", "guide", "tutorial", "overview",
    }
    seen = []
    for token in re.findall(r"[a-zA-Z0-9]+", subject.lower()):
        if len(token) <= 2:
            continue
        if token in stopwords:
            continue
        # Always keep domain-specific terms like programming languages, frameworks
        if not seen or token not in seen:
            seen.append(token)
    return seen


def _text_relevance_score(text: str, subject_terms: List[str]) -> int:
    """Count how many subject terms appear in text."""
    lowered = str(text or "").lower()
    return sum(1 for term in subject_terms if term in lowered)


def validate_curriculum_lesson(lesson: Dict[str, Any], subject: str = "") -> Tuple[bool, Dict[str, Any]]:
    """Comprehensive curriculum lesson validation.
    
    Args:
        lesson: Lesson dict with title, content, objectives, teaching_points, examples, estimated_minutes
        subject: Subject context for relevance checking
    
    Returns:
        (is_valid, validation_result_dict)
    
    validation_result_dict contains:
        - valid: bool
        - errors: list of validation errors
        - warnings: list of non-fatal concerns
        - quality_score: 0-100 score
        - checks: dict of individual check results
    """
    errors = []
    warnings = []
    checks = {}
    
    # Content depth validation
    content_valid, content_errors = _validate_lesson_content_depth(lesson, subject)
    checks["content_depth"] = content_valid
    errors.extend(content_errors)
    
    # Duration validation
    duration_valid, duration_errors = _validate_duration_estimates(lesson)
    checks["duration_estimates"] = duration_valid
    errors.extend(duration_errors)
    
    # Objectives validation
    objectives = [str(obj).strip() for obj in (lesson.get("objectives") or []) if str(obj).strip()]
    if not objectives:
        errors.append("No objectives defined")
        checks["objectives"] = False
    elif len(objectives) > 8:
        warnings.append(f"Too many objectives ({len(objectives)}, typically 3-5)")
        checks["objectives"] = True
    else:
        checks["objectives"] = True
    
    # Source tracking
    source = str(lesson.get("source") or "unknown").strip().lower()
    if source not in {"template", "llm_generated", "llm_enriched", "grounded", "authored"}:
        warnings.append(f"Unknown source type: '{source}'")
    checks["source"] = source in {"llm_generated", "llm_enriched", "grounded", "authored"}
    
    # Calculate quality score
    quality_score = 100
    quality_score -= len(errors) * 15
    quality_score -= len(warnings) * 3
    quality_score = max(0, min(100, quality_score))
    
    is_valid = len(errors) == 0 and quality_score >= 60
    
    return is_valid, {
        "valid": is_valid,
        "quality_score": quality_score,
        "errors": errors,
        "warnings": warnings,
        "checks": checks,
        "subject": subject,
    }


def validate_curriculum(curriculum: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    """Comprehensive curriculum validation.
    
    Returns:
        (is_valid, validation_result_dict)
    """
    errors = []
    warnings = []
    lesson_results = []
    
    subject = str(curriculum.get("subject") or "").strip()
    if not subject:
        subject_ext, confidence = _extract_subject_strict(str(curriculum.get("title") or ""))
        if confidence >= 0.60:
            subject = subject_ext
            warnings.append(f"Subject inferred from title (confidence: {confidence:.0%})")
        else:
            errors.append("No clear subject identified")
    
    # Validate modules exist
    modules = curriculum.get("modules")
    if not isinstance(modules, list):
        errors.append("Curriculum modules is not a list")
        return False, {"valid": False, "errors": errors, "warnings": warnings}
    
    if len(modules) == 0:
        errors.append("Curriculum has no modules")
    elif len(modules) > 20:
        warnings.append(f"Curriculum has many modules ({len(modules)}, typically 3-10)")
    
    # Validate each lesson
    total_lessons = 0
    valid_lessons = 0
    for module in modules:
        lessons = module.get("lessons") or []
        if not isinstance(lessons, list):
            warnings.append(f"Module '{module.get('module_id')}' lessons is not a list")
            continue
        for lesson in lessons:
            total_lessons += 1
            is_valid, result = validate_curriculum_lesson(lesson, subject)
            if is_valid:
                valid_lessons += 1
            lesson_results.append({
                "lesson_id": lesson.get("lesson_id", f"lesson_{total_lessons}"),
                **result
            })
    
    if total_lessons == 0:
        errors.append("Curriculum has no lessons")
    elif valid_lessons < total_lessons * 0.7:
        errors.append(f"Too many invalid lessons ({total_lessons - valid_lessons}/{total_lessons})")
    
    # Validate duration estimates
    total_minutes = curriculum.get("estimated_total_minutes")
    if total_minutes is not None:
        if not isinstance(total_minutes, int) or total_minutes <= 0:
            warnings.append(f"Invalid total duration: {total_minutes}")
        elif total_minutes > 10000:  # ~166 hours
            warnings.append(f"Very long curriculum: {total_minutes} minutes")
    
    is_valid = len(errors) == 0 and valid_lessons > 0
    
    return is_valid, {
        "valid": is_valid,
        "subject": subject,
        "lesson_results": lesson_results,
        "summary": {
            "total_lessons": total_lessons,
            "valid_lessons": valid_lessons,
            "valid_percent": round(100 * valid_lessons / total_lessons) if total_lessons > 0 else 0,
        },
        "errors": errors,
        "warnings": warnings,
    }
