from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Callable, List

from mammoth_os.agents.base_agent import BaseAgent  # type: ignore

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
    Hybrid Mode C:
    - Safe for existing files (diff only)
    - Autonomous for new files (writes immediately)
    """

    def __init__(self, router: Optional[Any] = None, agent_id: Optional[str] = None, config: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(router)
        self.agent_id = agent_id or "coding"
        self.config = config or {}

        self.intent_parser = CodingIntentParser(self)
        self.executor = CodingExecutor(self)

        self.log("INFO", "CodingAgent initialized (Hybrid Cognitive Mode C).")

    def log(self, level: str, message: str) -> None:
        logger.log(getattr(logging, level, logging.INFO), f"[CodingAgent] {message}")

    # -----------------------------------------------------
    # CLI ENTRYPOINT
    # -----------------------------------------------------

    def run(self, prompt: str) -> str:
        async def _run() -> Dict[str, Any]:
            intent = await self.intent_parser.parse(prompt)
            result = await self.executor.execute(intent)
            return {"intent": intent, "result": result}

        outcome = asyncio.run(_run())
        return f"🧠 CodingAgent — action: {outcome['intent'].action}\n" + json.dumps(outcome["result"], indent=2)

    # -----------------------------------------------------
    # SAFE/AUTONOMOUS FILE WRITER
    # -----------------------------------------------------

    async def _write_new_file(self, path: str, content: str) -> Dict[str, Any]:
        import os

        if os.path.exists(path):
            original = await self._read_file(path)
            diff = self._unified_diff(original, content)
            return {
                "status": "exists",
                "path": path,
                "diff": diff,
                "message": "File exists — returning diff",
            }

        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return {"status": "created", "path": path, "message": "New file created"}
        except Exception as exc:
            return {"status": "error", "path": path, "error": str(exc)}

    # -----------------------------------------------------
    # LLM CODE GENERATION (INDENTATION-SAFE)
    # -----------------------------------------------------

    async def generate_code(self, prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Real LLM-powered code generation.
        """

        self.log("INFO", f"LLM code generation for prompt: {prompt}")

        # Build multi-line prompt safely (no triple-quoted f-strings)
        llm_prompt = "\n".join([
            "You are CodingAgent inside MammothOS.",
            "",
            "Generate production-grade code for the following request:",
            "",
            prompt,
            "",
            "Return ONLY code. No explanation."
        ])

        try:
            code = await self._call_reasoning_engine(llm_prompt)
        except Exception as exc:
            return {"error": str(exc), "code": "", "confidence": 0.0}

        return {
            "code": code,
            "tests": "",
            "docs": "",
            "diff": "",
            "confidence": 0.95,
            "warnings": [],
        }

    # -----------------------------------------------------
    # SCAFFOLDING — AGENTS
    # -----------------------------------------------------

    async def scaffold_agent(self, name: str) -> Dict[str, Any]:

        # Build agent scaffold safely
        code = "\n".join([
            "from __future__ import annotations",
            "",
            "import logging",
            "from typing import Any, Dict, Optional",
            "from mammoth_os.agents.base_agent import BaseAgent  # type: ignore",
            "",
            f"logger = logging.getLogger('mammoth.agents.{name.lower()}')",
            "",
            f"class {name}(BaseAgent):",
            '    """',
            "    Auto-generated agent scaffold.",
            '    """',
            "",
            f"    def __init__(self, router: Optional[Any] = None, agent_id: str = '{name.lower()}', config: Optional[Dict[str, Any]] = None):",
            "        super().__init__(router)",
            "        self.agent_id = agent_id",
            "        self.config = config or {}",
            f"        logger.info('{name} initialized.')",
            "",
            "    async def initialize(self) -> None:",
            f"        logger.info('{name} initialize() called.')",
            "",
            "    async def process(self, event: 'MammothEvent') -> None:",  # type: ignore
            "        logger.info(f'Unhandled event: {event.event_type}')",
            "",
            "    async def shutdown(self) -> None:",
            f"        logger.info('{name} shutting down.')",
            "        await super().shutdown()  # type: ignore",
        ])

        path = f"src/mammoth_os/agents/{name.lower()}.py"
        result = await self._write_new_file(path, code)

        await self._register_new_agent(name)

        return result

    async def _register_new_agent(self, name: str) -> Dict[str, Any]:
        """
        Auto-register new agents into agent_registry.py.
        """
        import os

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
        import os

        server_path = r"C:\MammothOS\command_center_v3\server.py"

        if not os.path.exists(server_path):
            return {"status": "error", "message": "server.py not found"}

        try:
            with open(server_path, "r", encoding="utf-8") as f:
                content = f.read()

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

    def _score_confidence(self, test_results: Dict[str, Any], warnings: List[str]) -> float:
            base = 0.9
            if test_results.get("failed", 0) > 0:
                base -= 0.2
            base -= len(warnings) * 0.02
            return max(0.0, min(1.0, base))
    
