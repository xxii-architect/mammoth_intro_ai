"""cli/atlas.py — ATLAS tutor bot CLI commands

Registered under the `atlas` subcommand in cli/main.py.

Usage (after `pip install -e .` or via PYTHONPATH=src):
    python -m cli.main atlas lesson "Python for loops"
    python -m cli.main atlas status
    python -m cli.main atlas status --db
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
from pathlib import Path

_CLI_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _CLI_DIR.parent
_SRC_DIR = _REPO_ROOT / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

# Ensure UTF-8 output on Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


# Default paths
_MAMMOTH_DIR = os.path.join(str(_REPO_ROOT), ".mammoth")
_SESSION_STATE_FILE = os.path.join(_MAMMOTH_DIR, "atlas_cli_session.json")
_UI_STATE_FILE = os.path.join(_MAMMOTH_DIR, "atlas_ui_state.json")
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


def _save_active_ui_dir(path: str) -> None:
    try:
        os.makedirs(_MAMMOTH_DIR, exist_ok=True)
        with open(_UI_STATE_FILE, "w", encoding="utf-8") as fh:
            abs_path = os.path.abspath(path)
            json.dump(
                {"active_ui_project": abs_path, "active_ui_dir": abs_path},
                fh,
                indent=2,
            )
    except Exception as exc:
        print(f"⚠️  Could not persist active UI project: {exc}", file=sys.stderr)


def _resolve_active_ui_dir() -> str:
    try:
        with open(_UI_STATE_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh) or {}
        active_ui_dir = os.path.abspath(
            str(data.get("active_ui_project") or data.get("active_ui_dir") or "").strip()
        )
    except Exception:
        active_ui_dir = ""

    if not active_ui_dir:
        print("❌ No active UI project found. Run `python -m cli.main atlas ui scaffold \"<prompt>\"` first.")
        sys.exit(1)
    if not os.path.isdir(active_ui_dir):
        print(f"❌ Active UI project path does not exist: {active_ui_dir}")
        print("   Run `python -m cli.main atlas ui scaffold \"<prompt>\"` to create a new one.")
        sys.exit(1)
    return active_ui_dir


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


def _fetch_latest_ai_session() -> dict | None:
    """Return the most recent mammoth.ai_sessions row, or None on failure."""
    supabase_url = os.environ.get("SUPABASE_URL", "").strip()
    supabase_key = (
        os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        or os.environ.get("SUPABASE_ANON_KEY", "").strip()
        or os.environ.get("SUPABASE_KEY", "").strip()
    )
    if not supabase_url or not supabase_key:
        return None

    url = (
        f"{supabase_url.rstrip('/')}/rest/v1/ai_sessions"
        "?select=id,prompt,tokens_used,created_at,metadata"
        "&order=created_at.desc"
        "&limit=1"
    )
    req = urllib.request.Request(
        url,
        headers={
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Accept": "application/json",
            "Accept-Profile": "mammoth",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            rows = json.loads(resp.read().decode("utf-8"))
            return rows[0] if rows else {}
    except Exception as exc:
        return {"error": str(exc)}


def cmd_atlas_status(args) -> None:
    """Show the current ATLAS session state, optionally including the latest DB row."""
    session = _load_session()
    s = session.status()

    print("\n🐘 ATLAS — Session Status")
    _divider()

    if s["state"] == "idle":
        print("💤 No active lesson.")
        print("   Start one with: python -m cli.main atlas lesson <topic>")
    else:
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

    if getattr(args, "db", False):
        print("\n🗄️  Latest mammoth.ai_sessions row")
        _divider()
        row = _fetch_latest_ai_session()
        if row is None:
            print("⚠️  SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not set — cannot query DB.")
        elif "error" in row:
            print(f"❌ DB query failed: {row['error']}")
        elif not row:
            print("ℹ️  No ai_sessions rows found yet — run `atlas code generate` first.")
        else:
            print(f"  id          : {row.get('id', '—')}")
            print(f"  created_at  : {row.get('created_at', '—')}")
            tokens = row.get("tokens_used")
            print(f"  tokens_used : {tokens if tokens is not None else '—'}")
            prompt = (row.get("prompt") or "").replace("\n", " ")
            print(f"  prompt      : {prompt[:120]}{'…' if len(prompt) > 120 else ''}")
            meta = row.get("metadata") or {}
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except Exception:
                    pass
            if isinstance(meta, dict) and meta:
                print(f"  metadata    : {json.dumps(meta)}")
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

    # ── Language guard ──────────────────────────────────────────────────────
    _NON_PYTHON = {"react", "typescript", "tsx", "javascript", "vue", "svelte", "html", "css"}
    _UI_HINTS = {
        "ui",
        "ux",
        "panel",
        "notes panel",
        "component",
        "page",
        "layout",
        "dashboard",
        "sidebar",
        "modal",
        "dialog",
        "card",
        "theme",
        "palette",
        "style",
        "styling",
        "frontend",
    }
    prompt_lower = prompt.lower()
    is_non_python = any(kw in prompt_lower for kw in _NON_PYTHON)
    is_ui_prompt = any(kw in prompt_lower for kw in _UI_HINTS)
    if is_non_python or is_ui_prompt:
        suggested_command = "atlas ui palette" if any(kw in prompt_lower for kw in {"theme", "palette", "style", "styling", "color", "colors"}) else "atlas ui component"
        print("\n⚠️  UI-focused prompt detected — skipping Python CodingAgent sandbox.")
        print(f'👉  Use:  python -m cli.main {suggested_command} "{prompt}"')
        print("    That route uses UIBuilderAgent for panels, components, pages, and styling work.\n")
        sys.exit(0)
    # ────────────────────────────────────────────────────────────────────────

    session = _load_session()
    ...

    print("\n🐘 ATLAS — CodingAgent: generate → test → hint")
    _divider()
    print(f"📝 Prompt : {prompt}")
    _divider()

    try:
        result = asyncio.run(session.generate_and_test(
            prompt,
            context={
                "source": "atlas.code.generate",
                "user_id": session.user_id,
                "curriculum_id": getattr(session, "_curriculum_id", None),
                "lesson_id": getattr(session, "_lesson_id", None),
            },
        ))
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


def cmd_atlas_ui_scaffold(args) -> None:
    """Scaffold a small Vite + React UI from a natural-language prompt."""
    from mammoth_os.agents.ui_builder_agent import UIBuilderAgent

    prompt = " ".join(args.prompt).strip() or "ATLAS progress dashboard"
    agent = UIBuilderAgent(router=None)
    result = asyncio.run(agent.scaffold(prompt, target_dir=args.output))
    _save_active_ui_dir(result["target_dir"])

    print("\n🧩 ATLAS — UI scaffolding")
    _divider()
    print(f"Prompt     : {prompt}")
    print(f"Target     : {result['target_dir']}")
    print(f"Title      : {result['title']}")
    print("\nGenerated files:")
    for rel in result.get("files", []):
        print(f"  - {rel}")
    _divider()
    print("\nRun locally:")
    print(f"  cd {result['target_dir']}")
    print("  npm install")
    print("  npm run dev")


def cmd_atlas_ui_generate(args) -> None:
    """Generate a UI asset in the active UI project directory."""
    from mammoth_os.agents.ui_builder_agent import UIBuilderAgent

    prompt = (args.prompt or "").strip()
    if not prompt:
        print("❌ Please provide a prompt.")
        sys.exit(1)

    ui_command = getattr(args, "ui_command", "")
    active_ui_dir = _resolve_active_ui_dir()
    agent = UIBuilderAgent(router=None)

    if ui_command == "component":
        result = asyncio.run(agent.generate_component(prompt, target_dir=active_ui_dir))
    elif ui_command == "style":
        result = asyncio.run(agent.generate_style(prompt, target_dir=active_ui_dir))
    elif ui_command == "backend":
        result = asyncio.run(agent.generate_backend(prompt, target_dir=active_ui_dir))
    elif ui_command == "graph":
        result = asyncio.run(agent.generate_graph(prompt, target_dir=active_ui_dir))
    elif ui_command == "palette":
        result = asyncio.run(agent.generate_palette(prompt, target_dir=active_ui_dir))
    else:
        print(f"❌ Unknown ui command: {ui_command}")
        sys.exit(1)

    _save_active_ui_dir(result["target_dir"])

    print(f"\n🧩 ATLAS — UI {ui_command} generation")
    _divider()
    print(f"Prompt     : {prompt}")
    print(f"Target UI  : {result['target_dir']}")
    print(f"Output     : {result.get('relative_file', result.get('file', ''))}")
    _divider()


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
            from mammoth_os.llm_client import get_llm_client
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

def cmd_atlas_code_debug(args) -> None:
    """Ask the CodingAgent to hunt for bugs in a file."""
    from pathlib import Path
    path = Path(args.file)
    if not path.exists():
        print(f"❌ File not found: {path}")
        sys.exit(1)

    code = path.read_text(encoding="utf-8")
    print(f"\n🐘 ATLAS — CodingAgent: debug {path.name}")
    _divider()

    async def _do_debug() -> str:
        try:
            from mammoth_os.llm_client import get_llm_client
            client = get_llm_client()
            prompt = (
                "You are a senior code reviewer and bug hunter. "
                "Carefully read the following code and identify every bug, "
                "logic error, broken reference, and potential runtime exception. "
                "For each issue found, state: the line or section, what the bug is, "
                "and why it will fail. Be specific and direct.\n\n"
                f"```\n{code}\n```"
            )
            return await client.generate(prompt, max_tokens=600, temperature=0.2)
        except Exception as exc:
            return f"(debug unavailable: {exc})"

    result = asyncio.run(_do_debug())
    print(f"\n🐛 Bugs found:\n\n{result.strip()}\n")
    _divider()


def cmd_atlas_code_scan(args) -> None:
    """Run a structured audit scan: bugs, warnings, and improvement suggestions."""
    from pathlib import Path
    path = Path(args.file)
    if not path.exists():
        print(f"❌ File not found: {path}")
        sys.exit(1)

    code = path.read_text(encoding="utf-8")
    print(f"\n🐘 ATLAS — CodingAgent: scan {path.name}")
    _divider()

    async def _do_scan() -> str:
        try:
            from mammoth_os.llm_client import get_llm_client
            client = get_llm_client()
            prompt = (
                "You are a code quality auditor. Analyze the following code and return "
                "a structured report with exactly three numbered sections:\n"
                "1. BUGS — actual errors that will break the code at runtime\n"
                "2. WARNINGS — risky patterns, deprecated usage, or likely future breakage\n"
                "3. SUGGESTIONS — optional improvements for readability, performance, or maintainability\n"
                "Be concise. Each item gets one line. If a section has no items, write 'None found.'\n\n"
                f"```\n{code}\n```"
            )
            return await client.generate(prompt, max_tokens=700, temperature=0.2)
        except Exception as exc:
            return f"(scan unavailable: {exc})"

    result = asyncio.run(_do_scan())
    print(f"\n🔍 Scan report:\n\n{result.strip()}\n")
    _divider()


def cmd_atlas_code_patch(args) -> None:
    """Apply a targeted directed change to a file based on a --fix instruction."""
    from pathlib import Path
    path = Path(args.file)
    if not path.exists():
        print(f"❌ File not found: {path}")
        sys.exit(1)

    code = path.read_text(encoding="utf-8")
    instruction = args.fix
    print(f"\n🐘 ATLAS — CodingAgent: patch {path.name}")
    print(f"🔧 Instruction: {instruction}")
    _divider()

    async def _do_patch() -> str:
        try:
            from mammoth_os.llm_client import get_llm_client
            client = get_llm_client()
            prompt = (
                "You are a precise code editor. Apply ONLY the following change to the code below. "
                "Do not refactor, rename, reformat, or alter anything else. "
                "Return the COMPLETE updated file with the change applied.\n\n"
                f"INSTRUCTION: {instruction}\n\n"
                f"```\n{code}\n```"
            )
            raw = await client.generate(prompt, max_tokens=2000, temperature=0.1)
            import re
            m = re.search(r"```(?:\w+)?\s*\n([\s\S]*?)```", raw)
            return m.group(1).strip() if m else raw.strip()
        except Exception as exc:
            return f"# patch unavailable: {exc}\n{code}"

    patched = asyncio.run(_do_patch())

    if args.inplace:
        path.write_text(patched, encoding="utf-8")
        print(f"\n✅ Patch applied directly to {path}")
    else:
        out = Path(args.output) if args.output else path.with_suffix(".patched" + path.suffix)
        out.write_text(patched, encoding="utf-8")
        print(f"\n✅ Patched file written to {out}")
    _divider()


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
            from mammoth_os.llm_client import get_llm_client
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
    p_status.add_argument(
        "--db", action="store_true",
        help="Also print the most recent mammoth.ai_sessions row from Supabase",
    )
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

    # atlas ui — UIBuilderAgent scaffold
    p_ui = atlas_sub.add_parser("ui", help="Generate a simple frontend UI from a prompt")
    ui_sub = p_ui.add_subparsers(dest="ui_command", required=True)

    p_scaffold = ui_sub.add_parser("scaffold", help="Create a Vite + React starter app")
    p_scaffold.add_argument("prompt", nargs="+", help="Natural-language description of the UI")
    p_scaffold.add_argument("--output", default=None, metavar="DIR", help="Target directory for the generated app")
    p_scaffold.set_defaults(func=cmd_atlas_ui_scaffold)

    p_component = ui_sub.add_parser("component", help="Generate a UI component in the active project")
    p_component.add_argument("prompt", help="Natural-language prompt for component generation")
    p_component.set_defaults(func=cmd_atlas_ui_generate)

    p_style = ui_sub.add_parser("style", help="Generate UI styles in the active project")
    p_style.add_argument("prompt", help="Natural-language prompt for style generation")
    p_style.set_defaults(func=cmd_atlas_ui_generate)

    p_backend = ui_sub.add_parser("backend", help="Generate frontend backend hooks in the active project")
    p_backend.add_argument("prompt", help="Natural-language prompt for backend hook generation")
    p_backend.set_defaults(func=cmd_atlas_ui_generate)

    p_graph = ui_sub.add_parser("graph", help="Generate graph UI modules in the active project")
    p_graph.add_argument("prompt", help="Natural-language prompt for graph generation")
    p_graph.set_defaults(func=cmd_atlas_ui_generate)

    p_palette = ui_sub.add_parser("palette", help="Generate command palette UI logic in the active project")
    p_palette.add_argument("prompt", help="Natural-language prompt for palette generation")
    p_palette.set_defaults(func=cmd_atlas_ui_generate)

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

    # atlas code debug <file>
    p_dbg = code_sub.add_parser("debug", help="Hunt for bugs in a file using the CodingAgent")
    p_dbg.add_argument("file", help="Path to the file to debug")
    p_dbg.set_defaults(func=cmd_atlas_code_debug)

    # atlas code scan <file>
    p_scan = code_sub.add_parser("scan", help="Structured audit: bugs, warnings, suggestions")
    p_scan.add_argument("file", help="Path to the file to scan")
    p_scan.set_defaults(func=cmd_atlas_code_scan)

    # atlas code patch <file> --fix "instruction"
    p_patch = code_sub.add_parser("patch", help="Apply a targeted directed change to a file")
    p_patch.add_argument("file", help="Path to the file to patch")
    p_patch.add_argument("--fix", required=True, metavar="INSTRUCTION", help="What to change, e.g. --fix \"replace all #fff with var(--text-primary)\"")
    p_patch.add_argument("--inplace", action="store_true", help="Overwrite the original file")
    p_patch.add_argument("--output", default=None, metavar="FILE", help="Write patched output to this path")
    p_patch.set_defaults(func=cmd_atlas_code_patch)


    return p_atlas
