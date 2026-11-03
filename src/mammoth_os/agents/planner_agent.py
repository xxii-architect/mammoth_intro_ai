from .base_agent import BaseAgent
import json
import logging
from typing import Any

from mammoth_os.planning_quality import planning_agents, task_diagnostics
from mammoth_os.research_quality import strip_reasoning

logger = logging.getLogger(__name__)

PLANNER_SYSTEM = """You are MammothOS's execution planner. Break a goal into a precise task list.

Return JSON only — a list of tasks:
[{"task_id":"t1","agent":"<agent_slug>","title":"<task title>","input":{"goal":"<sub-goal>"},"depends_on":[],"estimated_minutes":<int>}]

Agent slugs (use ONLY these exact values): research, market_intel, coding, community_engine, field_ops, reasoning, executor, build, deploy, search, curriculum, orchestrator
Keep tasks focused, ordered, and DAG-valid (no circular depends_on).
NEVER use: tutor, brand_voice, reflection, mammoth_guide — these are not execution agents."""

class PlannerAgent(BaseAgent):# type: ignore
    """
    Converts high-level goals into structured execution plans represented
    as directed acyclic graphs (DAGs). Each node is a discrete task
    assigned to a specific agent. Plans are validated before execution.
    """

    name = "PlannerAgent"

    def __init__(self, router=None):
        super().__init__(router)

    def log(self, level: str, message: str) -> None:
        print(f"[PlannerAgent:{level}] {message}")
    @staticmethod
    def _run_async(coro):
        import asyncio
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)
        else:
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(asyncio.run, coro).result()

    @staticmethod
    def _valid_exec_tasks(tasks: list) -> bool:
        """Reject any list that doesn't carry the execution task schema.

        A valid execution task must have at minimum: task_id, agent, title,
        input, depends_on.  Curriculum-lesson payloads (which the LLM
        sometimes produces when context leaks) lack 'title' and carry
        lesson/module keys instead — those must be rejected so the prose
        fallback fires and returns well-formed tasks.
        """
        return not task_diagnostics(tasks)

    async def _llm_decompose(self, goal: str) -> dict:
        from mammoth_os.llm_client import get_llm_client

        allowed = planning_agents(goal)
        real_agents = ", ".join(sorted(allowed))
        template = (
            "Decompose the GOAL into only relevant tasks. Do not add business, publishing, "
            "maintenance, deployment or restore actions unless the goal actually requests them. "
            f"Use ONLY these agent slugs: {real_agents}. "
            "Each task requires task_id, agent, title, input (object), depends_on (earlier task IDs), "
            "estimated_minutes (positive integer). Output a complete JSON array, no prose. "
            "Lesson/module content is not an execution-task response.\n\nGOAL: " + goal
        )
        raw = await get_llm_client().generate(
            template,
            system_prompt=(
                "Output ONLY a JSON array of tasks. No prose. No explanation. "
                f"Valid agent slugs: {real_agents}. "
                "NEVER use tutor, brand_voice, reflection, or mammoth_guide."
            ),
            max_tokens=2000,
            temperature=0.1,
        )
        if not isinstance(raw, str) or raw.startswith("[LOCAL_ADAPTER]"):
            raise ValueError("Planner provider did not return structured task text.")
        clean, trace = strip_reasoning(raw)
        if clean.strip().startswith("```json") and clean.strip().endswith("```"):
            clean = clean.strip()[7:-3].strip()
        try:
            parsed = json.loads(clean)
        except json.JSONDecodeError as exc:
            raise ValueError("Planner returned incomplete or malformed task JSON.") from exc
        diagnostics = task_diagnostics(parsed, allowed=frozenset(allowed))
        if diagnostics:
            raise ValueError("Planner task contract rejected: " + "; ".join(diagnostics))
        return {"tasks": parsed, "reasoning_trace": trace}



    async def emit_event(self, event_type: str, payload) -> None:
        self.log("INFO", f"Emitting {event_type}")

    @staticmethod
    def _coerce_duration_minutes(value, *, fallback: int = 20) -> int:
        if isinstance(value, bool):
            return fallback
        if isinstance(value, (int, float)):
            value = int(value)
            return value if value > 0 else fallback
        if isinstance(value, str):
            try:
                parsed = int(float(value))
                return parsed if parsed > 0 else fallback
            except ValueError:
                return fallback
        return fallback

    def _duration_from_lesson(self, lesson: dict, *, fallback: int = 20) -> int:
        minutes = self._coerce_duration_minutes(lesson.get("estimated_minutes"), fallback=fallback)
        content = str(lesson.get("content") or "").strip()
        if content:
            minutes = max(minutes, min(180, max(10, (len(content) // 70) + 10)))
        return int(minutes)

    @staticmethod
    def _normalize_curriculum(constraints: dict | None) -> dict | None:
        if not isinstance(constraints, dict):
            return None
        curriculum = constraints.get("curriculum")
        if isinstance(curriculum, dict):
            if isinstance(curriculum.get("curriculum"), dict):
                return curriculum.get("curriculum")
            if isinstance(curriculum.get("modules"), list):
                return curriculum
        return None

    async def create_plan(self, goal: str, constraints: dict = None) -> dict:# type: ignore
        """
        Generate an execution plan for a given goal.

        If no curriculum is provided in constraints, attempt to generate one
        via CurriculumAgent (safe, best-effort). Then decompose into tasks.

        Returns:
            {
                "plan_id": str,
                "goal": str,
                "tasks": list[dict],  # Each: {task_id, agent, input, depends_on}
                "estimated_duration_sec": int,
            }
        """
        import uuid
        if constraints is None:
            constraints = {}
        constraints = dict(constraints)

        curriculum = self._normalize_curriculum(constraints)
        if curriculum is None and constraints.get("use_curriculum") is True:
            try:
                from mammoth_os.agent_registry import load_agent
                curriculum_agent = load_agent("curriculum", None)
                import asyncio
                cur_res = await asyncio.to_thread(curriculum_agent.run, goal)
                if not isinstance(cur_res, dict) or cur_res.get("status") != "ok":
                    raise ValueError("Requested curriculum generation failed.")
                constraints["curriculum"] = cur_res.get("curriculum")
                if self._normalize_curriculum(constraints) is None:
                    raise ValueError("Requested curriculum has no valid module list.")
            except (ValueError, TypeError, RuntimeError, OSError) as exc:
                logger.warning("Requested curriculum preparation failed: %s", type(exc).__name__)
                return {"status": "failed", "plan_id": str(uuid.uuid4()), "goal": goal, "tasks": [],
                        "estimated_duration_sec": 0, "quality_flags": ["planning_failed"],
                        "quality": {"ready": False, "status": "failed"},
                        "diagnostics": ["Requested curriculum could not be prepared. Retry explicitly."]}

        curriculum = self._normalize_curriculum(constraints)
        reasoning_trace = ""
        try:
            decomposition = await self._decompose_to_tasks(goal, {**constraints, "curriculum": curriculum} if curriculum else constraints)
            tasks = decomposition.get("tasks") if isinstance(decomposition, dict) else decomposition
            reasoning_trace = decomposition.get("reasoning_trace", "") if isinstance(decomposition, dict) else ""
            diagnostics = task_diagnostics(tasks, allowed=planning_agents(goal), curriculum=bool(curriculum))
            if diagnostics or not isinstance(tasks, list):
                raise ValueError("; ".join(diagnostics))
        except (ValueError, TypeError, RuntimeError, OSError) as exc:
            logger.warning("Planner generation rejected: %s", type(exc).__name__)
            return {"status": "failed", "plan_id": str(uuid.uuid4()), "goal": goal, "tasks": [],
                    "estimated_duration_sec": 0, "quality_flags": ["planning_failed"],
                    "quality": {"ready": False, "status": "failed"},
                    "diagnostics": ["No valid task graph was produced. Retry explicitly with a concrete goal."]}
        estimated_minutes = 0
        for task in tasks:
            value = self._coerce_duration_minutes(task.get("estimated_minutes"), fallback=max(15, len(goal.split()) // 10 + 10))
            task["estimated_minutes"] = value
            estimated_minutes += value
        if estimated_minutes <= 0:
            estimated_minutes = max(len(tasks) * 10, 30)

        return {
            "status": "planned",
            "plan_id": str(uuid.uuid4()),
            "goal": goal,
            "tasks": tasks,
            "estimated_duration_sec": estimated_minutes * 60,
            "quality_flags": ["structured_plan", "dag_validated", "duration_normalized"] if tasks else ["structured_plan", "duration_normalized"],
            "reasoning_trace": reasoning_trace,
            "quality": {"ready": True, "status": "structured", "independent_verification": False},
        }

    async def _decompose_to_tasks(self, goal: str, constraints: dict) -> list[dict] | dict:
        """Decompose a goal into an ordered task list.

        If `constraints` contains a 'curriculum' dict (as produced by
        CurriculumAgent), convert modules and lessons into discrete tasks.
        Otherwise, require a complete, validated model-generated task graph.
        """
        curriculum = self._normalize_curriculum(constraints)

        tasks: list[dict] = []
        if curriculum and isinstance(curriculum, dict):
            prev_task_id = None
            for module in curriculum.get("modules", []):
                if not isinstance(module, dict) or not isinstance(module.get("lessons"), list):
                    raise ValueError("Curriculum modules require a lesson list.")
                module_id = module.get("module_id")
                module_title = module.get("title") or ""
                for lesson in module.get("lessons", []):
                    if not isinstance(lesson, dict) or not lesson.get("lesson_id"):
                        raise ValueError("Curriculum lessons require their actual saved identity.")
                    task_id = lesson["lesson_id"]
                    estimated_minutes = self._duration_from_lesson(lesson, fallback=20)
                    task = {
                        "task_id": task_id,
                        "agent": "tutor",
                        "title": str(lesson.get("title") or lesson.get("lesson_title") or "").strip(),
                        "input": {"module_id": module_id, "module_title": module_title, "lesson": lesson},
                        "depends_on": [prev_task_id] if prev_task_id else [],
                        "estimated_minutes": int(estimated_minutes),
                    }
                    tasks.append(task)
                    prev_task_id = task_id
            if tasks:
                return tasks
            raise ValueError("Provided curriculum contains no lessons to plan.")

        # LLM DAG decomposition
        return await self._llm_decompose(goal)

    async def validate_plan(self, plan: dict) -> tuple[bool, list[str]]:
        """Check the plan DAG for cycles and ensure agent availability for tasks.

        Returns (is_valid: bool, diagnostics: list[str]). Diagnostics contains
        human-readable reasons when validation fails (missing refs, cycles, agent issues).
        """
        from mammoth_os.agent_registry import agent_registry, AgentStatus

        diagnostics: list[str] = []
        tasks = plan.get("tasks", [])
        diagnostics = task_diagnostics(tasks, allowed=planning_agents(str(plan.get("goal") or "")), curriculum=any(
            isinstance(task, dict) and task.get("agent") == "tutor" and isinstance(task.get("input"), dict)
            and isinstance(task["input"].get("lesson"), dict) for task in tasks
        ) if isinstance(tasks, list) else False)
        if diagnostics:
            return False, diagnostics
        task_map = {t["task_id"]: t for t in tasks}

        # Check for missing dependency references
        for t in tasks:
            for dep in t.get("depends_on", []) or []:
                if dep is None:
                    continue
                if dep not in task_map:
                    diagnostics.append(
                        f"Missing dependency reference: task '{t['task_id']}' depends on unknown task '{dep}'"
                    )

        # Detect cycles using DFS
        visiting = set()
        visited = set()
        cycle_found = False

        def has_cycle(node_id, path=None):
            nonlocal cycle_found
            if path is None:
                path = []
            if node_id in visited:
                return False
            if node_id in visiting:
                # Found a cycle; capture the cycle path
                cycle_path = " -> ".join(path + [node_id])
                diagnostics.append(f"Cycle detected in tasks: {cycle_path}")
                cycle_found = True
                return True
            visiting.add(node_id)
            node = task_map.get(node_id)
            if not node:
                visiting.remove(node_id)
                visited.add(node_id)
                return False
            for dep in node.get("depends_on", []) or []:
                if dep is None:
                    continue
                if has_cycle(dep, path + [node_id]):
                    return True
            visiting.remove(node_id)
            visited.add(node_id)
            return False

        for tid in task_map:
            if has_cycle(tid):
                # continue checking to collect diagnostics
                pass

        # Ensure agents are available (best-effort via AgentRegistry)
        # If an agent referenced by a task is not registered or in error, add diagnostic
        for t in tasks:
            agent_name = t.get("agent")
            if not agent_name:
                diagnostics.append(f"Task '{t.get('task_id')}' has no agent specified")
                continue
            manifest = await agent_registry.get_agent(agent_name)
            if manifest is None:
                diagnostics.append(f"Unknown agent referenced by task '{t.get('task_id')}': '{agent_name}'")
                continue
            if manifest.status in (AgentStatus.ERROR, AgentStatus.SHUTDOWN):
                diagnostics.append(
                    f"Agent '{agent_name}' referenced by task '{t.get('task_id')}' is unavailable (status={manifest.status})"
                )

        is_valid = len(diagnostics) == 0 and not cycle_found
        return is_valid, diagnostics

    async def run(self, payload) -> dict:
        if isinstance(payload, dict):
            goal = str(payload.get("goal") or payload.get("prompt") or "").strip()
            constraints = payload.get("constraints") or {}
        else:
            goal = str(payload or "").strip()
            constraints = {}
        if not goal:
            return {"status": "needs_context", "agent": "PlannerAgent", "summary": "Provide a goal to plan."}
        plan = await self.create_plan(goal, constraints)
        is_valid, diagnostics = await self.validate_plan(plan)
        return {
            "status": "ok" if is_valid else "failed",
            "agent": "PlannerAgent",
            "plan": plan,
            "valid": is_valid,
            "diagnostics": diagnostics,
            "summary": f"Plan created with {len(plan.get('tasks', []))} task(s). Valid={is_valid}.",
            "quality_flags": ["structured_plan", "dag_validated"] if is_valid else ["planning_failed"],
        }

    async def process(self, event: Any) -> None:
        if event.event_type == "PLAN_REQUEST":
            plan = await self.create_plan(event.payload["goal"], event.payload.get("constraints"))
            await self.emit_event("PLAN_READY" if plan.get("status") == "planned" else "PLAN_FAILED", plan)

    async def shutdown(self) -> None:
        self.log("INFO", "PlannerAgent shutting down.")
