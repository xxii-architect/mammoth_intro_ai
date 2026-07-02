# main.py
# Python 3.11+ required

import os
import json
import requests
from requests.adapters import HTTPAdapter
from rich.console import Console
from rich.text import Text
from typing import Any
from dotenv import load_dotenv
load_dotenv()
from openai import OpenAI
from supabase.client import create_client, ClientOptions

# 🧩 Session retry logic
session = requests.Session()
adapter = HTTPAdapter(max_retries=3)
session.mount("http://", adapter)
session.mount("https://", adapter)

# 🧩 Rich console setup
console = Console()

# 🧩 Default engine
CURRENT_ENGINE = "field_ops"  # Default inference engine; can be changed via CLI

# 1️⃣ Load environment variables
load_dotenv()

# 2️⃣ Initialize clients
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_ANON_KEY")
os.environ["SUPABASE_KEY"] = os.getenv("SUPABASE_ANON_KEY")  # type: ignore
supabase: Client = create_client(url, key, ClientOptions())  # type: ignore

# 3️⃣ Dynamic system prompt loader
from pathlib import Path

def load_system_prompt():
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

    # Fallback to local file
    fallback_path = Path("system_prompt.txt")
    if fallback_path.exists():
        print("[Startup] Loaded system prompt from local file.")
        return fallback_path.read_text(encoding="utf8")

    # Final fallback
    print("[Startup] Using built‑in default system prompt.")
    return (
        "You are the Mammoth OS Agent, responsible for autonomous task "
        "orchestration and content generation."
    )

SYSTEM_PROMPT: str = load_system_prompt()

# 4️⃣ Simple inference test
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "Explain tokens in one sentence."},
    ],
)
console.print(Text(str(response.choices[0].message.content or ""), style="green"))

# 5️⃣ Streaming response demo
console.print(Text("\nStreaming response:", style="bold cyan"))
for chunk in client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "Explain tokens in one sentence."},
    ],
    stream=True,
):
    console.print(chunk.choices[0].delta.content or "", end="")

# 6️⃣ Recall context helper
def recall_context(limit: int = 5) -> str:
    """Fetch the last few sessions from Supabase."""
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
    context = "\n".join([f"{row['agent']}: {row['response']}" for row in sessions])
    return context

# 7️⃣ Mammoth OS Agent Interface
from mammoth_os.agent_registry import AGENTS  # type: ignore

