import asyncio
import io
import json

import pytest
from fastapi import UploadFile

import api_server
from mammoth_os.document_review import DocumentReviews
from mammoth_os.documents import DocumentError, DocumentLibrary
from mammoth_os.llm_completion import Completion


@pytest.fixture
def reviews(tmp_path):
    library = DocumentLibrary(tmp_path / "documents", {"chat": tmp_path / "old-chat", "atlas": tmp_path / "old-atlas"})
    asyncio.run(library.upload(UploadFile(filename="source.txt", file=io.BytesIO(
        ("BEGIN_SENTINEL " + "A source explanation. " * 330 + " END_SENTINEL").encode())), "chat"))
    return DocumentReviews(library)


class Model:
    model = "fixture"

    def __init__(self):
        self.indices = []
        self.texts = []

    async def generate_completion(self, prompt, **kwargs):
        source = json.loads(prompt.split("\n", 1)[1])
        self.indices.append(source["chunk_index"])
        self.texts.append(source["text"])
        return Completion(json.dumps({
            "summary": "A bounded section assessment.", "quote": source["text"][:80],
        }), finish_reason="stop", usage={"total_tokens": 100}, model=self.model)


def create(reviews):
    return reviews.create("chat", reviews.library.list("chat")[0]["file_id"], "Check the explanation and late appendix.")


def test_durable_review_reaches_every_section_once_and_preserves_quote_provenance(reviews):
    state = create(reviews)
    assert state["status"] == "ready" and not state["review_complete"]
    model = Model()
    state = asyncio.run(reviews.advance(state["id"], lambda: model))
    assert state["status"] == "partial"
    assert len(state["assessments"]) == 3
    store = DocumentReviews(DocumentLibrary(reviews.library.folder, reviews.library.legacy_folders))
    while state["status"] == "partial":
        state = asyncio.run(store.advance(state["id"], lambda: model))
    assert state["status"] == "completed" and state["review_complete"]
    assert model.indices == list(range(state["total_sections"]))
    assert "END_SENTINEL" in model.texts[-1]
    assert state["usage"]["tokens"] == 100 * len(model.indices)
    assert "BEGIN_SENTINEL" in state["assessments"][0]["quote"]
    assert all(item["source_sha256"] == state["source_sha256"] for item in state["assessments"])
    assert state["coverage_basis"] == "indexed_sections_not_original_file_or_factual_verification"
    assert all(item["quality"]["fact_verification"] == "not_performed" for item in state["assessments"])
    with pytest.raises(DocumentError) as error:
        asyncio.run(store.advance(state["id"], lambda: model))
    assert error.value.status_code == 409
    assert model.indices == list(range(state["total_sections"]))


def test_partial_extraction_warnings_do_not_become_full_original_review(reviews):
    state = create(reviews)
    # Persist a source extraction warning exactly as an extractor would.
    with reviews.library._connect() as connection:
        entry = reviews.library.list("chat")[0]
        entry.update(warnings=["Scanned appendix unavailable."], processing_status="partial")
        connection.execute("UPDATE files SET payload=? WHERE file_id=?", (json.dumps(entry), entry["file_id"]))
    state = create(reviews)
    assert state["warnings"] == ["Scanned appendix unavailable."]
    assert state["extraction_status"] == "partial"
    assert not state["review_complete"]


@pytest.mark.parametrize("kind", ["missing_usage", "invalid_quote", "output_limit", "provider_error"])
def test_failed_calls_block_without_marking_section_assessed_or_replaying(reviews, kind):
    class Broken:
        model = "fixture"
        calls = 0

        async def generate_completion(self, prompt, **kwargs):
            self.calls += 1
            if kind == "provider_error":
                raise RuntimeError("PRIVATE_PROVIDER_ERROR")
            return Completion(json.dumps({"summary": "A summary.", "quote": "NOT_IN_SOURCE"}),
                              finish_reason="length" if kind == "output_limit" else "stop",
                              usage={} if kind == "missing_usage" else {"total_tokens": 100})

    model = Broken()
    review_id = create(reviews)["id"]
    if kind == "provider_error":
        with pytest.raises(RuntimeError, match="PRIVATE_PROVIDER_ERROR"):
            asyncio.run(reviews.advance(review_id, lambda: model))
        state = reviews.get(review_id)
    else:
        state = asyncio.run(reviews.advance(review_id, lambda: model))
    assert state["status"] == "blocked" and not state["review_complete"]
    assert state["assessments"] == []
    assert "PRIVATE_PROVIDER_ERROR" not in str(state)
    with pytest.raises(DocumentError):
        asyncio.run(reviews.advance(state["id"], lambda: model))
    assert model.calls == 1


def test_concurrent_batch_is_rejected_and_cancelled_unknown_call_is_not_replayed(reviews):
    started = asyncio.Event()
    wait = asyncio.Event()

    class Waiting:
        model = "fixture"

        async def generate_completion(self, prompt, **kwargs):
            started.set()
            await wait.wait()

    review_id = create(reviews)["id"]

    async def exercise():
        task = asyncio.create_task(reviews.advance(review_id, Waiting))
        await started.wait()
        with pytest.raises(DocumentError) as error:
            await reviews.advance(review_id, Model)
        assert error.value.status_code == 409
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(exercise())
    state = reviews.get(review_id)
    assert state["status"] == "blocked"
    assert state["stop_reason"] == "provider_outcome_unknown"
    assert state["assessments"] == []


