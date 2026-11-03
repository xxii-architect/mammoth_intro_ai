import asyncio
from concurrent.futures import ThreadPoolExecutor
import sqlite3

import pytest

from mammoth_os.learning_controls import (
    LearningCancelled, LearningControls, LearningLimitReached,
    check_cancelled, operation_context,
)


def test_default_is_uncapped_and_counts_are_durable(tmp_path):
    path = tmp_path / "controls.sqlite3"
    store = LearningControls(path)
    assert store.snapshot()["daily_request_limit"] is None
    for _ in range(3):
        operation = store.begin("/api/atlas/chat", "default")
        store.finish(operation, "finished")
    fresh = LearningControls(path)
    assert fresh.snapshot()["admitted_requests"] == 3
    fresh.set_limit(2)
    with pytest.raises(LearningLimitReached):
        fresh.begin("/api/atlas/chat", "default")
    fresh.set_limit(None)
    fresh.begin("/api/atlas/chat", "default")
    assert fresh.snapshot()["admitted_requests"] == 4


@pytest.mark.parametrize("value", [True, -1, 1.5, "2", 100001])
def test_limits_reject_invalid_types_and_values(tmp_path, value):
    with pytest.raises(ValueError):
        LearningControls(tmp_path / "controls.sqlite3").set_limit(value)


def test_exact_cap_is_atomic_under_concurrent_admission(tmp_path):
    path = tmp_path / "controls.sqlite3"
    LearningControls(path).set_limit(5)

    def attempt(_):
        try:
            LearningControls(path).begin("/api/atlas/chat", "default")
            return 1
        except LearningLimitReached:
            return 0

    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(attempt, range(16))) == 5
    result = LearningControls(path).snapshot()
    assert result["admitted_requests"] == 5
    assert result["remaining_requests"] == 0
    assert len(result["operations"]) == 5


def test_utc_day_usage_does_not_consume_todays_allowance(tmp_path):
    store = LearningControls(tmp_path / "controls.sqlite3")
    store.set_limit(1)
    with sqlite3.connect(store.path) as db:
        db.execute("INSERT INTO usage VALUES ('2000-01-01',100)")
    store.begin("/api/atlas/chat", "default")
    assert store.snapshot()["admitted_requests"] == 1


def test_cancellation_reaches_thread_context_and_is_not_false_completion(tmp_path):
    store = LearningControls(tmp_path / "controls.sqlite3")
    operation = store.begin("/api/atlas/chat", "one")
    other = store.begin("/api/atlas/chat", "two")
    store.cancel_account("one")
    assert store.snapshot()["operations"][0]["finished_at"] is None
    assert store.is_cancelled(operation)
    assert not store.is_cancelled(other)

    async def run():
        with operation_context(store, other):
            await asyncio.to_thread(check_cancelled)
        with pytest.raises(LearningCancelled):
            with operation_context(store, operation):
                await asyncio.to_thread(check_cancelled)

    asyncio.run(run())
    store.finish(operation, "cancelled_at_boundary")
    assert store.cancel(operation) == "cancelled_at_boundary"
    check_cancelled()
    with pytest.raises(LookupError):
        store.cancel("unknown")


def test_cancelled_context_stops_provider_fallback(tmp_path):
    from mammoth_os.llm_client import FallbackAdapter

    store = LearningControls(tmp_path / "controls.sqlite3")
    operation = store.begin("/api/atlas/chat", "default")
    calls = []

    class Primary:
        async def generate(self, prompt, **kwargs):
            calls.append("primary")
            store.cancel(operation)
            raise RuntimeError("429 insufficient_quota")

    class Fallback:
        async def generate(self, prompt, **kwargs):
            calls.append("fallback")
            return "Not expected"

    client = FallbackAdapter(primary=Primary(), fallback=Fallback(),
                             primary_name="primary", fallback_name="fallback")

    async def run():
        with operation_context(store, operation):
            with pytest.raises(LearningCancelled):
                await client.generate("test")

    asyncio.run(run())
    assert calls == ["primary"]


def test_cancelled_successful_model_result_is_discarded(tmp_path, monkeypatch):
    from mammoth_os import llm_client

    store = LearningControls(tmp_path / "controls.sqlite3")
    operation = store.begin("/api/atlas/chat", "default")
    calls = []

    class Client:
        async def generate(self, prompt, **kwargs):
            calls.append(prompt)
            store.cancel(operation)
            return "A result from work already sent."

    monkeypatch.setattr(llm_client, "_resolve_llm_client", lambda config: Client())

    async def run():
        with operation_context(store, operation):
            with pytest.raises(LearningCancelled):
                await llm_client.get_llm_client().generate("Original prompt")

    asyncio.run(run())
    assert calls == ["Original prompt"]
