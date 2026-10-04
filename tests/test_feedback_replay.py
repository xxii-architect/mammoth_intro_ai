"""Thumbs-down replay tooling (mammoth.feedback.replay.v1)."""

import asyncio
import json

from mammoth_os import feedback_replay, message_feedback as fb


def _down(prompt, reply="bad", stamp="2025-01-01T00:00:00+00:00", reason="incorrect"):
    entry = {"message": reply, "adapter": "deepseek", "model": "deepseek-chat"}
    return fb.build_record(user_id="u", account_id="default", key=f"ts:{stamp}", direction="down", assistant_entry=entry, prompt=prompt, reason=reason, now=stamp)


def test_load_cases_accepts_store_case_list_and_api_payload():
    store = [_down("What is X?"), _down("what is   x?", stamp="2025-01-02T00:00:00+00:00")]
    from_store = feedback_replay.load_cases(store)
    assert len(from_store) == 1 and from_store[0]["reports"] == 2
    assert feedback_replay.load_cases(from_store) == from_store
    assert feedback_replay.load_cases({"cases": from_store}) == from_store


def test_replay_strips_reasoning_and_isolates_failures():
    cases = feedback_replay.load_cases([_down("good one"), _down("boom", stamp="2025-01-03T00:00:00+00:00")])

    async def generate(prompt):
        if prompt == "boom":
            raise RuntimeError("provider down")
        return "<think>hidden plan</think>Better answer."

    report = asyncio.run(feedback_replay.replay_cases(cases, generate))
    by_prompt = {row["prompt"]: row for row in report["cases"]}
    assert by_prompt["good one"]["status"] == "replayed"
    assert by_prompt["good one"]["new_reply"] == "Better answer."
    assert by_prompt["boom"]["status"] == "failed" and "provider down" in by_prompt["boom"]["error"]
    assert report["counts"] == {"replayed": 1, "failed": 1}


def test_replay_timeout_and_no_replay():
    cases = feedback_replay.load_cases([_down("slow")])

    async def slow(prompt):
        await asyncio.sleep(1)
        return "late"

    timed = asyncio.run(feedback_replay.replay_cases(cases, slow, timeout=0.01))
    assert timed["cases"][0]["status"] == "failed" and "timed out" in timed["cases"][0]["error"]
    listed = asyncio.run(feedback_replay.replay_cases(cases, None))
    assert listed["cases"][0]["status"] == "skipped"


def test_markdown_report_and_cli(tmp_path):
    source = tmp_path / "store.json"
    source.write_text(json.dumps([_down("Explain tides", reply="Wrong.")]), encoding="utf-8")
    out = tmp_path / "report.md"
    assert feedback_replay.main(["--input", str(source), "--no-replay", "--out", str(out)]) == 0
    text = out.read_text(encoding="utf-8")
    assert "# Thumbs-down replay" in text and "> Explain tides" in text and "> Wrong." in text
    assert "**New reply**" not in text

    out_json = tmp_path / "report.json"
    assert feedback_replay.main(["--input", str(source), "--no-replay", "--out", str(out_json)]) == 0
    assert json.loads(out_json.read_text(encoding="utf-8"))["contract_version"] == "mammoth.feedback.replay.v1"

    bad = tmp_path / "bad.json"
    bad.write_text("{nope", encoding="utf-8")
    assert feedback_replay.main(["--input", str(bad), "--no-replay"]) == 2
