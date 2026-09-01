# mammoth_os/agents/curriculum_agent.py

from typing import Dict, Any, List, Optional
from .base_agent import BaseAgent
import uuid
import re
from datetime import datetime, timezone
import json
import os
import urllib.parse
import urllib.request
import asyncio
import concurrent.futures
from mammoth_os.rag_retrieval import get_retriever
from mammoth_os.llm_client import get_llm_client


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

    def _run_async(self, coro):
        """Run async work from sync code, including inside active event loops."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(asyncio.run, coro)
            return future.result()

    def _extract_subject(self, prompt: str) -> str:
        lesson_track_match = re.search(
            r"lesson track for\s+(.+?)(?:\s+with\s+|\s+emphasis\s+on:|[.;]|$)",
            prompt,
            re.IGNORECASE,
        )
        if lesson_track_match:
            subject = lesson_track_match.group(1).strip()
            if subject:
                return subject
        # Heuristic subject extraction: look for 'for <subject>' or before ':' or use full prompt
        match = re.search(r"for\s+([\w\s\-]+?)(?:[\.,]|$)", prompt, re.IGNORECASE)
        if match:
            subject = match.group(1).strip()
        else:
            parts = prompt.split(":", 1)
            subject = parts[0].strip() if len(parts) > 1 else prompt.strip()
        return subject or "Untitled Subject"

    def _build_template_curriculum(self, subject: str, curriculum_id: str, now: str) -> Dict[str, Any]:
        # Generate 3 modules with subject-aware beginner lessons when richer data is unavailable.
        phase_names = ["Foundations", "Core Skills", "Application"]
        modules = []
        for m in range(1, 4):
            lessons = []
            for l in range(1, 4):
                lesson_id = f"{curriculum_id}-m{m}-l{l}"
                phase = phase_names[m - 1]
                practical_focus = [
                    f"Identify the key ideas in {subject} for {phase.lower()} work",
                    f"Apply {subject} in a practical beginner-friendly scenario",
                ]
                lessons.append({
                    "lesson_id": lesson_id,
                    "title": f"{subject} — {phase} Lesson {l}",
                    "objectives": practical_focus,
                    "estimated_minutes": 15 + (m * 5) + (l * 2),
                    "source": "template",
                    "exercise_generation_mode": "llm_preferred",
                })
            modules.append({
                "module_id": f"{curriculum_id}-m{m}",
                "title": f"Module {m}: {phase_names[m - 1]}",
                "lessons": lessons,
                "estimated_minutes": sum(l["estimated_minutes"] for l in lessons),
            })
        return {
            "curriculum_id": curriculum_id,
            "title": f"{subject} — Short Curriculum",
            "subject": subject,
            "generated_at": now,
            "source": "template",
            "modules": modules,
            "estimated_total_minutes": sum(m["estimated_minutes"] for m in modules),
        }

    def _subject_terms(self, subject: str) -> List[str]:
        stopwords = {
            "and", "the", "for", "with", "into", "from", "your", "their", "this", "that",
            "basics", "basic", "beginner", "beginners", "fundamentals", "foundation", "foundations",
            "practical", "friendly", "real", "world", "introduction", "intro",
        }
        seen: List[str] = []
        for token in re.findall(r"[a-zA-Z0-9]+", subject.lower()):
            if len(token) <= 2:
                continue
            if token in stopwords:
                continue
            if token not in seen:
                seen.append(token)
        return seen

    def _text_relevance_score(self, text: str, subject_terms: List[str]) -> int:
        lowered = str(text or "").lower()
        return sum(1 for term in subject_terms if term in lowered)

    def _is_lesson_subject_relevant(self, lesson: Dict[str, Any], subject: str) -> bool:
        subject_terms = self._subject_terms(subject)
        if not subject_terms:
            return True
        lesson_blob = " ".join(
            [
                str(lesson.get("title") or ""),
                str(lesson.get("summary") or ""),
                str(lesson.get("content") or ""),
                " ".join(str(item) for item in (lesson.get("objectives") or [])),
            ]
        )
        return self._text_relevance_score(lesson_blob, subject_terms) > 0

    def _extract_json_object(self, raw_text: str) -> Dict[str, Any]:
        fenced = re.findall(r"```(?:json)?\s*([\s\S]*?)```", raw_text)
        candidates = fenced + [raw_text]
        for candidate in candidates:
            snippet = candidate.strip()
            if not snippet:
                continue
            try:
                parsed = json.loads(snippet)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass
            match = re.search(r"\{[\s\S]*\}", snippet)
            if not match:
                continue
            try:
                parsed = json.loads(match.group(0))
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                continue
        raise ValueError("No valid JSON object found in LLM response")

    def _build_structured_lesson_fallback(
        self,
        lesson: Dict[str, Any],
        *,
        subject: str,
        module_title: str,
    ) -> Dict[str, Any]:
        subject_relevant = self._is_lesson_subject_relevant(lesson, subject)
        title_seed = lesson.get("title") if subject_relevant else ""
        title = str(title_seed or subject or "Lesson").strip()
        objectives = [str(item).strip() for item in (lesson.get("objectives") or []) if str(item).strip()] if subject_relevant else []
        if not objectives:
            objectives = [
                f"Understand the core ideas behind {subject}.",
                f"Apply {subject} in a realistic beginner-friendly situation.",
            ]
        summary = str(lesson.get("summary") or "").strip() if subject_relevant else ""
        if not summary:
            summary = (
                f"{title} gives a beginner-friendly introduction to {subject}. "
                f"It focuses on practical understanding, safe judgment, and the first habits that matter in {module_title}."
            )
        teaching_points = [str(item).strip() for item in (lesson.get("teaching_points") or []) if str(item).strip()]
        if not teaching_points:
            teaching_points = [
                f"What {subject} is and where it fits in real-world practice.",
                f"The first decisions, checks, or principles a beginner should pay attention to.",
                f"How to apply {subject} carefully in a simple scenario without overcomplicating it.",
            ]
        examples = [str(item).strip() for item in (lesson.get("examples") or []) if str(item).strip()]
        if not examples:
            examples = [
                f"Example 1: Describe how a beginner would recognize when {subject} matters in a real situation.",
                f"Example 2: Walk through the first safe, practical step someone would take while learning {subject}.",
            ]
        content = str(lesson.get("content") or "").strip() if subject_relevant else ""
        if not content:
            content = "\n\n".join(
                [
                    summary,
                    f"In this lesson, focus on three ideas: {teaching_points[0]} {teaching_points[1]} {teaching_points[2]}",
                    f"Use the examples as anchors: {examples[0]} {examples[1]}",
                ]
            )
        estimated_minutes = lesson.get("estimated_minutes")
        if not isinstance(estimated_minutes, int) or estimated_minutes <= 0:
            estimated_minutes = 20
        return {
            **lesson,
            "title": title,
            "objectives": objectives[:4],
            "summary": summary,
            "content": content,
            "teaching_points": teaching_points[:5],
            "examples": examples[:3],
            "estimated_minutes": estimated_minutes,
            "source": str(lesson.get("source") or "template").strip() or "template",
            "exercise_generation_mode": "llm_preferred",
        }

    def _lesson_needs_authoring(self, lesson: Dict[str, Any], subject: str) -> bool:
        content = str(lesson.get("content") or "").strip()
        teaching_points = [str(item).strip() for item in (lesson.get("teaching_points") or []) if str(item).strip()]
        examples = [str(item).strip() for item in (lesson.get("examples") or []) if str(item).strip()]
        if str(lesson.get("source") or "").strip().lower() == "template":
            return True
        if len(content) < 220:
            return True
        if len(teaching_points) < 3 or len(examples) < 1:
            return True
        subject_terms = self._subject_terms(subject)
        if subject_terms and self._text_relevance_score(f"{lesson.get('title', '')} {content}", subject_terms) == 0:
            return True
        return False

    async def _author_lesson_with_llm(
        self,
        lesson: Dict[str, Any],
        *,
        subject: str,
        module_title: str,
        curriculum_title: str,
    ) -> Dict[str, Any]:
        fallback_lesson = self._build_structured_lesson_fallback(lesson, subject=subject, module_title=module_title)
        title = fallback_lesson["title"]
        objectives = fallback_lesson["objectives"]
        existing_content = str(lesson.get("content") or "").strip()
        chunks = [str(item).strip() for item in (lesson.get("_chunks") or []) if str(item).strip()]
        grounding_block = "\n".join(f"- {item}" for item in chunks[:3]) or "- No retrieved source chunks available."
        client = get_llm_client()
        prompt = (
            "You are ATLAS, a curriculum author inside MammothOS.\n"
            "Generate a grounded, beginner-friendly lesson in STRICT JSON only.\n"
            "Schema:\n"
            "{\n"
            '  "title": "string",\n'
            '  "objectives": ["string"],\n'
            '  "summary": "string",\n'
            '  "content": "string",\n'
            '  "teaching_points": ["string"],\n'
            '  "examples": ["string"],\n'
            '  "estimated_minutes": 20\n'
            "}\n\n"
            f"Curriculum title: {curriculum_title}\n"
            f"Module title: {module_title}\n"
            f"Lesson title seed: {title}\n"
            f"Subject: {subject}\n"
            f"Objectives seed: {json.dumps(objectives)}\n"
            f"Existing content seed: {existing_content or fallback_lesson['summary']}\n"
            "Retrieved grounding chunks (use when relevant, but do not fabricate citations):\n"
            f"{grounding_block}\n\n"
            "Requirements:\n"
            "- Keep the lesson truly about the subject, not about programming unless the subject itself is programming.\n"
            "- Make the tone practical, clear, and beginner-friendly.\n"
            "- Include concrete real-world examples or first actions.\n"
            "- Stay safety-first and educational for medical, emergency, legal, or field topics.\n"
            "- Return only valid JSON."
        )
        raw = await client.generate(prompt, temperature=0.3, max_tokens=1600)
        payload = self._extract_json_object(raw)
        authored = self._build_structured_lesson_fallback(
            {
                **fallback_lesson,
                "title": payload.get("title") or fallback_lesson["title"],
                "objectives": payload.get("objectives") or fallback_lesson["objectives"],
                "summary": payload.get("summary") or fallback_lesson["summary"],
                "content": payload.get("content") or fallback_lesson["content"],
                "teaching_points": payload.get("teaching_points") or fallback_lesson["teaching_points"],
                "examples": payload.get("examples") or fallback_lesson["examples"],
                "estimated_minutes": payload.get("estimated_minutes") or fallback_lesson["estimated_minutes"],
            },
            subject=subject,
            module_title=module_title,
        )
        authored["source"] = "llm_generated" if str(lesson.get("source") or "").strip().lower() == "template" else "llm_enriched"
        return authored

    def _enrich_curriculum_lessons(self, curriculum: Dict[str, Any], subject: str) -> Dict[str, Any]:
        modules = curriculum.get("modules")
        if not isinstance(modules, list):
            return curriculum
        warnings: List[str] = []
        for module in modules:
            module_title = str(module.get("title") or "Module").strip()
            lessons = module.get("lessons")
            if not isinstance(lessons, list):
                continue
            for index, lesson in enumerate(lessons):
                if not isinstance(lesson, dict):
                    continue
                if not self._lesson_needs_authoring(lesson, subject):
                    normalized = self._build_structured_lesson_fallback(lesson, subject=subject, module_title=module_title)
                    normalized["source"] = str(lesson.get("source") or curriculum.get("source") or "mammoth.supabase").strip() or "mammoth.supabase"
                    lessons[index] = normalized
                    continue
                try:
                    lessons[index] = self._run_async(
                        self._author_lesson_with_llm(
                            lesson,
                            subject=subject,
                            module_title=module_title,
                            curriculum_title=str(curriculum.get("title") or subject).strip(),
                        )
                    )
                except Exception as exc:
                    warnings.append(f"{lesson.get('lesson_id') or lesson.get('title') or 'lesson'}: {exc}")
                    fallback = self._build_structured_lesson_fallback(lesson, subject=subject, module_title=module_title)
                    fallback["source"] = "template"
                    fallback["generation_warning"] = str(exc)
                    lessons[index] = fallback
        if warnings:
            curriculum["generation_warnings"] = warnings
        if str(curriculum.get("source") or "").strip().lower() == "template":
            curriculum["source"] = "llm_or_template_fallback"
        return curriculum

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

        # Only use persisted curriculum when it actually matches the requested subject.
        subject_terms = self._subject_terms(subject)
        filtered_modules = []
        for m in module_rows:
            text = f"{m.get('title','')} {m.get('description','')}"
            if self._text_relevance_score(text, subject_terms) > 0:
                filtered_modules.append(m)
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
                    "source": "mammoth.supabase",
                    "exercise_generation_mode": "llm_preferred",
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

    async def _retrieve_lesson_chunks(self, lesson: Dict[str, Any]) -> List[str]:
        """Retrieve relevant lesson chunks for tutor context injection."""
        lesson_id = lesson.get("lesson_id", "")
        content = lesson.get("content", "")
        title = lesson.get("title", "")
        
        if not content or not lesson_id:
            return []

        try:
            retriever = get_retriever()
            # Retrieve top 3 chunks from lesson content
            chunks = await retriever.retrieve_for_lesson(
                lesson_id=lesson_id,
                content=content,
                query=title  # Use lesson title as context query
            )
            return chunks
        except Exception as e:
            self.log("WARN", f"Chunk retrieval failed for {lesson_id}: {e}")
            return []

    def _inject_chunks_into_lessons(self, curriculum: Dict[str, Any]) -> Dict[str, Any]:
        """Inject retrieved chunks into lesson metadata for tutor context."""
        if not curriculum or "modules" not in curriculum:
            return curriculum

        for module in curriculum.get("modules", []):
            for lesson in module.get("lessons", []):
                # Store chunks for later retrieval by tutor
                lesson["_chunks"] = self._run_async(self._retrieve_lesson_chunks(lesson))
        
        return curriculum


    def run(self, prompt: str) -> Dict[str, Any]:
        """
        Main entry point for CurriculumAgent.
        Returns a structured curriculum object generated from a natural-language prompt.

        Lightweight generator: produces modules and lessons with simple heuristics so
        other agents (PlannerAgent, OrchestratorAgent) can consume structured output.
        """
        subject = self._extract_subject(prompt)

        curriculum_id = uuid.uuid4().hex
        now = datetime.now(timezone.utc).isoformat()

        curriculum = self._load_from_mammoth_supabase(subject, curriculum_id, now)
        if curriculum is None:
            curriculum = self._build_template_curriculum(subject, curriculum_id, now)

        # Inject RAG-retrieved lesson chunks for tutor context
        curriculum = self._inject_chunks_into_lessons(curriculum)
        curriculum = self._enrich_curriculum_lessons(curriculum, subject)

        return {
            "status": "ok",
            "agent": self.name,
            "prompt": prompt,
            "summary": f"{curriculum.get('title', subject)} — {len(curriculum.get('modules', []))} modules, {curriculum.get('estimated_total_minutes', 0)} min estimated",
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

    def ground_lesson_in_rag(self, lesson_data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """
        Enrich a lesson with personalised difficulty adjustments and topic highlights
        drawn from the user's prior RAG context.

        Returns the lesson_data dict with an added ``rag_enrichment`` key.
        """
        try:
            from mammoth_os.rag_context_store import get_rag_context_store
            store = get_rag_context_store()
            prior = store.retrieve(user_id, limit=20)
        except Exception:
            prior = []

        if not prior:
            return {**lesson_data, "rag_enrichment": {"adjusted": False, "reason": "no_prior_context"}}

        # Collect signals from prior entries
        struggle_topics: List[str] = []
        mastered_topics: List[str] = []
        seen_difficulties: List[str] = []
        for entry in prior:
            content = entry.get("content", {})
            if isinstance(content, dict):
                struggle_topics.extend(content.get("struggle_indicators", []))
                mastered_topics.extend(content.get("mastery_signals", []))
                if content.get("difficulty"):
                    seen_difficulties.append(str(content["difficulty"]))

        # Suggest difficulty adjustment
        lesson_difficulty = lesson_data.get("difficulty", "intermediate")
        suggested_difficulty = lesson_difficulty
        if struggle_topics:
            difficulty_map = {"beginner": "beginner", "intermediate": "beginner", "advanced": "intermediate"}
            suggested_difficulty = difficulty_map.get(lesson_difficulty, lesson_difficulty)
        elif mastered_topics:
            difficulty_map = {"beginner": "intermediate", "intermediate": "advanced", "advanced": "advanced"}
            suggested_difficulty = difficulty_map.get(lesson_difficulty, lesson_difficulty)

        # Highlight topics the user has struggled with
        lesson_topics = lesson_data.get("topics", [])
        highlighted = [t for t in lesson_topics if any(s.lower() in t.lower() for s in struggle_topics)]

        enrichment: Dict[str, Any] = {
            "adjusted": True,
            "suggested_difficulty": suggested_difficulty,
            "prior_struggle_topics": struggle_topics[:5],
            "prior_mastery_topics": mastered_topics[:5],
            "highlighted_topics": highlighted,
            "prior_context_entries": len(prior),
        }
        return {**lesson_data, "difficulty": suggested_difficulty, "rag_enrichment": enrichment}

