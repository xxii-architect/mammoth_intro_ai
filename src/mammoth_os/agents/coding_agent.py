import asyncio
import json
import logging
from typing import Optional, Any, Dict

from mammoth_os.agents.base_agent import BaseAgent  # type: ignore
from mammoth_os.llm_client import get_llm_client, extract_code_from_text  # type: ignore


logger = logging.getLogger("mammoth.agents.coding")


# ---------------------------------------------------------
# INTENT MODEL
# ---------------------------------------------------------

@dataclass
class CodingIntent:
    action: str
    target: Optional[str] = None
    path: Optional[str] = None
    strategy: Optional[str] = None
    language: Optional[str] = None
    context: Dict[str, Any] = None


# ---------------------------------------------------------
# INTENT PARSER
# ---------------------------------------------------------

class CodingIntentParser:
    """
    Hybrid intent parser:
    - Fast keyword routing
    - LLM fallback via CodingAgent._call_reasoning_engine
    """

    def __init__(self, agent: "CodingAgent") -> None:
        self.agent = agent

    async def parse(self, prompt: str) -> CodingIntent:
        pl = prompt.lower()

        # Fast keyword routing
        if "refactor" in pl:
            return CodingIntent("refactor", target="unknown", strategy="default", language="python")

        if "analyze" in pl or "analysis" in pl:
            return CodingIntent("analyze_codebase", path=".", language="python")

        if "test" in pl:
            return CodingIntent("run_tests", path=".", language="python")

        if "docs" in pl or "documentation" in pl:
            return CodingIntent("write_docs", target="unknown", language="python")

        if "scaffold agent" in pl or "new agent" in pl:
            words = prompt.replace(",", " ").split()
            name = next((w for w in words if w.endswith("Agent")), "NewAgent")
            return CodingIntent("scaffold_agent", target=name, language="python")

        if "scaffold ui" in pl or "new ui" in pl or "react" in pl:
            return CodingIntent("scaffold_ui", target="NewComponent", language="typescript")

        if "scaffold backend" in pl or "api" in pl or "router" in pl:
            return CodingIntent("scaffold_backend", target="NewEndpoint", language="python")

        if "sql" in pl or "schema" in pl or "table" in pl:
            return CodingIntent("generate_sql", target="UnknownEntity", language="sql")

        if "commit" in pl:
            return CodingIntent("commit_changes", path=".", context={})

        # LLM fallback
        try:
            decision = await self.agent._call_reasoning_engine(
                "\n".join([
                    "User prompt:",
                    prompt,
                    "",
                    "Decide which tool to use:",
                    "generate_code, refactor, analyze_codebase, run_tests, write_docs,",
                    "scaffold_agent, scaffold_ui, scaffold_backend, generate_sql, commit_changes.",
                    "",
                    "Return ONLY the tool name."
                ])
            )
            decision = decision.strip().lower()
        except Exception:
            decision = "generate_code"

        if "refactor" in decision:
            return CodingIntent("refactor", target="unknown", strategy="default", language="python")
        if "analyze" in decision:
            return CodingIntent("analyze_codebase", path=".", language="python")
        if "test" in decision:
            return CodingIntent("run_tests", path=".", language="python")
        if "docs" in decision:
            return CodingIntent("write_docs", target="unknown", language="python")
        if "agent" in decision:
            return CodingIntent("scaffold_agent", target="NewAgent", language="python")
        if "ui" in decision or "react" in decision:
            return CodingIntent("scaffold_ui", target="NewComponent", language="typescript")
        if "backend" in decision or "router" in decision:
            return CodingIntent("scaffold_backend", target="NewEndpoint", language="python")
        if "sql" in decision:
            return CodingIntent("generate_sql", target="UnknownEntity", language="sql")
        if "commit" in decision:
            return CodingIntent("commit_changes", path=".", context={})

        return CodingIntent("generate_code", language="python", context={"raw_prompt": prompt})


