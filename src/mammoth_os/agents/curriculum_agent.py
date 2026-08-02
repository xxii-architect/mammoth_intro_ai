# mammoth_os/agents/curriculum_agent.py

from typing import Dict, Any, List, Optional
from .base_agent import BaseAgent
import uuid
import re
from datetime import datetime
import json
import os
import urllib.parse
import urllib.request


class CurriculumAgent(BaseAgent):
    """
    CurriculumAgent
    ----------------
    Generates structured curriculum tasks, lessons, and module plans.
    This is a lightweight version that avoids missing dependencies
    and ensures Mammoth OS can boot cleanly.
    """

    name = "CurriculumAgent"

    def __init__(self, router):
        super().__init__(router)
    
    def log(self, level: str, message: str) -> None:
        print(f"[{self.name}:{level}] {message}")

    def _extract_subject(self, prompt: str) -> str:
        # Heuristic subject extraction: look for 'for <subject>' or before ':' or use full prompt
        match = re.search(r"for\s+([\w\s\-]+?)(?:[\.,]|$)", prompt, re.IGNORECASE)
        if match:
            subject = match.group(1).strip()
        else:
            parts = prompt.split(":", 1)
            subject = parts[0].strip() if len(parts) > 1 else prompt.strip()
        return subject or "Untitled Subject"

    def _build_template_curriculum(self, subject: str, curriculum_id: str, now: str) -> Dict[str, Any]:
        # Generate 3 modules with simple lesson breakdown
        modules = []
        for m in range(1, 4):
            lessons = []
            for l in range(1, 4):
                lesson_id = f"{curriculum_id}-m{m}-l{l}"
                lessons.append({
                    "lesson_id": lesson_id,
                    "title": f"{subject} — Module {m} Lesson {l}",
                    "objectives": [f"Understand concept {m}.{l}", f"Practice problem {m}.{l}"],
                    "estimated_minutes": 15 + (m * 5) + (l * 2),
                })
            modules.append({
                "module_id": f"{curriculum_id}-m{m}",
                "title": f"Module {m}: {['Foundations','Core Skills','Application'][m-1]}",
                "lessons": lessons,
                "estimated_minutes": sum(l["estimated_minutes"] for l in lessons),
            })
        return {
            "curriculum_id": curriculum_id,
            "title": f"{subject} — Short Curriculum",
            "subject": subject,
            "generated_at": now,
            "modules": modules,
            "estimated_total_minutes": sum(m["estimated_minutes"] for m in modules),
        }

    def _load_from_mammoth_supabase(self, subject: str, curriculum_id: str, now: str) -> Optional[Dict[str, Any]]:
        """Load curriculum from mammoth.modules + mammoth.lessons if Supabase is configured.

        Returns None when Supabase is unavailable or no relevant records are found.
        """
        supabase_url = os.environ.get("SUPABASE_URL", "").strip()
        supabase_key = (
            os.environ.get("SUPABASE_ANON_KEY", "").strip()
            or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
            or os.environ.get("SUPABASE_KEY", "").strip()
        )
        if not supabase_url or not supabase_key:
            return None

        headers = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Accept": "application/json",
            "Accept-Profile": "mammoth",
        }

        modules_url = (
            f"{supabase_url.rstrip('/')}/rest/v1/modules"
            f"?select=id,title,description,order_index&order=order_index.asc"
        )
        lessons_url = (
            f"{supabase_url.rstrip('/')}/rest/v1/lessons"
            f"?select=id,module_id,title,content,order_index&order=order_index.asc"
        )

        try:
            with urllib.request.urlopen(
                urllib.request.Request(modules_url, headers=headers, method="GET"),
                timeout=8,
            ) as resp:
                module_rows = json.loads(resp.read().decode("utf-8"))
            with urllib.request.urlopen(
                urllib.request.Request(lessons_url, headers=headers, method="GET"),
                timeout=8,
            ) as resp:
                lesson_rows = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            self.log("WARN", f"Supabase curriculum lookup failed, using template fallback: {exc}")
            return None

        if not isinstance(module_rows, list) or not isinstance(lesson_rows, list):
            self.log("WARN", "Supabase curriculum response malformed, using template fallback")
            return None

        # Filter modules by subject relevance when possible, else keep all
        subject_terms = {t.lower() for t in re.findall(r"[a-zA-Z0-9]+", subject) if len(t) > 2}
        if subject_terms:
            filtered_modules = []
            for m in module_rows:
                text = f"{m.get('title','')} {m.get('description','')}".lower()
                if any(term in text for term in subject_terms):
                    filtered_modules.append(m)
        else:
            filtered_modules = module_rows
        if not filtered_modules:
            filtered_modules = module_rows
        if not filtered_modules:
            return None

        lessons_by_module: Dict[str, List[Dict[str, Any]]] = {}
        for lesson in lesson_rows:
            module_id = lesson.get("module_id")
            if module_id:
                lessons_by_module.setdefault(str(module_id), []).append(lesson)

        modules: List[Dict[str, Any]] = []
        for idx, module in enumerate(filtered_modules[:3], start=1):
            module_id = str(module.get("id") or f"{curriculum_id}-m{idx}")
            src_lessons = lessons_by_module.get(module_id, [])[:5]
            lessons: List[Dict[str, Any]] = []
            for l_idx, lesson in enumerate(src_lessons, start=1):
                content = (lesson.get("content") or "").strip()
                objectives = [f"Understand {lesson.get('title', f'lesson {l_idx}') }"]
                if content:
                    objectives.append("Apply lesson concepts in code")
                lessons.append({
                    "lesson_id": str(lesson.get("id") or f"{module_id}-l{l_idx}"),
                    "title": str(lesson.get("title") or f"Lesson {l_idx}"),
                    "objectives": objectives,
                    "estimated_minutes": 20 if content else 15,
                    "content": content,
                })
            if not lessons:
                continue
            modules.append({
                "module_id": module_id,
                "title": str(module.get("title") or f"Module {idx}"),
                "lessons": lessons,
                "estimated_minutes": sum(l["estimated_minutes"] for l in lessons),
            })

        if not modules:
            return None

        return {
            "curriculum_id": curriculum_id,
            "title": f"{subject} — Supabase Curriculum",
            "subject": subject,
            "generated_at": now,
            "source": "mammoth.supabase",
            "modules": modules,
            "estimated_total_minutes": sum(m["estimated_minutes"] for m in modules),
        }

    def run(self, prompt: str) -> Dict[str, Any]:
        """
        Main entry point for CurriculumAgent.
        Returns a structured curriculum object generated from a natural-language prompt.

        Lightweight generator: produces modules and lessons with simple heuristics so
        other agents (PlannerAgent, OrchestratorAgent) can consume structured output.
        """
        subject = self._extract_subject(prompt)

        curriculum_id = uuid.uuid4().hex
        now = datetime.utcnow().isoformat() + "Z"

        curriculum = self._load_from_mammoth_supabase(subject, curriculum_id, now)
        if curriculum is None:
            curriculum = self._build_template_curriculum(subject, curriculum_id, now)

        return {
            "status": "ok",
            "agent": self.name,
            "prompt": prompt,
            "curriculum": curriculum,
        }

    def execute_action(self, action_type: str, target: str, details: Dict[str, Any]):
        """
        Action handler for curriculum operations. Supports:
        - 'generate': details can include 'prompt' to create a curriculum
        - fallback: returns intent for manual handling
        """
        if action_type == "generate":
            gen_prompt = details.get("prompt") or target or ""
            return self.run(gen_prompt)

        return {
            "status": "intent",
            "agent": self.name,
            "action": action_type,
            "target": target,
            "details": details,
        }
