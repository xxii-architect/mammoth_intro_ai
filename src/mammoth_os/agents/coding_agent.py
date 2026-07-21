import asyncio
import json
import logging
from typing import Optional, Any, Dict

from mammoth_os.agents.base_agent import BaseAgent  # type: ignore
from mammoth_os.llm_client import get_llm_client, extract_code_from_text  # type: ignore


logger = logging.getLogger("mammoth.agents.coding")


class CodingAgent(BaseAgent):
    """
    Level 5 Flagship Agent — Full-stack code intelligence.

    This version removes references to non‑existent sub‑engines
    (SyntaxAnalyzer, SemanticChecker, etc.) so the agent can run
    cleanly inside Mammoth OS.
    """
    
        # ---------------------------------------------------------
    # HYBRID ROUTING: Natural-language entrypoint
    # ---------------------------------------------------------

    def run(self, prompt: str) -> str:
        """
        Hybrid natural-language router for CodingAgent.
        - Fast keyword routing for obvious cases
        - LLM reasoning for ambiguous cases
        - Pretty formatted output for Mammoth CLI
        """

        prompt_lower = prompt.lower()

        # ─────────────────────────────────────────────
        # 1. Keyword Routing (fast path)
        # ─────────────────────────────────────────────

        if "refactor" in prompt_lower:
            target = "unknown"
            strategy = "default"
            result = asyncio.run(self.refactor(target, strategy))
            return (
                "🧠 Refactor (keyword routed)\n"
                f"Refactored:\n{result.get('refactored','')}\n\n"
                f"Diff:\n{result.get('diff','')}\n\n"
                f"Confidence: {result.get('confidence',0.0):.2f}"
            )

        if "analyze" in prompt_lower or "analysis" in prompt_lower:
            path = "."
            result = asyncio.run(self.analyze_codebase(path))
            return (
                "🧠 Codebase Analysis (keyword routed)\n"
                f"{json.dumps(result, indent=2)}"
            )

        if "test" in prompt_lower:
            result = asyncio.run(self.run_tests(project_path="."))
            return (
                "🧪 Test Results (keyword routed)\n"
                f"{json.dumps(result, indent=2)}"
            )

        if "docs" in prompt_lower or "documentation" in prompt_lower:
            result = asyncio.run(self.write_docs(target="unknown"))
            return (
                "📘 Documentation (keyword routed)\n"
                f"{json.dumps(result, indent=2)}"
            )

        if "commit" in prompt_lower:
            return (
                "🧷 Code Commit requires interactive mode.\n"
                "Use: code commit:\n"
            )

        # ─────────────────────────────────────────────
        # 2. LLM Routing (intelligent fallback)
        # ─────────────────────────────────────────────

        try:
            decision = asyncio.run(
                self._call_reasoning_engine(
                    f"Decide which CodingAgent tool should handle this prompt:\n\n{prompt}\n\n"
                    "Options: generate_code, refactor, analyze_codebase, run_tests, write_docs.\n"
                    "Return ONLY the tool name."
                )
            )
        except Exception:
            decision = "generate_code"  # safe fallback

        decision = decision.strip().lower()

        # ─────────────────────────────────────────────
        # 3. Execute chosen tool
        # ─────────────────────────────────────────────

        if "refactor" in decision:
            result = asyncio.run(self.refactor("unknown", "default"))
            return (
                "🧠 Refactor (LLM routed)\n"
                f"{json.dumps(result, indent=2)}"
            )

        if "analyze" in decision:
            result = asyncio.run(self.analyze_codebase("."))
            return (
                "🧠 Codebase Analysis (LLM routed)\n"
                f"{json.dumps(result, indent=2)}"
            )

        if "test" in decision:
            result = asyncio.run(self.run_tests("."))
            return (
                "🧪 Test Results (LLM routed)\n"
                f"{json.dumps(result, indent=2)}"
            )

        if "docs" in decision:
            result = asyncio.run(self.write_docs("unknown"))
            return (
                "📘 Documentation (LLM routed)\n"
                f"{json.dumps(result, indent=2)}"
            )

        # ─────────────────────────────────────────────
        # 4. Default: generate code
        # ─────────────────────────────────────────────

        result = asyncio.run(self.generate_code(prompt, context={}))
        return (
            "🧠 Code Generation (LLM routed)\n"
            f"Code:\n{result.get('code','')}\n\n"
            f"Tests:\n{result.get('tests','')}\n\n"
            f"Docs:\n{result.get('docs','')}\n\n"
            f"Confidence: {result.get('confidence',0.0):.2f}\n"
            f"Warnings: {result.get('warnings',[])}"
        )


    def __init__(
        self,
        router: Optional[Any] = None,
        agent_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(router)

        self.agent_id = agent_id or "coding"
        self.config = config or {}

        # Safe logging
        self.log("WARN", "CodingAgent initialized without sub-engines.")

    # ---------------------------------------------------------
    # Logging helper (fixes your crash)
    # ---------------------------------------------------------

    def log(self, level: str, message: str):
        """
        Simple logging wrapper so CodingAgent never crashes
        when BaseAgent does not provide a log() method.
        """
        print(f"[CodingAgent:{level}] {message}")

    # ---------------------------------------------------------
    # Initialization
    # ---------------------------------------------------------

    async def initialize(self) -> None:
        self.log("INFO", "CodingAgent initialized (no sub-engines to load).")

    # ---------------------------------------------------------
    # PUBLIC API (placeholders until engines exist)
    # ---------------------------------------------------------

    async def analyze_codebase(self, codebase_path: str) -> dict:
        self.log("WARN", "analyze_codebase called but no analysis engines exist.")
        return {
            "symbols": [],
            "issues": [],
            "complexity": {},
            "dependencies": [],
            "file_count": 0,
        }

    async def _retrieve_context(self, query: str, collection: str = "default") -> list:
        """Retrieve context snippets from the local VectorStoreAgent using the LLM embedding for the query.

        Returns a list of dicts with keys: id, text, metadata, score
        """
        snippets = []
        try:
            # Build embedding for the query
            client = get_llm_client()
            embed = await client.embed([query])
            vec = embed[0]

            # Instantiate VectorStoreAgent directly (lightweight)
            try:
                from mammoth_os.agents.vector_store_agent import VectorStoreAgent
                v = VectorStoreAgent(router=None)
                await v.initialize()
                results = await v.search(collection, vec, top_k=5)
                for r in results:
                    # r contains score and stored doc info
                    snippets.append({
                        "id": r.get("id"),
                        "text": r.get("metadata", {}).get("text") or r.get("vector") or "",
                        "metadata": r.get("metadata", {}),
                        "score": r.get("score"),
                    })
            except Exception:
                # If vector store not available or empty, return empty list
                return []
        except Exception:
            return []

        return snippets

    async def generate_code(self, prompt: str, context: dict = None) -> dict:  # type: ignore
        """Generate code, tests and docs for a natural-language prompt.

        This implementation builds a prompt using a template and augments it
        with contextual snippets retrieved from the vector store.
        """
        client = None
        try:
            client = get_llm_client()
        except Exception as exc:
            self.log("ERROR", f"LLM client initialization failed: {exc}")
            return {
                "code": "",
                "tests": "",
                "docs": "",
                "diff": "",
                "confidence": 0.0,
                "warnings": [f"LLM client unavailable: {exc}"],
            }

        # Retrieve context snippets (best-effort)
        context_snippets = []
        try:
            context_snippets = await self._retrieve_context(prompt, collection=(context or {}).get("collection", "default"))
        except Exception:
            context_snippets = []

        # Build a prompt using the template library
        try:
            from mammoth_os.prompt_templates import build_code_gen_prompt
            llm_prompt = build_code_gen_prompt(prompt, context_snippets)
        except Exception:
            llm_prompt = prompt

        try:
            # Basic generation call — allow config-based overrides later
            raw = await client.generate(llm_prompt, max_tokens=1500, temperature=0.2)
            code = extract_code_from_text(raw)

            return {
                "code": code,
                "tests": "",
                "docs": "",
                "diff": "",
                "confidence": 0.6,
                "warnings": [],
            }
        except Exception as exc:
            self.log("ERROR", f"generate_code failed: {exc}")
            return {
                "code": "",
                "tests": "",
                "docs": "",
                "diff": "",
                "confidence": 0.0,
                "warnings": [str(exc)],
            }

    async def refactor(self, target: str, strategy: str) -> dict:
        self.log("WARN", "refactor called but no refactor engine exists.")
        return {
            "original": "",
            "refactored": "",
            "diff": "",
            "confidence": 0.0,
        }

    async def run_tests(self, project_path: str, test_pattern: str = "test_*.py") -> dict:
        """Run tests for a project path inside the sandbox runner.

        This method collects python files under project_path and runs pytest in the sandbox.
        Returns a dict with pass/fail summary and raw output.
        """
        try:
            from mammoth_os.sandbox_runner import run_code
        except Exception as exc:
            self.log("ERROR", f"SandboxRunner unavailable: {exc}")
            return {"passed": False, "error": str(exc)}

        import glob
        import os
        import sys

        if not os.path.exists(project_path):
            return {"passed": False, "error": "project_path not found"}

        project_files = {}
        # collect python files to include in the sandbox
        for p in glob.glob(os.path.join(project_path, "**", "*.py"), recursive=True):
            rel = os.path.relpath(p, project_path)
            try:
                with open(p, "r", encoding="utf-8") as f:
                    project_files[rel] = f.read()
            except Exception:
                continue

        # test runner script: simple, dependency-free runner that imports test modules and executes functions named test_*
        test_script = '''
import importlib.util, sys, os, traceback
# Find test files in the workspace that start with "test_" and end with ".py"
test_files = [p for p in os.listdir('.') if p.startswith("test_") and p.endswith('.py')]
failed = 0
out_lines = []
err_lines = []
for t in test_files:
    try:
        spec = importlib.util.spec_from_file_location('mod_' + t, t)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        for name in dir(mod):
            if name.startswith('test_') and callable(getattr(mod, name)):
                try:
                    getattr(mod, name)()
                    out_lines.append("OK: %s::%s" % (t, name))
                except AssertionError as ae:
                    failed += 1
                    err_lines.append("FAIL: %s::%s: %s" % (t, name, ae))
                except Exception:
                    failed += 1
                    err_lines.append("ERROR: %s::%s: %s" % (t, name, traceback.format_exc()))
    except Exception:
        failed += 1
        err_lines.append("IMPORT ERROR: %s: %s" % (t, traceback.format_exc()))
print("\n".join(out_lines))
if err_lines:
    print("\n".join(err_lines), file=sys.stderr)
sys.exit(failed)
'''
        # run in sandbox
        result = run_code(code="", test_script=test_script, timeout=120, memory_limit_mb=256, project_files=project_files)

        # If sandbox runner failed or timed out, fall back to a simple in-process test runner
        if not result.get("passed"):
            try:
                import importlib.util, traceback
                failures = 0
                out_lines = []
                err_lines = []
                for rel, content in project_files.items():
                    if rel.startswith("test_") and rel.endswith(".py"):
                        # write to a temp file and import by module name
                        tmp_path = os.path.join(project_path, rel)
                        mod_name = os.path.splitext(os.path.basename(rel))[0]
                        try:
                            spec = importlib.util.spec_from_file_location(mod_name, tmp_path)
                            mod = importlib.util.module_from_spec(spec)
                            # Ensure the project root is on sys.path so package imports like 'pkg.mathlib' resolve
                            if project_path not in sys.path:
                                sys.path.insert(0, project_path)
                                remove_project_path = True
                            else:
                                remove_project_path = False
                            try:
                                spec.loader.exec_module(mod)
                            finally:
                                if remove_project_path:
                                    try:
                                        sys.path.remove(project_path)
                                    except ValueError:
                                        pass
                            for name in dir(mod):
                                if name.startswith('test_') and callable(getattr(mod, name)):
                                    try:
                                        getattr(mod, name)()
                                        out_lines.append(f"OK: {rel}::{name}")
                                    except AssertionError as ae:
                                        failures += 1
                                        err_lines.append(f"FAIL: {rel}::{name}: {ae}")
                                    except Exception:
                                        failures += 1
                                        err_lines.append(f"ERROR: {rel}::{name}: {traceback.format_exc()}")
                        except Exception:
                            failures += 1
                            err_lines.append(f"IMPORT ERROR: {rel}: {traceback.format_exc()}")

                return {
                    "passed": failures == 0,
                    "stdout": "\n".join(out_lines),
                    "stderr": "\n".join(err_lines),
                    "returncode": 0 if failures == 0 else 1,
                    "method": "in-process-fallback",
                }
            except Exception as exc:
                # If fallback also fails, return original sandbox result
                result.setdefault('stderr', '')
                result['stderr'] += f"\nfallback_error: {exc}"

        # Normalize result
        return {
            "passed": bool(result.get("passed")),
            "stdout": result.get("stdout", ""),
            "stderr": result.get("stderr", ""),
            "returncode": result.get("returncode", -1),
            "method": result.get("method"),
            "duration_ms": result.get("duration_ms"),
        }

    async def write_docs(self, target: str, doc_style: str = "google") -> dict:
        self.log("WARN", "write_docs called but no doc engine exists.")
        return {"documented_code": "", "doc_coverage_pct": 0.0}

    async def commit_changes(
        self,
        project_path: str,
        files: list[str],
        message: str,
        auto_push: bool = False,
    ) -> dict:
        """
        This one CAN work because it uses shell commands.
        """
        staged = " ".join(files)
        await self._run_shell(f"cd {project_path} && git add {staged}")
        await self._run_shell(f'cd {project_path} && git commit -m "{message}"')

        commit_hash = (await self._run_shell(
            f"cd {project_path} && git rev-parse HEAD"
        ))["stdout"].strip()

        pushed = False
        if auto_push:
            await self._run_shell(f"cd {project_path} && git push")
            pushed = True

        await self.emit_event("CODE_COMMITTED", {"hash": commit_hash, "message": message})# type: ignore
        return {"commit_hash": commit_hash, "pushed": pushed, "branch": "main"}

    # ---------------------------------------------------------
    # INTERNAL HELPERS (unchanged placeholders)
    # ---------------------------------------------------------

    async def _get_files(self, path: str) -> list[str]:
        ...

    async def _read_file(self, path: str) -> str:
        ...

    async def _retrieve_context(self, query: str, codebase_path: str) -> list[dict]:
        ...

    def _build_prompt(self, prompt: str, context_files: list, language: str, constraints: dict) -> str:
        ...

    async def _call_reasoning_engine(self, prompt: str) -> str:
        ...

    async def _run_tests_sandboxed(self, tests: str, code: str, language: str) -> dict:
        ...

    async def _compute_diff(self, original_path: str, new_code: str) -> str:
        ...

    def _unified_diff(self, a: str, b: str) -> str:
        import difflib
        return "\n".join(difflib.unified_diff(a.splitlines(), b.splitlines(), lineterm=""))

    async def _compute_complexity(self, ast_results: list) -> dict:
        ...

    async def _extract_dependencies(self, ast_results: list) -> list[str]:
        ...

    async def _run_shell(self, cmd: str) -> dict:
        ...

    def _parse_pytest_output(self, result: dict) -> dict:
        ...

    def _score_confidence(self, test_results: dict, warnings: list) -> float:
        base = 0.9
        if test_results.get("failed", 0) > 0:
            base -= 0.2
        base -= len(warnings) * 0.02
        return max(0.0, min(1.0, base))

    # ---------------------------------------------------------
    # LIFECYCLE
    # ---------------------------------------------------------

    async def process(self, event: "MammothEvent") -> None:  # type: ignore
        handlers = {
            "CODE_GENERATE": lambda e: self.generate_code(
                e.payload["prompt"], e.payload.get("context")
            ),
            "CODE_REFACTOR": lambda e: self.refactor(
                e.payload["target"], e.payload["strategy"]
            ),
            "CODE_ANALYZE": lambda e: self.analyze_codebase(e.payload["path"]),
            "CODE_TEST": lambda e: self.run_tests(e.payload["project_path"]),
            "CODE_DOCS": lambda e: self.write_docs(e.payload["target"]),
            "CODE_COMMIT": lambda e: self.commit_changes(**e.payload),
        }

        handler = handlers.get(event.event_type)
        if handler:
            result = await handler(event)
            await self.emit_event(f"{event.event_type}_RESULT", result)# type: ignore
        else:
            self.log("WARN", f"Unhandled event type: {event.event_type}")

    async def shutdown(self) -> None:
        self.log("INFO", "CodingAgent shutting down.")
        await super().shutdown()# type: ignore
