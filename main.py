# main.py — Mammoth OS CLI
# Python 3.11+ required

import os
import json
import asyncio
from pathlib import Path
from typing import Any, Callable, Dict

import requests
from requests.adapters import HTTPAdapter
from rich.console import Console
from rich.text import Text
from dotenv import load_dotenv

from openai import OpenAI
from supabase import create_client, Client  # type: ignore
from supabase.client import ClientOptions

# ──────────────────────────────────────────────────────────────
# Environment
# ──────────────────────────────────────────────────────────────

load_dotenv()

console = Console()

session = requests.Session()
adapter = HTTPAdapter(max_retries=3)
session.mount("http://", adapter)
session.mount("https://", adapter)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY", "")

if not SUPABASE_URL or not SUPABASE_KEY:
    console.print(
        "[bold red]⚠️ Supabase env vars missing. "
        "Set SUPABASE_URL and SUPABASE_ANON_KEY before running.[/bold red]"
    )

openai_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY, ClientOptions())

CURRENT_AGENT = "field_ops"

# ──────────────────────────────────────────────────────────────
# Fallback Agents (only used if registry import fails)
# ──────────────────────────────────────────────────────────────

def fallback_coding_agent(prompt: str) -> str:
    return f"[CodingAgent stub] You asked: {prompt}"

def fallback_field_ops_agent(prompt: str) -> str:
    return f"[FieldOpsAgent stub] You asked: {prompt}"

FALLBACK_AGENTS = {
    "coding": fallback_coding_agent,
    "field_ops": fallback_field_ops_agent,
}

# ──────────────────────────────────────────────────────────────
# Load Agents from Registry
# ──────────────────────────────────────────────────────────────

def load_agents() -> Dict[str, Callable[[str], Any]]:
    """
    Load AGENTS from Mammoth OS registry.
    Falls back to stub agents if registry import fails.
    """
    try:
        from mammoth_os.registry.agent_registry import AGENTS  # type: ignore
        return AGENTS
    except Exception as e:
        console.print(
            f"[yellow]⚠️ Agent registry unavailable — using fallback agents.[/yellow]\n{e}"
        )
        return FALLBACK_AGENTS

# ──────────────────────────────────────────────────────────────
# System Prompt Loader
# ──────────────────────────────────────────────────────────────

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
            console.print("[cyan][Startup] Loaded system prompt from Supabase.[/cyan]")
            return result.data[0]["prompt"]
    except Exception as e:
        console.print(f"[bold red]⚠️ Supabase system_prompt load failed:[/bold red] {e}")

    fallback_path = Path("system_prompt.txt")
    if fallback_path.exists():
        console.print("[cyan][Startup] Loaded system prompt from local file.[/cyan]")
        return fallback_path.read_text(encoding="utf8")

    console.print("[yellow][Startup] Using built-in default system prompt.[/yellow]")
    return (
        "You are the Mammoth OS Agent — the core intelligence of a learning "
        "operating system. You speak with clarity, confidence, and purpose."
    )

# ──────────────────────────────────────────────────────────────
# Context Recall
# ──────────────────────────────────────────────────────────────

def recall_context(limit: int = 5) -> str:
    try:
        result: Any = (
            supabase
            .table("mammoth_sessions")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
    except Exception as e:
        return f"Supabase recall failed: {e}"

    sessions = result.data or []
    if not sessions:
        return "No previous context found."
    return "\n".join([f"{row['agent']}: {row['response']}" for row in sessions])

# ──────────────────────────────────────────────────────────────
# Health Check
# ──────────────────────────────────────────────────────────────

def health_check() -> Dict[str, str]:
    results = {}

    # Supabase
    try:
        supabase.table("mammoth_sessions").select("id").limit(1).execute()
        results["supabase"] = "OK"
    except Exception as e:
        results["supabase"] = f"ERROR: {e}"

    # OpenAI
    if not openai_client:
        results["openai"] = "NO_API_KEY"
    else:
        try:
            openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": "ping"}],
            )
            results["openai"] = "OK"
        except Exception as e:
            results["openai"] = f"ERROR: {e}"

    # Agents
    agents = load_agents()
    results["agents_loaded"] = ", ".join(agents.keys())

    return results

# ──────────────────────────────────────────────────────────────
# Agent Runner
# ──────────────────────────────────────────────────────────────

