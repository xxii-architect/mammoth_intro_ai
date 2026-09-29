# reasoning_agent_v2_upgrade.py
# Wave 3 improvements: deeper error pattern detection and contextual Socratic guidance

from typing import Dict, Any, List, Optional
import re


def _extract_error_pattern_enhanced(context: Dict[str, Any]) -> str:
    """Enhanced error pattern extraction with more granular categories."""
    tutor_result = context.get("tutor_result") if isinstance(context, dict) else {}
    if not isinstance(tutor_result, dict):
        tutor_result = {}
    
    adaptive = tutor_result.get("adaptive_signals") if isinstance(tutor_result.get("adaptive_signals"), dict) else {}
    fingerprint = str(adaptive.get("error_fingerprint") or "").strip().lower()
    if fingerprint and fingerprint != "unknown":
        return fingerprint
    
    output = f"{tutor_result.get('message', '')} {tutor_result.get('error', '')} {tutor_result.get('stdout', '')}".lower()
    
    patterns = {
        "syntax_error": ["syntaxerror", "invalid syntax", "syntax error"],
        "indentation_error": ["indentationerror", "indent", "unindent"],
        "assertion_error": ["assertionerror", "assert ", "assertion failed"],
        "import_error": ["importerror", "modulenotfounderror", "no module named"],
        "type_error": ["typeerror", "unsupported operand"],
        "name_error": ["nameerror", "not defined"],
        "value_error": ["valueerror", "invalid value"],
        "key_error": ["keyerror", "key error"],
        "index_error": ["indexerror", "index out of range"],
        "attribute_error": ["attributeerror", "has no attribute"],
        "runtime_error": ["runtimeerror", "runtime error"],
        "timeout": ["timeout", "timed out", "max execution time"],
        "not_implemented": ["notimplementederror", "not yet implemented"],
        "memory_error": ["memoryerror", "out of memory"],
        "recursion_error": ["recursionerror", "maximum recursion depth"],
    }
    
    for category, keywords in patterns.items():
        if any(keyword in output for keyword in keywords):
            return category
    
    if context.get("mode") == "coach":
        return "coaching_request"
    
    return "unknown"


def _socratic_questions_enhanced(pattern: str, problem: str) -> List[str]:
    """Generate targeted Socratic questions based on error pattern and problem context."""
    questions: List[str] = []
    
    if pattern == "syntax_error":
        questions = [
            "Which line first breaks Python's parser, and what character or keyword is the issue?",
            "Can you identify the opening bracket/parenthesis that's missing its closing match?",
            "Does the indentation match the block structure you intended?",
        ]
    elif pattern == "indentation_error":
        questions = [
            "Which indented block doesn't align with the statement that opened it (if/for/def/class)?",
            "Are you mixing tabs and spaces?",
            "What is the correct indent level for this line relative to the one before it?",
        ]
    elif pattern == "assertion_error":
        questions = [
            "What does the test expect vs. what is your function actually returning?",
            "Which edge case or boundary value could explain the mismatch?",
            "What is the simplest input that should pass, and does it?",
        ]
    elif pattern == "import_error":
        questions = [
            "Is the module installed and on the Python path?",
            "What is the correct relative or absolute import path from the test file's location?",
            "Can you import the module in isolation in a Python REPL?",
        ]
    elif pattern == "type_error":
        questions = [
            "What type is the value at the point of failure?",
            "Does the operation support both operands' types?",
            "Should you convert one value to match the other's type?",
        ]
    elif pattern == "name_error":
        questions = [
            "Is the variable assigned before you use it?",
            "Did you spell the variable name correctly?",
            "Is the variable defined in the right scope (global vs. local)?",
        ]
    elif pattern == "index_error":
        questions = [
            "What is the length of the list/string you're indexing?",
            "Is your index within [0, length-1]?",
            "Should you check the length before indexing?",
        ]
    elif pattern == "attribute_error":
        questions = [
            "What is the actual type of the object you're calling this method on?",
            "Does that type have the method/attribute you're trying to access?",
            "Should you call a different method or check the object's type first?",
        ]
    elif pattern == "timeout":
        questions = [
            "Is there an infinite loop or unbounded recursion?",
            "Are you waiting on external resources (network, file)?",
            "Can you add a simpler test case to isolate the slow section?",
        ]
    elif pattern == "recursion_error":
        questions = [
            "Do you have a base case that stops the recursion?",
            "Is the base case being reached?",
            "Should you increase the recursion limit or switch to an iterative solution?",
        ]
    elif pattern == "coaching_request":
        questions = [
            f"What is the first concrete checkpoint for: {problem[:90]}?",
            "How will you verify progress in under five minutes?",
            "What is the smallest thing you can test right now?",
        ]
    else:
        questions = [
            "What changed right before the failure appeared?",
            "What tiny experiment can confirm your next assumption?",
            "Can you isolate the failing behavior into a minimal test?",
        ]
    
    return questions[:3]


def _micro_lesson_enhanced(pattern: str, problem_context: str = "") -> str:
    """Generate targeted micro-lessons based on error pattern."""
    lessons = {
        "syntax_error": "Micro-lesson: Python reads code character-by-character. Fix one syntax error at a time — run the code, note the first error line, then correct it before re-running.",
        "indentation_error": "Micro-lesson: indent marks code blocks (if, for, def, class). Each block must have consistent indentation. Use spaces or tabs consistently; never mix.",
        "assertion_error": "Micro-lesson: assertions say 'I expect X'. When it fails, print both expected and actual, then adjust your code to match the expectation.",
        "import_error": "Micro-lesson: Python looks for modules in standard paths. Check sys.path; install missing packages; verify the module name matches the import statement.",
        "type_error": "Micro-lesson: operations require compatible types (e.g., + works on numbers and strings, but not mixed). Print types with type(x) to debug.",
        "name_error": "Micro-lesson: use variables only after you assign them. If you see 'not defined', check spelling and scope (is it in the right function or global?).",
        "index_error": "Micro-lesson: lists are 0-indexed. len(lst) - 1 is the last valid index. Check bounds before indexing, or use a try/except.",
        "attribute_error": "Micro-lesson: methods and attributes belong to objects. If you see 'has no attribute', check what type the object actually is (print type(x)).",
        "timeout": "Micro-lesson: timeouts mean your code is stuck. Look for infinite loops, deep recursion, or waiting on external resources. Add debug prints to trace where it hangs.",
        "recursion_error": "Micro-lesson: recursion needs a base case (when to stop). Without it, you recurse infinitely until memory runs out.",
    }
    return lessons.get(pattern, "Micro-lesson: isolate the failing behavior and verify it with a single targeted check.")


def _estimate_confidence_enhanced(error_pattern: str, has_context: bool = True) -> float:
    """Estimate confidence in guidance based on error clarity and context availability."""
    pattern_confidence = {
        "syntax_error": 0.95,
        "assertion_error": 0.85,
        "import_error": 0.88,
        "indentation_error": 0.92,
        "type_error": 0.82,
        "name_error": 0.88,
        "index_error": 0.85,
        "attribute_error": 0.80,
        "timeout": 0.70,
        "recursion_error": 0.78,
        "coaching_request": 0.75,
    }
    
    base = pattern_confidence.get(error_pattern, 0.65)
    if not has_context:
        base *= 0.85
    
    return round(min(0.99, base), 2)


__all__ = [
    "_extract_error_pattern_enhanced",
    "_socratic_questions_enhanced",
    "_micro_lesson_enhanced",
    "_estimate_confidence_enhanced",
]
