"""Shared education routing and strict execution-plan shape checks."""
import re
from typing import Any


EXECUTION_AGENTS = frozenset({
    "research", "market_intel", "coding", "community_engine", "field_ops",
    "reasoning", "executor", "build", "deploy", "search", "curriculum", "orchestrator",
})
EDUCATION_AGENTS = frozenset({"research", "reasoning", "search", "curriculum"})


def education_goal(goal: str) -> bool:
    return bool(re.search(
        r"\b(?:learn(?:ing)?|teach(?:ing)?|tutor(?:ing)?|curricul(?:um|a)|lesson(?:s)?|"
        r"education(?:al)?|pedagog(?:y|ical)|study|studying|course(?:s)?|classroom|"
        r"comprehension|flashcards?|spaced\s+repetition)\b", goal, re.IGNORECASE,
    ))


def software_goal(goal: str) -> bool:
    return bool(re.search(
        r"\b(?:implement|patch|debug|refactor|endpoint|frontend|backend|"
        r"software|codebase|component|api|ui)\b|"
        r"\b(?:write|build|fix|generate)\s+(?:(?:a|the)\s+)?(?:code|script|app|application)\b|"
        r"\b[\w.-]+\.(?:py|jsx|tsx|js|ts)\b", goal, re.IGNORECASE,
    ))


def planning_agents(goal: str) -> frozenset[str]:
    if education_goal(goal):
        return EDUCATION_AGENTS | ({"coding"} if software_goal(goal) else set())
    return EXECUTION_AGENTS


def task_diagnostics(tasks: Any, *, allowed: frozenset[str] = EXECUTION_AGENTS,
                     curriculum: bool = False) -> list[str]:
    if not isinstance(tasks, list) or not 1 <= len(tasks) <= 80:
        return ["A plan requires 1-80 structured tasks."]
    diagnostics = []
    seen: set[str] = set()
    for index, task in enumerate(tasks):
        if not isinstance(task, dict):
            diagnostics.append(f"Task {index + 1} must be an object.")
            continue
        task_id = task.get("task_id")
        if not isinstance(task_id, str) or not task_id.strip() or len(task_id) > 200 or task_id in seen:
            diagnostics.append(f"Task {index + 1} needs a unique, nonempty task_id.")
        agent = task.get("agent")
        if not isinstance(agent, str) or agent not in allowed | ({"tutor"} if curriculum else set()):
            diagnostics.append(f"Task {index + 1} names an unavailable planning agent.")
        if not isinstance(task.get("title"), str) or not task["title"].strip():
            diagnostics.append(f"Task {index + 1} needs an explicit title.")
        payload = task.get("input")
        if not isinstance(payload, dict) or not payload:
            diagnostics.append(f"Task {index + 1} needs an input object.")
        elif not curriculum and ("lesson" in payload or "module_id" in task):
            diagnostics.append(f"Task {index + 1} is lesson data, not an execution task.")
        dependencies = task.get("depends_on")
        if (not isinstance(dependencies, list)
                or any(not isinstance(dep, str) or dep not in seen for dep in dependencies)
                or len(dependencies) != len(set(dep for dep in dependencies if isinstance(dep, str)))):
            diagnostics.append(f"Task {index + 1} dependencies must name distinct earlier tasks.")
        if isinstance(task_id, str):
            seen.add(task_id)
    return diagnostics