def test_source_changed_before_resume_blocks_with_saved_work_intact(reviews):
    model = Model()
    state = asyncio.run(reviews.advance(create(reviews)["id"], lambda: model))
    entry = reviews.library.list("chat")[0]
    from pathlib import Path
    path = Path(entry["chunks_path"])
    chunks = json.loads(path.read_text(encoding="utf-8"))
    chunks[-1]["text"] += "Changed."
    path.write_text(json.dumps(chunks), encoding="utf-8")
    resumed = asyncio.run(reviews.advance(state["id"], lambda: model))
    assert resumed["status"] == "blocked" and resumed["stop_reason"] == "source_changed"
    assert len(resumed["assessments"]) == 3 and model.indices == [0, 1, 2]


def test_source_delete_purges_reviews_and_inflight_call_cannot_resurrect_them(reviews):
    state = create(reviews)

    class Deleting(Model):
        async def generate_completion(self, prompt, **kwargs):
            result = await super().generate_completion(prompt, **kwargs)
            reviews.library.delete("chat", state["file_id"])
            return result

    with pytest.raises(DocumentError):
        asyncio.run(reviews.advance(state["id"], Deleting))
    with pytest.raises(DocumentError) as error:
        reviews.get(state["id"])
    assert error.value.status_code == 404


def test_saved_review_routes_enforce_scope_user_and_explicit_paid_confirmation(reviews, monkeypatch, tmp_path):
    other = DocumentReviews(DocumentLibrary(tmp_path / "other", {"chat": tmp_path / "other-old"}))
    active = [reviews]
    monkeypatch.setattr(api_server, "_document_reviews", lambda: active[0])
    state = create(reviews)
    assert asyncio.run(api_server.document_review_get(state["id"]))["review"]["status"] == "ready"
    assert asyncio.run(api_server.document_review_advance(state["id"], {})).status_code == 400
    assert asyncio.run(api_server.document_review_list(state["file_id"], "atlas")).status_code == 404
    active[0] = other
    assert asyncio.run(api_server.document_review_get(state["id"])).status_code == 404
    assert asyncio.run(api_server.document_review_delete(state["id"])).status_code == 404


def test_budget_stop_keeps_completed_sections_and_never_raises_the_cap(reviews):
    state = create(reviews)
    state["usage"]["tokens"] = 63_999
    reviews._save(state)
    model = Model()
    state = asyncio.run(reviews.advance(state["id"], lambda: model))
    assert state["status"] == "blocked"
    assert state["stop_reason"] == "insufficient_call_allowance"
    assert state["max_tokens"] == 64_000
    assert state["usage"]["tokens"] == 63_999
    assert model.indices == []


def test_restart_with_unknown_active_call_remains_non_replayable(reviews):
    state = create(reviews)
    state.update(status="active", inflight_section=0)
    reviews._save(state)
    reloaded = DocumentReviews(DocumentLibrary(reviews.library.folder, reviews.library.legacy_folders))
    model = Model()
    with pytest.raises(DocumentError) as error:
        asyncio.run(reloaded.advance(state["id"], lambda: model))
    assert error.value.status_code == 409
    assert model.indices == []
    assert reloaded.get(state["id"])["inflight_section"] == 0


def test_source_change_during_call_cannot_commit_a_stale_assessment(reviews):
    state = create(reviews)
    entry = reviews.library.list("chat")[0]
    from pathlib import Path

    class Changing(Model):
        async def generate_completion(self, prompt, **kwargs):
            result = await super().generate_completion(prompt, **kwargs)
            path = Path(entry["chunks_path"])
            chunks = json.loads(path.read_text(encoding="utf-8"))
            chunks[0]["text"] += "Changed."
            path.write_text(json.dumps(chunks), encoding="utf-8")
            return result

    state = asyncio.run(reviews.advance(state["id"], Changing))
    assert state["status"] == "blocked" and state["stop_reason"] == "source_changed"
    assert state["usage"]["tokens"] == 100
    assert state["assessments"] == []


def test_reported_token_overrun_is_retained_and_never_certifies_completion(reviews):
    class Expensive(Model):
        async def generate_completion(self, prompt, **kwargs):
            result = await super().generate_completion(prompt, **kwargs)
            return Completion(result.text, finish_reason="stop", usage={"total_tokens": 64_001})

    state = asyncio.run(reviews.advance(create(reviews)["id"], Expensive))
    assert state["status"] == "blocked" and not state["review_complete"]
    assert state["usage"]["tokens"] == 64_001
    assert state["stop_reason"] == "reported_token_limit"
    assert len(state["assessments"]) == 1


def test_retention_quota_is_explicit_and_delete_frees_one_slot(reviews):
    for _ in range(20):
        state = create(reviews)
    with pytest.raises(DocumentError, match="limit"):
        create(reviews)
    reviews.delete(state["id"])
    assert create(reviews)["status"] == "ready"


def test_delete_review_frees_quota_without_deleting_source(reviews):
    state = create(reviews)
    assert reviews.list("chat", state["file_id"])
    reviews.delete(state["id"])
    assert reviews.list("chat", state["file_id"]) == []
    assert reviews.library.list("chat")


@pytest.mark.parametrize("scope,goal", [([], "Review"), ("other", "Review"), ("chat", ""),
                                      ("chat", "x" * 1001), ("chat", None)])
def test_invalid_create_input_is_explicit_and_never_creates_work(reviews, scope, goal):
    with pytest.raises(DocumentError) as error:
        reviews.create(scope, reviews.library.list("chat")[0]["file_id"], goal)
    assert error.value.status_code == 400
    assert reviews.list("chat", reviews.library.list("chat")[0]["file_id"]) == []
