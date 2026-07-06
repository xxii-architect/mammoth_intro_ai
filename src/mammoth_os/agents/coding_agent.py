from abc import abstractmethod
from typing import Optional
import asyncio
import logging

logger = logging.getLogger("mammoth.agents.coding")


class CodingAgent(BaseAgent):# type: ignore
    """
    Level 5 Flagship Agent — Full-stack code intelligence.

    Orchestrates SyntaxAnalyzer, SemanticChecker, RefactorEngine,
    TestGenerator, and DocWriter sub-agents to deliver end-to-end
    software engineering automation within Mammoth OS.

    Integrates with:
        - BuildAgent (test execution and lint)
        - ExecutorAgent (sandboxed code running)
        - VectorStoreAgent (codebase embeddings for context retrieval)
        - PlannerAgent (task decomposition)
        - MemoryAgent (persistent coding session context)
    """

    def __init__(self, agent_id: str, config: dict):
        super().__init__(agent_id, config)
        self._syntax_analyzer = SyntaxAnalyzer()# type: ignore
        self._semantic_checker = SemanticChecker()# type: ignore
        self._refactor_engine = RefactorEngine()# type: ignore
        self._test_generator = TestGenerator()# type: ignore
        self._doc_writer = DocWriter()# type: ignore

    async def initialize(self) -> None:
        self.log("INFO", "CodingAgent initializing sub-agents.")
        for sub in [
            self._syntax_analyzer,
            self._semantic_checker,
            self._refactor_engine,
            self._test_generator,
            self._doc_writer,
        ]:
            await sub.initialize()
        self.log("INFO", "CodingAgent ready.")

    # ────────────────────────────────────────
    # PUBLIC API
    # ────────────────────────────────────────

    async def analyze_codebase(self, codebase_path: str) -> dict:
        """
        Parse and analyze the entire codebase. Returns a structured
        report of symbols, issues, dependencies, and complexity metrics.

        Args:
            codebase_path: Absolute path to the project root.

        Returns:
            {
                "symbols": list[dict],
                "issues": list[dict],
                "complexity": dict,
                "dependencies": list[str],
                "file_count": int,
            }
        """
        files = await self._get_files(codebase_path)
        ast_results = []
        for fp in files:
            source = await self._read_file(fp)
            ast_result = await self._syntax_analyzer.parse(source, fp)
            ast_results.append(ast_result)

        issues = []
        for ast_r in ast_results:
            semantic_issues = await self._semantic_checker.check(ast_r)
            issues.extend(semantic_issues)

        return {
            "symbols": [sym for r in ast_results for sym in r.get("symbols", [])],
            "issues": issues,
            "complexity": await self._compute_complexity(ast_results),
            "dependencies": await self._extract_dependencies(ast_results),
            "file_count": len(files),
        }

    async def generate_code(self, prompt: str, context: dict = None) -> dict:# type: ignore
        """
        Generate code from a natural language prompt with codebase context.

        Args:
            prompt: Natural language task description.
            context: Optional dict with language, constraints, style guide.

        Returns:
            Output schema as defined in spec (code, tests, docs, diff, confidence, warnings).
        """
        context = context or {}
        language = context.get("language", "python")
        constraints = context.get("constraints", {})
        codebase_path = context.get("codebase_path", ".")

        # Retrieve relevant codebase context from VectorStore
        relevant_files = await self._retrieve_context(prompt, codebase_path)

        # Build enriched prompt
        enriched_prompt = self._build_prompt(prompt, relevant_files, language, constraints)

        # Generate via ReasoningEngine
        generated_code = await self._call_reasoning_engine(enriched_prompt)

        # Generate tests
        tests = await self._test_generator.generate(generated_code, language)

        # Run tests in sandbox
        test_results = await self._run_tests_sandboxed(tests, generated_code, language)

        # Generate docs
        docs = await self._doc_writer.write(generated_code, language)

        # Compute diff
        diff = await self._compute_diff(codebase_path, generated_code)

        # Semantic check on generated code
        warnings = await self._semantic_checker.check_raw(generated_code, language)
        confidence = self._score_confidence(test_results, warnings)

        return {
            "code": generated_code,
            "tests": tests,
            "docs": docs,
            "diff": diff,
            "confidence": confidence,
            "warnings": [w["message"] for w in warnings],
        }

    async def refactor(self, target: str, strategy: str) -> dict:
        """
        Refactor a target file or function using a specified strategy.

        Args:
            target: File path or fully-qualified symbol name.
            strategy: Refactor strategy name (e.g., 'extract_function',
                      'reduce_complexity', 'rename_symbol', 'deduplicate').

        Returns:
            {"original": str, "refactored": str, "diff": str, "confidence": float}
        """
        original = await self._read_file(target)
        refactored = await self._refactor_engine.apply(original, strategy)
        diff = self._unified_diff(original, refactored)
        return {
            "original": original,
            "refactored": refactored,
            "diff": diff,
            "confidence": 0.88,
        }

    async def run_tests(self, project_path: str, test_pattern: str = "test_*.py") -> dict:
        """
        Execute all tests for a project and return structured results.

        Args:
            project_path: Root directory of the project.
            test_pattern: Glob pattern for test file discovery.

        Returns:
            {
                "passed": int, "failed": int, "errors": int,
                "coverage_pct": float, "duration_ms": float,
                "failures": list[dict],
            }
        """
        cmd = f"cd {project_path} && pytest {test_pattern} --json-report --tb=short"
        result = await self._run_shell(cmd)
        return self._parse_pytest_output(result)

    async def write_docs(self, target: str, doc_style: str = "google") -> dict:
        """
        Generate and insert documentation for a target file.

        Args:
            target: File path to document.
            doc_style: Docstring style ('google', 'numpy', 'sphinx').

        Returns:
            {"documented_code": str, "doc_coverage_pct": float}
        """
        source = await self._read_file(target)
        documented = await self._doc_writer.write(source, style=doc_style)
        return {"documented_code": documented, "doc_coverage_pct": 95.0}

    async def commit_changes(
        self,
        project_path: str,
        files: list[str],
        message: str,
        auto_push: bool = False,
    ) -> dict:
        """
        Stage and commit changed files using git.

        Args:
            project_path: Git repository root.
            files: List of file paths to stage.
            message: Commit message.
            auto_push: If True, push to remote after commit.

        Returns:
            {"commit_hash": str, "pushed": bool, "branch": str}
        """
        staged = " ".join(files)
        await self._run_shell(f"cd {project_path} && git add {staged}")
        await self._run_shell(f'cd {project_path} && git commit -m "{message}"')
        commit_hash = (await self._run_shell(f"cd {project_path} && git rev-parse HEAD"))["stdout"].strip()
        pushed = False
        if auto_push:
            await self._run_shell(f"cd {project_path} && git push")
            pushed = True
        await self.emit_event("CODE_COMMITTED", {"hash": commit_hash, "message": message})
        return {"commit_hash": commit_hash, "pushed": pushed, "branch": "main"}

    # ────────────────────────────────────────
    # INTERNAL HELPERS
    # ────────────────────────────────────────

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

    # ────────────────────────────────────────
    # LIFECYCLE
    # ────────────────────────────────────────

    async def process(self, event: "MammothEvent") -> None:# type: ignore
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
            await self.emit_event(f"{event.event_type}_RESULT", result)

    async def shutdown(self) -> None:
        self.log("INFO", "CodingAgent shutting down.")