from typing import Any, Dict

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

class MammothGuideAgent:
    def __init__(self, router=None):
        self.router = router

    def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        repo_context = payload.get("repo_context", {})
        message = payload.get("message", "")

        return {
            "role": "assistant",
            "message": self._build_response(message, repo_context),
            "repo_context_used": bool(repo_context),
        }

    def _build_response(self, message: str, repo_context: Dict[str, Any]) -> str:
        summary = repo_context.get("summary", {})
        todos = repo_context.get("todos", [])
        files = summary.get("files")
        lines = summary.get("lines")
        functions = summary.get("functions")
        classes = summary.get("classes")

        return (
            f"MammothOS Guide\n\n"
            f"Message: {message}\n\n"
            f"Repository Overview:\n"
            f"- Files: {files}\n"
            f"- Lines: {lines}\n"
            f"- Functions: {functions}\n"
            f"- Classes: {classes}\n\n"
            f"TODO markers found:\n"
            + "\n".join([f"- {t['file']}:{t['line']} — {t['text']}" for t in todos[:10]])
        )
