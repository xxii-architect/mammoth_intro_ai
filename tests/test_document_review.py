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


def assessed(reviews, sections=4):
    entry = reviews.library.list("chat")[0]
    from pathlib import Path
    chunks = [{"text": f"Original section {index}.", "location": f"section {index}"} for index in range(sections)]
    Path(entry["chunks_path"]).write_text(json.dumps(chunks), encoding="utf-8")
    state = create(reviews)
    state.update(status="completed", review_complete=True, assessments=[
        {"chunk_index": index, "summary": f"Assessment {index}.", "quote": chunk["text"],
         "location": chunk["location"], "source_sha256": state["source_sha256"]}
        for index, chunk in enumerate(chunks)])
    reviews._save(state)
    return state


class SynthesisModel:
    model = "synthesis-fixture"

    def __init__(self):
        self.groups = []

    async def generate_completion(self, prompt, **kwargs):
        source = json.loads(prompt.split("\n", 1)[1])
        self.groups.append(source["section_indices"])
        assert all("reasoning_trace" not in item for item in source["evidence"])
        return Completion(json.dumps({"summary": "A combined assessment with limitations.",
                                      "citations": source["section_indices"][:2]}),
                          finish_reason="stop", usage={"total_tokens": 100}, model=self.model)


def test_synthesis_traverses_every_assessment_with_checkpointed_hierarchical_resume(reviews):
    state = assessed(reviews, 65)
    model = SynthesisModel()
    state = asyncio.run(reviews.synthesize(state["id"], lambda: model))
    assert state["synthesis"]["status"] == "partial" and len(model.groups) == 3
    assert state["usage"]["tokens"] == 300
    store = DocumentReviews(reviews.library)
    while state["synthesis"]["status"] == "partial":
        state = asyncio.run(store.synthesize(state["id"], lambda: model))
    synthesis = state["synthesis"]
    assert synthesis["status"] == "completed"
    assert synthesis["result"]["section_indices"] == list(range(65))
    assert synthesis["basis"] == "saved_assessments_not_full_source"
    assert synthesis["fact_verification"] == "not_performed"
    assert len(model.groups) == 12  # 9 leaf groups, 2 intermediate groups, 1 final.
    assert [index for group in model.groups[:9] for index in group] == list(range(65))
    assert synthesis["levels"][0][-1]["section_indices"] == [64]
    assert state["usage"]["tokens"] == 1200
    assert store.get(state["id"])["synthesis"] == synthesis
    with pytest.raises(DocumentError):
        asyncio.run(store.synthesize(state["id"], lambda: model))
    assert len(model.groups) == 12


@pytest.mark.parametrize("kind", ["bad_citation", "bool_citation", "empty_citations", "missing_usage", "length", "invalid_json"])
def test_invalid_synthesis_is_blocked_without_replaying_paid_work(reviews, kind):
    state = assessed(reviews)

    class Broken(SynthesisModel):
        async def generate_completion(self, prompt, **kwargs):
            await super().generate_completion(prompt, **kwargs)
            citations = {"bad_citation": [999], "bool_citation": [True], "empty_citations": []}.get(kind, [0])
            return Completion("not json" if kind == "invalid_json" else json.dumps(
                {"summary": "Combined assessment.", "citations": citations}),
                finish_reason="length" if kind == "length" else "stop",
                usage={} if kind == "missing_usage" else {"total_tokens": 100})

    model = Broken()
    state = asyncio.run(reviews.synthesize(state["id"], lambda: model))
    assert state["synthesis"]["status"] == "blocked" and state["synthesis"]["result"] is None
    assert state["usage"]["tokens"] == (0 if kind == "missing_usage" else 100)
    with pytest.raises(DocumentError):
        asyncio.run(reviews.synthesize(state["id"], lambda: model))
    with pytest.raises(DocumentError):
        reviews.extend_budget(state["id"], 64_000, 128_000)
    assert len(model.groups) == 1


def test_synthesis_requires_complete_unchanged_source(reviews):
    state = create(reviews)
    with pytest.raises(DocumentError):
        asyncio.run(reviews.synthesize(state["id"], SynthesisModel))
    state = assessed(reviews)
    from pathlib import Path
    Path(reviews.library.list("chat")[0]["chunks_path"]).write_text("[]", encoding="utf-8")
    state = asyncio.run(reviews.synthesize(state["id"], SynthesisModel))
    assert state["synthesis"]["stop_reason"] == "source_changed"
    with pytest.raises(DocumentError):
        reviews.extend_budget(state["id"], 64_000, 128_000)


