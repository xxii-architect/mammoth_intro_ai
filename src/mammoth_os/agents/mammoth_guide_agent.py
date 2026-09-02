from typing import Any, Dict, List

from .base_agent import BaseAgent

GUIDE_SYSTEM_PROMPT = """
You are the MammothOS Guide — a documentation and architecture expert.
Your job is to explain MammothOS clearly, accurately, and helpfully.

You use repo-context snapshots to:
- describe the SDK layout
- explain agent capabilities
- outline command structures
- summarize architecture
- reference real files and functions
- give newcomers a tour of the system
- explain how autonomous runs work
- explain how repo-context works
- explain how the runtime contracts work

You NEVER modify files.
You NEVER generate patches.
You NEVER execute code.
You ONLY explain, summarize, and guide.

Be clear, structured, and helpful.
"""

# Well-known MammothOS file reference map for SDK/ATLAS guidance
_SDK_FILE_MAP = {
    "sdk": ("src/mammoth_os/sdk.py", "AtlasFAB, ATLASSession, embed API"),
    "atlas": ("src/mammoth_os/agents/atlas_agent.py", "Adaptive tutoring engine"),
    "orchestrator": ("src/mammoth_os/agents/orchestrator.py", "Central router & cognitive coordinator"),
    "coding_agent": ("src/mammoth_os/agents/coding_agent.py", "Code generation, patching, refactor"),
    "planner": ("src/mammoth_os/agents/planner_agent.py", "Plan generation & step routing"),
    "curriculum": ("src/mammoth_os/agents/curriculum_agent.py", "Adaptive curriculum generator"),
    "registry": ("src/mammoth_os/agent_registry.py", "Canonical agent manifest & health state"),
    "api_server": ("api_server.py", "Backend integration surface & UI wiring"),
    "memory": ("src/mammoth_os/memory_engine.py", "Session memory & context storage"),
    "cortex": ("src/mammoth_os/cortex/router.py", "Runtime routing & dispatch"),
    "guide": ("src/mammoth_os/agents/mammoth_guide_agent.py", "This guide agent"),
}

def _score_relevance(message: str, keys: List[str]) -> List[str]:
    """Return keys whose topic words appear in the message (case-insensitive)."""
    msg_lower = message.lower()
    return [k for k in keys if k in msg_lower or k.replace("_", " ") in msg_lower]

class MammothGuideAgent(BaseAgent):
    def __init__(self, router=None):
        super().__init__(router)

    def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        repo_context = payload.get("repo_context", {})
        message = payload.get("message", "")
        branch = str(repo_context.get("branch") or "main")

        steps = self._build_steps(message, repo_context)
        summary_text = self._build_summary(message, repo_context, steps)

        return {
            "role": "assistant",
            "message": summary_text,
            "guide_steps": steps,
            "branch": branch,
            "repo_context_used": bool(repo_context),
            "adapter": "mammoth-guide",
        }

    def _build_steps(self, message: str, repo_context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Build structured steps from message intent + repo context."""
        summary = repo_context.get("summary", {})
        snippets = repo_context.get("snippets", []) if isinstance(repo_context.get("snippets"), list) else []
        search_hits = repo_context.get("search_hits", []) if isinstance(repo_context.get("search_hits"), list) else []
        branch = str(repo_context.get("branch") or "main")

        steps: List[Dict[str, Any]] = []

        # Step 1: Repo overview
        files = summary.get("files", "?")
        lines = summary.get("lines", "?")
        functions = summary.get("functions", "?")
        classes = summary.get("classes", "?")
        steps.append({
            "title": "Repository Overview",
            "detail": f"{files} files · {lines} lines · {functions} functions · {classes} classes (branch: {branch})",
            "kind": "info",
            "code": None,
            "lang": None,
            "file_ref": None,
        })

        # Step 2: Relevant SDK/agent references based on message
        relevant_keys = _score_relevance(message, list(_SDK_FILE_MAP.keys()))
        if not relevant_keys:
            relevant_keys = ["sdk", "orchestrator", "registry"]

        for key in relevant_keys[:4]:
            path, desc = _SDK_FILE_MAP[key]
            steps.append({
                "title": f"{key.replace('_', ' ').title()} — {desc}",
                "detail": f"Primary source: `{path}`",
                "kind": "info",
                "code": None,
                "lang": None,
                "file_ref": path,
            })

        # Step 3: Code snippets from repo context
        for item in snippets[:3]:
            if not isinstance(item, dict):
                continue
            path = item.get("path", "")
            content = item.get("content", "") or item.get("snippet", "") or item.get("excerpt", "")
            if path and content:
                steps.append({
                    "title": f"Live snippet — {path}",
                    "detail": f"From `{path}` on branch `{item.get('ref') or branch}`",
                    "kind": "snippet",
                    "code": str(content).strip(),
                    "lang": _infer_lang(path),
                    "file_ref": path,
                    "line_ref": item.get("line"),
                })

        # Step 4: Search hits
        for item in search_hits[:2]:
            if not isinstance(item, dict):
                continue
            path = item.get("path", "")
            text = item.get("text", "") or item.get("line_text", "") or item.get("preview", "")
            if path and text:
                steps.append({
                    "title": f"Search hit — {path}",
                    "detail": f"Match on branch `{item.get('ref') or branch}` line {item.get('line') or '?'}",
                    "kind": "snippet",
                    "code": str(text).strip(),
                    "lang": _infer_lang(path),
                    "file_ref": path,
                    "line_ref": item.get("line"),
                })

        # Step 5: How to use guide (always appended as last step)
        steps.append({
            "title": "Using the MammothOS Guide",
            "detail": "Type /guide <question> to ask anything about MammothOS architecture, SDK, agents, or ATLAS.",
            "kind": "tip",
            "code": "# Example guide queries:\n/guide How do I embed the ATLAS SDK?\n/guide Walk me through the orchestrator routing\n/guide Show me the agent registry layout",
            "lang": "shell",
            "file_ref": None,
            "notes": "Guide is read-only — it never modifies files or executes code.",
        })

        return steps

    def _build_summary(self, message: str, repo_context: Dict[str, Any], steps: List[Dict[str, Any]]) -> str:
        branch = str(repo_context.get("branch") or "main")
        ref_files = [s["file_ref"] for s in steps if s.get("file_ref")]
        ref_list = "\n".join(f"  - {f}" for f in ref_files[:6]) or "  - No live file references in this request."
        return (
            f"**MammothOS Guide** (branch: `{branch}`)\n\n"
            f"Query: _{message}_\n\n"
            f"**{len(steps)} step guide generated.** Expand each step below to see details and live code snippets.\n\n"
            f"**Live file references included:**\n{ref_list}"
        )


def _infer_lang(path: str) -> str:
    ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    return {
        "py": "python", "js": "javascript", "jsx": "javascript",
        "ts": "typescript", "tsx": "typescript",
        "sh": "shell", "bash": "shell",
        "sql": "sql", "json": "json", "yaml": "yaml", "yml": "yaml",
        "md": "markdown",
    }.get(ext, "plaintext")
