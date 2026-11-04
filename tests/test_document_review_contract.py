"""Both clients consume the same malformed-state matrix without paid retries."""

import asyncio
import copy
import json
from pathlib import Path

import pytest

from mammoth_os.paths.document_review import validate_document_review
from mammoth_os import MammothPaths, PathsError
from test_mammoth_paths_sdk import backend  # noqa: F401
from test_document_review import reviews, Model, SynthesisModel  # noqa: F401

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "document-review-contract.json").read_text())


@pytest.mark.parametrize("case", FIXTURE["invalid"], ids=lambda case: case["name"])
def test_nested_review_contract_rejects_malformed_evidence(case):
    review = copy.deepcopy(FIXTURE["review"])
    target = review
    for key in case["path"][:-1]:
        target = target[key]
    target[case["path"][-1]] = case["value"]
    with pytest.raises(ValueError, match="Invalid saved document review"):
        validate_document_review(review)


def test_valid_review_states_preserve_additions_unknown_work_and_overrun():
    review = copy.deepcopy(FIXTURE["review"])
    assert validate_document_review(review) is review
    review.update(status="blocked", review_complete=False, synthesis=None)
    review["usage"]["tokens"] = 130000
    assert validate_document_review(review) is review
    review.update(status="active", inflight_section=0, assessments=[])
    assert validate_document_review(review) is review
    review.update(status="ready", inflight_section=None)
    assert validate_document_review(review) is review
    review.update(status="completed", review_complete=True, assessments=copy.deepcopy(FIXTURE["review"]["assessments"]),
                  synthesis=copy.deepcopy(FIXTURE["review"]["synthesis"]), inflight_section="synthesis")
    review["synthesis"]["status"] = "blocked"
    assert validate_document_review(review) is review
    review.update(max_tokens=128000, budget_extensions=[{
        "previous_max_tokens": 64000, "max_tokens": 128000, "reported_tokens": 200, "confirmed_at": "t",
    }])
    assert validate_document_review(review) is review
    review["budget_extensions"][0]["reported_tokens"] = True
    with pytest.raises(ValueError):
        validate_document_review(review)

@pytest.mark.parametrize("case", FIXTURE["invalid_node"], ids=lambda case: case["name"])
def test_synthesis_node_contract(case):
    review = copy.deepcopy(FIXTURE["review"])
    node = copy.deepcopy(FIXTURE["node"])
    review["synthesis"].update(status="completed", nodes=[node], result=copy.deepcopy(node))
    assert validate_document_review(review) is review
    target = node
    for key in case["path"][:-1]:
        target = target[key]
    target[case["path"][-1]] = case["value"]
    with pytest.raises(ValueError):
        validate_document_review(review)


def test_real_hierarchical_checkpoints_validate_even_during_writes(reviews, monkeypatch):  # noqa: F811
    entry = reviews.library.list("chat")[0]
    Path(entry["chunks_path"]).write_text(json.dumps([
        {"text": f"Original section {index}.", "location": f"section {index}"} for index in range(65)
    ]), encoding="utf-8")
    save = reviews._save
    def checked_save(state):
        validate_document_review(state)
        save(state)
    monkeypatch.setattr(reviews, "_save", checked_save)
    state = reviews.create("chat", entry["file_id"], "Assess every indexed section.")
    validate_document_review(state)
    while not state["review_complete"]:
        state = asyncio.run(reviews.advance(state["id"], Model))
    synthesis = SynthesisModel()
    while not state.get("synthesis", {}).get("result"):
        state = asyncio.run(reviews.synthesize(state["id"], lambda: synthesis))
    assert len(synthesis.groups) == 12
    assert validate_document_review(state) is state


def test_review_methods_guard_all_envelopes_identity_and_never_repeat_paid_post(backend):  # noqa: F811
    review = FIXTURE["review"]
    client = MammothPaths(backend.url)
    path = f"/api/mammoth/document-reviews/{review['id']}"
    backend.route("POST", path + "/advance", body={"review": {"private": "private-body-sentinel"}})
    with pytest.raises(PathsError) as error:
        client.advance_document_review(review["id"], confirm_model_usage=True)
    assert error.value.code == "invalid_response" and error.value.payload == {}
    assert "private-body-sentinel" not in str(error.value)
    assert len(backend.requests) == 1
    backend.route("GET", path, body={"review": review})
    assert client.get_document_review(review["id"])["review"] == review
    backend.route("GET", "/api/mammoth/document-reviews", body={"reviews": [review]})
    with pytest.raises(PathsError, match="invalid_response"):
        client.list_document_reviews("wrong-file", scope="atlas")
    backend.route("GET", path, body={"review": {**review, "id": "review-" + "c" * 24}})
    with pytest.raises(PathsError, match="invalid_response"):
        client.get_document_review(review["id"])
    backend.route("DELETE", path, body={"deleted": "wrong-id"})
    with pytest.raises(PathsError, match="invalid_response"):
        client.delete_document_review(review["id"])
    backend.route("GET", "/api/mammoth/document-reviews", body={"reviews": []})
    assert client.list_document_reviews("file-one")["reviews"] == []
