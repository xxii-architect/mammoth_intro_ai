"""cli/atlas.py — ATLAS tutor bot CLI commands

Registered under the `atlas` subcommand in cli/main.py.

Usage (after `pip install -e .` or via PYTHONPATH=src):
    python -m cli.main atlas lesson "Python for loops"
    python -m cli.main atlas status
    python -m cli.main atlas submit solution.py
    python -m cli.main atlas submit --inline "def solution(a, b): return a + b"
    python -m cli.main atlas next
    python -m cli.main atlas reset
"""
import argparse
import asyncio
import json
import os
import re
import sys
import urllib.parse
import urllib.request

# Ensure UTF-8 output on Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


# Default paths
_MAMMOTH_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), "..", ".mammoth")
_SESSION_STATE_FILE = os.path.join(_MAMMOTH_DIR, "atlas_cli_session.json")
_DEFAULT_USER = os.environ.get("ATLAS_USER_ID", "cli_user")


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _load_session():
    """Load the persisted ATLASSession (or a fresh idle one)."""
    try:
        from mammoth_os.atlas_session import ATLASSession
        session = ATLASSession.load_state(_SESSION_STATE_FILE)
        _ensure_user_id(session)
        return session
    except Exception as exc:
        print(f"❌ Could not load ATLASSession: {exc}", file=sys.stderr)
        sys.exit(1)


def _is_uuid(value: str) -> bool:
    return bool(re.match(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
        str(value or ""),
        re.IGNORECASE,
    ))