def run_agent(agents: Dict[str, Callable[[str], Any]], agent_name: str, prompt: str) -> Any:
    if agent_name not in agents:
        raise ValueError(f"Agent '{agent_name}' not in registry.")
    handler = agents[agent_name]
    return handler(prompt)

# ──────────────────────────────────────────────────────────────
# CodingAgent Helpers (Hybrid routing commands)
# ──────────────────────────────────────────────────────────────

def handle_code_generate(prompt: str) -> None:
    """
    code generate: <natural language prompt>
    """
    try:
        from mammoth_os.agents.coding_agent import CodingAgent  # type: ignore
    except Exception as e:
        console.print(f"[bold red]❌ CodingAgent import failed:[/bold red] {e}")
        return

    code_prompt = prompt.split("code generate:", 1)[1].strip()
    if not code_prompt:
        console.print("[bold red]❌ Missing prompt after 'code generate:'[/bold red]")
        return

    agent = CodingAgent(router=None)
    try:
        result = asyncio.run(agent.generate_code(code_prompt, context={}))  # type: ignore
    except Exception as e:
        console.print(f"[bold red]❌ CodingAgent.generate_code error:[/bold red] {e}")
        return

    console.print(Text("\n🧠 Code Generation Result\n", style="bold cyan"))
    console.print(Text(result.get("code", "") or "// no code generated", style="green"))
    console.print(Text("\n🧪 Tests:\n", style="bold magenta"))
    console.print(Text(result.get("tests", "") or "// no tests generated", style="yellow"))
    console.print(Text("\n📘 Docs:\n", style="bold blue"))
    console.print(Text(result.get("docs", "") or "// no docs generated", style="cyan"))
    console.print(Text(f"\nConfidence: {result.get('confidence', 0.0):.2f}", style="bold green"))
    warnings = result.get("warnings", [])
    if warnings:
        console.print(Text("\n⚠️ Warnings:\n", style="bold yellow"))
        for w in warnings:
            console.print(Text(f"- {w}", style="yellow"))

def handle_code_analyze(prompt: str) -> None:
    """
    code analyze: <path>
    """
    try:
        from mammoth_os.agents.coding_agent import CodingAgent  # type: ignore
    except Exception as e:
        console.print(f"[bold red]❌ CodingAgent import failed:[/bold red] {e}")
        return

    path = prompt.split("code analyze:", 1)[1].strip()
    if not path:
        console.print("[bold red]❌ Missing path after 'code analyze:'[/bold red]")
        return

    agent = CodingAgent(router=None)
    try:
        result = asyncio.run(agent.analyze_codebase(path))  # type: ignore
    except Exception as e:
        console.print(f"[bold red]❌ CodingAgent.analyze_codebase error:[/bold red] {e}")
        return

    console.print(Text("\n🧠 Codebase Analysis\n", style="bold cyan"))
    console.print(Text(json.dumps(result, indent=2), style="green"))

def handle_code_refactor(prompt: str) -> None:
    """
    code refactor: <target> | <strategy>
    """
    try:
        from mammoth_os.agents.coding_agent import CodingAgent  # type: ignore
    except Exception as e:
        console.print(f"[bold red]❌ CodingAgent import failed:[/bold red] {e}")
        return

    payload = prompt.split("code refactor:", 1)[1].strip()
    if "|" not in payload:
        console.print("[bold red]❌ Use: code refactor: <target> | <strategy>[/bold red]")
        return

    target, strategy = [p.strip() for p in payload.split("|", 1)]
    if not target or not strategy:
        console.print("[bold red]❌ Both target and strategy are required.[/bold red]")
        return

    agent = CodingAgent(router=None)
    try:
        result = asyncio.run(agent.refactor(target, strategy))  # type: ignore
    except Exception as e:
        console.print(f"[bold red]❌ CodingAgent.refactor error:[/bold red] {e}")
        return

    console.print(Text("\n🧠 Refactor Result\n", style="bold cyan"))
    console.print(Text(result.get("refactored", "") or "// no refactor output", style="green"))
    console.print(Text("\nDiff:\n", style="bold magenta"))
    console.print(Text(result.get("diff", "") or "// no diff", style="yellow"))
    console.print(Text(f"\nConfidence: {result.get('confidence', 0.0):.2f}", style="bold green"))