def mammoth_cli() -> None:
    console.print(Text("\n🦣 Mammoth OS CLI — Agent Interface", style="bold cyan"))
    global SYSTEM_PROMPT
    global CURRENT_ENGINE

    while True:
        prompt = input("\nEnter prompt (or 'exit'): ")

        if prompt.lower() == "exit":
            break

        # 🧠 Recall context
        if prompt.lower() == "recall":
            context = recall_context()
            console.print(Text("\nRecalled Context:\n", style="bold cyan"))
            console.print(Text(context, style="green"))
            continue

        # 🏆 ATLAS Leaderboard
        if prompt.lower().startswith("atlas leaderboard"):
            from mammoth_os.community_engine import render_leaderboard
            render_leaderboard()
            continue

        # 🔥 Hot‑reload personality command
        if prompt.lower().startswith("set personality:"):
            new_prompt = prompt.split("set personality:", 1)[1].strip()
            if not new_prompt:
                console.print(
                    Text(
                        "\n⚠️  Please provide a new personality text after 'set personality:'",
                        style="bold red",
                    )
                )
                continue

            supabase.table("mammoth_system").update({"value": new_prompt}).eq(
                "key", "system_prompt"
            ).execute()
            SYSTEM_PROMPT = load_system_prompt()
            console.print(
                Text(
                    "\n✅  Mammoth OS personality updated successfully!",
                    style="bold green",
                )
            )
            continue

        # 🧠 View current personality
        if prompt.lower() == "view personality":
            current_prompt = load_system_prompt()
            console.print(
                Text(
                    "\n🦣 Current Mammoth OS Personality:\n", style="bold cyan"
                )
            )
            console.print(Text(current_prompt, style="green"))
            continue

        # 🧩 Reset personality
        if prompt.lower() == "reset personality":
            default_prompt = (
                "You are the Mammoth OS Agent — the core intelligence of a learning operating system. "
                "You understand Mammoth OS architecture, memory, and modules. "
                "You speak with clarity, confidence, and purpose. "
                "You recall previous sessions from Supabase to maintain continuity. "
                "You never say you don’t know Mammoth OS — you *are* Mammoth OS."
            )
            supabase.table("mammoth_system").update({"value": default_prompt}).eq(
                "key", "system_prompt"
            ).execute()
            SYSTEM_PROMPT = load_system_prompt()
            console.print(
                Text(
                    "\n✅  Mammoth OS personality reset to default.",
                    style="bold green",
                )
            )
            continue

        # 🧩 View recent sessions
        if prompt.lower() == "view sessions":
            context = recall_context(limit=10)
            console.print(Text("\n🦣 Recent Sessions:\n", style="bold cyan"))
            console.print(Text(context, style="green"))
            continue

        # 🧩 Switch inference engine
        if prompt.lower().startswith("set engine:"):
            new_engine = prompt.split("set engine:", 1)[1].strip().lower()
            if new_engine not in AGENTS:
                console.print(
                    f"[bold red]⚠️ Unknown engine '{new_engine}'. Available:[/bold red] "
                    f"[yellow]{', '.join(AGENTS.keys())}[/yellow]"
                )
                continue
            CURRENT_ENGINE = new_engine
            console.print(
                f"[bold green]✅ Inference engine switched to '{CURRENT_ENGINE}'.[/bold green]"
            )
            continue

        # 🧠 View current inference engine
        if prompt.lower() == "view engine":
            console.print(
                f"[bold cyan]🦣 Current inference engine:[/bold cyan] [green]{CURRENT_ENGINE}[/green]"
            )
            continue

        # 🧩 Help command
        if prompt.lower() == "help":
            console.print("[bold magenta]🦣 Mammoth OS CLI Commands:[/bold magenta]")
            console.print(
                "[yellow]set engine:[/yellow] [green][plant_the_seed|field_ops|market_intel|reflection|brand_voice|visual_engine|community_engine|research][/green]"
            )
            console.print("[yellow]view engine[/yellow]")
            console.print("[yellow]set personality:[/yellow] [green][text][/green]")
            console.print("[yellow]view personality[/yellow]")
            console.print("[yellow]reset personality[/yellow]")
            console.print("[yellow]view sessions[/yellow]")
            console.print("[yellow]recall[/yellow]")
            console.print("[yellow]atlas lessons:[/yellow] <module>")
            console.print(
                "[yellow]atlas progress:[/yellow] <user_id>: <lesson_id>: <status>"
            )
            console.print("[yellow]atlas visualize:[/yellow] <user_id>")
            console.print("[yellow]atlas leaderboard[/yellow]")
            console.print("[yellow]exit[/yellow]")
            continue

        # 🧩 ATLAS: View lessons
        if prompt.lower().startswith("atlas lessons:"):
            module = prompt.split("atlas lessons:", 1)[1].strip()
            from mammoth_os.atlas_sync import fetch_lessons
            lessons = fetch_lessons(module)
            if not lessons:
                console.print(
                    f"[bold red]⚠️ No lessons found for module '{module}'.[/bold red]"
                )
            else:
                console.print(
                    f"[bold cyan]🦣 Lessons for module:[/bold cyan] [green]{module}[/green]"
                )
                for lesson in lessons:
                    console.print(
                        f"[yellow]- {lesson['lesson_title']}[/yellow]"  # type: ignore
                    )
            continue

        # 🧩 ATLAS: Update progress
        if prompt.lower().startswith("atlas progress:"):
            parts = prompt.split(":")
            if len(parts) < 4:
                console.print(
                    "[bold red]⚠️ Usage: atlas progress: <user_id>: <lesson_id>: <status>[/bold red]"
                )
                continue
            _, _, user_id, lesson_id, status = parts
            from mammoth_os.atlas_sync import update_progress
            result = update_progress(
                user_id.strip(), lesson_id.strip(), status.strip()
            )
            console.print(result)
            continue

        # 🧩 ATLAS: Visualize progress
        if prompt.lower().startswith("atlas visualize:"):
            user_id = prompt.split("atlas visualize:", 1)[1].strip()
            from mammoth_os.visual_engine import (
                render_progress, # type: ignore
                render_insight_summary, # type: ignore
            )  # type: ignore
            render_progress(user_id)
            render_insight_summary(user_id)
            continue

        # 🧠 Default agent response
        response = AGENTS[CURRENT_ENGINE](prompt)
        console.print(Text("\nResponse:\n", style="bold cyan"))

        # Safely print dict or string
        if isinstance(response, dict):
            console.print(Text(json.dumps(response, indent=2), style="green"))
        else:
            console.print(Text(str(response), style="green"))

        # 🧩 Log session
        data = {"prompt": prompt, "response": response, "agent": CURRENT_ENGINE}
        try:
            supabase.table("mammoth_sessions").insert(data).execute()
        except Exception as e:
            console.print(f"[bold red]⚠️ Supabase logging error:[/bold red] {e}")

# 8️⃣ Entry point
if __name__ == "__main__":
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": "Explain tokens in one sentence."},
        ],
    )
    console.print(Text(str(response.choices[0].message.content or ""), style="green"))
    mammoth_cli()
