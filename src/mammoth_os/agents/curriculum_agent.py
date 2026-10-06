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
from .curriculum_validation_v2 import validate_curriculum
from mammoth_os.tutor_delivery import curriculum_readiness
from mammoth_os.research_quality import strip_reasoning, trim_to_last_sentence, dedupe_items
from mammoth_os.curriculum_sequence import remove_forward_promises


class LessonAuthoringError(ValueError):
    def __init__(self, code: str, issues: List[str]):
        self.code = code
        self.issues = issues
        super().__init__("; ".join(issues))


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

    def _extract_subject(self, prompt) -> str:
        import json as _json
        # ── normalize dict / JSON-string payloads ──────────────────────────────
        if isinstance(prompt, dict):
            return self._extract_subject(str(
                prompt.get("topic") or prompt.get("subject") or
                prompt.get("prompt") or prompt.get("task") or "Untitled Subject"
            ).strip())
        if isinstance(prompt, str):
            s = prompt.strip()
            if s.startswith("{"):
                try:
                    d = _json.loads(s)
                    if isinstance(d, dict):
                        extracted = str(
                            d.get("topic") or d.get("subject") or
                            d.get("prompt") or d.get("task") or ""
                        ).strip()
                        if extracted:
                            return self._extract_subject(extracted)
                except Exception:
                    pass
        # ── original heuristic extraction (unchanged) ──────────────────────────
        prompt = str(prompt or "").strip()
        prompt = re.sub(r"^(?:please\s+)?(?:generate|create|build|design|make)\s+(?:me\s+)?(?:a\s+|an\s+)?(?:curriculum|course|lesson plan)\s+(?:for|on|about)\s+", "", prompt, flags=re.IGNORECASE)
        prompt = re.split(r"\s+(?:for\s+(?:a|an)\s+(?:beginner|intermediate|advanced|expert)|with\s+(?:a\s+)?(?:thorough|detailed)\s+introduction)", prompt, maxsplit=1, flags=re.IGNORECASE)[0]
        prompt = re.sub(r"\s+please[!.]*$", "", prompt, flags=re.IGNORECASE).strip(" !.")
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
        lesson_roles = [
            ["Orientation and vocabulary", "Core ideas explained", "Guided first application"],
            ["Comparing methods", "Interpreting evidence", "Common mistakes and correction"],
            ["Integrated scenario", "Independent practice", "Review and transfer"],
        ]
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
                    "title": f"{subject} — {lesson_roles[m - 1][l - 1]}",
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
        if len(content.split()) < 180 or content.endswith(("...", "\u2026")):
            return True
        if len(teaching_points) < 3 or len(examples) < 2:
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
        learner_context: Optional[Dict[str, Any]] = None,
        course_sequence: Optional[List[Dict[str, Any]]] = None,
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
            "Generate a complete, subject-specific teaching lesson in STRICT JSON only.\n"
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
            f"Learner profile: {json.dumps(learner_context or {}, default=str)}\n"
            f"Actual ordered course sequence: {json.dumps(course_sequence or [], default=str)}\n"
            f"Current lesson ID: {lesson.get('lesson_id')}\n"
            f"Objectives seed: {json.dumps(objectives)}\n"
            f"Existing content seed: {existing_content or fallback_lesson['summary']}\n"
            "Retrieved grounding chunks (use when relevant, but do not fabricate citations):\n"
            f"{grounding_block}\n\n"
            "Requirements:\n"
            "- Keep the lesson truly about the subject, not about programming unless the subject itself is programming.\n"
            "- Use the learner's recommended_difficulty (beginner by default), goals, pacing, and preferred examples.\n"
            "- For beginners assume no prior subject knowledge: define vocabulary before using it, explain why each step works, and teach before asking for practice.\n"
            "- For intermediate/advanced/expert learners state prerequisites and explain tradeoffs, limitations, and evidence. Expert study is not certification.\n"
            "- Write 350-600 words of complete teaching content with headings: Introduction, Key concepts, Worked examples, Guided practice, and Recap and next step.\n"
            "- Include at least three specific teaching points and two worked examples with steps and explanations, not prompts to invent examples.\n"
            "- Each lesson must teach a distinct subtopic appropriate to its module and lesson position, not repeat the same generic overview.\n"
            "- Follow the actual course sequence. Use only earlier lessons as prerequisites, briefly connect prior learning, and keep this lesson's objectives and subtopic.\n"
            "- Keep the exact lesson title seed and the planned objectives in the output; do not rename the lesson or broaden it to cover the whole course.\n"
            "- Do not promise what the next lesson covers in teaching text; the application adds the actual next lesson from the course manifest.\n"
            "- Label invented numerical studies, participants, percentages, or data as 'Hypothetical example' in the SAME paragraph. Never describe them as real research.\n"
            "- For factual studies or quantitative research claims, cite an exact supplied grounding chunk. If none exists, use an explicitly hypothetical exercise or omit the claim.\n"
            "- Explain limits and uncertainties. Nutrition and medical material is general education, not individualized treatment, diagnosis, or prescriptions.\n"
            "- Stay safety-first and educational for medical, emergency, legal, or field topics.\n"
            "- Estimate total minutes for reading, worked examples, and guided practice; use an integer between 5 and 480.\n"
            "- Return only valid JSON."
        )
        for attempt in range(2):
            raw = await client.generate(prompt, temperature=0.3, max_tokens=3200, response_format={"type": "json_object"})
            try:
                authored = self._parse_authored_lesson(raw, lesson, subject=subject, learner_context=learner_context)
                if course_sequence:
                    if authored["title"] != lesson["title"]:
                        raise LessonAuthoringError("sequence_mismatch", ["Keep the exact planned lesson title."])
                    authored["content"], removed = remove_forward_promises(authored["content"])
                    authored["sequence_review"] = {"removed_forward_promises": removed, "navigation_source": "course_manifest"}
                    checked = curriculum_readiness({"subject": subject, "modules": [{"lessons": [authored]}]})
                    if not checked["ready"]:
                        raise LessonAuthoringError("teaching_checks_failed", ["Keep substantive teaching content after removing forward lesson promises."])
                    position = next(index for index, row in enumerate(course_sequence) if row["lesson_id"] == lesson["lesson_id"])
                    following = course_sequence[position + 1] if position + 1 < len(course_sequence) else None
                    authored["course_position"] = position + 1
                    authored["next_lesson_id"] = following["lesson_id"] if following else None
                    authored["next_lesson_title"] = following["title"] if following else None
                    authored["objectives"] = lesson["objectives"]
                    authored["subtopic"] = lesson.get("subtopic", "")
                    authored["prerequisites"] = lesson.get("prerequisites", [])
                    authored["content"] += f"\n\nNext lesson: {following['title']}." if following else "\n\nCourse complete: review the objectives and use the final practice to check your understanding."
                authored["authoring_attempts"] = attempt + 1
                return authored
            except LessonAuthoringError as exc:
                if attempt == 1:
                    raise
                self.log("WARN", f"Retrying lesson {lesson.get('lesson_id')} once after {exc.code}: {exc}")
                prompt += (
                    "\nThe previous attempt failed these checks: " + json.dumps(exc.issues) +
                    "\nReturn a corrected COMPLETE lesson using the exact top-level schema above. "
                    "Do not nest the lesson in a wrapper. content must be one JSON string containing the teaching text, "
                    "not an object or array. Retain every required field and meet all content and example requirements."
                )

    def _parse_authored_lesson(
        self, raw: str, lesson: Dict[str, Any], *, subject: str,
        learner_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        clean, trace = strip_reasoning(raw)
        try:
            payload = self._extract_json_object(clean)
        except ValueError as exc:
            raise LessonAuthoringError("invalid_json", ["The model did not return a complete valid lesson JSON object."]) from exc
        for key in ("title", "summary", "content"):
            if not isinstance(payload.get(key), str) or not payload[key].strip():
                raise LessonAuthoringError("invalid_schema", [f"Authored lesson needs non-empty {key} as a top-level string."])
        for key in ("objectives", "teaching_points", "examples"):
            if not isinstance(payload.get(key), list) or not all(isinstance(item, str) for item in payload[key]):
                raise LessonAuthoringError("invalid_schema", [f"Authored lesson has invalid {key}."])
            payload[key] = dedupe_items(payload[key])
        content, content_trace = strip_reasoning(payload["content"])
        payload["content"], _ = trim_to_last_sentence(content)
        teaching_texts = [payload["content"], *payload["examples"], *payload["teaching_points"]]
        for paragraph in (paragraph for text in teaching_texts for paragraph in re.split(r"\n\s*\n", text)):
            if re.search(r"\b(?:study|trial|participants|researchers)\b", paragraph, re.I) and re.search(r"\d+(?:\.\d+)?\s*(?:%|percent|participants|people)", paragraph, re.I):
                if not re.search(r"\b(?:hypothetical|illustrative|fictional|simulated)\b", paragraph, re.I):
                    chunks = [str(chunk) for chunk in lesson.get("_chunks", [])]
                    if not any(paragraph.strip() in chunk for chunk in chunks):
                        raise LessonAuthoringError("unsupported_study_claim", ["Label invented numerical studies 'Hypothetical example' in the same paragraph, or quote supplied evidence exactly."])
        authored = {**lesson, **payload, "reasoning_trace": "\n\n".join(item for item in (trace, content_trace) if item),
                    "lesson_id": lesson.get("lesson_id"),
                    "exercise_generation_mode": "llm_preferred",
                    "difficulty": (learner_context or {}).get("recommended_difficulty", "beginner")}
        authored["source"] = "llm_generated" if str(lesson.get("source") or "").strip().lower() == "template" else "llm_enriched"
        authored["status"] = "ready"
        authored["evidence_review"] = {"status": "not_independently_verified", "grounding_chunks": len(lesson.get("_chunks", []))}
        authored.pop("generation_warning", None)
        quality = curriculum_readiness({"subject": subject, "modules": [{"lessons": [authored]}]})
        if not quality["ready"]:
            issues = quality["errors"] + [issue for result in quality["lessons"] for issue in result["errors"]]
            raise LessonAuthoringError("teaching_checks_failed", issues or ["Authored lesson did not meet teaching-readiness checks."])
        return authored

    def _enrich_curriculum_lessons(self, curriculum: Dict[str, Any], subject: str, learner_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        modules = curriculum.get("modules")
        if not isinstance(modules, list):
            return curriculum
        if curriculum.get("source") == "template":
            try:
                curriculum = self._run_async(self._plan_curriculum(curriculum, subject, learner_context or {}))
            except Exception as exc:
                self.log("WARN", f"Curriculum sequence planning failed: {exc}")
                curriculum["generation_warnings"] = ["Course sequence planning failed; review or regenerate this draft. No teaching content was substituted."]
                curriculum["generation_diagnostics"] = [{"code": "sequence_planning_failed", "issues": ["The course outline could not be validated. Check runtime diagnostics and regenerate."]}]
                return curriculum
        sequence = [
            {"lesson_id": lesson["lesson_id"], "title": lesson["title"],
             "subtopic": lesson.get("subtopic", ""), "objectives": lesson.get("objectives", []),
             "prerequisites": lesson.get("prerequisites", [])}
            for module in modules for lesson in module.get("lessons", []) if isinstance(lesson, dict)
        ]
        curriculum["course_sequence"] = sequence
        curriculum = self._inject_chunks_into_lessons(curriculum)
        warnings: List[str] = []
        diagnostics: List[Dict[str, Any]] = []
        for module in modules:
            module_title = str(module.get("title") or "Module").strip()
            lessons = module.get("lessons")
            if not isinstance(lessons, list):
                continue
            for index, lesson in enumerate(lessons):
                if not isinstance(lesson, dict):
                    continue
                if not self._lesson_needs_authoring(lesson, subject):
                    normalized = dict(lesson)
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
                            learner_context=learner_context,
                            course_sequence=sequence,
                        )
                    )
                except Exception as exc:
                    self.log("WARN", f"Lesson authoring failed for {lesson.get('lesson_id')}: {exc}")
                    if isinstance(exc, LessonAuthoringError):
                        code, issues = exc.code, exc.issues
                    else:
                        code, issues = "provider_or_runtime_error", ["Lesson generation could not complete. Check provider availability and server diagnostics."]
                    warning = f"{lesson.get('lesson_id') or 'lesson'}: {code}: {' '.join(issues)}"
                    warnings.append(warning)
                    diagnostics.append({"lesson_id": lesson.get("lesson_id"), "code": code, "issues": issues})
                    fallback = dict(lesson)
                    fallback["source"] = "template"
                    fallback["status"] = "failed"
                    fallback["content"] = ""
                    fallback["generation_warning"] = "Lesson authoring failed. No teaching content was substituted."
                    lessons[index] = fallback
            module["estimated_minutes"] = sum(
                lesson["estimated_minutes"] for lesson in lessons
                if isinstance(lesson, dict) and isinstance(lesson.get("estimated_minutes"), int)
                and not isinstance(lesson["estimated_minutes"], bool) and lesson["estimated_minutes"] > 0
            )
        curriculum["estimated_total_minutes"] = sum(module.get("estimated_minutes", 0) for module in modules if isinstance(module, dict))
        if warnings:
            curriculum["generation_warnings"] = warnings
            curriculum["generation_diagnostics"] = diagnostics
        if str(curriculum.get("source") or "").strip().lower() == "template":
            curriculum["source"] = "llm_or_template_fallback"
        return curriculum

    async def _plan_curriculum(self, curriculum, subject, learner_context):
        lessons = [lesson for module in curriculum["modules"] for lesson in module["lessons"]]
        client = get_llm_client()
        prompt = (
            "Plan a coherent subject-specific course outline before teaching content is authored. Return STRICT JSON:\n"
            '{"lessons":[{"lesson_id":"exact supplied ID","title":"specific lesson title","subtopic":"distinct concrete subtopic",'
            '"objectives":["measurable specific objective","measurable specific objective"],"prerequisites":["earlier lesson ID"]}]}\n'
            f"Subject: {subject}\nLearner profile: {json.dumps(learner_context)}\n"
            f"Ordered lesson slots: {json.dumps([{'lesson_id': lesson['lesson_id'], 'module_stage': module['title']} for module in curriculum['modules'] for lesson in module['lessons']])}\n"
            "Keep the supplied ID order and count. Cover every named part of the subject; do not repeat one overview "
            "throughout the course. Begin at the learner's chosen level, define needed foundations, build practical skills, "
            "then independent application and review. Each subtopic and title must be unique and concrete. "
            "Allocate separate lessons to the distinct core concepts named in the request, rather than compressing "
            "all core concepts into one lesson followed by generic learning activities. Titles must name actual domain "
            "concepts or concrete tasks, not 'comparing methods', 'independent practice', 'review and transfer', or similar "
            "activity-only placeholders. Make the practical lessons apply the specific concepts already taught. "
            "Prerequisites may only reference earlier supplied IDs. Do not generate teaching content or claim factual verification."
        )
        raw = await client.generate(prompt, temperature=0.3, max_tokens=2600, response_format={"type": "json_object"})
        clean, trace = strip_reasoning(raw)
        payload = self._extract_json_object(clean)
        planned = payload.get("lessons")
        if not isinstance(planned, list) or len(planned) != len(lessons):
            raise ValueError("Outline does not match the required lesson count.")
        seen_ids, seen_topics, seen_titles = set(), set(), set()
        for slot, row in zip(lessons, planned):
            if not isinstance(row, dict) or row.get("lesson_id") != slot["lesson_id"]:
                raise ValueError("Outline changed lesson identities or order.")
            for key, seen in (("subtopic", seen_topics), ("title", seen_titles)):
                value = row.get(key)
                if not isinstance(value, str) or len(value.strip()) < 5 or value.strip().casefold() in seen:
                    raise ValueError(f"Outline needs distinct concrete {key} values.")
                seen.add(value.strip().casefold())
            objectives = row.get("objectives")
            prerequisites = row.get("prerequisites")
            if not isinstance(objectives, list) or len(objectives) < 2 or not all(isinstance(value, str) and len(value.strip()) >= 10 for value in objectives):
                raise ValueError("Outline needs specific measurable objectives.")
            if not isinstance(prerequisites, list) or not all(isinstance(value, str) and value in seen_ids for value in prerequisites):
                raise ValueError("Outline refers to missing or future prerequisites.")
            seen_ids.add(row["lesson_id"])
        for slot, row in zip(lessons, planned):
            slot.update({key: row[key] for key in ("title", "subtopic", "objectives", "prerequisites")})
        curriculum["outline_trace"] = trace
        curriculum["outline_status"] = "validated_structure"
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


    def _apply_validation_gate(self, curriculum: Dict[str, Any], subject: str) -> Dict[str, Any]:
        if not isinstance(curriculum, dict):
            return curriculum

        modules = curriculum.get("modules")
        if isinstance(modules, list):
            for module in modules:
                if not isinstance(module, dict):
                    continue
                lessons = module.get("lessons")
                if not isinstance(lessons, list):
                    continue
                for idx, lesson in enumerate(lessons):
                    if not isinstance(lesson, dict):
                        continue
                    content = str(lesson.get("content") or "").strip()
                    estimated_minutes = lesson.get("estimated_minutes")
                    if not isinstance(estimated_minutes, (int, float)) or int(estimated_minutes) <= 0:
                        lesson["estimated_minutes"] = max(15, min(120, (len(content) // 60) + 10))

        is_valid, result = validate_curriculum(curriculum)
        curriculum["validation"] = result
        curriculum["validation_valid"] = is_valid
        if not is_valid and "generation_warnings" not in curriculum:
            limited_errors = result.get("errors", [])[:5]
            if limited_errors:
                curriculum["generation_warnings"] = limited_errors
        return curriculum

    def run(self, prompt: Any) -> Dict[str, Any]:
        """
        Main entry point for CurriculumAgent.
        Returns a structured curriculum object generated from a natural-language prompt.

        Lightweight generator: produces modules and lessons with simple heuristics so
        other agents (PlannerAgent, OrchestratorAgent) can consume structured output.
        """
        subject = self._extract_subject(prompt)
        learner_context = prompt.get("learner_context", {}) if isinstance(prompt, dict) else {}
        if not isinstance(learner_context, dict):
            learner_context = {}

        curriculum_id = uuid.uuid4().hex
        now = datetime.now(timezone.utc).isoformat()

        curriculum = self._load_from_mammoth_supabase(subject, curriculum_id, now)
        if curriculum is None:
            curriculum = self._build_template_curriculum(subject, curriculum_id, now)

        curriculum = self._enrich_curriculum_lessons(curriculum, subject, learner_context)
        curriculum = self._apply_validation_gate(curriculum, subject)
        curriculum["quality"] = curriculum_readiness(curriculum)
        curriculum["difficulty"] = learner_context.get("recommended_difficulty", "beginner")

        summary = f"{curriculum.get('title', subject)} — {len(curriculum.get('modules', []))} modules, {curriculum.get('estimated_total_minutes', 0)} min estimated"
        if not curriculum.get("validation_valid", True):
            summary += " (validation warnings)"

        return {
            "status": "ok",
            "agent": self.name,
            "prompt": prompt,
            "summary": summary,
            "curriculum": curriculum,
            "validation": curriculum.get("validation"),
            "quality": curriculum["quality"],
            "quality_flags": ["validation_gate_active", "automated_quality_checks", "draft_requires_review"] if not curriculum["quality"]["ready"] else ["validation_gate_active", "automated_quality_checks"],
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
