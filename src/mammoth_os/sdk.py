"""Embeddable ATLAS FAB SDK surface for developers integrating MammothOS."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field, fields
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from mammoth_os.atlas_session import ATLASSession
from mammoth_os.llm_client import get_llm_client

SDK_CONTRACT_VERSION = "v2"
PRODUCT_SURFACE = "atlas_fab"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_blocking(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    raise RuntimeError(
        "AtlasFAB blocking methods cannot run inside an active event loop. Use the async variant instead."
    )


def _copy_dict(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _safe_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    try:
        if value in (None, ""):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


class _SerializableDataclass:
    def as_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {}
        for item in fields(self):
            value = getattr(self, item.name)
            if isinstance(value, dict):
                payload[item.name] = dict(value)
            elif isinstance(value, list):
                payload[item.name] = list(value)
            else:
                payload[item.name] = value
        return payload


class AtlasFABError(Exception):
    """Structured SDK error for embedders."""

    def __init__(self, code: str, message: str, *, context: Optional[Dict[str, Any]] = None):
        self.code = str(code or "atlas_fab_error")
        self.message = str(message or "AtlasFAB error")
        self.context = dict(context or {})
        super().__init__(self.message)

    def __str__(self) -> str:
        return f"{self.code}: {self.message}" if self.code else self.message

    def as_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "context": dict(self.context),
        }


@dataclass(slots=True)
class AtlasFABConfig(_SerializableDataclass):
    """Configuration for embedding the ATLAS tutoring loop inside another product."""

    user_id: str = "workspace:default"
    tenant_id: str = ""
    plan: str = "embedded"
    adapter: str = ""
    model: str = ""
    audience: str = "developer"
    mode: str = "tutor"
    telemetry_enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def llm_config(self) -> Dict[str, Any]:
        config: Dict[str, Any] = {}
        if self.adapter:
            config["MAMMOTH_LLM_ADAPTER"] = self.adapter
        if self.model:
            config["model"] = self.model
        return config

    def usage_limits(self) -> Dict[str, Any]:
        limits = self.metadata.get("usage")
        return dict(limits) if isinstance(limits, dict) else {}


@dataclass(slots=True)
class AtlasLessonSnapshot(_SerializableDataclass):
    contract_version: str
    product_surface: str
    user_id: str
    topic: str
    module_idx: int
    lesson_idx: int
    exercise_count: int
    difficulty: str
    lesson: Dict[str, Any] = field(default_factory=dict)
    curriculum: Dict[str, Any] = field(default_factory=dict)
    exercise: Dict[str, Any] = field(default_factory=dict)
    curriculum_id: str = ""
    lesson_id: str = ""
    exercise_id: str = ""
    progress: Dict[str, Any] = field(default_factory=dict)
    usage: Dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    status: str = "ok"


@dataclass(slots=True)
class AtlasSubmissionReport(_SerializableDataclass):
    contract_version: str
    product_surface: str
    user_id: str
    passed: bool
    recommendation: str
    hint: str
    result: Dict[str, Any] = field(default_factory=dict)
    status: str = "ok"
    exercise_id: str = ""
    lesson_id: str = ""
    submission_index: int = 0
    progress: Dict[str, Any] = field(default_factory=dict)
    usage: Dict[str, Any] = field(default_factory=dict)
    updated_at: str = ""


@dataclass(slots=True)
class AtlasGenerationReport(_SerializableDataclass):
    contract_version: str
    product_surface: str
    user_id: str
    prompt: str
    code: str
    tests: str
    docs: str
    passed: bool
    hint: str
    result: Dict[str, Any] = field(default_factory=dict)
    status: str = "ok"
    context: Dict[str, Any] = field(default_factory=dict)
    generation_index: int = 0
    progress: Dict[str, Any] = field(default_factory=dict)
    usage: Dict[str, Any] = field(default_factory=dict)
    updated_at: str = ""


@dataclass(slots=True)
class AtlasProgressSnapshot(_SerializableDataclass):
    contract_version: str
    product_surface: str
    user_id: str
    session_state: str
    workflow_stage: str
    current_topic: str = ""
    curriculum_title: str = ""
    lesson_title: str = ""
    exercise_title: str = ""
    curriculum_id: str = ""
    lesson_id: str = ""
    exercise_id: str = ""
    lesson_starts: int = 0
    submissions: int = 0
    passes: int = 0
    failures: int = 0
    generations: int = 0
    last_event: str = ""
    last_submission_passed: Optional[bool] = None
    ready_for_submission: bool = False
    started_at: str = ""
    updated_at: str = ""


@dataclass(slots=True)
class AtlasUsageSnapshot(_SerializableDataclass):
    contract_version: str
    product_surface: str
    user_id: str
    plan: str
    telemetry_enabled: bool
    request_count: int
    request_limit: Optional[int]
    token_count: Optional[int]
    token_limit: Optional[int]
    percent_used: Optional[float]
    warning_level: str
    source: str
    lesson_starts: int = 0
    submissions: int = 0
    passes: int = 0
    failures: int = 0
    generations: int = 0
    event_count: int = 0
    updated_at: str = ""


@dataclass(slots=True)
class AtlasRuntimeSnapshot(_SerializableDataclass):
    contract_version: str
    product_surface: str
    user_id: str
    plan: str
    audience: str
    mode: str
    telemetry_enabled: bool
    primary_provider: str
    fallback_provider: str
    last_used_provider: str
    last_fallback_used: bool
    last_fallback_reason: str
    last_error_type: str
    last_error_detail: str
    model: str
    provider_state: Dict[str, Any] = field(default_factory=dict)
    progress: Dict[str, Any] = field(default_factory=dict)
    usage: Dict[str, Any] = field(default_factory=dict)
    session_state: str = ""
    updated_at: str = ""


class AtlasFAB:
    """Small public SDK for embedding ATLAS lesson and code workflows."""

    contract_version = SDK_CONTRACT_VERSION

    def __init__(
        self,
        config: Optional[AtlasFABConfig] = None,
        session: Optional[ATLASSession] = None,
        session_factory: Optional[Callable[[], ATLASSession]] = None,
    ):
        self.config = config or AtlasFABConfig()
        self._session_factory = session_factory
        self.session = session or self._build_session()
        self._events: List[Dict[str, Any]] = []
        self._lesson_starts = 0
        self._submissions = 0
        self._passes = 0
        self._failures = 0
        self._generations = 0
        self._started_at = _utc_now_iso()
        self._updated_at = self._started_at
        self._last_topic = ""
        self._last_lesson_id = ""
        self._last_exercise_id = ""
        self._last_submission_passed: Optional[bool] = None
        self._last_submission_result: Dict[str, Any] = {}
        self._last_generation_result: Dict[str, Any] = {}

    def _build_session(self) -> ATLASSession:
        if self._session_factory is not None:
            return self._session_factory()
        return ATLASSession(user_id=self.config.user_id)

    def _touch(self) -> str:
        self._updated_at = _utc_now_iso()
        return self._updated_at

    def _record_event(self, event_type: str, detail: Optional[Dict[str, Any]] = None) -> None:
        self._events.append(
            {
                "event": event_type,
                "detail": dict(detail or {}),
                "at": self._touch(),
            }
        )

    def _usage_limits(self) -> Dict[str, Any]:
        return self.config.usage_limits()

    def _progress_stage(self, status: Dict[str, Any]) -> str:
        if str(status.get("state") or "").strip().lower() != "active":
            return "idle"
        if self._last_submission_passed is True:
            return "mastered"
        if self._last_submission_passed is False:
            return "needs_revision"
        if self._lesson_starts > 0:
            return "awaiting_submission"
        return "ready"

    def _progress_snapshot(self) -> AtlasProgressSnapshot:
        status = _copy_dict(self.session.status())
        lesson = _copy_dict(getattr(self.session, "current_lesson", None))
        exercise = _copy_dict(getattr(self.session, "current_exercise", None))
        return AtlasProgressSnapshot(
            contract_version=self.contract_version,
            product_surface=PRODUCT_SURFACE,
            user_id=self.config.user_id,
            session_state=str(status.get("state") or "idle").strip() or "idle",
            workflow_stage=self._progress_stage(status),
            current_topic=str(self._last_topic or lesson.get("topic") or "").strip(),
            curriculum_title=str(status.get("curriculum_title") or "").strip(),
            lesson_title=str(status.get("lesson_title") or "").strip(),
            exercise_title=str(status.get("exercise_title") or "").strip(),
            curriculum_id=str(status.get("curriculum_id") or "").strip(),
            lesson_id=str(status.get("lesson_id") or self._last_lesson_id or "").strip(),
            exercise_id=str(exercise.get("exercise_id") or self._last_exercise_id or "").strip(),
            lesson_starts=self._lesson_starts,
            submissions=self._submissions,
            passes=self._passes,
            failures=self._failures,
            generations=self._generations,
            last_event=self._events[-1]["event"] if self._events else "",
            last_submission_passed=self._last_submission_passed,
            ready_for_submission=bool(exercise),
            started_at=self._started_at,
            updated_at=self._updated_at,
        )

    def _usage_snapshot(self) -> AtlasUsageSnapshot:
        limits = self._usage_limits()
        request_limit = _safe_int(
            limits.get("request_limit")
            or limits.get("requests_limit")
            or limits.get("requests")
        )
        token_limit = _safe_int(
            limits.get("token_limit")
            or limits.get("tokens_limit")
            or limits.get("tokens")
        )
        token_count = _safe_int(limits.get("token_count") or limits.get("tokens_used"))
        request_count = self._lesson_starts + self._submissions + self._generations
        if request_limit and request_limit > 0:
            percent_used = round((request_count / request_limit) * 100, 1)
        elif token_limit and token_limit > 0 and token_count is not None:
            percent_used = round((token_count / token_limit) * 100, 1)
        else:
            percent_used = None
        if request_count == 0:
            warning_level = "idle"
        elif percent_used is None:
            warning_level = "unknown"
        elif percent_used >= 90:
            warning_level = "critical"
        elif percent_used >= 80:
            warning_level = "elevated"
        else:
            warning_level = "normal"
        source = "configured" if limits else "embedded_estimate"
        return AtlasUsageSnapshot(
            contract_version=self.contract_version,
            product_surface=PRODUCT_SURFACE,
            user_id=self.config.user_id,
            plan=self.config.plan,
            telemetry_enabled=self.config.telemetry_enabled,
            request_count=request_count,
            request_limit=request_limit,
            token_count=token_count,
            token_limit=token_limit,
            percent_used=percent_used,
            warning_level=warning_level,
            source=source,
            lesson_starts=self._lesson_starts,
            submissions=self._submissions,
            passes=self._passes,
            failures=self._failures,
            generations=self._generations,
            event_count=len(self._events),
            updated_at=self._updated_at,
        )

    def start_lesson_model(
        self,
        topic: str,
        *,
        module_idx: int = 0,
        lesson_idx: int = 0,
        exercise_count: int = 1,
        use_llm: Optional[bool] = None,
        difficulty: str = "beginner",
        learner_context: Optional[Dict[str, Any]] = None,
    ) -> AtlasLessonSnapshot:
        resolved_context = dict(self.config.metadata.get("learner_context") or {})
        if learner_context:
            resolved_context.update(learner_context)
        raw = self.session.start_lesson(
            topic,
            module_idx=module_idx,
            lesson_idx=lesson_idx,
            exercise_count=exercise_count,
            use_llm=use_llm,
            difficulty=difficulty,
            learner_context=resolved_context or None,
        )
        self._lesson_starts += 1
        self._last_topic = str(topic or "").strip()
        self._last_lesson_id = str(raw.get("lesson_id") or "").strip()
        self._last_exercise_id = str(raw.get("exercise_id") or "").strip()
        self._last_submission_passed = None
        self._record_event(
            "lesson_started",
            {
                "topic": self._last_topic,
                "module_idx": module_idx,
                "lesson_idx": lesson_idx,
                "exercise_count": exercise_count,
                "difficulty": difficulty,
            },
        )
        progress = self._progress_snapshot().as_dict()
        usage = self._usage_snapshot().as_dict()
        return AtlasLessonSnapshot(
            contract_version=self.contract_version,
            product_surface=PRODUCT_SURFACE,
            user_id=self.config.user_id,
            topic=self._last_topic,
            module_idx=module_idx,
            lesson_idx=lesson_idx,
            exercise_count=exercise_count,
            difficulty=difficulty,
            lesson=_copy_dict(raw.get("lesson")),
            curriculum=_copy_dict(raw.get("curriculum")),
            exercise={k: v for k, v in raw.items() if k not in {"lesson", "curriculum"}},
            curriculum_id=str(raw.get("curriculum_id") or "").strip(),
            lesson_id=str(raw.get("lesson_id") or "").strip(),
            exercise_id=str(raw.get("exercise_id") or "").strip(),
            progress=progress,
            usage=usage,
            created_at=self._updated_at,
            status=str(raw.get("status") or "ok"),
        )

    def start_lesson(
        self,
        topic: str,
        *,
        module_idx: int = 0,
        lesson_idx: int = 0,
        exercise_count: int = 1,
        use_llm: Optional[bool] = None,
        difficulty: str = "beginner",
        learner_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return self.start_lesson_model(
            topic,
            module_idx=module_idx,
            lesson_idx=lesson_idx,
            exercise_count=exercise_count,
            use_llm=use_llm,
            difficulty=difficulty,
            learner_context=learner_context,
        ).as_dict()

    def status(self) -> Dict[str, Any]:
        return self.session.status()

    def next_lesson(self, lesson_idx_delta: int = 1) -> Dict[str, Any]:
        result = self.session.next_lesson(lesson_idx_delta=lesson_idx_delta)
        self._last_lesson_id = str(result.get("lesson_id") or self._last_lesson_id or "").strip()
        self._last_exercise_id = str(result.get("exercise_id") or self._last_exercise_id or "").strip()
        self._record_event("lesson_advanced", {"lesson_idx_delta": lesson_idx_delta})
        return result

    async def submit_model(
        self,
        *,
        files: Optional[Dict[str, str]] = None,
        solution_code: str = "",
        solution_filename: str = "solution.py",
    ) -> AtlasSubmissionReport:
        payload = dict(files or {})
        if solution_code and solution_filename not in payload:
            payload[solution_filename] = solution_code
        if not payload:
            raise AtlasFABError(
                "empty_submission",
                "submit_model requires files or solution_code.",
                context={"solution_filename": solution_filename},
            )
        raw = await self.session.submit(payload)
        passed = bool(raw.get("passed"))
        self._submissions += 1
        self._passes += 1 if passed else 0
        self._failures += 0 if passed else 1
        self._last_submission_passed = passed
        self._last_submission_result = dict(raw)
        self._record_event("submission_evaluated", {"passed": passed, "files": sorted(payload.keys())})
        progress = self._progress_snapshot().as_dict()
        usage = self._usage_snapshot().as_dict()
        return AtlasSubmissionReport(
            contract_version=self.contract_version,
            product_surface=PRODUCT_SURFACE,
            user_id=self.config.user_id,
            status=str(raw.get("status") or "ok"),
            passed=passed,
            recommendation=str(raw.get("recommendation") or "same"),
            hint=str(raw.get("hint") or ""),
            result=dict(raw),
            exercise_id=self._last_exercise_id,
            lesson_id=self._last_lesson_id,
            submission_index=self._submissions,
            progress=progress,
            usage=usage,
            updated_at=self._touch(),
        )

    async def submit(
        self,
        *,
        files: Optional[Dict[str, str]] = None,
        solution_code: str = "",
        solution_filename: str = "solution.py",
    ) -> Dict[str, Any]:
        return (
            await self.submit_model(
                files=files,
                solution_code=solution_code,
                solution_filename=solution_filename,
            )
        ).as_dict()

    async def generate_and_test_model(
        self,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> AtlasGenerationReport:
        resolved = {"source": PRODUCT_SURFACE, "audience": self.config.audience, "mode": self.config.mode}
        if context:
            resolved.update(context)
        raw = await self.session.generate_and_test(prompt, context=resolved)
        code = str(raw.get("code") or "")
        tests = str(raw.get("tests") or "")
        docs = str(raw.get("docs") or "")
        passed = bool(raw.get("passed"))
        hint = str(raw.get("hint") or "")
        self._generations += 1
        self._last_generation_result = dict(raw)
        self._record_event("code_generated", {"prompt": prompt, "passed": passed})
        progress = self._progress_snapshot().as_dict()
        usage = self._usage_snapshot().as_dict()
        return AtlasGenerationReport(
            contract_version=self.contract_version,
            product_surface=PRODUCT_SURFACE,
            user_id=self.config.user_id,
            status=str(raw.get("status") or "ok"),
            prompt=prompt,
            code=code,
            tests=tests,
            docs=docs,
            passed=passed,
            hint=hint,
            result=dict(raw),
            context=dict(resolved),
            generation_index=self._generations,
            progress=progress,
            usage=usage,
            updated_at=self._touch(),
        )

    def progress_model(self) -> AtlasProgressSnapshot:
        return self._progress_snapshot()

    def get_progress(self) -> Dict[str, Any]:
        return self.progress_model().as_dict()

    def resume_model(self) -> AtlasProgressSnapshot:
        return self.progress_model()

    def resume(self) -> Dict[str, Any]:
        return self.resume_model().as_dict()

    def usage_model(self) -> AtlasUsageSnapshot:
        return self._usage_snapshot()

    def get_usage(self) -> Dict[str, Any]:
        return self.usage_model().as_dict()

    def runtime_state_model(self) -> AtlasRuntimeSnapshot:
        client = get_llm_client(self.config.llm_config())
        describe = getattr(client, "describe_runtime_state", None)
        if callable(describe):
            provider_state = describe()
        else:
            provider_state = {
                "primary_provider": type(client).__name__.replace("Adapter", "").lower(),
                "model": str(getattr(client, "model", "unknown")),
            }
        progress = self.progress_model().as_dict()
        usage = self.usage_model().as_dict()
        return AtlasRuntimeSnapshot(
            contract_version=self.contract_version,
            product_surface=PRODUCT_SURFACE,
            user_id=self.config.user_id,
            plan=self.config.plan,
            audience=self.config.audience,
            mode=self.config.mode,
            telemetry_enabled=self.config.telemetry_enabled,
            primary_provider=str(provider_state.get("primary_provider") or "local").strip() or "local",
            fallback_provider=str(provider_state.get("fallback_provider") or "").strip(),
            last_used_provider=str(provider_state.get("last_used_provider") or provider_state.get("primary_provider") or "local").strip() or "local",
            last_fallback_used=bool(provider_state.get("last_fallback_used", False)),
            last_fallback_reason=str(provider_state.get("last_fallback_reason") or "").strip(),
            last_error_type=str(provider_state.get("last_error_type") or "").strip(),
            last_error_detail=str(provider_state.get("last_error_detail") or "").strip(),
            model=str(provider_state.get("model") or getattr(client, "model", "unknown") or "unknown"),
            provider_state=dict(provider_state),
            progress=progress,
            usage=usage,
            session_state=str(progress.get("session_state") or "idle"),
            updated_at=self._updated_at,
        )

    def runtime_state(self) -> Dict[str, Any]:
        return self.runtime_state_model().as_dict()

    def reset(self) -> Dict[str, Any]:
        self.session = self._build_session()
        self._events = []
        self._lesson_starts = 0
        self._submissions = 0
        self._passes = 0
        self._failures = 0
        self._generations = 0
        self._started_at = _utc_now_iso()
        self._updated_at = self._started_at
        self._last_topic = ""
        self._last_lesson_id = ""
        self._last_exercise_id = ""
        self._last_submission_passed = None
        self._last_submission_result = {}
        self._last_generation_result = {}
        self._record_event("session_reset", {"user_id": self.config.user_id})
        return self.progress_model().as_dict()

    def snapshot(self) -> Dict[str, Any]:
        usage = self.get_usage()
        runtime = self.runtime_state()
        return {
            "contract_version": self.contract_version,
            "product_surface": PRODUCT_SURFACE,
            "tenant": {
                "tenant_id": self.config.tenant_id,
                "is_bound": bool(str(self.config.tenant_id or "").strip()),
                "plan": self.config.plan,
                "audience": self.config.audience,
                "mode": self.config.mode,
            },
            "usage_policy": {
                "metering_mode": "request_and_token",
                "telemetry_enabled": self.config.telemetry_enabled,
                "limits": self._usage_limits(),
                "warning_level": usage.get("warning_level"),
                "percent_used": usage.get("percent_used"),
                "source": usage.get("source"),
            },
            "config": self.config.as_dict(),
            "progress": self.get_progress(),
            "usage": usage,
            "runtime": runtime,
            "last_submission": dict(self._last_submission_result),
            "last_generation": dict(self._last_generation_result),
            "events": list(self._events),
        }


__all__ = [
    "AtlasFAB",
    "AtlasFABConfig",
    "AtlasFABError",
    "AtlasGenerationReport",
    "AtlasLessonSnapshot",
    "AtlasProgressSnapshot",
    "AtlasRuntimeSnapshot",
    "AtlasSubmissionReport",
    "AtlasUsageSnapshot",
    "PRODUCT_SURFACE",
    "SDK_CONTRACT_VERSION",
]