# ---------------------------------------------------------
# EXECUTOR
# ---------------------------------------------------------

class CodingExecutor:
    """
    Executes CodingIntent objects using CodingAgent's tools.
    """

    def __init__(self, agent: "CodingAgent") -> None:
        self.agent = agent
        self._routes: Dict[str, Callable[[CodingIntent], Any]] = {
            "generate_code": self._exec_generate_code,
            "refactor": self._exec_refactor,
            "analyze_codebase": self._exec_analyze_codebase,
            "run_tests": self._exec_run_tests,
            "write_docs": self._exec_write_docs,
            "scaffold_agent": self._exec_scaffold_agent,
            "scaffold_ui": self._exec_scaffold_ui,
            "scaffold_backend": self._exec_scaffold_backend,
            "generate_sql": self._exec_generate_sql,
            "commit_changes": self._exec_commit_changes,
        }

    async def execute(self, intent: CodingIntent) -> Dict[str, Any]:
        handler = self._routes.get(intent.action)
        if not handler:
            return {"error": f"Unknown action: {intent.action}"}
        return await handler(intent)

    async def _exec_generate_code(self, intent: CodingIntent) -> Dict[str, Any]:
        prompt = intent.context.get("raw_prompt", "") if intent.context else ""
        return await self.agent.generate_code(prompt, context=intent.context or {})

    async def _exec_refactor(self, intent: CodingIntent) -> Dict[str, Any]:
        return await self.agent.refactor(intent.target or "unknown", intent.strategy or "default")

    async def _exec_analyze_codebase(self, intent: CodingIntent) -> Dict[str, Any]:
        return await self.agent.analyze_codebase(intent.path or ".")

    async def _exec_run_tests(self, intent: CodingIntent) -> Dict[str, Any]:
        return await self.agent.run_tests(intent.path or ".")

    async def _exec_write_docs(self, intent: CodingIntent) -> Dict[str, Any]:
        return await self.agent.write_docs(intent.target or "unknown")

    async def _exec_scaffold_agent(self, intent: CodingIntent) -> Dict[str, Any]:
        return await self.agent.scaffold_agent(intent.target or "NewAgent")

    async def _exec_scaffold_ui(self, intent: CodingIntent) -> Dict[str, Any]:
        return await self.agent.scaffold_ui(intent.target or "NewComponent")

    async def _exec_scaffold_backend(self, intent: CodingIntent) -> Dict[str, Any]:
        return await self.agent.scaffold_backend(intent.target or "NewEndpoint")

    async def _exec_generate_sql(self, intent: CodingIntent) -> Dict[str, Any]:
        return await self.agent.generate_sql(intent.target or "UnknownEntity")

    async def _exec_commit_changes(self, intent: CodingIntent) -> Dict[str, Any]:
        return {"error": "commit_changes requires explicit payload via events"}