def test_concurrent_synthesis_and_cancelled_unknown_call_cannot_be_unlocked(reviews):
    state = assessed(reviews)
    started, wait = asyncio.Event(), asyncio.Event()

    class Waiting(SynthesisModel):
        async def generate_completion(self, *args, **kwargs):
            started.set()
            await wait.wait()

    async def exercise():
        task = asyncio.create_task(reviews.synthesize(state["id"], Waiting))
        await started.wait()
        with pytest.raises(DocumentError):
            await reviews.synthesize(state["id"], Waiting)
        with pytest.raises(DocumentError):
            reviews.extend_budget(state["id"], 64_000, 128_000)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(exercise())
    state = reviews.get(state["id"])
    assert state["synthesis"]["stop_reason"] == "provider_outcome_unknown"
    assert state["inflight_section"] == "synthesis"
    with pytest.raises(DocumentError):
        reviews.extend_budget(state["id"], 64_000, 128_000)


def test_budget_extension_is_compare_and_set_keeps_usage_and_resumes_only_known_cap_stop(reviews):
    state = create(reviews)
    state["usage"]["tokens"] = 63_999
    reviews._save(state)
    state = asyncio.run(reviews.advance(state["id"], Model))
    assert state["stop_reason"] == "insufficient_call_allowance"
    state = reviews.extend_budget(state["id"], 64_000, 100_000)
    assert state["usage"]["tokens"] == 63_999
    assert state["status"] == "partial" and state["max_tokens"] == 100_000
    assert state["budget_extensions"][0]["previous_max_tokens"] == 64_000
    with pytest.raises(DocumentError) as error:
        reviews.extend_budget(state["id"], 64_000, 128_000)
    assert error.value.status_code == 409
    state = asyncio.run(reviews.advance(state["id"], Model))
    assert state["usage"]["tokens"] > 63_999
    assert len(state["assessments"]) == 3


@pytest.mark.parametrize("old,new", [(True, 128_000), (64_000, "128000"), (64_000, 128_001),
                                    (64_000, 64_000), (64_000, 32_000), (64_000, 100_000.0)])
def test_invalid_budget_ceiling_never_changes_saved_state(reviews, old, new):
    state = create(reviews)
    with pytest.raises(DocumentError) as error:
        reviews.extend_budget(state["id"], old, new)
    assert error.value.status_code == 400
    assert reviews.get(state["id"]) == state


def test_synthesis_budget_extension_recovers_checkpoint_without_resubmitting_units(reviews):
    state = assessed(reviews, 65)
    state["usage"]["tokens"] = 63_999
    reviews._save(state)
    model = SynthesisModel()
    state = asyncio.run(reviews.synthesize(state["id"], lambda: model))
    assert state["synthesis"]["stop_reason"] == "insufficient_call_allowance" and not model.groups
    state = reviews.extend_budget(state["id"], 64_000, 128_000)
    assert state["synthesis"]["status"] == "partial" and state["usage"]["tokens"] == 63_999
    state = asyncio.run(reviews.synthesize(state["id"], lambda: model))
    assert len(model.groups) == 3 and state["usage"]["tokens"] == 64_299


def test_concurrent_budget_confirmations_accept_exactly_one_without_lost_history(reviews):
    from concurrent.futures import ThreadPoolExecutor
    state = create(reviews)

    def extend(ceiling):
        try:
            reviews.extend_budget(state["id"], 64_000, ceiling)
            return 200
        except DocumentError as exc:
            return exc.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(extend, [100_000, 128_000])) == [200, 409]
    saved = reviews.get(state["id"])
    assert len(saved["budget_extensions"]) == 1
    assert saved["usage"]["tokens"] == 0


def test_legacy_record_gains_current_limit_metadata_without_model_calls(reviews):
    state = create(reviews)
    state.pop("max_extended_tokens")
    with reviews.library._connect() as connection, connection:
        connection.execute("UPDATE document_reviews SET payload=? WHERE id=?", (json.dumps(state), state["id"]))
    assert reviews.get(state["id"])["max_extended_tokens"] == 128_000
    assert reviews.list("chat", state["file_id"])[0]["max_extended_tokens"] == 128_000
    state = reviews.extend_budget(state["id"], 64_000, 100_000)
    assert state["max_extended_tokens"] == 128_000 and state["usage"]["tokens"] == 0