def _resolve_user_id_from_supabase() -> str | None:
    """Resolve ATLAS user UUID from public.profiles using Supabase REST API.

    Uses SUPABASE_URL + SUPABASE_ANON_KEY (or service role key fallback).
    Optional ATLAS_USER_EMAIL narrows lookup to a specific profile email.
    """
    supabase_url = os.environ.get("SUPABASE_URL", "").strip()
    supabase_key = (
        os.environ.get("SUPABASE_ANON_KEY", "").strip()
        or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    )
    if not supabase_url or not supabase_key:
        return None

    email = os.environ.get("ATLAS_USER_EMAIL", "").strip()
    query_parts = ["select=id,email,full_name,role", "limit=1"]
    if email:
        query_parts.append(f"email=eq.{urllib.parse.quote(email, safe='')}")
    else:
        query_parts.append("order=created_at.desc")
    query = "&".join(query_parts)
    url = f"{supabase_url.rstrip('/')}/rest/v1/profiles?{query}"

    req = urllib.request.Request(
        url,
        headers={
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Accept": "application/json",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            body = resp.read().decode("utf-8")
        rows = json.loads(body)
    except Exception:
        return None

    if not isinstance(rows, list) or not rows:
        return None
    resolved = str(rows[0].get("id", "")).strip()
    if not _is_uuid(resolved):
        return None

    os.environ["ATLAS_USER_ID"] = resolved
    return resolved


def _ensure_user_id(session=None) -> str:
    """Ensure we have a stable ATLAS user id, auto-resolving if needed."""
    env_user = os.environ.get("ATLAS_USER_ID", "").strip()
    if _is_uuid(env_user):
        if session is not None:
            session.user_id = env_user
        return env_user

    if session is not None and _is_uuid(getattr(session, "user_id", "")):
        return session.user_id

    resolved = _resolve_user_id_from_supabase()
    if resolved:
        if session is not None:
            session.user_id = resolved
        return resolved

    fallback = env_user or _DEFAULT_USER
    if session is not None:
        session.user_id = fallback
    return fallback


def _save_session(session) -> None:
    """Persist the session to disk."""
    try:
        session.save_state(_SESSION_STATE_FILE)
    except Exception as exc:
        print(f"⚠️  Could not save session state: {exc}", file=sys.stderr)


def _divider():
    print("─" * 60)


# ─────────────────────────────────────────────────────────────────────────────
# Commands
# ─────────────────────────────────────────────────────────────────────────────

def cmd_atlas_lesson(args) -> None:
    """Start a new ATLAS lesson on a topic."""
    topic: str = " ".join(args.topic)  # supports multi-word topics without quotes
    if not topic.strip():
        print("❌ Please provide a topic. Example: atlas lesson Python for loops")
        sys.exit(1)

    from mammoth_os.atlas_session import ATLASSession
    session = ATLASSession(user_id=_ensure_user_id())

    print(f"\n🐘 ATLAS — Starting lesson on: {topic!r}")
    _divider()

    try:
        exercise = session.start_lesson(
            topic,
            module_idx=args.module,
            lesson_idx=args.lesson,
            use_llm=getattr(args, "llm", False),
            difficulty=getattr(args, "difficulty", "beginner"),
        )
    except Exception as exc:
        print(f"❌ Failed to generate lesson: {exc}", file=sys.stderr)
        sys.exit(1)

    _save_session(session)

    print(f"📚 Curriculum : {exercise['lesson']['title'].split('—')[0].strip()}")
    print(f"📖 Lesson     : {exercise['lesson']['title']}")
    print(f"🏋️  Exercise   : {exercise['title']}")
    _divider()
    print(f"\n{exercise['prompt']}\n")
    _divider()
    print("\n📄 Starter file(s):\n")
    for fname, content in exercise.get("starter_files", {}).items():
        print(f"  ── {fname} ──")
        for line in content.splitlines():
            print(f"    {line}")
    _divider()
    print(
        "\n💡 Write your solution in the starter file, then run:\n"
        f"   python -m cli.main atlas submit <your_solution.py>\n"
        f"   OR: python -m cli.main atlas submit --inline \"def solution(a, b): ...\"\n"
    )


def cmd_atlas_status(args) -> None:
    """Show the current ATLAS session state."""
    session = _load_session()
    s = session.status()

    print("\n🐘 ATLAS — Session Status")
    _divider()

    if s["state"] == "idle":
        print("💤 No active lesson.")
        print("   Start one with: python -m cli.main atlas lesson <topic>")
        return

    print(f"👤 User       : {s['user_id']}")
    print(f"📚 Curriculum : {s['curriculum_title']}")
    print(f"📖 Lesson     : {s['lesson_title']}")
    print(f"🏋️  Exercise   : {s['exercise_title']}")
    _divider()
    print(f"\n{s.get('exercise_prompt', '')}\n")
    _divider()
    starters = s.get("starter_files", {})
    if starters:
        print("\n📄 Starter file(s):\n")
        for fname, content in starters.items():
            print(f"  ── {fname} ──")
            for line in content.splitlines():
                print(f"    {line}")
    _divider()


def cmd_atlas_submit(args) -> None:
    """Submit a solution — from a file or inline code string."""
    session = _load_session()

    if session.current_exercise is None:
        print("❌ No active exercise. Start a lesson first:")
        print("   python -m cli.main atlas lesson <topic>")
        sys.exit(1)

    # Build the files dict from --inline or from a path argument
    files: dict = {}

    if args.inline:
        files["solution.py"] = args.inline
    elif args.file:
        path = args.file
        if not os.path.exists(path):
            print(f"❌ File not found: {path}")
            sys.exit(1)
        with open(path, "r", encoding="utf-8") as fh:
            files[os.path.basename(path)] = fh.read()
    else:
        print("❌ Provide a file path or use --inline \"<code>\"")
        sys.exit(1)

    print(f"\n🐘 ATLAS — Submitting solution…")
    _divider()

    try:
        result = asyncio.run(session.submit(files))
    except Exception as exc:
        print(f"❌ Submission error: {exc}", file=sys.stderr)
        sys.exit(1)

    _save_session(session)

    passed = result["passed"]
    rec = result["recommendation"]
    hint = result["hint"]

    status_icon = "✅ PASSED" if passed else "❌ FAILED"
    print(f"\n{status_icon}")
    print(f"\n💬 Hint: {hint}")
    _divider()

    # Difficulty recommendation
    rec_msg = {
        "increase": "🚀 You're ready for harder challenges! Use `atlas next` to advance.",
        "decrease": "🔄 Take it steady — try revising this exercise before moving on.",
        "same":     "➡️  Good effort! Keep working at this level.",
    }.get(rec, "")
    if rec_msg:
        print(f"\n{rec_msg}")

    # Show raw test output if failed (helpful for debugging)
    if not passed:
        raw = result.get("result", {})
        stderr = (raw.get("stderr") or "").strip()
        stdout = (raw.get("stdout") or "").strip()
        if stderr or stdout:
            print("\n📋 Test output:")
            if stdout:
                print(f"  stdout: {stdout[:500]}")
            if stderr:
                print(f"  stderr: {stderr[:800]}")

    print()


def cmd_atlas_next(args) -> None:
    """Advance to the next lesson in the current curriculum."""
    session = _load_session()

    if session.curriculum is None:
        print("❌ No active curriculum. Start a lesson first:")
        print("   python -m cli.main atlas lesson <topic>")
        sys.exit(1)

    print("\n🐘 ATLAS — Advancing to next lesson…")
    _divider()

    try:
        exercise = session.next_lesson()
    except RuntimeError as exc:
        print(f"🏁 {exc}")
        print("   You've completed this curriculum! Start a new topic with:")
        print("   python -m cli.main atlas lesson <topic>")
        sys.exit(0)

    _save_session(session)

    print(f"📖 Lesson   : {exercise['lesson']['title']}")
    print(f"🏋️  Exercise : {exercise['title']}")
    _divider()
    print(f"\n{exercise['prompt']}\n")
    _divider()
    print("\n📄 Starter file(s):\n")
    for fname, content in exercise.get("starter_files", {}).items():
        print(f"  ── {fname} ──")
        for line in content.splitlines():
            print(f"    {line}")
    _divider()
    print(
        "\n💡 Submit your solution with:\n"
        "   python -m cli.main atlas submit <solution.py>\n"
    )


def cmd_atlas_reset(args) -> None:
    """Clear the current ATLAS session (start fresh)."""
    if os.path.exists(_SESSION_STATE_FILE):
        os.remove(_SESSION_STATE_FILE)
        print("🗑️  ATLAS session cleared. Start a new lesson with:")
    else:
        print("💤 No active session to clear.")
    print("   python -m cli.main atlas lesson <topic>")


# ─────────────────────────────────────────────────────────────────────────────
# atlas code — CodingAgent generate → test → hint loop
# ─────────────────────────────────────────────────────────────────────────────

def cmd_atlas_code_generate(args) -> None:
    """Generate code for a prompt, run its tests, and show a hint."""
    prompt = " ".join(args.prompt)
    if not prompt.strip():
        print("❌ Provide a prompt, e.g.:")
        print('   python -m cli.main atlas code generate "write a function that reverses a string"')
        sys.exit(1)

    session = _load_session()

    print("\n🐘 ATLAS — CodingAgent: generate → test → hint")
    _divider()
    print(f"📝 Prompt : {prompt}")
    _divider()

    try:
        result = asyncio.run(session.generate_and_test(prompt))
    except Exception as exc:
        print(f"❌ generate_and_test failed: {exc}", file=sys.stderr)
        sys.exit(1)

    # Show generated code
    code = result.get("code", "")
    tests = result.get("tests", "")
    docs = result.get("docs", "")

    if code:
        print("\n💻 Generated code:\n")
        for line in code.splitlines():
            print(f"    {line}")
    else:
        print("⚠️  No code was generated.")

    if tests:
        print("\n🧪 Generated tests:\n")
        for line in tests.splitlines():
            print(f"    {line}")

    if docs:
        print(f"\n📄 Docs/example:\n    {docs}")

    _divider()
    passed = result.get("passed", False)
    if passed:
        print("\n✅ Tests PASSED")
    else:
        print("\n❌ Tests FAILED")
        raw = result.get("result", {})
        stderr = (raw.get("stderr") or "").strip()
        if stderr:
            print(f"\n  stderr: {stderr[:600]}")

    print(f"\n💡 {result.get('hint', '')}")
    _divider()

    if not args.no_save:
        _save_session(session)


def cmd_atlas_code_refactor(args) -> None:
    """Refactor a Python file using the CodingAgent LLM prompt."""
    from pathlib import Path
    path = Path(args.file)
    if not path.exists():
        print(f"❌ File not found: {path}")
        sys.exit(1)

    original = path.read_text(encoding="utf-8")
    print(f"\n🐘 ATLAS — CodingAgent: refactor {path.name}")
    _divider()

    async def _do_refactor() -> str:
        from mammoth_os.agents.coding_agent import CodingAgent
        from mammoth_os.prompt_templates import build_refactor_prompt
        try:
            from mammoth_os.llm_clients import get_llm_client
            client = get_llm_client()
            prompt = build_refactor_prompt(original)
            raw = await client.generate(prompt, max_tokens=1800, temperature=0.2)
            import re
            m = re.search(r"```python\s*\n([\s\S]*?)```", raw)
            return m.group(1).strip() if m else raw.strip()
        except Exception as exc:
            return f"# refactor unavailable: {exc}\n{original}"

    refactored = asyncio.run(_do_refactor())
    print("\n🔧 Refactored code:\n")
    for line in refactored.splitlines():
        print(f"    {line}")
    _divider()

    if args.inplace:
        path.write_text(refactored, encoding="utf-8")
        print(f"\n✅ Wrote refactored code back to {path}")
    else:
        out = Path(args.output) if args.output else path.with_suffix(".refactored.py")
        out.write_text(refactored, encoding="utf-8")
        print(f"\n✅ Refactored code written to {out}")


def cmd_atlas_code_explain(args) -> None:
    """Ask the CodingAgent to explain a Python file to a learner."""
    from pathlib import Path
    path = Path(args.file)
    if not path.exists():
        print(f"❌ File not found: {path}")
        sys.exit(1)

    code = path.read_text(encoding="utf-8")
    print(f"\n🐘 ATLAS — CodingAgent: explain {path.name}")
    _divider()

    async def _do_explain() -> str:
        from mammoth_os.prompt_templates import build_explain_prompt
        try:
            from mammoth_os.llm_clients import get_llm_client
            client = get_llm_client()
            prompt = build_explain_prompt(code)
            return await client.generate(prompt, max_tokens=400, temperature=0.3)
        except Exception as exc:
            return f"(explanation unavailable: {exc})"

    explanation = asyncio.run(_do_explain())
    print(f"\n📖 {explanation.strip()}\n")
    _divider()


# ─────────────────────────────────────────────────────────────────────────────
# Parser builder — called from cli/main.py
# ─────────────────────────────────────────────────────────────────────────────

def build_atlas_parser(sub: argparse._SubParsersAction) -> argparse.ArgumentParser:
    """Attach the `atlas` subcommand tree to an existing subparsers action."""
    p_atlas = sub.add_parser(
        "atlas",
        help="ATLAS tutor bot — start lessons, submit solutions, track progress",
    )
    atlas_sub = p_atlas.add_subparsers(dest="atlas_command", required=True)

    # atlas lesson <topic...>
    p_lesson = atlas_sub.add_parser("lesson", help="Start a new lesson on a topic")
    p_lesson.add_argument("topic", nargs="+", help="Topic to learn, e.g. Python for loops")
    p_lesson.add_argument("--module", type=int, default=0, metavar="N", help="Module index (default: 0)")
    p_lesson.add_argument("--lesson", type=int, default=0, metavar="N", help="Lesson index within module (default: 0)")
    p_lesson.add_argument("--difficulty", default="beginner", choices=["beginner", "intermediate", "advanced"], help="Exercise difficulty level")
    p_lesson.add_argument("--llm", action="store_true", help="Use LLM-powered personalized exercise generation")
    p_lesson.set_defaults(func=cmd_atlas_lesson)

    # atlas status
    p_status = atlas_sub.add_parser("status", help="Show current lesson and exercise")
    p_status.set_defaults(func=cmd_atlas_status)

    # atlas submit [file] [--inline code]
    p_submit = atlas_sub.add_parser("submit", help="Submit a solution file or inline code")
    p_submit.add_argument(
        "file", nargs="?", default=None,
        help="Path to your solution file (e.g. solution.py)",
    )
    p_submit.add_argument(
        "--inline", default=None, metavar="CODE",
        help="Inline Python code string, e.g. --inline \"def solution(a,b): return a+b\"",
    )
    p_submit.set_defaults(func=cmd_atlas_submit)

    # atlas next
    p_next = atlas_sub.add_parser("next", help="Advance to the next lesson")
    p_next.set_defaults(func=cmd_atlas_next)

    # atlas reset
    p_reset = atlas_sub.add_parser("reset", help="Clear the current ATLAS session")
    p_reset.set_defaults(func=cmd_atlas_reset)

    # atlas code — CodingAgent generate / refactor / explain
    p_code = atlas_sub.add_parser("code", help="CodingAgent: generate, refactor, or explain code")
    code_sub = p_code.add_subparsers(dest="code_command", required=True)

    # atlas code generate <prompt...>
    p_gen = code_sub.add_parser("generate", help="Generate code from a natural-language prompt and run its tests")
    p_gen.add_argument("prompt", nargs="+", help="Natural-language description of what to code")
    p_gen.add_argument("--no-save", dest="no_save", action="store_true", help="Do not save session state after generation")
    p_gen.set_defaults(func=cmd_atlas_code_generate)

    # atlas code refactor <file>
    p_ref = code_sub.add_parser("refactor", help="Refactor a Python file using the CodingAgent LLM")
    p_ref.add_argument("file", help="Path to the Python file to refactor")
    p_ref.add_argument("--inplace", action="store_true", help="Overwrite the original file")
    p_ref.add_argument("--output", default=None, metavar="FILE", help="Write refactored output to this path")
    p_ref.set_defaults(func=cmd_atlas_code_refactor)

    # atlas code explain <file>
    p_exp = code_sub.add_parser("explain", help="Ask the CodingAgent to explain a Python file")
    p_exp.add_argument("file", help="Path to the Python file to explain")
    p_exp.set_defaults(func=cmd_atlas_code_explain)

    return p_atlas