def handle_code_docs(prompt: str) -> None:
    """
    code docs: <target>
    """
    try:
        from mammoth_os.agents.coding_agent import CodingAgent  # type: ignore
    except Exception as e:
        console.print(f"[bold red]❌ CodingAgent import failed:[/bold red] {e}")
        return

    target = prompt.split("code docs:", 1)[1].strip()
    if not target:
        console.print("[bold red]❌ Missing target after 'code docs:'[/bold red]")
        return

    agent = CodingAgent(router=None)
    try:
        result = asyncio.run(agent.write_docs(target))  # type: ignore
    except Exception as e:
        console.print(f"[bold red]❌ CodingAgent.write_docs error:[/bold red] {e}")
        return

    console.print(Text("\n📘 Documentation Result\n", style="bold cyan"))
    console.print(Text(result.get("documented_code", "") or "// no docs generated", style="green"))
    console.print(Text(f"\nDoc coverage: {result.get('doc_coverage_pct', 0.0):.2f}%", style="bold blue"))

def handle_code_commit(prompt: str) -> None:
    """
    code commit: interactive helper
    """
    try:
        from mammoth_os.agents.coding_agent import CodingAgent  # type: ignore
    except Exception as e:
        console.print(f"[bold red]❌ CodingAgent import failed:[/bold red] {e}")
        return

    console.print(Text("\n🧷 Code Commit Helper\n", style="bold cyan"))
    project_path = input("Project path: ").strip()
    files_raw = input("Files (comma-separated): ").strip()
    message = input("Commit message: ").strip()
    auto_push_raw = input("Auto-push? (y/N): ").strip().lower()

    if not project_path or not files_raw or not message:
        console.print("[bold red]❌ project_path, files, and message are required.[/bold red]")
        return

    files = [f.strip() for f in files_raw.split(",") if f.strip()]
    auto_push = auto_push_raw in ("y", "yes")

    agent = CodingAgent(router=None)
    try:
        result = asyncio.run(
            agent.commit_changes(
                project_path=project_path,
                files=files,
                message=message,
                auto_push=auto_push,
            )
        )  # type: ignore
    except Exception as e:
        console.print(f"[bold red]❌ CodingAgent.commit_changes error:[/bold red] {e}")
        return

    console.print(Text("\n✅ Commit Result\n", style="bold green"))
    console.print(Text(f"Hash: {result.get('commit_hash', '')}", style="green"))
    console.print(Text(f"Pushed: {result.get('pushed', False)}", style="green"))
    console.print(Text(f"Branch: {result.get('branch', 'main')}", style="green"))
    
    def handle_code_generate(prompt: str) -> None:
    try:# type: ignore
        from mammoth_os.agents.coding_agent import CodingAgent  # type: ignore
    except Exception as e:
        console.print(f"[bold red]❌ CodingAgent import failed:[/bold red] {e}")
        return

    code_prompt = prompt.split("code generate:", 1)[1].strip()
    if not code_prompt:
        console.print("[bold red]❌ Missing prompt after 'code generate:'[/bold red]")
        return

    agent = CodingAgent(router=None)
    try:
        result = asyncio.run(agent.generate_code(code_prompt, context={}))  # type: ignore
    except Exception as e:
        console.print(f"[bold red]❌ CodingAgent.generate_code error:[/bold red] {e}")
        return

    console.print(Text("\n🧠 Code Generation Result\n", style="bold cyan"))
    console.print(Text(result.get("code", "") or "// no code generated", style="green"))
    console.print(Text("\n🧪 Tests:\n", style="bold magenta"))
    console.print(Text(result.get("tests", "") or "// no tests generated", style="yellow"))
    console.print(Text("\n📘 Docs:\n", style="bold blue"))
    console.print(Text(result.get("docs", "") or "// no docs generated", style="cyan"))
    console.print(Text(f"\nConfidence: {result.get('confidence', 0.0):.2f}", style="bold green"))

    warnings = result.get("warnings", [])
    if warnings:
        console.print(Text("\n⚠️ Warnings:\n", style="bold yellow"))
        for w in warnings:
            console.print(Text(f"- {w}", style="yellow"))
    
    def handle_code_analyze(prompt: str) -> None:
    try:# type: ignore
        from mammoth_os.agents.coding_agent import CodingAgent  # type: ignore
    except Exception as e:
        console.print(f"[bold red]❌ CodingAgent import failed:[/bold red] {e}")
        return

    path = prompt.split("code analyze:", 1)[1].strip()
    if not path:
        console.print("[bold red]❌ Missing path after 'code analyze:'[/bold red]")
        return

    agent = CodingAgent(router=None)
    try:
        result = asyncio.run(agent.analyze_codebase(path))  # type: ignore
    except Exception as e:
        console.print(f"[bold red]❌ CodingAgent.analyze_codebase error:[/bold red] {e}")
        return

    console.print(Text("\n🧠 Codebase Analysis\n", style="bold cyan"))
    console.print(Text(json.dumps(result, indent=2), style="green"))
    
    def handle_code_refactor(prompt: str) -> None:
    try:# type: ignore
        from mammoth_os.agents.coding_agent import CodingAgent  # type: ignore
    except Exception as e:
        console.print(f"[bold red]❌ CodingAgent import failed:[/bold red] {e}")
        return

    payload = prompt.split("code refactor:", 1)[1].strip()
    if "|" not in payload:
        console.print("[bold red]❌ Use: code refactor: <target> | <strategy>[/bold red]")
        return

    target, strategy = [p.strip() for p in payload.split("|", 1)]
    if not target or not strategy:
        console.print("[bold red]❌ Both target and strategy are required.[/bold red]")
        return

    agent = CodingAgent(router=None)
    try:
        result = asyncio.run(agent.refactor(target, strategy))  # type: ignore
    except Exception as e:
        console.print(f"[bold red]❌ CodingAgent.refactor error:[/bold red] {e}")
        return

    console.print(Text("\n🧠 Refactor Result\n", style="bold cyan"))
    console.print(Text(result.get("refactored", "") or "// no refactor output", style="green"))
    console.print(Text("\nDiff:\n", style="bold magenta"))
    console.print(Text(result.get("diff", "") or "// no diff", style="yellow"))
    console.print(Text(f"\nConfidence: {result.get('confidence', 0.0):.2f}", style="bold green"))
    
    def handle_code_docs(prompt: str) -> None:
    try:# type: ignore
        from mammoth_os.agents.coding_agent import CodingAgent  # type: ignore
    except Exception as e:
        console.print(f"[bold red]❌ CodingAgent import failed:[/bold red] {e}")
        return

    target = prompt.split("code docs:", 1)[1].strip()
    if not target:
        console.print("[bold red]❌ Missing target after 'code docs:'[/bold red]")
        return

    agent = CodingAgent(router=None)
    try:
        result = asyncio.run(agent.write_docs(target))  # type: ignore
    except Exception as e:
        console.print(f"[bold red]❌ CodingAgent.write_docs error:[/bold red] {e}")
        return

    console.print(Text("\n📘 Documentation Result\n", style="bold cyan"))
    console.print(Text(result.get("documented_code", "") or "// no docs generated", style="green"))
    console.print(Text(f"\nDoc coverage: {result.get('doc_coverage_pct', 0.0):.2f}%", style="bold blue"))
    
    def handle_code_commit(prompt: str) -> None:
    try:# type: ignore
        from mammoth_os.agents.coding_agent import CodingAgent  # type: ignore
    except Exception as e:
        console.print(f"[bold red]❌ CodingAgent import failed:[/bold red] {e}")
        return

    console.print(Text("\n🧷 Code Commit Helper\n", style="bold cyan"))
    project_path = input("Project path: ").strip()
    files_raw = input("Files (comma-separated): ").strip()
    message = input("Commit message: ").strip()
    auto_push_raw = input("Auto-push? (y/N): ").strip().lower()

    if not project_path or not files_raw or not message:
        console.print("[bold red]❌ project_path, files, and message are required.[/bold red]")
        return

    files = [f.strip() for f in files_raw.split(",") if f.strip()]
    auto_push = auto_push_raw in ("y", "yes")

    agent = CodingAgent(router=None)
    try:
        result = asyncio.run(
            agent.commit_changes(
                project_path=project_path,
                files=files,
                message=message,
                auto_push=auto_push,
            )
        )  # type: ignore
    except Exception as e:
        console.print(f"[bold red]❌ CodingAgent.commit_changes error:[/bold red] {e}")
        return

    console.print(Text("\n✅ Commit Result\n", style="bold green"))
    console.print(Text(f"Hash: {result.get('commit_hash', '')}", style="green"))
    console.print(Text(f"Pushed: {result.get('pushed', False)}", style="green"))
    console.print(Text(f"Branch: {result.get('branch', 'main')}", style="green"))
    
