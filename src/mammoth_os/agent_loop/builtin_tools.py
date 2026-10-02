"""Built-in Mammoth Mind tools.

Repository tools only ever operate on ``ctx.repo_root``, which is resolved by
:class:`mammoth_os.repo_access.RepoAccessPolicy` before a run starts. They never
accept absolute paths, never follow symlinks, and never read secret files.
"""

from __future__ import annotations

import difflib
import fnmatch
import os
import subprocess
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .tools import TIER_NETWORK, TIER_READ, TIER_WRITE, ToolContext, ToolRegistry, ToolSpec

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", ".next", ".mammoth", ".pytest_cache", ".mypy_cache"}
SECRET_PATTERNS = (
    ".env", ".env.*", "*.pem", "*.key", "*.p12", "*.pfx", "id_rsa*", "id_ed25519*",
    ".npmrc", ".pypirc", ".netrc", "credentials*", "*secret*", "*.keystore",
)
MAX_READ_BYTES = 20_000
MAX_READ_LINES = 400
MAX_FILE_BYTES = 5_000_000
MAX_LIST = 300


def is_secret_path(rel: str) -> bool:
    name = rel.replace("\\", "/").rsplit("/", 1)[-1].lower()
    return any(fnmatch.fnmatch(name, pattern) for pattern in SECRET_PATTERNS)


def safe_repo_path(root: Path, rel: Any) -> Optional[Path]:
    """Resolve ``rel`` inside ``root``; ``None`` if it escapes, is a symlink, or is secret."""
    text = str(rel or "").replace("\\", "/").strip()
    if not text or text.startswith("/") or ":" in text:
        return None
    parts = [p for p in text.split("/") if p not in {"", "."}]
    if any(p == ".." for p in parts) or (parts and parts[0] == ".git"):
        return None
    if is_secret_path(text):
        return None
    root_resolved = root.resolve()
    candidate = root_resolved
    for part in parts:
        candidate = candidate / part
        if candidate.is_symlink():
            return None
    try:
        candidate.resolve().relative_to(root_resolved)
    except ValueError:
        return None
    return candidate


def _rel(root: Path, path: Path) -> str:
    return path.relative_to(root.resolve()).as_posix()


def _list_files(args: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
    root = ctx.repo_root.resolve()
    base_rel = str(args.get("path") or "").strip()
    base = safe_repo_path(root, base_rel) if base_rel else root
    if base is None or not base.exists() or not base.is_dir():
        return {"status": "error", "code": "invalid_path", "error": f"Not a directory in this repository: {base_rel or '.'}"}
    pattern = str(args.get("glob") or "").strip()
    limit = int(args.get("limit") or 200)
    files: List[str] = []
    truncated = False
    for dirpath, dirnames, filenames in os.walk(base, followlinks=False):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not (Path(dirpath) / d).is_symlink())
        for filename in sorted(filenames):
            full = Path(dirpath) / filename
            if full.is_symlink():
                continue
            rel = _rel(root, full)
            if is_secret_path(rel) or (pattern and not fnmatch.fnmatch(rel, pattern)):
                continue
            if len(files) >= limit:
                truncated = True
                break
            files.append(rel)
        if truncated:
            break
    return {"status": "ok", "path": base_rel or ".", "files": files, "truncated": truncated}


