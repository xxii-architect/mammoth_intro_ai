"""Tests for curriculum validation hardening (Wave 4 Phase 2)."""

import pytest
from src.mammoth_os.agents.curriculum_validation_v2 import (
    _extract_subject_strict,
    _validate_lesson_content_depth,
    _validate_duration_estimates,
    validate_curriculum_lesson,
    validate_curriculum,
)


# ─────────────────────────────────────────────────────────────────────
# Subject Extraction Tests
# ─────────────────────────────────────────────────────────────────────

def test_extract_subject_strict_with_lesson_track():
    """Test extraction from 'lesson track for X' pattern."""
    prompt = "Create a lesson track for Python error handling with emphasis on debugging"
    subject, confidence = _extract_subject_strict(prompt)
    assert subject == "Python error handling"
    assert confidence >= 0.90


def test_extract_subject_strict_with_for_pattern():
    """Test extraction from 'for X' pattern."""
    prompt = "Teaching material for Machine Learning fundamentals"
    subject, confidence = _extract_subject_strict(prompt)
    assert "Machine Learning" in subject
    assert confidence >= 0.80


def test_extract_subject_strict_generic_rejection():
    """Test that generic subjects are rejected."""
    prompt = "Create lesson for lesson"
    subject, confidence = _extract_subject_strict(prompt)
    assert subject == "" or confidence < 0.70


def test_extract_subject_strict_too_short():
    """Test that short prompts are rejected."""
    prompt = "For AI"
    subject, confidence = _extract_subject_strict(prompt)
    assert confidence < 0.70 or len(subject) == 0


# ─────────────────────────────────────────────────────────────────────
# Content Depth Validation Tests
# ─────────────────────────────────────────────────────────────────────

def test_validate_lesson_content_depth_valid():
    """Test validation passes for well-structured lesson."""
    lesson = {
        "title": "Introduction to Variables",
        "content": "Variables are fundamental building blocks in programming. "
                  "They allow you to store data values and reference them by name. "
                  "Think of a variable as a labeled box that holds a value. "
                  "When you create a variable, you choose a meaningful name and assign it a value. "
                  "That value can change throughout your program's execution.",
        "teaching_points": [
            "What variables are and why they matter in programming",
            "How to name variables meaningfully",
            "Basic variable assignment and reassignment",
        ],
        "examples": [
            "Declaring a variable: age = 25",
            "Updating a variable: age = age + 1",
        ],
    }
    is_valid, errors = _validate_lesson_content_depth(lesson, "Variables in Python")
    assert is_valid, f"Expected valid lesson but got errors: {errors}"


def test_validate_lesson_content_depth_rejects_placeholders():
    """Test that placeholder markers are detected."""
    lesson = {
        "title": "Variable Lesson",
        "content": "TODO: Add content here. [Example to be implemented later]",
        "teaching_points": ["Placeholder point"],
        "examples": ["[Insert example here]"],
    }
    is_valid, errors = _validate_lesson_content_depth(lesson, "Variables")
    assert not is_valid
    assert any("placeholder" in err.lower() for err in errors)


def test_validate_lesson_content_depth_rejects_generic_title():
    """Test that generic titles are rejected."""
    lesson = {
        "title": "Lesson",
        "content": "Some content about the subject matter goes here in detail.",
        "teaching_points": ["Point 1", "Point 2"],
        "examples": ["Example 1"],
    }
    is_valid, errors = _validate_lesson_content_depth(lesson, "")
    assert not is_valid
    assert any("title" in err.lower() and "generic" in err.lower() for err in errors)


def test_validate_lesson_content_depth_checks_subject_relevance():
    """Test that lesson content is checked for subject relevance."""
    lesson = {
        "title": "Advanced Painting Techniques",
        "content": "This is a detailed lesson about advanced painting. "
                  "We cover brush strokes, color theory, composition, and perspective. "
                  "Each technique builds on the fundamentals.",
        "teaching_points": ["Brush technique", "Color mixing", "Composition"],
        "examples": ["Oil painting example", "Watercolor example"],
    }
    is_valid, errors = _validate_lesson_content_depth(lesson, "Python Programming")
    assert not is_valid
    assert any("subject" in err.lower() or "relevant" in err.lower() for err in errors)


# ─────────────────────────────────────────────────────────────────────
# Duration Validation Tests
# ─────────────────────────────────────────────────────────────────────

def test_validate_duration_valid():
    """Test that realistic durations pass."""
    lesson = {"estimated_minutes": 25}
    is_valid, errors = _validate_duration_estimates(lesson)
    assert is_valid, errors


def test_validate_duration_rejects_zero():
    """Test that zero duration is rejected."""
    lesson = {"estimated_minutes": 0}
    is_valid, errors = _validate_duration_estimates(lesson)
    assert not is_valid
    assert any("invalid" in err.lower() for err in errors)


def test_validate_duration_rejects_negative():
    """Test that negative duration is rejected."""
    lesson = {"estimated_minutes": -10}
    is_valid, errors = _validate_duration_estimates(lesson)
    assert not is_valid


def test_validate_duration_rejects_unrealistic():
    """Test that unrealistic duration is rejected."""
    lesson = {"estimated_minutes": 999}
    is_valid, errors = _validate_duration_estimates(lesson)
    assert not is_valid


def test_validate_duration_rejects_missing():
    """Test that missing duration is rejected."""
    lesson = {}
    is_valid, errors = _validate_duration_estimates(lesson)
    assert not is_valid
    assert any("missing" in err.lower() for err in errors)