# ──────────────────────────────────────────────────────────────
# CLI Loop
# ──────────────────────────────────────────────────────────────

def mammoth_cli(system_prompt: str) -> None:
    console.print(Text("\n🦣 Mammoth OS CLI — Agent Interface", style="bold cyan"))
    global CURRENT_AGENT

    agents = load_agents()

    while True:
        prompt = input("\nEnter prompt (or 'help' / 'exit'): ").strip()

        if not prompt:
            continue

        if prompt.lower() == "exit":
            break

        if prompt.lower().startswith("code generate:"):
            handle_code_generate(prompt)
            continue

        if prompt.lower().startswith("code analyze:"):
            handle_code_analyze(prompt)
            continue

        if prompt.lower().startswith("code refactor:"):
            handle_code_refactor(prompt)
            continue

        if prompt.lower().startswith("code docs:"):
            handle_code_docs(prompt)
            continue

        if prompt.lower().startswith("code commit:"):
            handle_code_commit(prompt)
            continue

        # Health
        if prompt.lower() == "health":
            results = health_check()
            console.print(Text("\n🦣 Mammoth OS Health Check\n", style="bold cyan"))
            for k, v in results.items():
                console.print(f"[yellow]{k}[/yellow]: [green]{v}[/green]")
            continue

        # Recall
        if prompt.lower() == "recall":
            context = recall_context()
            console.print(Text("\nRecalled Context", style="bold cyan"))
            console.print(Text(context, style="green"))
            continue

        # Switch agent
        if prompt.lower().startswith("set agent:"):
            new_agent = prompt.split("set agent:", 1)[1].strip().lower()
            if new_agent not in agents:
                console.print(
                    f"[bold red]⚠️ Unknown agent '{new_agent}'. Available:[/bold red] "
                    f"[yellow]{', '.join(agents.keys())}[/yellow]"
                )
                continue
            CURRENT_AGENT = new_agent
            console.print(f"[bold green]✅ Agent switched to '{CURRENT_AGENT}'.[/bold green]")
            continue

        # View agent
        if prompt.lower() == "view agent":
            console.print(
                f"[bold cyan]🦣 Current agent:[/bold cyan] [green]{CURRENT_AGENT}[/green]"
            )
            continue

        # Help
        if prompt.lower() == "help":
            console.print("[bold magenta]🦣 Mammoth OS CLI Commands:[/bold magenta]")
            commands = [
                ("set agent:", "<coding|field_ops>"),
                ("view agent", ""),
                ("health", ""),
                ("recall", ""),
                ("code generate:", "<prompt>"),
                ("code analyze:", "<path>"),
                ("code refactor:", "<target> | <strategy>"),
                ("code docs:", "<target>"),
                ("code commit:", "interactive"),
                ("exit", ""),
            ]
            for cmd, arg in commands:
                console.print(f"[yellow]{cmd}[/yellow] [green]{arg}[/green]")
            continue

        # Default: run through current agent
        try:
            agent_response = run_agent(agents, CURRENT_AGENT, prompt)
        except Exception as e:
            console.print(f"[bold red]⚠️ Agent execution error:[/bold red] {e}")
            continue

        console.print(Text("\nResponse:\n", style="bold cyan"))
        if isinstance(agent_response, dict):
            console.print(Text(json.dumps(agent_response, indent=2), style="green"))
        else:
            console.print(Text(str(agent_response), style="green"))

        # Log to Supabase
        try:
            supabase.table("mammoth_sessions").insert({
                "prompt": prompt,
                "response": agent_response,
                "agent": CURRENT_AGENT,
            }).execute()
        except Exception as e:
            console.print(f"[bold red]⚠️ Supabase logging error:[/bold red] {e}")

# ──────────────────────────────────────────────────────────────
# Warmup
# ──────────────────────────────────────────────────────────────

def warmup_engine(system_prompt: str) -> None:
    if not openai_client:
        console.print("[yellow]⚠️ OPENAI_API_KEY not set — skipping warmup.[/yellow]")
        return

    console.print(Text("\n🦣 MammothOS starting up...\n", style="bold cyan"))
    try:
        warmup = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "Confirm you are online in one sentence."},
            ],
        )
        console.print(Text(str(warmup.choices[0].message.content or ""), style="green"))
    except Exception as e:
        console.print(f"[bold red]⚠️ OpenAI warmup failed:[/bold red] {e}")

# ──────────────────────────────────────────────────────────────
# Entry Point
# ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    SYSTEM_PROMPT = load_system_prompt()
    warmup_engine(SYSTEM_PROMPT)
    mammoth_cli(SYSTEM_PROMPT)
