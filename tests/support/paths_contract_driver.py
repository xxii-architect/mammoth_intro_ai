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
token = "tenant-b"
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
try:
    client.run("Anonymous")
except PathsError as error:
    assert error.status == 401
else:
    raise AssertionError("Anonymous request succeeded")
print(json.dumps({"context_run": result.run_id, "cancelled_run": cancelled.run_id}))
