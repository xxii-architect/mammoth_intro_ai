"""Exercise the installed wheel through the loopback loaded-API test bridge."""

import json
import sys

sys.path.insert(0, sys.argv[2])

from mammoth_os import MammothPaths, PathsError
import mammoth_os.paths.client

assert sys.argv[2] in mammoth_os.paths.client.__file__
token = "tenant-a"
client = MammothPaths(sys.argv[1], token_provider=lambda: token)
result = client.run(
    "Review the context", surface="agent_workspace", task="analyze_codebase",
    history=[{"role": "user", "text": "Prior workspace turn"}, {"role": "assistant", "message": "Prior answer"}],
    attached_file_ids=["fixture-file"], thread_id="must-not-persist-to-mind",
)
assert result.status == "completed" and result.reply == "Context received."
assert result.events[0].data["repo"] is None
assert client.recover_run(result.run_id).status == "completed"
file_id = sys.argv[3]
start, indices, source = 0, [], ""
while True:
    page = client.read_document(file_id, start=start, count=2)
    assert page["selection"]["review_complete"] is False
    indices.extend(section["chunk_index"] for section in page["sections"])
    source += page["text"]
    if page["next_start"] is None:
        break
    start = page["next_start"]
assert indices == list(range(page["total_chunks"]))
assert "BEGIN_SOURCE" in source and "END_SOURCE" in source
review = client.create_document_review(file_id, "Assess all indexed sections.")["review"]
assert review["status"] == "ready" and review["usage"]["tokens"] == 0
assert client.get_document_review(review["id"])["review"]["assessments"] == []
while review["status"] in {"ready", "partial"}:
    review = client.advance_document_review(review["id"], confirm_model_usage=True)["review"]
assert review["status"] == "completed" and review["review_complete"]
assert [item["chunk_index"] for item in review["assessments"]] == list(range(review["total_sections"]))
assert client.list_document_reviews(file_id)["reviews"][0]["id"] == review["id"]
before = review["usage"]["tokens"]
review = client.extend_document_review_budget(review["id"], expected_max_tokens=64000, max_tokens=128000,
                                              confirm_budget_extension=True)["review"]
assert review["usage"]["tokens"] == before and review["max_tokens"] == 128000
review = client.synthesize_document_review(review["id"], confirm_model_usage=True)["review"]
while review["synthesis"]["status"] == "partial":
    review = client.synthesize_document_review(review["id"], confirm_model_usage=True)["review"]
assert review["synthesis"]["status"] == "completed"
assert review["synthesis"]["result"]["section_indices"] == list(range(review["total_sections"]))
assert client.get_document_review(review["id"])["review"]["synthesis"] == review["synthesis"]
for options, status in [({"count": 11}, 400), ({"scope": "atlas"}, 404)]:
    try:
        client.read_document(file_id, **options)
    except PathsError as error:
        assert error.status == status
    else:
        raise AssertionError("Invalid document page or scope succeeded")
token = "tenant-b"
for action in [
    lambda: client.synthesize_document_review(review["id"], confirm_model_usage=True),
    lambda: client.extend_document_review_budget(review["id"], expected_max_tokens=64000, max_tokens=128000,
                                                 confirm_budget_extension=True),
]:
    try:
        action()
    except PathsError as error:
        assert error.status == 404
    else:
        raise AssertionError("Another tenant mutated this review")
try:
    client.get_document_review(review["id"])
except PathsError as error:
    assert error.status == 404
else:
    raise AssertionError("Another tenant read this review")
try:
    client.read_document(file_id)
except PathsError as error:
    assert error.status == 404
else:
    raise AssertionError("Another tenant read this document")
try:
    client.get_run(result.run_id)
except PathsError as error:
    assert error.status == 404
else:
    raise AssertionError("Another tenant read this run")
token = "tenant-a"
try:
    client.run("Read platform", repo="platform", surface="agent_workspace")
except PathsError as error:
    assert error.status == 403 and error.code == "repo_access_denied"
    assert error.payload["message"] == error.message
else:
    raise AssertionError("Tenant accessed platform repo")
pending = client.run("Review first", surface="agent_workspace", approval_mode="always")
assert pending.status == "awaiting_approval"
approved = list(client.decide(pending.run_id, pending.pending_approval["id"], "approve"))
assert approved[-1].type == "run.completed"
cancelled = client.run("Do not execute", surface="agent_workspace", approval_mode="always")
assert cancelled.status == "awaiting_approval"
client.cancel_run(cancelled.run_id)
assert client.recover_run(cancelled.run_id).status == "cancelled"
token = None
for action in [
    lambda: client.synthesize_document_review(review["id"], confirm_model_usage=True),
    lambda: client.extend_document_review_budget(review["id"], expected_max_tokens=64000, max_tokens=128000,
                                                 confirm_budget_extension=True),
]:
    try:
        action()
    except PathsError as error:
        assert error.status == 401
    else:
        raise AssertionError("Anonymous review mutation succeeded")
try:
    client.get_document_review(review["id"])
except PathsError as error:
    assert error.status == 401
else:
    raise AssertionError("Anonymous review read succeeded")
try:
    client.read_document(file_id)
except PathsError as error:
    assert error.status == 401
else:
    raise AssertionError("Anonymous document read succeeded")
try:
    client.run("Anonymous")
except PathsError as error:
    assert error.status == 401
else:
    raise AssertionError("Anonymous request succeeded")
print(json.dumps({"context_run": result.run_id, "cancelled_run": cancelled.run_id}))