def test_intermediate_citations_cannot_invent_lineage_from_uncited_child_sections(reviews):
    state = assessed(reviews, 9)

    class BadLineage(SynthesisModel):
        async def generate_completion(self, prompt, **kwargs):
            source = json.loads(prompt.split("\n", 1)[1])
            self.groups.append(source["section_indices"])
            citations = [source["section_indices"][-1]] if len(self.groups) < 3 else [0]
            return Completion(json.dumps({"summary": "A combined assessment.", "citations": citations}),
                              finish_reason="stop", usage={"total_tokens": 100})

    model = BadLineage()
    state = asyncio.run(reviews.synthesize(state["id"], lambda: model))
    assert state["synthesis"]["status"] == "blocked"
    assert state["synthesis"]["stop_reason"] == "invalid_synthesis"
    assert state["synthesis"]["result"] is None
    assert len(state["synthesis"]["levels"][0]) == 2
    assert state["usage"]["tokens"] == 300


def test_synthesis_overrun_checkpoint_finishes_after_extension_without_new_model_call(reviews):
    state = assessed(reviews)

    class Expensive(SynthesisModel):
        async def generate_completion(self, prompt, **kwargs):
            result = await super().generate_completion(prompt, **kwargs)
            return Completion(result.text, finish_reason="stop", usage={"total_tokens": 64_001})

    model = Expensive()
    state = asyncio.run(reviews.synthesize(state["id"], lambda: model))
    assert state["synthesis"]["status"] == "blocked" and state["synthesis"]["stop_reason"] == "reported_token_limit"
    state = reviews.extend_budget(state["id"], 64_000, 128_000)
    assert state["synthesis"]["status"] == "completed" and len(model.groups) == 1
    assert state["usage"]["tokens"] == 64_001


def test_synthesis_deletion_during_call_cannot_resurrect_saved_work(reviews):
    state = assessed(reviews)

    class Deleting(SynthesisModel):
        async def generate_completion(self, prompt, **kwargs):
            result = await super().generate_completion(prompt, **kwargs)
            reviews.library.delete("chat", state["file_id"])
            return result

    with pytest.raises(DocumentError):
        asyncio.run(reviews.synthesize(state["id"], Deleting))
    with pytest.raises(DocumentError):
        reviews.get(state["id"])


def test_synthesis_source_mutation_during_call_retains_usage_but_no_stale_result(reviews):
    state = assessed(reviews)

    class Changing(SynthesisModel):
        async def generate_completion(self, prompt, **kwargs):
            result = await super().generate_completion(prompt, **kwargs)
            from pathlib import Path
            Path(reviews.library.list("chat")[0]["chunks_path"]).write_text("[]", encoding="utf-8")
            return result

    state = asyncio.run(reviews.synthesize(state["id"], Changing))
    assert state["usage"]["tokens"] == 100
    assert state["synthesis"]["stop_reason"] == "source_changed"
    assert state["synthesis"]["nodes"] == [] and state["synthesis"]["result"] is None


def test_new_routes_require_confirmation_and_successful_audit_before_work(reviews, monkeypatch):
    state = assessed(reviews)
    monkeypatch.setattr(api_server, "_document_reviews", lambda: reviews)
    assert asyncio.run(api_server.document_review_synthesize(state["id"], {})).status_code == 400
    assert asyncio.run(api_server.document_review_extend_budget(state["id"], {})).status_code == 400

    def failed_audit(**kwargs):
        raise RuntimeError("Audit unavailable")

    monkeypatch.setattr(api_server, "_append_audit_event", failed_audit)
    for action in [
        api_server.document_review_synthesize(state["id"], {"confirm_model_usage": True}),
        api_server.document_review_extend_budget(state["id"], {
            "confirm_budget_extension": True, "expected_max_tokens": 64_000, "max_tokens": 128_000}),
    ]:
        with pytest.raises(RuntimeError, match="Audit unavailable"):
            asyncio.run(action)
    assert reviews.get(state["id"]) == state


def test_capability_surfaces_use_canonical_synthesis_and_extension_limits(monkeypatch):
    from mammoth_os.document_review import capability
    from mammoth_os.agent_loop import ToolContext
    expected = capability()
    monkeypatch.setattr(api_server, "_current_request_user_id", lambda: "reader")
    assert expected["max_extended_tokens"] == 128_000 and expected["synthesis_group_size"] == 8
    assert api_server._guide_platform_status(ToolContext(user_id="reader"))["document_review"] == expected


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
