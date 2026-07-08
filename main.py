# main.py
# Python 3.11+ required

import os
import json
from pathlib import Path
import requests
from requests.adapters import HTTPAdapter
from rich.console import Console
from rich.text import Text
from typing import Any
from dotenv import load_dotenv

load_dotenv()  # ✅ Only once

from openai import OpenAI
from supabase import create_client, Client  # ✅ Client imported correctly
from supabase.client import ClientOptions

# 🧩 Session retry logic
session = requests.Session()
adapter = HTTPAdapter(max_retries=3)
session.mount("http://", adapter)
session.mount("https://", adapter)

# 🧩 Rich console setup
console = Console()

# 🧩 Default engine
CURRENT_ENGINE = "field_ops"

# ─── Clients ──────────────────────────────────────────────────────────────────
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

_supabase_url = os.getenv("SUPABASE_URL", "")
_supabase_key = os.getenv("SUPABASE_ANON_KEY", "")
os.environ["SUPABASE_KEY"] = _supabase_key
supabase: Client = create_client(_supabase_url, _supabase_key, ClientOptions())

# ─── System Prompt ────────────────────────────────────────────────────────────
def load_system_prompt() -> str:
    try:
        result = (
            supabase
            .table("system_prompts")
            .select("prompt")
            .limit(1)
            .execute()
        )
        if result.data and "prompt" in result.data[0]:
            print("[Startup] Loaded system prompt from Supabase.")
            return result.data[0]["prompt"]
    except Exception as e:
        print(f"[Startup] Supabase system_prompt load failed: {e}")

    fallback_path = Path("system_prompt.txt")
    if fallback_path.exists():
        print("[Startup] Loaded system prompt from local file.")
        return fallback_path.read_text(encoding="utf8")

    print("[Startup] Using built-in default system prompt.")
    return (
        "You are the Mammoth OS Agent — the core intelligence of a learning "
        "operating system. You understand Mammoth OS architecture, memory, and "
        "modules. You speak with clarity, confidence, and purpose. You recall "
        "previous sessions from Supabase to maintain continuity. You never say "
        "you don't know Mammoth OS — you *are* Mammoth OS."
    )