# ---------------------------------------------------------
# CODING AGENT (HYBRID COGNITIVE)
# ---------------------------------------------------------

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


    def __init__(self, router: Optional[Any] = None, agent_id: Optional[str] = None, config: Optional[Dict[str, Any]] = None) -> None:
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

        self.log("INFO", "CodingAgent initialized (Hybrid Cognitive Mode C).")

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

        registry_path = r"C:\Users\runni\mammoth_intro_ai\src\mammoth_os\registry\agent_registry.py"

        if not os.path.exists(registry_path):
            return {"status": "error", "message": "agent_registry.py not found"}

        try:
            with open(registry_path, "r", encoding="utf-8") as f:
                content = f.read()

            agent_key = name.lower().replace("agent", "")
            import_line = f"from mammoth_os.agents.{name.lower()} import {name}"
            loader_line = f'    if agent_name == "{agent_key}": return {name}(router)'

            updated = content

            if import_line not in updated:
                updated = import_line + "\n" + updated

            if loader_line not in updated:
                updated = updated.replace(
                    "def load_agent(agent_name: str, router):",
                    f"def load_agent(agent_name: str, router):\n{loader_line}",
                )

            with open(registry_path, "w", encoding="utf-8") as f:
                f.write(updated)

            return {"status": "registered", "agent": name}

        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    # -----------------------------------------------------
    # SCAFFOLDING — UI
    # -----------------------------------------------------

    async def scaffold_ui(self, name: str) -> Dict[str, Any]:

        code = "\n".join([
            'import React from "react";',
            "",
            f"export const {name} = () => {{",
            "  return (",
            '    <div className="p-4">',
            f"      <h1>{name}</h1>",
            "    </div>",
            "  );",
            "};",
        ])

        path = f"src/atlas/ui/{name}.tsx"
        return await self._write_new_file(path, code)

    # -----------------------------------------------------
    # SCAFFOLDING — BACKEND
    # -----------------------------------------------------

    async def scaffold_backend(self, name: str) -> Dict[str, Any]:

        code = "\n".join([
            "from fastapi import APIRouter",
            "",
            "router = APIRouter()",
            "",
            f"@router.get('/{name}')",
            f"async def get_{name}():",
            f"    return {{'status': 'ok', 'endpoint': '{name}'}}",
        ])

        path = f"src/mammoth_os/backend/{name}_router.py"
        result = await self._write_new_file(path, code)

        await self._insert_backend_router(name)

        return result

    async def _insert_backend_router(self, name: str) -> Dict[str, Any]:
        """
        Auto-insert backend routers into server.py.
        """
        staged = " ".join(files)
        await self._run_shell(f"cd {project_path} && git add {staged}")
        await self._run_shell(f'cd {project_path} && git commit -m "{message}"')

        commit_hash = (await self._run_shell(
            f"cd {project_path} && git rev-parse HEAD"
        ))["stdout"].strip()

        server_path = r"C:\MammothOS\command_center_v3\server.py"

        await self.emit_event("CODE_COMMITTED", {"hash": commit_hash, "message": message})# type: ignore
        return {"commit_hash": commit_hash, "pushed": pushed, "branch": "main"}

    # ---------------------------------------------------------
    # INTERNAL HELPERS (unchanged placeholders)
    # ---------------------------------------------------------

            import_line = f"from mammoth_os.backend.{name}_router import router as {name}_router"
            include_line = f"app.include_router({name}_router)"

            updated = content

            if import_line not in updated:
                updated = import_line + "\n" + updated

            if include_line not in updated:
                updated = updated.replace(
                    "app = FastAPI()",
                    f"app = FastAPI()\n{include_line}",
                )

            with open(server_path, "w", encoding="utf-8") as f:
                f.write(updated)

            return {"status": "router_inserted", "router": name}

        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    # -----------------------------------------------------
    # SQL GENERATION
    # -----------------------------------------------------

    async def generate_sql(self, entity: str) -> Dict[str, Any]:

        sql = "\n".join([
            f"create table if not exists {entity} (",
            "    id uuid primary key default gen_random_uuid(),",
            "    created_at timestamptz default now()",
            ");",
        ])

        path = f"src/atlas/schema/{entity}.sql"
        return await self._write_new_file(path, sql)

    # -----------------------------------------------------
    # INTERNAL HELPERS
    # -----------------------------------------------------

    async def _read_file(self, path: str) -> str:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            return ""

    def _unified_diff(self, a: str, b: str) -> str:
        import difflib
        return "\n".join(difflib.unified_diff(a.splitlines(), b.splitlines(), lineterm=""))

    async def _call_reasoning_engine(self, prompt: str) -> str:
        if hasattr(self, "call_llm"):
            return await self.call_llm(prompt)  # type: ignore
        return "generate_code"

    async def _run_shell(self, cmd: str) -> Dict[str, Any]:
        self.log("INFO", f"Shell: {cmd}")
        return {"stdout": "", "stderr": "", "returncode": 0}

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