def _read_file(args: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
    root = ctx.repo_root
    rel = str(args.get("path") or "")
    target = safe_repo_path(root, rel)
    if target is None or not target.is_file():
        return {"status": "error", "code": "invalid_path", "error": f"File not readable: {rel}"}
    if target.stat().st_size > MAX_FILE_BYTES:
        return {"status": "error", "code": "too_large", "error": f"{rel} is larger than {MAX_FILE_BYTES // 1_000_000} MB; use repo_search instead."}
    raw = target.read_bytes()
    if b"\x00" in raw[:4096]:
        return {"status": "error", "code": "binary", "error": f"Binary file: {rel}"}
    # Slice by line over the whole file so every range stays reachable; the
    # byte budget applies only to the returned excerpt.
    lines = raw.decode("utf-8", errors="replace").splitlines()
    total = len(lines)
    start = max(1, int(args.get("start_line") or 1))
    if total and start > total:
        return {"status": "error", "code": "out_of_range", "error": f"{rel} has {total} lines; start_line {start} is past the end."}
    end = int(args.get("end_line") or (start + MAX_READ_LINES - 1))
    end = max(start, min(end, start + MAX_READ_LINES - 1, total))
    kept: List[str] = []
    used = 0
    for line in lines[start - 1:end]:
        used += len(line.encode("utf-8")) + 1
        if kept and used > MAX_READ_BYTES:
            break
        kept.append(line)
    end = start + len(kept) - 1 if kept else start
    result: Dict[str, Any] = {
        "status": "ok",
        "path": _rel(root, target),
        "start_line": start,
        "end_line": end,
        "total_lines": total,
        "content": "\n".join(kept),
    }
    if end < total:
        result["next_start_line"] = end + 1
    return result


def _search(args: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
    root = ctx.repo_root.resolve()
    query = str(args.get("query") or "").strip()
    max_results = int(args.get("max_results") or 30)
    matches: List[Dict[str, Any]] = []
    if (root / ".git").exists():
        env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_PAGER": "cat"}
        proc = subprocess.run(
            ["git", "-c", "core.quotepath=off", "grep", "-n", "-I", "-F", "-i", "--no-color", "-e", query, "--"],
            cwd=str(root), capture_output=True, text=True, timeout=20, env=env,
        )
        for line in proc.stdout.splitlines():
            path, _, rest = line.partition(":")
            line_no, _, text = rest.partition(":")
            if not path or is_secret_path(path) or safe_repo_path(root, path) is None:
                continue
            matches.append({"path": path, "line": int(line_no) if line_no.isdigit() else 0, "text": text.strip()[:240]})
            if len(matches) >= max_results:
                break
    else:
        needle = query.lower()
        for rel in _list_files({"limit": 2000}, ctx).get("files", []):
            target = root / rel
            try:
                for idx, text in enumerate(target.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1):
                    if needle in text.lower():
                        matches.append({"path": rel, "line": idx, "text": text.strip()[:240]})
                        break
            except OSError:
                continue
            if len(matches) >= max_results:
                break
    return {"status": "ok", "query": query, "matches": matches}


def _unified_diff(root: Path, changes: List[Dict[str, Any]]) -> str:
    chunks: List[str] = []
    for change in changes:
        rel = str(change.get("path") or "")
        target = safe_repo_path(root, rel)
        before = ""
        if target is not None and target.is_file():
            before = target.read_text(encoding="utf-8", errors="replace")
        after = str(change.get("content") or "")
        chunks.extend(difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=f"a/{rel}" if before else "/dev/null",
            tofile=f"b/{rel}",
        ))
    return "".join(chunks)


def _edit_location_hint(text: str, old: str) -> str:
    """Point a failed edit at the lines that most likely hold its first line."""
    anchor = next((ln.strip() for ln in old.splitlines() if ln.strip()), "")
    if len(anchor) < 4:
        return ""
    hits = [no for no, ln in enumerate(text.splitlines(), start=1) if anchor in ln]
    if not hits:
        return " Its first line does not appear in the file either."
    shown = ", ".join(str(n) for n in hits[:5])
    return f" Its first line appears at line(s) {shown}; read around there (whitespace or later lines likely differ)."


def _resolve_changes(root: Path, raw_changes: List[Dict[str, Any]]) -> "tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]":
    """Turn each change into ``{path, content}``.

    A change carries either ``content`` (full new file) or ``edits`` (exact
    ``old`` → ``new`` replacements applied to the current file). Edits keep
    model output small, so large files never need to be re-sent in full.
    """
    resolved: List[Dict[str, Any]] = []
    for change in raw_changes:
        rel = str(change.get("path") or "")
        target = safe_repo_path(root, rel)
        if target is None:
            return [], {"status": "error", "code": "invalid_path", "error": f"Cannot propose a change to: {rel}"}
        has_content = isinstance(change.get("content"), str)
        edits = change.get("edits")
        if has_content == bool(edits):
            return [], {"status": "error", "code": "invalid_change", "error": f"{rel}: provide exactly one of 'content' or 'edits'."}
        if has_content:
            resolved.append({"path": rel, "content": change["content"]})
            continue
        if not target.is_file():
            return [], {"status": "error", "code": "not_found", "error": f"{rel}: 'edits' need an existing file; use 'content' to create it."}
        text = target.read_text(encoding="utf-8", errors="replace")
        for idx, edit in enumerate(edits, start=1):
            old, new = str(edit.get("old") or ""), str(edit.get("new") or "")
            count = text.count(old) if old else 0
            if count != 1:
                problem = "was not found" if count == 0 else f"matches {count} places; include more surrounding lines"
                hint = _edit_location_hint(text, old) if count == 0 else ""
                return [], {
                    "status": "error", "code": "edit_mismatch",
                    "error": f"{rel} edit {idx}: 'old' text {problem}. Re-read the file and copy the exact lines.{hint}",
                }
            text = text.replace(old, new, 1)
        resolved.append({"path": rel, "content": text})
    return resolved, None


def _propose_patch(args: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
    root = ctx.repo_root
    changes, error = _resolve_changes(root, args.get("files") or [])
    if error is not None:
        return error
    title = str(args.get("title") or "MammothOS proposal")
    diff = _unified_diff(root, changes)
    if not diff:
        return {"status": "error", "code": "no_changes", "error": "The proposed content matches the current files."}
    result: Dict[str, Any] = {
        "status": "ok",
        "title": title,
        "diff": diff[:200_000],
        "files": [str(c.get("path")) for c in changes],
        "pushed": False,
        "applied": False,
    }
    if ctx.repo_scope == "tenant" and ctx.policy is not None and ctx.repo_source_id:
        patch = ctx.policy.propose_patch(ctx.user_id, ctx.repo_source_id, changes, title=title)
        if patch.get("status") != "ok":
            return patch
        result.update({"branch": patch.get("branch"), "patch": patch.get("patch"), "stat": patch.get("stat"), "next_step": patch.get("next_step")})
    else:
        result["next_step"] = "Review the diff and apply it yourself. MammothOS did not modify any files."
    return result


REPO_LIST_SCHEMA = {
    "type": "object",
    "properties": {
        "path": {"type": "string", "maxLength": 300, "description": "Directory relative to the repo root. Omit for the root."},
        "glob": {"type": "string", "maxLength": 120, "description": "Optional fnmatch filter such as 'src/**/*.py'."},
        "limit": {"type": "integer", "minimum": 1, "maximum": MAX_LIST},
    },
    "additionalProperties": False,
}
REPO_READ_SCHEMA = {
    "type": "object",
    "properties": {
        "path": {"type": "string", "minLength": 1, "maxLength": 300},
        "start_line": {"type": "integer", "minimum": 1},
        "end_line": {"type": "integer", "minimum": 1},
    },
    "required": ["path"],
    "additionalProperties": False,
}
REPO_SEARCH_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {"type": "string", "minLength": 2, "maxLength": 200, "description": "Literal, case-insensitive text to find."},
        "max_results": {"type": "integer", "minimum": 1, "maximum": 100},
    },
    "required": ["query"],
    "additionalProperties": False,
}
REPO_PROPOSE_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "minLength": 3, "maxLength": 120},
        "files": {
            "type": "array",
            "minItems": 1,
            "maxItems": 20,
            "items": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "minLength": 1, "maxLength": 300},
                    "content": {"type": "string", "maxLength": 400_000, "description": "Full new file content. Use only for new or small files."},
                    "edits": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 30,
                        "description": "Preferred for existing files: exact replacements applied in order. 'old' must match exactly once.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "old": {"type": "string", "minLength": 1, "maxLength": 20_000},
                                "new": {"type": "string", "maxLength": 40_000},
                            },
                            "required": ["old", "new"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["path"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["title", "files"],
    "additionalProperties": False,
}
QUERY_SCHEMA = {
    "type": "object",
    "properties": {"query": {"type": "string", "minLength": 2, "maxLength": 300}},
    "required": ["query"],
    "additionalProperties": False,
}


def register_repo_tools(registry: ToolRegistry) -> None:
    registry.register(ToolSpec(
        name="repo_list_files",
        description="List files in the connected repository.",
        input_schema=REPO_LIST_SCHEMA, tier=TIER_READ, handler=_list_files,
        trace_kind="read", needs_repo=True,
    ))
    registry.register(ToolSpec(
        name="repo_read_file",
        description=(
            "Read a line range from the connected repository (up to 400 lines per call). Reports total_lines; "
            "when more remains it returns next_start_line. For large files, repo_search first and read around the hit."
        ),
        input_schema=REPO_READ_SCHEMA, tier=TIER_READ, handler=_read_file,
        trace_kind="read", needs_repo=True,
    ))
    registry.register(ToolSpec(
        name="repo_search",
        description="Find literal text in the connected repository. Returns path, line, and text.",
        input_schema=REPO_SEARCH_SCHEMA, tier=TIER_READ, handler=_search,
        trace_kind="searched", needs_repo=True,
    ))
    registry.register(ToolSpec(
        name="repo_propose_patch",
        description=(
            "Propose file changes as a reviewable diff/patch; never pushes or edits the user's checkout. "
            "For existing files send small exact 'edits' (old → new); send full 'content' only for new or small files."
        ),
        input_schema=REPO_PROPOSE_SCHEMA, tier=TIER_WRITE, handler=_propose_patch,
        trace_kind="proposed", needs_repo=True, requires_approval=False,
    ))


def register_query_tool(
    registry: ToolRegistry,
    *,
    name: str,
    description: str,
    tier: str,
    trace_kind: str,
    handler: Callable[[str, ToolContext], Dict[str, Any]],
    admin_only: bool = False,
) -> None:
    """Register a single-``query`` tool backed by an api_server helper."""

    def _wrapped(args: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
        return handler(str(args.get("query") or ""), ctx)

    registry.register(ToolSpec(
        name=name, description=description, input_schema=QUERY_SCHEMA, tier=tier,
        handler=_wrapped, trace_kind=trace_kind, admin_only=admin_only,
    ))


__all__ = [
    "register_repo_tools",
    "register_query_tool",
    "safe_repo_path",
    "is_secret_path",
    "TIER_NETWORK",
]
