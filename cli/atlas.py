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
import os
import sys

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
        return ATLASSession.load_state(_SESSION_STATE_FILE)
    except Exception as exc:
        print(f"❌ Could not load ATLASSession: {exc}", file=sys.stderr)
        sys.exit(1)


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
    session = ATLASSession(user_id=_DEFAULT_USER)

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

    return p_atlas
