import os
import json
import asyncio
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

from .base_agent import BaseAgent
from mammoth_os.agents.coding_agent import CodingAgent
from mammoth_os.rag_retrieval import get_retriever
from .tutor_agent_v2_upgrade import (
    _extract_difficulty_hint,
    _safe_retrieve_context,
    _build_adaptive_checkpoints,
    _build_coaching_summary,
)


class TutorAgent(BaseAgent):
    """TutorAgent MVP

    Responsibilities:
    - accept_submission(user_id, curriculum_id, lesson_id, files)
    - run tests via CodingAgent.run_tests
    - persist progress to .mammoth/progress.json (local fallback)
    - emit a result dict with pass/fail and test outputs
    """

    name = "TutorAgent"

    def __init__(self, router=None, storage_path: str = None):
        super().__init__(router)
        self.storage_path = storage_path or os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '.mammoth'))
        os.makedirs(self.storage_path, exist_ok=True)
        self.progress_file = os.path.join(self.storage_path, 'progress.json')

        # Optional Supabase persistence (disabled by default).
        # Accepts SUPABASE_KEY or the standard SUPABASE_ANON_KEY / SUPABASE_SERVICE_ROLE_KEY.
        self.supabase_url = os.environ.get('SUPABASE_URL')
        self.supabase_key = (
            os.environ.get('SUPABASE_SERVICE_ROLE_KEY')  # preferred — bypasses RLS
            or os.environ.get('SUPABASE_KEY')
            or os.environ.get('SUPABASE_ANON_KEY')
        )
        self.supabase = None
        if self.supabase_url and self.supabase_key:
            try:
                from supabase import create_client
                self.supabase = create_client(self.supabase_url, self.supabase_key)
            except Exception:
                # fail quietly — Supabase is optional
                self.supabase = None

    def log(self, level: str, message: str) -> None:
        print(f"[{self.name}:{level}] {message}")

    async def run(self, payload: Any) -> Dict[str, Any]:
        """
        Workflow entrypoint used by the runtime registry.

        - When `files` are provided, grade a submission through `accept_submission`.
        - Otherwise, return a lightweight coaching packet for the current lesson/module.
        """
        if isinstance(payload, dict) and payload.get("files"):
            return await self.accept_submission(
                str(payload.get("user_id") or "default_user"),
                str(payload.get("curriculum_id") or "atlas-curriculum"),
                str(payload.get("lesson_id") or "current-lesson"),
                payload.get("files") or {},
            )

        if isinstance(payload, dict):
            topic = str(payload.get("topic") or payload.get("prompt") or "current lesson").strip()
            lesson_title = str(payload.get("lesson_title") or topic).strip()
            module_id = str(payload.get("module_id") or "").strip()
            user_id = str(payload.get("user_id") or payload.get("user") or "default_user").strip()
            lesson_id = str(payload.get("lesson_id") or payload.get("current_lesson_id") or "").strip()
            lesson_chunks = payload.get("_chunks") or []
        else:
            topic = str(payload or "current lesson").strip()
            lesson_title = topic
            module_id = ""
            user_id = "default_user"
            lesson_id = ""
            lesson_chunks = []

        retriever = get_retriever()
        signal_summary = "Signals:\n- Difficulty: unknown\n- Performance score: unknown\n- Struggle tags: none"
        personalized_chunks: List[Dict[str, Any]] = []
        
        # Extract difficulty hint from signal summary (adaptive)
        if lesson_id:
            personalized_chunks = await _safe_retrieve_context(
                retriever=retriever,
                user_id=user_id,
                lesson_id=lesson_id,
                query=topic or lesson_title,
                top_k=5,
            )
            signal_summary = retriever.build_signal_summary(
                await retriever.load_user_signals(user_id, lesson_id)
            )
        elif lesson_chunks:
            personalized_chunks = [{"chunk_text": chunk, "chunk_index": idx, "score": 0.0} for idx, chunk in enumerate(lesson_chunks)]
        
        # Extract adaptive difficulty hint
        difficulty = _extract_difficulty_hint(signal_summary)
        
        # Build adaptive checkpoints based on difficulty
        checkpoints = _build_adaptive_checkpoints(lesson_title, module_id or "m0", difficulty)
        if len(checkpoints) < 3:
            checkpoints.extend([
                f"Restate the objective for {lesson_title} in your own words.",
                "Identify one concrete success check before you start.",
                "Record what confused you so the next coaching step can adapt.",
            ])
            checkpoints = checkpoints[:5]

        # Build coaching response with RAG-enriched context and adaptive coaching
        coaching_context = ""
        if personalized_chunks:
            coaching_context = "\n".join([
                f"• {str(chunk.get('chunk_text') or '')[:200]}..."
                for chunk in personalized_chunks[:3]
                if chunk.get("chunk_text")
            ])
        elif lesson_chunks:
            coaching_context = "\n".join([f"• {chunk[:200]}..." for chunk in lesson_chunks[:3]])

        quality_flags: List[str] = []
        if not topic:
            quality_flags.append("missing_topic")
        if not coaching_context:
            quality_flags.append("limited_context")
        if personalized_chunks:
            quality_flags.append("personalized_context")
        if not quality_flags:
            quality_flags.append("coaching_ready")
        
        # Add difficulty flag
        quality_flags.append(f"difficulty_{difficulty}")
        
        # Build adaptive coaching summary
        adaptive_summary = _build_coaching_summary(
            lesson_title,
            difficulty,
            has_context=bool(personalized_chunks),
        )

        return {
            "status": "ok",
            "agent": self.name,
            "mode": "coach",
            "topic": topic,
            "lesson_title": lesson_title,
            "user_id": user_id,
            "lesson_id": lesson_id,
            "module_id": module_id,
            "lesson_context": coaching_context,
            "signal_summary": signal_summary,
            "personalized_chunks": personalized_chunks,
            "coach_summary": adaptive_summary,
            "checkpoints": checkpoints,
            "next_step": "Complete the smallest verifiable part of the lesson, then reflect before escalating difficulty.",
            "summary": f"Tutor guidance for {lesson_title} ({difficulty} difficulty): {adaptive_summary[:60]}...",
            "quality_flags": quality_flags,
            "evidence": {
                "has_personalized_context": bool(personalized_chunks),
                "signal_summary_present": bool(signal_summary),
                "lesson_context_length": len(coaching_context),
                "adaptive_difficulty": difficulty,
                "checkpoint_count": len(checkpoints),
            },
        }

    async def accept_submission(self, user_id: str, curriculum_id: str, lesson_id: str, files: Dict[str, str]) -> Dict[str, Any]:
        """Accept a student's submission and grade it by running tests.

        files is a dict mapping relative filenames to their contents.
        """
        # Ensure CodingAgent is available
        coding = CodingAgent()
        # Write files to a temp directory and call run_tests on that path
        import tempfile
        tmpdir = tempfile.mkdtemp()
        started = time.perf_counter()
        try:
            for rel, content in files.items():
                dest = os.path.join(tmpdir, rel)
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with open(dest, 'w', encoding='utf-8') as fh:
                    fh.write(content)

            # Run tests (CodingAgent.run_tests is async)
            result = await coding.run_tests(tmpdir)
            duration_ms = int((time.perf_counter() - started) * 1000)
            error_fingerprint = self._fingerprint_error(result)

            # Persist progress locally and to Supabase (if configured)
            progress = self._record_progress(
                user_id,
                curriculum_id,
                lesson_id,
                result,
                duration_ms=duration_ms,
                error_fingerprint=error_fingerprint,
            )

            return {
                "user_id": user_id,
                "curriculum_id": curriculum_id,
                "lesson_id": lesson_id,
                "result": result,
                "recommendation": progress["recommendation"],
                "adaptive_signals": {
                    "attempt_index": progress["attempt_index"],
                    "time_to_pass_attempts": progress["time_to_pass_attempts"],
                    "duration_ms": duration_ms,
                    "error_fingerprint": error_fingerprint,
                },
            }
        finally:
            # best-effort cleanup
            try:
                import shutil
                shutil.rmtree(tmpdir)
            except Exception:
                pass

    def _record_progress(
        self,
        user_id: str,
        curriculum_id: str,
        lesson_id: str,
        result: Dict[str, Any],
        duration_ms: int,
        error_fingerprint: str,
    ) -> Dict[str, Any]:
        """Record progress locally and optionally to Supabase.

        Returns adaptive output containing recommendation and progress signals.
        """
        entry = {
            "user_id": user_id,
            "curriculum_id": curriculum_id,
            "lesson_id": lesson_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "result": result,
            "duration_ms": duration_ms,
            "error_fingerprint": error_fingerprint,
        }
        data: List[Dict[str, Any]] = []
        if os.path.exists(self.progress_file):
            try:
                with open(self.progress_file, 'r', encoding='utf-8') as fh:
                    data = json.load(fh)
            except Exception:
                data = []

        # compute prior attempts for this user+lesson
        prior_attempts = [
            d for d in data
            if d.get('user_id') == user_id and d.get('lesson_id') == lesson_id
        ]
        current_attempt = len(prior_attempts) + 1
        entry["attempt_index"] = current_attempt
        data.append(entry)

        # Write back
        try:
            with open(self.progress_file, 'w', encoding='utf-8') as fh:
                json.dump(data, fh, indent=2)
        except Exception:
            pass

        # Persist to Supabase if configured — write to existing atlas schema tables
        if self.supabase:
            self._persist_to_atlas_schema(
                user_id=user_id,
                curriculum_id=curriculum_id,
                lesson_id=lesson_id,
                result=result,
                duration_ms=duration_ms,
                error_fingerprint=error_fingerprint,
                current_attempt=current_attempt,
            )

        passed = bool(result.get('passed'))
        recommendation = self._recommend_difficulty(
            passed=passed,
            current_attempt=current_attempt,
            duration_ms=duration_ms,
            error_fingerprint=error_fingerprint,
            prior_attempts=prior_attempts,
        )

        time_to_pass_attempts: Optional[int] = None
        if passed:
            time_to_pass_attempts = self._attempts_since_last_success(prior_attempts) + 1

        return {
            "recommendation": recommendation,
            "attempt_index": current_attempt,
            "time_to_pass_attempts": time_to_pass_attempts,
        }

    # ------------------------------------------------------------------ #
    # Supabase: write to existing atlas schema tables                      #
    # ------------------------------------------------------------------ #

    def _resolve_user_uuid(self, user_id: str) -> Optional[str]:
        """Return user_id if it's already a valid UUID, else try to look it up
        in auth.users by email/username. Returns None if unresolvable so the
        caller can skip Supabase writes without crashing."""
        import re
        _UUID_RE = re.compile(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
            re.IGNORECASE,
        )
        if _UUID_RE.match(user_id):
            return user_id
        # Non-UUID user_id (e.g. "cli_user") — skip Supabase writes for now
        # (a proper auth integration would resolve this via auth.users)
        return None

    def _persist_to_atlas_schema(
        self,
        user_id: str,
        curriculum_id: str,
        lesson_id: str,
        result: Dict[str, Any],
        duration_ms: int,
        error_fingerprint: str,
        current_attempt: int,
    ) -> None:
        """Write submission data to the existing atlas schema tables.

        Tables used:
          mammoth.progress        — canonical completed-lesson progress
          mammoth.activity_log    — attempt audit trail / metadata
          atlas.atlas_progress    — lesson status + last_accessed for ATLAS UX
          atlas.adaptive_metrics  — performance score, timing, difficulty
          atlas.community_stats   — XP award on pass
        All writes are best-effort; any exception is swallowed so submission
        flow is never blocked by a Supabase error.
        """
        user_uuid = self._resolve_user_uuid(user_id)
        if user_uuid is None:
            self.log("WARN", f"Skipping Supabase writes: user_id '{user_id}' is not a UUID")
            return

        passed = bool(result.get('passed'))

        # 1. mammoth.progress — record completed lessons in the core schema
        if passed and self._is_uuid(lesson_id):
            try:
                mammoth_progress = {
                    "user_id": user_uuid,
                    "lesson_id": lesson_id,
                    "completed_at": __import__('datetime').datetime.utcnow().isoformat() + 'Z',
                }
                self.supabase.schema("mammoth").table("progress").upsert(
                    mammoth_progress,
                    on_conflict="user_id,lesson_id",
                ).execute()
            except Exception as exc:
                self.log("WARN", f"mammoth.progress write failed: {exc}")

        # 2. mammoth.activity_log — attempt-level audit trail
        try:
            activity = {
                "user_id": user_uuid,
                "action": "atlas_submission_passed" if passed else "atlas_submission_failed",
                "metadata": {
                    "curriculum_id": curriculum_id,
                    "lesson_id": lesson_id,
                    "attempt_index": current_attempt,
                    "duration_ms": duration_ms,
                    "error_fingerprint": error_fingerprint,
                    "passed": passed,
                },
            }
            self.supabase.schema("mammoth").table("activity_log").insert(activity).execute()
        except Exception as exc:
            self.log("WARN", f"mammoth.activity_log write failed: {exc}")

        # 3. atlas.atlas_progress — track lesson status
        try:
            progress_record = {
                "user_id": user_uuid,
                "module": curriculum_id,
                "lesson_id": lesson_id if self._is_uuid(lesson_id) else None,
                "status": "completed" if passed else "in_progress",
                "last_accessed": __import__('datetime').datetime.utcnow().isoformat() + 'Z',
            }
            # Remove None values
            progress_record = {k: v for k, v in progress_record.items() if v is not None}
            self.supabase.schema("atlas").table("atlas_progress").upsert(
                progress_record,
                on_conflict="user_id,module,lesson_id",
            ).execute()
        except Exception as exc:
            self.log("WARN", f"atlas_progress write failed: {exc}")

        # 4. atlas.adaptive_metrics — record performance for adaptive engine
        try:
            performance_score = 1.0 if passed else max(0.0, 1.0 - (current_attempt - 1) * 0.15)
            difficulty_level = self._to_metric_difficulty(
                passed=passed,
                current_attempt=current_attempt,
            )
            # duration_ms → PostgreSQL interval string e.g. "1234 milliseconds"
            interval_str = f"{duration_ms} milliseconds" if duration_ms else None
            metrics_record = {
                "user_id": user_uuid,
                "lesson_id": lesson_id if self._is_uuid(lesson_id) else None,
                "performance_score": round(performance_score, 3),
                "difficulty_level": difficulty_level,
            }
            if interval_str:
                metrics_record["completion_time"] = interval_str
            metrics_record = {k: v for k, v in metrics_record.items() if v is not None}
            self.supabase.schema("atlas").table("adaptive_metrics").insert(
                metrics_record
            ).execute()
        except Exception as exc:
            self.log("WARN", f"adaptive_metrics write failed: {exc}")

        # 5. atlas.community_stats — award XP on pass, bump streak
        if passed:
            try:
                XP_PER_PASS = 10
                existing = (
                    self.supabase.schema("atlas")
                    .table("community_stats")
                    .select("xp,lessons_completed")
                    .eq("user_id", user_uuid)
                    .limit(1)
                    .execute()
                )
                row = existing.data[0] if getattr(existing, "data", None) else {}
                self.supabase.schema("atlas").table("community_stats").upsert(
                    {
                        "user_id": user_uuid,
                        "xp": int(row.get("xp", 0)) + XP_PER_PASS,
                        "lessons_completed": int(row.get("lessons_completed", 0)) + 1,
                        "last_active": __import__('datetime').datetime.utcnow().isoformat() + 'Z',
                    },
                    on_conflict="user_id",
                ).execute()
            except Exception as exc:
                self.log("WARN", f"community_stats XP award failed: {exc}")

    @staticmethod
    def _is_uuid(value: str) -> bool:
        import re
        return bool(re.match(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
            str(value), re.IGNORECASE,
        ))

    @staticmethod
    def _to_metric_difficulty(passed: bool, current_attempt: int) -> str:
        """Map adaptive outcome to atlas.adaptive_metrics difficulty enum."""
        if passed and current_attempt <= 2:
            return "hard"
        if not passed and current_attempt >= 3:
            return "easy"
        return "medium"

    def _fingerprint_error(self, result: Dict[str, Any]) -> str:
        """Map test output to coarse error categories for adaptive tutoring."""
        if bool(result.get('passed')):
            return 'passed'
        text = f"{result.get('stdout', '')}\n{result.get('stderr', '')}".lower()
        if 'syntaxerror' in text:
            return 'syntax_error'
        if 'indentationerror' in text:
            return 'indentation_error'
        if 'modulenotfounderror' in text or 'importerror' in text:
            return 'import_error'
        if 'assertionerror' in text or 'assert ' in text:
            return 'assertion_error'
        if 'typeerror' in text:
            return 'type_error'
        if 'nameerror' in text:
            return 'name_error'
        if 'timeout' in text:
            return 'timeout'
        if 'notimplementederror' in text:
            return 'not_implemented'
        return 'unknown_failure'

    def _attempts_since_last_success(self, prior_attempts: List[Dict[str, Any]]) -> int:
        """Count attempts after the most recent pass (or all attempts if never passed)."""
        count = 0
        for attempt in reversed(prior_attempts):
            if bool((attempt.get('result') or {}).get('passed')):
                break
            count += 1
        return count

    def _recommend_difficulty(
        self,
        passed: bool,
        current_attempt: int,
        duration_ms: int,
        error_fingerprint: str,
        prior_attempts: List[Dict[str, Any]],
    ) -> str:
        """Heuristic recommendation using attempts, timing, and repeated error patterns."""
        if passed:
            attempts_since_last_success = self._attempts_since_last_success(prior_attempts) + 1
            # Fast pass with few retries indicates readiness for harder material.
            if attempts_since_last_success == 1 and duration_ms <= 60_000:
                return 'increase'
            if attempts_since_last_success <= 2 and duration_ms <= 120_000:
                return 'increase'
            return 'same'

        # Repeated failures with same fingerprint suggests cognitive overload.
        recent = prior_attempts[-2:]
        repeated_same_error = (
            len(recent) >= 1
            and all((r.get('error_fingerprint') == error_fingerprint) for r in recent)
        )
        if repeated_same_error and current_attempt >= 2:
            return 'decrease'

        # Multiple failures in a row, especially structural errors, should reduce difficulty.
        if current_attempt >= 3 and error_fingerprint in {'syntax_error', 'indentation_error', 'type_error', 'timeout'}:
            return 'decrease'

        return 'same'