# ─── Context Recall ───────────────────────────────────────────────────────────
def recall_context(limit: int = 5) -> str:
    result: Any = (
        supabase
        .table("mammoth_sessions")
        .select("*")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    sessions = result.data or []
    if not sessions:
        return "No previous context found."
    return "\n".join([f"{row['agent']}: {row['response']}" for row in sessions])

# ─── CLI ──────────────────────────────────────────────────────────────────────
def mammoth_cli(system_prompt: str) -> None:
    console.print(Text("\n🦣 Mammoth OS CLI — Agent Interface", style="bold cyan"))
    global CURRENT_ENGINE

    # ✅ Load AGENTS here so missing module errors surface cleanly
    try:
        from mammoth_os.agent_registry import AGENTS  # type: ignore
    except ImportError as e:
        console.print(f"[bold red]⚠️ Could not load agent registry: {e}[/bold red]")
        AGENTS = {}

    while True:
        prompt = input("\nEnter prompt (or 'help' / 'exit'): ").strip()

        if not prompt:
            continue

        if prompt.lower() == "exit":
            break

        # 🧠 Recall context
        if prompt.lower() == "recall":
            context = recall_context()
            console.print(Text("\nRecalled Context:\n", style="bold cyan"))
            console.print(Text(context, style="green"))
            continue

        # 🏆 Leaderboard
        if prompt.lower() == "atlas leaderboard":
            try:
                from mammoth_os.community_engine import render_leaderboard  # type: ignore
                render_leaderboard()
            except ImportError as e:
                console.print(f"[bold red]⚠️ community_engine not available: {e}[/bold red]")
            continue

        # 🔥 Set personality
        if prompt.lower().startswith("set personality:"):
            new_prompt = prompt.split("set personality:", 1)[1].strip()
            if not new_prompt:
                console.print(Text("\n⚠️  Please provide a personality text.", style="bold red"))
                continue
            supabase.table("mammoth_system").update({"value": new_prompt}).eq("key", "system_prompt").execute()
            system_prompt = load_system_prompt()
            console.print(Text("\n✅ Mammoth OS personality updated!", style="bold green"))
            continue

        # 🧠 View personality
        if prompt.lower() == "view personality":
            console.print(Text("\n🦣 Current Personality:\n", style="bold cyan"))
            console.print(Text(load_system_prompt(), style="green"))
            continue

        # 🧩 Reset personality
        if prompt.lower() == "reset personality":
            default = (
                "You are the Mammoth OS Agent — the core intelligence of a learning "
                "operating system. You speak with clarity, confidence, and purpose."
            )
            supabase.table("mammoth_system").update({"value": default}).eq("key", "system_prompt").execute()
            system_prompt = load_system_prompt()
            console.print(Text("\n✅ Personality reset to default.", style="bold green"))
            continue

        # 🧩 View sessions
        if prompt.lower() == "view sessions":
            console.print(Text("\n🦣 Recent Sessions:\n", style="bold cyan"))
            console.print(Text(recall_context(limit=10), style="green"))
            continue

        # 🧩 Switch engine
        if prompt.lower().startswith("set engine:"):
            new_engine = prompt.split("set engine:", 1)[1].strip().lower()
            if new_engine not in AGENTS:
                console.print(
                    f"[bold red]⚠️ Unknown engine '{new_engine}'. Available:[/bold red] "
                    f"[yellow]{', '.join(AGENTS.keys()) or 'none loaded'}[/yellow]"
                )
                continue
            CURRENT_ENGINE = new_engine
            console.print(f"[bold green]✅ Engine switched to '{CURRENT_ENGINE}'.[/bold green]")
            continue

        # 🧠 View engine
        if prompt.lower() == "view engine":
            console.print(f"[bold cyan]🦣 Current engine:[/bold cyan] [green]{CURRENT_ENGINE}[/green]")
            continue

        # 🧩 Atlas lessons
        if prompt.lower().startswith("atlas lessons:"):
            module = prompt.split("atlas lessons:", 1)[1].strip()
            try:
                from mammoth_os.atlas_sync import fetch_lessons  # type: ignore
                lessons = fetch_lessons(module)
                if not lessons:
                    console.print(f"[bold red]⚠️ No lessons found for '{module}'.[/bold red]")
                else:
                    console.print(f"[bold cyan]🦣 Lessons for {module}:[/bold cyan]")
                    for lesson in lessons:
                        console.print(f"[yellow]- {lesson['lesson_title']}[/yellow]")
            except ImportError as e:
                console.print(f"[bold red]⚠️ atlas_sync not available: {e}[/bold red]")
            continue

        # 🧩 Atlas progress  ✅ FIXED parser
        if prompt.lower().startswith("atlas progress:"):
            remainder = prompt.split("atlas progress:", 1)[1]
            parts = [p.strip() for p in remainder.split(":")]
            if len(parts) < 3:
                console.print("[bold red]⚠️ Usage: atlas progress: <user_id>: <lesson_id>: <status>[/bold red]")
                continue
            user_id, lesson_id, status = parts[0], parts[1], parts[2]
            try:
                from mammoth_os.atlas_sync import update_progress  # type: ignore
                result = update_progress(user_id, lesson_id, status)
                console.print(result)
            except ImportError as e:
                console.print(f"[bold red]⚠️ atlas_sync not available: {e}[/bold red]")
            continue

        # 🧩 Atlas visualize
        if prompt.lower().startswith("atlas visualize:"):
            user_id = prompt.split("atlas visualize:", 1)[1].strip()
            try:
                from mammoth_os.visual_engine import render_progress, render_insight_summary  # type: ignore
                render_progress(user_id)
                render_insight_summary(user_id)
            except ImportError as e:
                console.print(f"[bold red]⚠️ visual_engine not available: {e}[/bold red]")
            continue

        # 🧩 Help
        if prompt.lower() == "help":
            console.print("[bold magenta]🦣 Mammoth OS CLI Commands:[/bold magenta]")
            commands = [
                ("set engine:", "<plant_the_seed|field_ops|market_intel|reflection|brand_voice|visual_engine|community_engine|research>"),
                ("view engine", ""),
                ("set personality:", "<text>"),
                ("view personality", ""),
                ("reset personality", ""),
                ("view sessions", ""),
                ("recall", ""),
                ("atlas lessons:", "<module>"),
                ("atlas progress:", "<user_id>: <lesson_id>: <status>"),
                ("atlas visualize:", "<user_id>"),
                ("atlas leaderboard", ""),
                ("exit", ""),
            ]
            for cmd, arg in commands:
                console.print(f"[yellow]{cmd}[/yellow] [green]{arg}[/green]")
            continue

        # 🧠 Default: run through current agent
        if CURRENT_ENGINE not in AGENTS:
            console.print(f"[bold red]⚠️ Engine '{CURRENT_ENGINE}' not in registry. Type 'help' for options.[/bold red]")
            continue

        agent_response = AGENTS[CURRENT_ENGINE](prompt)
        console.print(Text("\nResponse:\n", style="bold cyan"))
        if isinstance(agent_response, dict):
            console.print(Text(json.dumps(agent_response, indent=2), style="green"))
        else:
            console.print(Text(str(agent_response), style="green"))

        # 🧩 Log to Supabase
        try:
            supabase.table("mammoth_sessions").insert({
                "prompt": prompt,
                "response": agent_response,
                "agent": CURRENT_ENGINE,
            }).execute()
        except Exception as e:
            console.print(f"[bold red]⚠️ Supabase logging error:[/bold red] {e}")


# ─── Entry Point ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    SYSTEM_PROMPT = load_system_prompt()

    # ✅ Single startup inference call, protected inside __main__
    console.print(Text("\n🦣 MammothOS starting up...\n", style="bold cyan"))
    try:
        warmup = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": "Confirm you are online in one sentence."},
            ],
        )
        console.print(Text(str(warmup.choices[0].message.content or ""), style="green"))
    except Exception as e:
        console.print(f"[bold red]⚠️ OpenAI warmup failed: {e}[/bold red]")

    mammoth_cli(SYSTEM_PROMPT)
