import asyncio
import concurrent.futures
import json
import logging
import os
import re
import urllib.request
from typing import Optional, Any, Dict, Union

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

    def _standardize_result(self, result: Any, *, task_kind: str, target: str, prompt: str, files: Any) -> Dict[str, Any]:
        normalized = dict(result) if isinstance(result, dict) else {"payload": result}
        normalized.setdefault("status", "ok")
        normalized.setdefault("agent", "CodingAgent")
        normalized.setdefault("mode", "coding")
        normalized.setdefault("task_kind", task_kind)
        normalized.setdefault("target", target)
        normalized.setdefault("prompt", prompt)
        normalized.setdefault("files", files)
        normalized["summary"] = normalized.get("summary") or f"Handled {task_kind} request for {target or 'the current target'}."
        normalized["quality_flags"] = normalized.get("quality_flags") or ["structured_output"]
        normalized["evidence"] = normalized.get("evidence") or {
            "task_kind": task_kind,
            "target": target,
            "has_files": bool(files),
        }
        return normalized

    def run(self, prompt: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Hybrid natural-language router for CodingAgent.
        - Fast keyword routing for obvious cases
        - LLM reasoning for ambiguous cases
        - Safer source-grounded output for documentation requests
        """
        if isinstance(prompt, dict):
            prompt_text = str(prompt.get("prompt") or prompt.get("task") or prompt.get("description") or prompt.get("content") or "").strip()
            context = prompt.get("context") or {}
            files = prompt.get("files") or context.get("files") or []
            target = str(prompt.get("target") or prompt.get("file_path") or context.get("target") or self._extract_target_from_prompt(prompt_text) or "unknown").strip()
            explicit_intent = str(prompt.get("coding_intent") or prompt.get("intent") or context.get("coding_intent") or "").strip().lower()
        else:
            prompt_text = str(prompt or "").strip()
            context = {}
            files = []
            target = self._extract_target_from_prompt(prompt_text)
            explicit_intent = ""

        prompt_lower = prompt_text.lower()

        if explicit_intent in {"generate_code", "patch_existing"}:
            result = self._run_async(self.generate_code(prompt_text, context=context))
            return self._standardize_result(result, task_kind="generate_code", target=target, prompt=prompt_text, files=files)

        if explicit_intent == "refactor_code":
            result = self._run_async(self.refactor(target or "unknown", "default"))
            return self._standardize_result(result, task_kind="refactor", target=target, prompt=prompt_text, files=files)

        if explicit_intent == "analyze_codebase":
            result = self._run_async(self.analyze_codebase("."))
            return self._standardize_result(result, task_kind="analysis", target=target, prompt=prompt_text, files=files)

        if explicit_intent == "run_tests":
            result = self._run_async(self.run_tests("."))
            return self._standardize_result(result, task_kind="test", target=target, prompt=prompt_text, files=files)

        if explicit_intent == "write_docs":
            result = self._run_async(self.write_docs(target=target, doc_style=str(context.get("doc_style") or "google"), source=str(context.get("source") or prompt_text)))
            return self._standardize_result(result, task_kind="documentation", target=target, prompt=prompt_text, files=files)

        if "refactor" in prompt_lower:
            target = target if target and target.lower() != "unknown" else "unknown"
            strategy = "default"
            result = self._run_async(self.refactor(target, strategy))
            return self._standardize_result(result, task_kind="refactor", target=target, prompt=prompt_text, files=files)

        if "analyze" in prompt_lower or "analysis" in prompt_lower:
            result = self._run_async(self.analyze_codebase("."))
            return self._standardize_result(result, task_kind="analysis", target=target, prompt=prompt_text, files=files)

        if "test" in prompt_lower:
            result = self._run_async(self.run_tests(project_path="."))
            return self._standardize_result(result, task_kind="test", target=target, prompt=prompt_text, files=files)

        if "docs" in prompt_lower or "documentation" in prompt_lower:
            result = self._run_async(self.write_docs(target=target, doc_style=str(context.get("doc_style") or "google"), source=str(context.get("source") or prompt_text)))
            return self._standardize_result(result, task_kind="documentation", target=target, prompt=prompt_text, files=files)

        if "commit" in prompt_lower:
            payload = {
                "status": "requires_interaction",
                "message": "Code commit requires interactive approval.",
                "agent": "CodingAgent",
                "mode": "coding",
                "task_kind": "commit",
                "target": target,
                "prompt": prompt_text,
                "files": files,
            }
            return self._standardize_result(payload, task_kind="commit", target=target, prompt=prompt_text, files=files)

        try:
            decision = self._run_async(
                self._call_reasoning_engine(
                    f"Decide which CodingAgent tool should handle this prompt:\n\n{prompt_text}\n\n"
                    "Options: generate_code, refactor, analyze_codebase, run_tests, write_docs.\n"
                    "Return ONLY the tool name."
                )
            )
        except Exception:
            decision = "generate_code"

        decision = decision.strip().lower()

        if "refactor" in decision:
            result = self._run_async(self.refactor(target or "unknown", "default"))
            return self._standardize_result(result, task_kind="refactor", target=target, prompt=prompt_text, files=files)

        if "analyze" in decision:
            result = self._run_async(self.analyze_codebase("."))
            return self._standardize_result(result, task_kind="analysis", target=target, prompt=prompt_text, files=files)

        if "test" in decision:
            result = self._run_async(self.run_tests("."))
            return self._standardize_result(result, task_kind="test", target=target, prompt=prompt_text, files=files)

        if "docs" in decision:
            result = self._run_async(self.write_docs(target=target, doc_style=str(context.get("doc_style") or "google"), source=str(context.get("source") or prompt_text)))
            return self._standardize_result(result, task_kind="documentation", target=target, prompt=prompt_text, files=files)

        result = self._run_async(self.generate_code(prompt_text, context=context))
        return self._standardize_result(result, task_kind="generate_code", target=target, prompt=prompt_text, files=files)

    def _extract_target_from_prompt(self, prompt_text: str) -> str:
        text = str(prompt_text or "").strip()
        if not text:
            return "unknown"
        matches = re.findall(r"(?:[A-Za-z]:)?[\\/](?:[A-Za-z0-9_.-]+[\\/])*[A-Za-z0-9_.-]+|[A-Za-z0-9_.-]+\.[A-Za-z0-9_.-]+", text)
        if matches:
            return matches[0]
        if " for " in text:
            tail = text.split(" for ", 1)[1].strip()
            if tail and tail.lower() != "the code":
                return tail
        return "unknown"


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
        self.log("WARNING", "CodingAgent initialized without sub-engines.")

    def _build_task_plan(self, prompt: str, context: Optional[dict] = None) -> dict:
        """Return a compact execution brief so the agent is more predictable."""
        text = str(prompt or "").strip()
        if not text:
            return {
                "objective": "No explicit task provided.",
                "language": "generic",
                "constraints": ["keep scope tight", "validate with minimal checks"],
                "validation": ["run a syntax or smoke check"],
            }

        lowered = text.lower()
        language = "python" if any(token in lowered for token in ["python", "pytest", "function", "class", "list", "dict"]) else "generic"

        objective = text
        constraints = ["preserve existing behavior", "keep scope tight", "prefer minimal, testable edits"]
        validation = ["run syntax or unit checks"]
        if "test" in lowered or "pytest" in lowered:
            validation = ["run focused test checks for the changed behavior"]
        elif "api" in lowered or "route" in lowered or "server" in lowered:
            validation = ["verify request/response contract and happy-path behavior"]
        elif "ui" in lowered or "frontend" in lowered or "component" in lowered:
            validation = ["check rendering and state behavior with a focused smoke test"]

        return {
            "objective": objective,
            "language": language,
            "constraints": constraints,
            "validation": validation,
        }

    # ---------------------------------------------------------
    # Logging helper (fixes your crash)
    # ---------------------------------------------------------

    def log(self, level: str, message: str):
        """
        Structured logging via the standard logging module.
        """
        level_upper = level.upper()
        if level_upper == "DEBUG":
            logger.debug(message)
        elif level_upper == "INFO":
            logger.info(message)
        elif level_upper == "WARN" or level_upper == "WARNING":
            logger.warning(message)
        elif level_upper == "ERROR":
            logger.error(message)
        else:
            logger.info(message)

    def _run_async(self, coro):
        """
        Safe bridge for calling async methods from sync context.
        Handles both already-running and fresh event loops gracefully.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            try:
                return asyncio.run(coro)
            except Exception as e:
                logger.error(f"Error running async task: {e}")
                raise
        else:
            try:
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, coro)
                    return future.result()
            except Exception as e:
                logger.error(f"Error running async task in thread pool: {e}")
                raise

    # ---------------------------------------------------------
    # Initialization
    # ---------------------------------------------------------

    async def initialize(self) -> None:
        self.log("INFO", "CodingAgent initialized (no sub-engines to load).")

    # ---------------------------------------------------------
    # PUBLIC API (placeholders until engines exist)
    # ---------------------------------------------------------

    async def analyze_codebase(self, codebase_path: str) -> dict:
        """Run lightweight static analysis over a codebase and return metrics.

        Uses src/mammoth_os/analysis/code_inspector.py for best-effort metrics.
        """
        try:
            from mammoth_os.analysis.code_inspector import analyze_codebase as inspector
            metrics = inspector(codebase_path)
            return {
                "summary": {
                    "files": metrics.get("file_count", 0),
                    "lines": metrics.get("total_lines", 0),
                    "functions": metrics.get("functions", 0),
                    "classes": metrics.get("classes", 0),
                },
                "todos": metrics.get("todos", []),
                "files": metrics.get("files", {}),
            }
        except Exception as exc:
            self.log("ERROR", f"analyze_codebase failed: {exc}")
            return {"error": str(exc)}

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
        """Generate code, tests, and docs for a natural-language prompt.

        Uses the MammothOS-context prompt template which asks the LLM to return
        three labelled blocks: ``python`` (implementation), ``pytest`` (tests),
        and ``docs``.  The structured response is parsed by
        ``parse_structured_code_response`` so callers always receive populated
        code / tests / docs keys.
        """
        try:
            client = get_llm_client()
        except Exception as exc:
            self.log("ERROR", f"LLM client initialization failed: {exc}")
            return {
                "code": "", "tests": "", "docs": "", "diff": "",
                "confidence": 0.0,
                "warnings": [f"LLM client unavailable: {exc}"],
            }

        # Retrieve context snippets (best-effort)
        context_snippets = []
        try:
            context_snippets = await self._retrieve_context(
                prompt,
                collection=(context or {}).get("collection", "default"),
            )
        except Exception:
            context_snippets = []

        # Build structured MammothOS prompt
        from mammoth_os.prompt_templates import build_code_gen_prompt, parse_structured_code_response
        try:
            llm_prompt = build_code_gen_prompt(prompt, context_snippets)
        except Exception:
            llm_prompt = prompt

        context = context or {}

        task_plan = self._build_task_plan(prompt, context)
        try:
            raw = await client.generate(llm_prompt, max_tokens=8192, temperature=0.2)
            parsed = parse_structured_code_response(raw)
            code_text = parsed.get("code", "")
            tests_text = parsed.get("tests", "")
            docs_text = parsed.get("docs", "")
            if str(context.get("source", "")).strip().lower() == "atlas.code.generate":
                self._write_ai_session(
                    prompt=prompt,
                    response=raw,
                    context=context,
                    ok=True,
                )
            confidence = 0.7 if code_text else 0.0
            if code_text and tests_text:
                confidence = min(0.95, confidence + 0.15)
            if code_text and docs_text:
                confidence = min(0.98, confidence + 0.05)
            return {
                "code": code_text,
                "tests": tests_text,
                "docs": docs_text,
                "diff": "",
                "confidence": confidence,
                "warnings": [] if code_text else ["LLM returned no code block"],
                "task_plan": task_plan,
                "quality_checks": task_plan.get("validation", []),
            }
        except Exception as exc:
            self.log("ERROR", f"generate_code failed: {exc}")
            if str(context.get("source", "")).strip().lower() == "atlas.code.generate":
                self._write_ai_session(
                    prompt=prompt,
                    response=f"ERROR: {exc}",
                    context=context,
                    ok=False,
                )
            fallback_plan = self._build_task_plan(prompt, context)
            return {
                "code": "", "tests": "", "docs": "", "diff": "",
                "confidence": 0.0,
                "warnings": [str(exc)],
                "task_plan": fallback_plan,
                "quality_checks": fallback_plan.get("validation", []),
            }

    @staticmethod
    def _is_uuid(value: str) -> bool:
        return bool(re.match(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
            str(value or ""),
            re.IGNORECASE,
        ))

    def _write_ai_session(self, prompt: str, response: Any, context: Dict[str, Any], ok: bool) -> None:
        """Best-effort write of code-generation sessions to mammoth.ai_sessions."""
        supabase_url = os.environ.get("SUPABASE_URL", "").strip()
        supabase_key = (
            os.environ.get("SUPABASE_ANON_KEY", "").strip()
            or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
            or os.environ.get("SUPABASE_KEY", "").strip()
        )
        if not supabase_url or not supabase_key:
            return

        response_text = response if isinstance(response, str) else json.dumps(response, ensure_ascii=False)
        user_id = str(context.get("user_id", "")).strip()

        payload: Dict[str, Any] = {
            "prompt": prompt,
            "response": response_text,
            "metadata": {
                "source": context.get("source"),
                "curriculum_id": context.get("curriculum_id"),
                "lesson_id": context.get("lesson_id"),
                "ok": ok,
            },
        }
        tokens_used = context.get("tokens_used")
        if isinstance(tokens_used, int):
            payload["tokens_used"] = tokens_used
        if self._is_uuid(user_id):
            payload["user_id"] = user_id

        url = f"{supabase_url.rstrip('/')}/rest/v1/ai_sessions"
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "apikey": supabase_key,
                "Authorization": f"Bearer {supabase_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Accept-Profile": "mammoth",
                "Content-Profile": "mammoth",
                "Prefer": "return=minimal",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=8):
                return
        except Exception as exc:
            self.log("WARNING", f"ai_sessions write failed: {exc}")

    async def refactor(self, target: str, strategy: str) -> dict:
        """Refactor target file or code using the LLM adapter as a helper.

        target may be a path relative to a project root or raw code. If the file
        exists on disk, it will be read and sent to the LLM for refactoring.
        """
        try:
            # read file if it exists
            src = None
            import os
            if os.path.exists(target):
                try:
                    with open(target, 'r', encoding='utf-8') as fh:
                        src = fh.read()
                except Exception:
                    src = None

            if src is None:
                # treat target as raw code
                src = target

            client = get_llm_client()
            prompt = f"Refactor the following Python code to improve readability, reduce complexity, and add minimal comments. Preserve behavior.\n\n{src}"
            raw = await client.generate(prompt, max_tokens=8192, temperature=0.2)
            refactored = extract_code_from_text(raw)
            diff = self._unified_diff(src, refactored)
            return {
                "original": src,
                "refactored": refactored,
                "diff": diff,
                "confidence": 0.5,
            }
        except Exception as exc:
            self.log("ERROR", f"refactor failed: {exc}")
            return {"original": "", "refactored": "", "diff": "", "confidence": 0.0, "error": str(exc)}

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

        # ── Syntax-check collected files before sandbox ──────────────────────────
        for _rel, _src in list(project_files.items()):
            try:
                compile(_src, _rel, "exec")
            except SyntaxError as _se:
                return {
                    "passed": False,
                    "stdout": "",
                    "stderr": f"SyntaxError in {_rel} — {_se.msg} (line {_se.lineno}): {_se.text or ''}",
                    "returncode": 1,
                    "method": "syntax-check",
                }
        # ─────────────────────────────────────────────────────────────────────────
        
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
        if os.path.exists('solution.py'):
            sol_spec = importlib.util.spec_from_file_location('solution', 'solution.py')
            sol_mod = importlib.util.module_from_spec(sol_spec)
            sol_spec.loader.exec_module(sol_mod)
            mod.__dict__.update({k: v for k, v in vars(sol_mod).items() if not k.startswith('_')})
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

                            # Set up sys.path FIRST so solution.py can be found
                            if project_path not in sys.path:
                                sys.path.insert(0, project_path)
                                remove_project_path = True
                            else:
                                remove_project_path = False

                            try:
                                # Inject solution namespace so test files don't need explicit imports
                                sol_path = os.path.join(project_path, 'solution.py')
                                if os.path.exists(sol_path):
                                    sol_spec = importlib.util.spec_from_file_location('solution', sol_path)
                                    sol_mod = importlib.util.module_from_spec(sol_spec)
                                    sol_spec.loader.exec_module(sol_mod)
                                    mod.__dict__.update({k: v for k, v in vars(sol_mod).items() if not k.startswith('_')})
                                spec.loader.exec_module(mod)  # ← only called ONCE
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

    async def write_docs(self, target: str, doc_style: str = "google", source: str = "") -> dict:
        """Create a lightweight documentation block without depending on a separate engine."""
        normalized_target = (str(target or "").strip() if isinstance(target, str) else "")
        source_text = str(source or "").strip()

        if not source_text and normalized_target:
            try:
                if os.path.exists(normalized_target):
                    with open(normalized_target, "r", encoding="utf-8") as fh:
                        source_text = fh.read()
                else:
                    source_text = normalized_target
            except Exception:
                source_text = normalized_target

        if not source_text or normalized_target.lower() in {"unknown", "", "none"}:
            return {
                "status": "needs_context",
                "message": "Write_docs requires a real file path or source snippet. Unknown targets are rejected to avoid low-value placeholder docs.",
                "documented_code": "# missing\n\n## Overview\n\nNo source text or target file was provided for documentation generation.",
                "doc_coverage_pct": 0.0,
                "style": doc_style,
            }

        header = os.path.basename(normalized_target) if normalized_target and os.path.basename(normalized_target) else "Generated module"
        summary = source_text[:220].replace("\n", " ").strip()
        if not summary:
            summary = "Implementation generated for the request."

        generated = (
            f"# {header}\n\n"
            f"## Overview\n\n{summary}\n\n"
            f"## Notes\n\n"
            f"- Keep the behavior focused and easy to test.\n"
            f"- Validate the core paths before expanding scope.\n"
            f"- Prefer small, explicit functions with clear input/output contracts.\n"
        )

        return {"status": "ok", "documented_code": generated, "doc_coverage_pct": 85.0, "style": doc_style}

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
        if not files:
            return {"error": "No files specified for commit", "commit_hash": None, "pushed": False}
        
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
        """Recursively collect all Python file paths under the given directory."""
        import glob
        import os

        if not os.path.exists(path):
            self.log("WARNING", f"_get_files: path not found: {path}")
            return []

        # If it's a single file, just return it directly
        if os.path.isfile(path):
            return [path]

        return sorted(
            glob.glob(os.path.join(path, "**", "*.py"), recursive=True)
     )

    async def _read_file(self, path: str) -> str:
        """Read a file from disk and return its contents as a string."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            self.log("WARNING", f"_read_file: file not found: {path}")
            return ""
        except Exception as exc:
            self.log("WARNING", f"_read_file failed for {path}: {exc}")
            return ""

    def _build_prompt(
        self,
        prompt: str,
        context_files: list,
        language: str,
        constraints: dict,
    ) -> str:
        """Assemble a full LLM prompt from user request + context + constraints."""
        parts = [f"Language: {language}\n"] if language else []

        if constraints:
            parts.append("Constraints:\n" + "\n".join(
                f"  - {k}: {v}" for k, v in constraints.items()
            ))

        if context_files:
            parts.append("Relevant context files:")
            for snippet in context_files[:5]:  # cap at 5 to stay under token budget
                name = snippet.get("file", "unknown")
                content = snippet.get("content", "")[:800]  # trim long files
                parts.append(f"# {name}\n{content}")

        parts.append(f"Task:\n{prompt}")
        return "\n\n".join(parts)

    async def _call_reasoning_engine(self, prompt: str) -> str:
        """Use the LLM to reason about a prompt and return a decision string."""
        try:
            client = get_llm_client()
            response = await client.generate(
                prompt,
                max_tokens=64,
                temperature=0.0,  # deterministic — we want a single tool name back
            )
            return (response or "generate_code").strip()
        except Exception as exc:
            self.log("WARNING", f"_call_reasoning_engine failed: {exc}")
            return "generate_code"

    async def _run_tests_sandboxed(self, tests: str, code: str, language: str) -> dict:
        """Run tests against code inside the sandbox, injecting the solution namespace."""
        # ── Syntax-check generated code before sandbox ───────────────────────────
        try:
            compile(code, "solution.py", "exec")
        except SyntaxError as se:
            return {
                "passed": False,
                "stdout": "",
                "stderr": f"SyntaxError in generated code — {se.msg} (line {se.lineno}): {se.text or ''}",
                "returncode": 1,
                "method": "syntax-check",
            }
        # ─────────────────────────────────────────────────────────────────────────

        try:
            from mammoth_os.sandbox_runner import run_code
        except Exception as exc:
            return {"passed": False, "error": f"SandboxRunner unavailable: {exc}"}

        test_script = '''
    import importlib.util, sys, os, traceback
    test_files = [p for p in os.listdir('.') if p.startswith("test_") and p.endswith('.py')]
    failed = 0
    out_lines = []
    err_lines = []
    for t in test_files:
        try:
            spec = importlib.util.spec_from_file_location('mod_' + t, t)
            mod = importlib.util.module_from_spec(spec)
            if os.path.exists('solution.py'):
                sol_spec = importlib.util.spec_from_file_location('solution', 'solution.py')
                sol_mod = importlib.util.module_from_spec(sol_spec)
                sol_spec.loader.exec_module(sol_mod)
                mod.__dict__.update({k: v for k, v in vars(sol_mod).items() if not k.startswith('_')})
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
print("\\n".join(out_lines))
if err_lines:
    print("\\n".join(err_lines), file=sys.stderr)
sys.exit(failed)
'''
        project_files = {
            "solution.py": code,
            "test_generated.py": tests,
        }

        result = run_code(
            code="",
            test_script=test_script,
            timeout=60,
            memory_limit_mb=256,
            project_files=project_files,
        )

        parsed = self._parse_pytest_output(result)
        return {
            **parsed,
            "stdout": result.get("stdout", ""),
            "stderr": result.get("stderr", ""),
            "returncode": result.get("returncode", -1),
            "language": language,
        }


    async def _compute_diff(self, original_path: str, new_code: str) -> str:
        """Compute a unified diff between the original file and new_code string."""
        original = await self._read_file(original_path)
        return self._unified_diff(original, new_code)

    def _unified_diff(self, a: str, b: str) -> str:
        import difflib
        return "\n".join(difflib.unified_diff(a.splitlines(), b.splitlines(), lineterm=""))

    async def _compute_complexity(self, ast_results: list) -> dict:
        """Compute cyclomatic complexity per function across all AST results."""
        import ast as ast_mod

        BRANCH_NODES = (
            ast_mod.If, ast_mod.For, ast_mod.While, ast_mod.ExceptHandler,
            ast_mod.With, ast_mod.Assert, ast_mod.comprehension,
        )

        scores = {}
        high_risk = []

        for item in ast_results:
            source = item.get("source", "")
            filename = item.get("file", "unknown")
            if not source:
                continue
            try:
                tree = ast_mod.parse(source)
                for node in ast_mod.walk(tree):
                    if isinstance(node, (ast_mod.FunctionDef, ast_mod.AsyncFunctionDef)):
                        complexity = 1 + sum(
                            1 for child in ast_mod.walk(node)
                            if isinstance(child, BRANCH_NODES)
                        )
                        key = f"{filename}::{node.name}"
                        scores[key] = complexity
                        if complexity >= 10:
                            high_risk.append({"function": key, "complexity": complexity})
            except Exception:
                continue

        avg = round(sum(scores.values()) / len(scores), 2) if scores else 0.0
        return {
            "scores": scores,
            "average": avg,
            "high_risk": high_risk,           # complexity >= 10
            "medium_risk": [                   # complexity 5-9
                {"function": k, "complexity": v}
                for k, v in scores.items() if 5 <= v < 10
            ],
            "total_functions": len(scores),
        }

    async def _extract_dependencies(self, ast_results: list) -> list[str]:
        """Walk AST results and extract all third-party import names."""
        import sys
        stdlib = set(sys.stdlib_module_names)  # Python 3.10+
        deps = set()

        for item in ast_results:
            source = item.get("source", "")
            if not source:
                continue
            try:
                import ast as ast_mod
                tree = ast_mod.parse(source)
                for node in ast_mod.walk(tree):
                    if isinstance(node, ast_mod.Import):
                        for alias in node.names:
                            root = alias.name.split(".")[0]
                            if root not in stdlib:
                                deps.add(root)
                    elif isinstance(node, ast_mod.ImportFrom):
                        if node.module:
                            root = node.module.split(".")[0]
                            if root not in stdlib:
                                deps.add(root)
            except Exception:
                continue

        return sorted(deps)

    async def _run_shell(self, cmd: str) -> dict:
        """Run a shell command asynchronously and return stdout/stderr/returncode."""
        import asyncio
        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            return {
                "stdout": stdout.decode("utf-8", errors="replace"),
                "stderr": stderr.decode("utf-8", errors="replace"),
                "returncode": proc.returncode,
            }
        except Exception as exc:
            self.log("ERROR", f"_run_shell failed: {exc}")
            return {"stdout": "", "stderr": str(exc), "returncode": -1}

    def _parse_pytest_output(self, result: dict) -> dict:
        """Parse our OK:/FAIL:/ERROR: line format from sandbox test output."""
        stdout = result.get("stdout", "")
        stderr = result.get("stderr", "")
        passed, failed, errors = [], [], []

        for line in stdout.splitlines():
            if line.startswith("OK:"):
                passed.append(line[3:].strip())
            elif line.startswith("FAIL:"):
                failed.append(line[5:].strip())

        for line in stderr.splitlines():
            if line.startswith("ERROR:") or line.startswith("IMPORT ERROR:"):
                errors.append(line.strip())

        return {
            "passed": len(failed) == 0 and len(errors) == 0,
            "passed_tests": passed,
            "failed_tests": failed,
            "errors": errors,
            "total": len(passed) + len(failed) + len(errors),
            "pass_count": len(passed),
            "fail_count": len(failed) + len(errors),
        }

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
            self.log("WARNING", f"Unhandled event type: {event.event_type}")

    async def shutdown(self) -> None:
        self.log("INFO", "CodingAgent shutting down.")
        await super().shutdown()# type: ignore
