# insight_engine.py
from supabase import create_client, Client
import os
from dotenv import load_dotenv
from statistics import mean

load_dotenv()
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase: Client = create_client(url, key)  # type: ignore

def generate_insight(user_id: str):
    """Generate personalized learning insights."""
    metrics = (
        supabase.schema("atlas")
        .table("adaptive_metrics")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(10)
        .execute()
    ).data or []

    if not metrics:
        return "No performance data found."

    scores = [float(m.get("performance_score", 0)) for m in metrics] # type: ignore
    avg_score = mean(scores)
    fast_completions = [m for m in metrics if m.get("completion_time", {}).get("seconds", 0) < 600] # type: ignore
    slow_completions = [m for m in metrics if m.get("completion_time", {}).get("seconds", 0) > 1800] # type: ignore

    strengths = []
    weaknesses = []

    if avg_score > 80:
        strengths.append("Consistent high performance")
    if len(fast_completions) > len(metrics) / 2:
        strengths.append("Efficient learning pace")

    if avg_score < 60:
        weaknesses.append("Low retention or comprehension")
    if len(slow_completions) > len(metrics) / 2:
        weaknesses.append("Slow lesson completion")

    report = (
        f"🧠 Insight Report for {user_id}\n"
        f"Average Score: {avg_score:.1f}\n"
        f"Strengths: {', '.join(strengths) or 'None'}\n"
        f"Weaknesses: {', '.join(weaknesses) or 'None'}"
    )

    supabase.schema("atlas").table("insight_reports").insert({
        "user_id": user_id,
        "report_text": report,
        "strengths": strengths,
        "weaknesses": weaknesses
    }).execute()

    return report
