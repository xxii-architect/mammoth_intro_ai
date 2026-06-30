# pyright: reportUnknownArgumentType=false, reportUnknownMemberType=false, reportOptionalMemberAccess=false, reportOperatorIssue=false
# community_engine.py

from supabase import create_client, Client
from rich.console import Console
from rich.table import Table
import os
from dotenv import load_dotenv

load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

supabase: Client = create_client(url, key)  # type: ignore
console = Console()

def render_leaderboard():
    # IMPORTANT:
    # Use .from_() instead of .schema().table()
    # because .schema() does NOT work for views.
    response = (
        supabase
        .schema("atlas")  # type: ignore    
        .from_("leaderboard")
        .select("*")
        .execute()
    )

    data = response.data or []

    if not data:
        console.print("[bold red]⚠️ No leaderboard data found.[/bold red]")
        return

    table = Table(title="🏆 Mammoth OS Leaderboard")
    table.add_column("User", style="cyan")
    table.add_column("Lessons Completed", style="green")
    table.add_column("Streak (days)", style="yellow")
    table.add_column("Last Active", style="magenta")

    for row in data:
        table.add_row(
            row["user_id"], # type: ignore
            str(row["lessons_completed"]), # type: ignore
            str(row["streak_days"]), # type: ignore
            str(row["last_active"]) # type: ignore
        )

    console.print(table)