# ─────────────────────────────────────────────────────────────────────
# Complete Lesson Validation Tests
# ─────────────────────────────────────────────────────────────────────

def test_validate_curriculum_lesson_good():
    """Test that a good lesson passes validation."""
    lesson = {
        "title": "Exception Handling in Python",
        "content": "Exception handling is crucial for writing robust code. "
                  "When errors occur, Python raises exceptions that can crash your program. "
                  "Try-except blocks let you catch and handle these gracefully. "
                  "Understanding exception types helps you write better error handlers.",
        "objectives": ["Understand when exceptions occur", "Write try-except blocks"],
        "teaching_points": [
            "Built-in exception types in Python",
            "Try-except-finally structure",
            "Catching specific exceptions",
        ],
        "examples": [
            "try: result = 1 / x except ZeroDivisionError: print('Cannot divide by zero')",
            "Using except Exception as e: to catch the error object",
        ],
        "estimated_minutes": 20,
        "source": "llm_generated",
    }
    is_valid, result = validate_curriculum_lesson(lesson, "Exception Handling")
    assert is_valid, f"Lesson validation failed: {result['errors']}"
    assert result["quality_score"] >= 60


def test_validate_curriculum_lesson_rejects_fabrication():
    """Test that fabricated content is rejected."""
    lesson = {
        "title": "Magic Method Overview",
        "content": "{{ magic_methods_here }}",
        "objectives": ["Implement magic methods"],
        "teaching_points": ["[Teaching point 1]", "[Teaching point 2]"],
        "examples": ["[Example to add]"],
        "estimated_minutes": 15,
    }
    is_valid, result = validate_curriculum_lesson(lesson, "Python Magic Methods")
    assert not is_valid
    assert len(result["errors"]) > 0


# ─────────────────────────────────────────────────────────────────────
# Full Curriculum Validation Tests
# ─────────────────────────────────────────────────────────────────────

def test_validate_curriculum_good():
    """Test that a well-formed curriculum passes."""
    curriculum = {
        "title": "Python Fundamentals",
        "subject": "Python Programming",
        "modules": [
            {
                "module_id": "m1",
                "title": "Module 1: Basics",
                "lessons": [
                    {
                        "lesson_id": "m1-l1",
                        "title": "Variables and Types",
                        "content": "Variables are named containers that store data values in memory. "
                                  "Python has several built-in data types: int for integers, str for text, "
                                  "float for decimals, bool for True/False values, list for ordered collections, "
                                  "and dict for key-value pairs. Each type has specific properties and methods you can use. "
                                  "For example, string variables have methods like .upper() and .lower(), "
                                  "while list variables have methods like .append() and .remove().",
                        "objectives": ["Understand data types", "Create and assign variables"],
                        "teaching_points": [
                            "Basic data types in Python and when to use each one",
                            "How to check variable type using type()",
                            "Type conversion between different data types",
                        ],
                        "examples": [
                            "age = 25 (integer variable)",
                            "name = 'Alice' (string variable)",
                            "height = 5.8 (float variable)",
                        ],
                        "estimated_minutes": 20,
                        "source": "authored",
                    }
                ],
            }
        ],
        "estimated_total_minutes": 20,
    }
    is_valid, result = validate_curriculum(curriculum)
    assert is_valid, f"Curriculum validation failed: {result['errors']}"


def test_validate_curriculum_rejects_no_lessons():
    """Test that curriculum with no lessons is rejected."""
    curriculum = {
        "title": "Empty Curriculum",
        "subject": "Test",
        "modules": [
            {"module_id": "m1", "lessons": []}
        ],
    }
    is_valid, result = validate_curriculum(curriculum)
    assert not is_valid
    assert len(result["errors"]) > 0


def test_validate_curriculum_infers_subject():
    """Test that subject can be inferred from title."""
    curriculum = {
        "title": "lesson track for Advanced Python with emphasis on async programming",
        "modules": [
            {
                "module_id": "m1",
                "lessons": [
                    {
                        "lesson_id": "m1-l1",
                        "title": "Async Fundamentals",
                        "content": "Async programming allows concurrent code execution. "
                                  "Python's asyncio module provides the necessary tools.",
                        "teaching_points": ["Async basics", "Concurrency patterns"],
                        "examples": ["async def", "await"],
                        "estimated_minutes": 20,
                    }
                ],
            }
        ],
    }
    is_valid, result = validate_curriculum(curriculum)
    # Should infer Python as subject from title
    assert result["subject"] != ""


def test_validate_curriculum_tracks_lesson_validity():
    """Test that curriculum validation tracks which lessons are valid."""
    curriculum = {
        "title": "Mixed Quality Curriculum",
        "subject": "Testing",
        "modules": [
            {
                "module_id": "m1",
                "lessons": [
                    {
                        "lesson_id": "good",
                        "title": "Good Lesson",
                        "content": "This is a comprehensive lesson with detailed content.",
                        "teaching_points": ["Point A", "Point B"],
                        "examples": ["Example 1", "Example 2"],
                        "estimated_minutes": 20,
                    },
                    {
                        "lesson_id": "bad",
                        "title": "Bad",
                        "content": "[TODO]",
                        "teaching_points": [],
                        "examples": [],
                        "estimated_minutes": 0,
                    },
                ],
            }
        ],
    }
    is_valid, result = validate_curriculum(curriculum)
    # Should report that some lessons are invalid
    assert result["summary"]["valid_lessons"] < result["summary"]["total_lessons"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
