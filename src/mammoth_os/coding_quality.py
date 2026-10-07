"""Source and validation contracts for code proposals (never execute model code)."""
import ast
import re

_EXISTING = re.compile(
    r"\b(?:patch|refactor|fix|modify|update|extend|integrate)\b"
    r"|\bexisting\s+(?:file|module|code|class|project|repository)\b"
    r"|\b(?:inside|within)\b.{0,80}\b(?:module|file|codebase)\b"
    r"|\bleave\b.{0,60}\b(?:alone|unchanged)\b", re.IGNORECASE,
)


def requires_existing_source(prompt: str) -> bool:
    return bool(_EXISTING.search(prompt or ""))


def is_advice_request(prompt: str) -> bool:
    text = re.sub(r"```[\s\S]*?```", "", prompt or "")
    asks_advice = re.search(
        r"\b(?:what (?:do you think|are your (?:thoughts|suggestions))|"
        r"your (?:thoughts|suggestions|recommendations)|"
        r"pros and cons|tradeoffs|trade-offs)\b", text, re.IGNORECASE,
    )
    asks_implementation = re.search(
        r"\b(?:implement|build|write|generate|patch|refactor|fix|modify|"
        r"update|replace|apply|delete|change|add|remove)\b", text, re.IGNORECASE,
    )
    return bool(asks_advice and not asks_implementation)


def supplied_source(prompt: str, context: dict, target: str) -> str:
    for key in ("source", "code", "content", "snippet", "implementation"):
        value = context.get(key)
        if isinstance(value, str) and value.strip() and value != "atlas.code.generate":
            return value
    for item in context.get("files", []):
        if not isinstance(item, dict):
            continue
        path = item.get("path") or item.get("file") or item.get("target")
        if path == target:
            value = item.get("content") or item.get("text") or item.get("source")
            if isinstance(value, str) and value.strip():
                return value
    match = re.search(r"```(?:python|py|javascript|js|typescript|ts|tsx|jsx|css|html|vue|svelte)?[ \t]*\r?\n([\s\S]+?)```", prompt)
    return match.group(1) if match else ""


def syntax_checks(code: str, tests: str, language: str) -> list[dict]:
    if language not in {"python", "py"}:
        return [{"name": "syntax", "status": "not_run", "detail": "No language-specific compiler was run."}]
    checks = []
    for name, text in (("implementation_syntax", code), ("test_syntax", tests)):
        if not text:
            checks.append({"name": name, "status": "not_run", "detail": "No content supplied."})
            continue
        try:
            ast.parse(text)
            checks.append({"name": name, "status": "passed", "detail": "Python AST parsing only; code was not executed."})
        except SyntaxError as exc:
            checks.append({"name": name, "status": "failed", "detail": f"Line {exc.lineno}: {exc.msg}"})
    return checks
