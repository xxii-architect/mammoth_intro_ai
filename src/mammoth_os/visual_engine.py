# pyright: reportUnknownArgumentType=false, reportUnknownMemberType=false, reportOptionalMemberAccess=false, reportOperatorIssue=false
# visual_engine.py
from rich.console import Console
from rich.table import Table
from rich.progress import Progress
import plotext as plt
supabase.client import create_client
import os
from dotenv import load_dotenv

load_dotenv()
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase: Client = create_client(url, key)  # type: ignore
console = Console()

def render_progress(user_id: str):
    """Render progress dashboard for user."""
    progress_data = (
        supabase.schema("atlas")
        .table("atlas_progress")
        .select("*")
        .eq("user_id", user_id)
        .execute()
    ).data or []

    if not progress_data:
        console.print("[bold red]⚠️ No progress data found.[/bold red]")
        return

    table = Table(title=f"🦣 Mammoth OS Progress — {user_id}")
    table.add_column("Lesson", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Last Accessed", style="yellow")

    for row in progress_data:
        table.add_row(row.get("lesson_id", "—"), row.get("status", "—"), str(row.get("last_accessed", "—"))) # type: ignore

    console.print(table)

    # Chart visualization
    statuses = [row.get("status") for row in progress_data] # type: ignore
    completed = statuses.count("completed")
    in_progress = statuses.count("in_progress")
    not_started = statuses.count("not_started")

    plt.clear_plot() # type: ignore
    plt.bar(["Completed", "In Progress", "Not Started"], [completed, in_progress, not_started])
    plt.title("Lesson Completion Overview")
    plt.show()

def render_insight_summary(user_id: str):
    """Render latest insight report."""
    report = (
        supabase.schema("atlas")
        .table("insight_reports")
        .select("*")
        .eq("user_id", user_id)
        .order("generated_at", desc=True)
        .limit(1)
        .execute()
    ).data # type: ignore

    if not report:
        console.print("[bold red]⚠️ No insight report found.[/bold red]")
        return

    report = report[0]
    console.print(f"[bold cyan]{report['report_text']}[/bold cyan]") # type: ignore
