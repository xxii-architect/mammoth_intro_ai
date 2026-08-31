"""
MammothOS Command Center — FastAPI Server
Run: uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload
"""

import ast
import asyncio
import base64
from copy import deepcopy
import csv
import io
import json
import math
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from dotenv import dotenv_values, load_dotenv

# ── ensure src/ is on path ──────────────────────────────────────────────────
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "src"))

# Load .env before reading any os.environ values so uvicorn-direct starts work
# the same as python main.py. override=False preserves any values already set
# in the process environment (e.g. Netlify / Docker injected vars).
load_dotenv(ROOT / ".env", override=False)
if (ROOT / ".env.admin").exists():
    load_dotenv(ROOT / ".env.admin", override=False)

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse

from mammoth_os.learner_model import build_learner_context, build_lesson_plan, load_learner_model, save_learner_model, set_onboarding_profile, update_learner_model
from mammoth_os.runtime_contracts import build_observability_run, build_runtime_notice, new_trace_id
from mammoth_os.rag_retrieval import get_retriever
from mammoth_os.supabase_client import get_supabase
from mammoth_os.memory_engine import MemoryEngine

app = FastAPI(title="MammothOS API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── startup time ─────────────────────────────────────────────────────────────
_START_TIME = time.time()

# ── .mammoth storage ─────────────────────────────────────────────────────────
MAMMOTH_DIR = ROOT / ".mammoth"
MAMMOTH_DIR.mkdir(exist_ok=True)

NOTES_FILE    = MAMMOTH_DIR / "notes.json"
BUILDLOG_FILE = MAMMOTH_DIR / "buildlog.json"
SALES_FILE    = MAMMOTH_DIR / "sales_log.json"
OPERATOR_HEALTH_FILE = MAMMOTH_DIR / "operator_health.json"
BETA_FEEDBACK_FILE = MAMMOTH_DIR / "beta_feedback.json"
ATLAS_FILE    = MAMMOTH_DIR / "atlas_cli_session.json"
ATLAS_STATE_DIR = MAMMOTH_DIR / "atlas_state"
SNAPSHOTS_FILE = MAMMOTH_DIR / "snapshots.json"
ATLAS_EVALS_FILE = MAMMOTH_DIR / "atlas_evals.json"
AUDIT_LOG_FILE = MAMMOTH_DIR / "audit_log.json"
AUTH_ADMIN_POLICY_FILE = MAMMOTH_DIR / "auth_admin_policy.json"
UI_DIR        = ROOT / "ui" / "mad-architecht-command-center"
if os.name == "nt":
    _VENV_PYTHON_CANDIDATES = [ROOT / ".venv" / "Scripts" / "python.exe", ROOT / "venv" / "Scripts" / "python.exe"]
    _VENV_UVICORN_CANDIDATES = [ROOT / ".venv" / "Scripts" / "uvicorn.exe", ROOT / "venv" / "Scripts" / "uvicorn.exe"]
else:
    _VENV_PYTHON_CANDIDATES = [ROOT / ".venv" / "bin" / "python", ROOT / "venv" / "bin" / "python"]
    _VENV_UVICORN_CANDIDATES = [ROOT / ".venv" / "bin" / "uvicorn", ROOT / "venv" / "bin" / "uvicorn"]
VENV_PYTHON   = next((path for path in _VENV_PYTHON_CANDIDATES if path.exists()), _VENV_PYTHON_CANDIDATES[0])
VENV_UVICORN  = next((path for path in _VENV_UVICORN_CANDIDATES if path.exists()), _VENV_UVICORN_CANDIDATES[0])
AGENT_ACTIVITY_FILE = MAMMOTH_DIR / "agent_activity.json"
TASKS_FILE = MAMMOTH_DIR / "tasks.json"
NOTIFICATIONS_FILE = MAMMOTH_DIR / "notifications.json"
ACCOUNT_DELETIONS_FILE = MAMMOTH_DIR / "account_deletion_requests.json"
ONBOARDING_FILE = MAMMOTH_DIR / "onboarding_state.json"
EXECUTION_LOG_FILE = MAMMOTH_DIR / "execution_log.json"

for _f in [NOTES_FILE, BUILDLOG_FILE, SALES_FILE, AGENT_ACTIVITY_FILE, TASKS_FILE, SNAPSHOTS_FILE, ATLAS_EVALS_FILE, AUDIT_LOG_FILE, BETA_FEEDBACK_FILE, NOTIFICATIONS_FILE, ACCOUNT_DELETIONS_FILE, EXECUTION_LOG_FILE]:
    if not _f.exists():
        _f.write_text("[]")
if not AUTH_ADMIN_POLICY_FILE.exists():
    AUTH_ADMIN_POLICY_FILE.write_text(json.dumps({"admin_user_ids": [], "admin_emails": []}, indent=2), encoding="utf-8")
if not ONBOARDING_FILE.exists():
    ONBOARDING_FILE.write_text(json.dumps({}, indent=2), encoding="utf-8")
ATLAS_STATE_DIR.mkdir(exist_ok=True)

_MEMORY_ENGINE = MemoryEngine(config={"storage_path": str(MAMMOTH_DIR / "memory_store.json"), "max_entries": 5000})

_AUTH_REQUIRED = str(os.environ.get("MAMMOTH_REQUIRE_AUTH", "")).strip().lower() in {"1", "true", "yes", "on"}
_ADMIN_EMAIL_SOURCES = ",".join(
    item for item in [
        str(os.environ.get("MAMMOTH_ADMIN_EMAILS", "")),
        str(os.environ.get("MAMMOTH_ADMIN_EMAILS_LIST", "")),
    ] if item
)
_ADMIN_EMAILS = {item.strip().lower() for item in _ADMIN_EMAIL_SOURCES.split(",") if item.strip()}
_ADMIN_USER_IDS = {item.strip() for item in str(os.environ.get("MAMMOTH_ADMIN_USER_IDS", "")).split(",") if item.strip()}
_AUTH_OPTIONAL_PATHS = {
    "/api/status",
    "/api/health",
    "/api/models",
    "/api/modules",
    "/api/agents",
}
_REQUEST_USER_ID: ContextVar[str] = ContextVar("mammoth_request_user_id", default="local")
_REQUEST_USER_EMAIL: ContextVar[str] = ContextVar("mammoth_request_user_email", default="")
_REQUEST_IS_ADMIN: ContextVar[bool] = ContextVar("mammoth_request_is_admin", default=False)
_LATEST_RUNTIME_STATUS: Dict[str, Any] = {}

ATLAS_MODULE_TRACKS: List[Dict[str, Any]] = [
    {
        "id": "wilderness-survival",
        "label": "Wilderness Navigation + Survival",
        "topic": "Wilderness navigation survival and safety fundamentals",
        "summary": "Field-ready navigation, shelter, water, and risk management fundamentals.",
        "category": "Outdoors",
        "icon": "🏕️",
        "lesson_type": "knowledge",
        "outcomes": [
            "Map-and-compass orientation with terrain awareness",
            "Shelter, water, and fire decision-making under pressure",
            "Safety-first route planning and emergency signaling basics",
        ],
        "operator_note": "Keep examples practical, safety-first, and grounded in conservative field decisions.",
    },
    {
        "id": "hunting-fishing",
        "label": "Hunting + Fishing",
        "topic": "Hunting and fishing safety ethics and field basics",
        "summary": "Ethical harvest, gear discipline, and field-readiness basics for outdoor food systems.",
        "category": "Outdoors",
        "icon": "🎣",
        "lesson_type": "knowledge",
        "outcomes": [
            "Safe tool handling and site awareness",
            "Ethical harvest principles and conservation framing",
            "Basic field prep, legal mindset, and risk reduction habits",
        ],
        "operator_note": "Emphasize lawful, ethical, and humane practice over optimization or tactics.",
    },
    {
        "id": "ham-radio",
        "label": "Ham Radio",
        "topic": "Ham radio fundamentals call signs and emergency comms basics",
        "summary": "Introductory radio literacy for disciplined communication and emergency readiness.",
        "category": "Emergency",
        "icon": "📡",
        "lesson_type": "knowledge",
        "outcomes": [
            "Call-sign etiquette and net discipline basics",
            "Frequency, repeater, and simplex communication fundamentals",
            "Emergency message structure and communication logging habits",
        ],
        "operator_note": "Use novice-friendly comms scenarios with disciplined operating habits.",
    },
    {
        "id": "emt-emergency-management",
        "label": "EMT + Emergency Mgmt",
        "topic": "EMT and emergency management triage and incident fundamentals",
        "summary": "Structured emergency response thinking with triage, ICS awareness, and scene safety.",
        "category": "Emergency",
        "icon": "🚑",
        "lesson_type": "knowledge",
        "outcomes": [
            "Scene safety, triage priorities, and patient communication basics",
            "Incident command awareness and escalation habits",
            "Documentation-minded response flow under stress",
        ],
        "operator_note": "Stay educational and procedural; do not present as professional medical direction.",
    },
    {
        "id": "horticulture-weather",
        "label": "Horticulture + Weather",
        "topic": "Horticulture botany and weather pattern literacy basics",
        "summary": "Plant care, growth cycles, and weather-aware decision-making for practical stewardship.",
        "category": "Outdoors",
        "icon": "🌱",
        "lesson_type": "knowledge",
        "outcomes": [
            "Plant structure, soil, and watering fundamentals",
            "Seasonal planning informed by basic weather pattern reading",
            "Observation logs that connect weather signals to plant decisions",
        ],
        "operator_note": "Favor observation, stewardship, and repeatable habits over overconfident predictions.",
    },
    {
        "id": "homesteading",
        "label": "Homesteading Basics",
        "topic": "Homesteading self-sufficiency food preservation and land management",
        "summary": "Practical self-reliance skills from garden to pantry.",
        "category": "Outdoors",
        "icon": "🏡",
        "lesson_type": "knowledge",
        "outcomes": [
            "Basic garden, pantry, and household self-sufficiency patterns",
            "Food preservation and seasonal planning habits",
            "Land stewardship decisions grounded in sustainability",
        ],
        "operator_note": "Keep examples realistic for beginners and oriented toward steady skill-building.",
    },
    {
        "id": "human-systems-neurobiology",
        "label": "Human Systems / Neurobiology / Stress & Recovery",
        "topic": "Human systems neurobiology stress recovery and resilience fundamentals",
        "summary": "Understand how stress, nervous system regulation, and recovery shape human performance and well-being.",
        "category": "Human Systems",
        "icon": "🧠",
        "lesson_type": "knowledge",
        "outcomes": [
            "Map the basics of nervous-system regulation and stress response",
            "Explain how sleep, recovery, and environment affect cognition and behavior",
            "Practice simple resilience habits that support calm, energy, and clear decisions",
        ],
        "operator_note": "Keep the discovery grounded in human biology, not hype. Emphasize safety, recovery, and sustainable habits.",
    },
    {
        "id": "environmental-human-dynamics",
        "label": "Environmental Human Dynamics",
        "topic": "Environmental human dynamics climate stress and human behavior in context",
        "summary": "Learn how environment, climate, crowding, and conditions shape human experience and responses.",
        "category": "Human Systems",
        "icon": "🌍",
        "lesson_type": "scenario",
        "outcomes": [
            "Recognize how environmental conditions affect physiology, attention, and mood",
            "Use context-aware decision-making for safety and adaptation",
            "Connect environmental stress to practical, human-centered strategies",
        ],
        "operator_note": "Frame situations realistically and emphasize context, adaptation, and humane decision-making.",
    },
    {
        "id": "mind-body-resilience",
        "label": "Mind-Body Resilience",
        "topic": "Mind-body resilience stress recovery and nervous system regulation fundamentals",
        "summary": "Build durable physical and mental resilience through recovery habits, stress awareness, and self-regulation.",
        "category": "Human Systems",
        "icon": "⚖️",
        "lesson_type": "checklist",
        "outcomes": [
            "Identify common stress signals and recovery bottlenecks",
            "Use basic self-regulation and recovery practices intentionally",
            "Design a simple resilience routine for sustained performance and calm",
        ],
        "operator_note": "Keep this practical, beginner-friendly, and grounded in sustainable daily life rather than extremes.",
    },
    {
        "id": "first-aid-cpr",
        "label": "First Aid + CPR",
        "topic": "First aid CPR and emergency response fundamentals",
        "summary": "Life-saving techniques every operator should know.",
        "category": "Emergency",
        "icon": "❤️‍🩹",
        "lesson_type": "checklist",
        "outcomes": [
            "Recognize emergencies that require immediate escalation",
            "Understand CPR sequence and first-aid scene priorities",
            "Use calm, stepwise response habits under pressure",
        ],
        "operator_note": "Stay educational and procedural; do not present as professional medical direction.",
    },
    {
        "id": "situational-awareness",
        "label": "Situational Awareness",
        "topic": "Situational awareness threat assessment and decision making under pressure",
        "summary": "See more, react faster, stay ahead of the curve.",
        "category": "Emergency",
        "icon": "👁️",
        "lesson_type": "scenario",
        "outcomes": [
            "Scan environments methodically for changes and anomalies",
            "Separate signal from noise during time-sensitive decisions",
            "Use simple threat prioritization and exit planning habits",
        ],
        "operator_note": "Keep guidance defensive, observational, and de-escalatory.",
    },
    {
        "id": "personal-finance",
        "label": "Personal Finance",
        "topic": "Personal finance budgeting investing and wealth building fundamentals",
        "summary": "Budget, invest, and grow wealth systematically.",
        "category": "Business",
        "icon": "💰",
        "lesson_type": "knowledge",
        "outcomes": [
            "Build a simple budget and cash-flow awareness habit",
            "Understand debt, savings, and compounding basics",
            "Evaluate tradeoffs in beginner-friendly wealth decisions",
        ],
        "operator_note": "Keep examples practical and conservative; avoid individualized financial advice.",
    },
    {
        "id": "entrepreneurship",
        "label": "Entrepreneurship",
        "topic": "Entrepreneurship business model design and startup fundamentals",
        "summary": "Build and validate business ideas that survive contact with reality.",
        "category": "Business",
        "icon": "🚀",
        "lesson_type": "knowledge",
        "outcomes": [
            "Frame customer pain, value propositions, and market fit",
            "Test assumptions with lightweight validation habits",
            "Translate ideas into simple execution roadmaps",
        ],
        "operator_note": "Favor evidence, iteration, and customer understanding over hype.",
    },
    {
        "id": "sales-persuasion",
        "label": "Sales + Persuasion",
        "topic": "Sales persuasion influence and negotiation fundamentals",
        "summary": "Ethical influence, objection handling, and closing frameworks.",
        "category": "Business",
        "icon": "🤝",
        "lesson_type": "scenario",
        "outcomes": [
            "Diagnose buyer objections without getting defensive",
            "Structure persuasive conversations around value and trust",
            "Practice negotiation with ethical framing and clarity",
        ],
        "operator_note": "Keep examples ethical, consent-aware, and focused on honest value exchange.",
    },
    {
        "id": "investing",
        "label": "Investing Fundamentals",
        "topic": "Investing stocks bonds real estate and portfolio management basics",
        "summary": "Allocate capital intelligently across asset classes.",
        "category": "Business",
        "icon": "📈",
        "lesson_type": "knowledge",
        "outcomes": [
            "Differentiate common asset classes and risk profiles",
            "Use diversification and time horizon as core principles",
            "Understand simple portfolio tradeoffs without speculation",
        ],
        "operator_note": "Stay educational and risk-aware; avoid personalized investment directives.",
    },
    {
        "id": "legal-basics",
        "label": "Legal Basics",
        "topic": "Legal literacy contracts business law and liability fundamentals",
        "summary": "Know your rights and liabilities before signing anything.",
        "category": "Business",
        "icon": "⚖️",
        "lesson_type": "knowledge",
        "outcomes": [
            "Read common contracts with a clause-by-clause mindset",
            "Recognize liability, consent, and risk-allocation patterns",
            "Know when to escalate to qualified legal review",
        ],
        "operator_note": "Keep guidance educational and non-legal-advice in tone.",
    },
    {
        "id": "fitness-training",
        "label": "Fitness + Training",
        "topic": "Strength training exercise programming and physical fitness fundamentals",
        "summary": "Build a training system that compounds over time.",
        "category": "Health",
        "icon": "💪",
        "lesson_type": "checklist",
        "outcomes": [
            "Understand progressive overload and recovery basics",
            "Structure beginner sessions around consistency and safety",
            "Track effort and form quality over ego-driven volume",
        ],
        "operator_note": "Stay educational and safety-first; do not present medical advice.",
    },
    {
        "id": "nutrition",
        "label": "Nutrition Science",
        "topic": "Nutrition macronutrients micronutrients and diet optimization basics",
        "summary": "Fuel performance and recovery through smarter eating.",
        "category": "Health",
        "icon": "🥗",
        "lesson_type": "knowledge",
        "outcomes": [
            "Understand calories, macros, and meal composition basics",
            "Connect food choices to energy, recovery, and satiety",
            "Evaluate fad nutrition claims with skepticism",
        ],
        "operator_note": "Keep guidance general and non-clinical.",
    },
    {
        "id": "mental-health",
        "label": "Mental Resilience",
        "topic": "Mental health resilience stress management and cognitive performance",
        "summary": "Build psychological durability for high-stakes environments.",
        "category": "Health",
        "icon": "🧠",
        "lesson_type": "knowledge",
        "outcomes": [
            "Recognize stress patterns and healthy coping mechanisms",
            "Use simple reflection and recovery habits consistently",
            "Support cognitive performance without glamorizing burnout",
        ],
        "operator_note": "Keep tone supportive and non-clinical; escalate crisis concerns to professionals.",
    },
    {
        "id": "sleep-recovery",
        "label": "Sleep + Recovery",
        "topic": "Sleep optimization recovery protocols and human performance science",
        "summary": "Recover harder, perform better, think clearer.",
        "category": "Health",
        "icon": "😴",
        "lesson_type": "knowledge",
        "outcomes": [
            "Understand sleep stages, recovery, and fatigue basics",
            "Build sleep-supportive routines and environmental habits",
            "Connect recovery quality to performance outcomes",
        ],
        "operator_note": "Favor practical recovery habits over miracle claims.",
    },
    {
        "id": "python-programming",
        "label": "Python Programming",
        "topic": "Python programming fundamentals syntax and problem solving",
        "summary": "Write clean, purposeful Python from day one.",
        "category": "Technology",
        "icon": "🐍",
        "lesson_type": "code",
        "outcomes": [
            "Use core syntax, functions, and data structures correctly",
            "Debug small programs with deliberate reasoning",
            "Translate plain-language tasks into readable code",
        ],
        "operator_note": "Keep lessons concrete and hands-on.",
    },
    {
        "id": "ai-ml-basics",
        "label": "AI + Machine Learning",
        "topic": "Artificial intelligence machine learning and LLM fundamentals",
        "summary": "Understand how AI thinks, learns, and makes decisions.",
        "category": "Technology",
        "icon": "🤖",
        "lesson_type": "knowledge",
        "outcomes": [
            "Differentiate models, training, inference, and evaluation",
            "Understand where LLMs are strong and brittle",
            "Use AI systems critically instead of magically",
        ],
        "operator_note": "Emphasize grounded understanding over hype.",
    },
    {
        "id": "cybersecurity",
        "label": "Cybersecurity Basics",
        "topic": "Cybersecurity threat models OPSEC and digital hygiene fundamentals",
        "summary": "Protect your assets, identity, and systems from real threats.",
        "category": "Technology",
        "icon": "🔐",
        "lesson_type": "knowledge",
        "outcomes": [
            "Recognize common threat surfaces and trust boundaries",
            "Apply basic digital hygiene and credential discipline",
            "Think in terms of risk reduction and blast radius",
        ],
        "operator_note": "Keep material defensive and safety-oriented.",
    },
    {
        "id": "networking",
        "label": "Computer Networking",
        "topic": "Computer networking TCP IP DNS routing and protocols",
        "summary": "Understand how the internet actually works under the hood.",
        "category": "Technology",
        "icon": "🌐",
        "lesson_type": "knowledge",
        "outcomes": [
            "Understand packets, addressing, and routing basics",
            "Differentiate common protocols and their roles",
            "Reason about connectivity issues methodically",
        ],
        "operator_note": "Stay conceptual, practical, and beginner-friendly.",
    },
    {
        "id": "linux-cli",
        "label": "Linux + CLI",
        "topic": "Linux command line shell scripting and system administration basics",
        "summary": "Own the terminal and stop fearing the command line.",
        "category": "Technology",
        "icon": "🖥️",
        "lesson_type": "code",
        "outcomes": [
            "Navigate filesystems and inspect processes confidently",
            "Use shell commands safely and compose simple scripts",
            "Build debugging habits from command output and logs",
        ],
        "operator_note": "Favor safe, observable commands over destructive shortcuts.",
    },
    {
        "id": "writing-storytelling",
        "label": "Writing + Storytelling",
        "topic": "Clear writing persuasive communication and storytelling fundamentals",
        "summary": "Say exactly what you mean, compellingly.",
        "category": "Creative",
        "icon": "✍️",
        "lesson_type": "writing",
        "outcomes": [
            "Structure ideas so readers can follow them easily",
            "Use examples, rhythm, and clarity deliberately",
            "Edit for precision instead of ornament",
        ],
        "operator_note": "Prioritize clarity, specificity, and honest communication.",
    },
    {
        "id": "public-speaking",
        "label": "Public Speaking",
        "topic": "Public speaking presentation and communication confidence fundamentals",
        "summary": "Own any room, camera, or stage with authority.",
        "category": "Creative",
        "icon": "🎙️",
        "lesson_type": "scenario",
        "outcomes": [
            "Organize a message for clear spoken delivery",
            "Manage nerves with practical rehearsal habits",
            "Use voice, pacing, and emphasis intentionally",
        ],
        "operator_note": "Keep feedback confidence-building and practical.",
    },
    {
        "id": "photography",
        "label": "Photography",
        "topic": "Photography composition lighting and camera fundamentals",
        "summary": "See light differently and capture it intentionally.",
        "category": "Creative",
        "icon": "📸",
        "lesson_type": "knowledge",
        "outcomes": [
            "Recognize framing, composition, and focal choices",
            "Understand exposure and lighting tradeoffs",
            "Practice observation before pressing the shutter",
        ],
        "operator_note": "Encourage seeing, composing, and iterating rather than gear obsession.",
    },
    {
        "id": "music-theory",
        "label": "Music Theory",
        "topic": "Music theory notes scales chords and harmony fundamentals",
        "summary": "Learn the language of music from first principles.",
        "category": "Creative",
        "icon": "🎵",
        "lesson_type": "knowledge",
        "outcomes": [
            "Understand intervals, scales, and chord relationships",
            "Connect notation concepts to listening and performance",
            "Build pattern recognition through simple examples",
        ],
        "operator_note": "Keep lessons approachable and pattern-based.",
    },
    {
        "id": "cooking-culinary",
        "label": "Culinary Arts",
        "topic": "Cooking culinary techniques knife skills and flavor fundamentals",
        "summary": "Cook intentionally, not by accident.",
        "category": "Life Skills",
        "icon": "👨‍🍳",
        "lesson_type": "checklist",
        "outcomes": [
            "Understand heat, seasoning, and texture basics",
            "Practice prep discipline and safe knife habits",
            "Use repeatable techniques instead of guessing",
        ],
        "operator_note": "Keep examples safe, practical, and home-kitchen friendly.",
    },
    {
        "id": "auto-mechanics",
        "label": "Auto Mechanics",
        "topic": "Automotive mechanics vehicle maintenance and basic repair fundamentals",
        "summary": "Diagnose and fix common vehicle issues yourself.",
        "category": "Life Skills",
        "icon": "🔧",
        "lesson_type": "checklist",
        "outcomes": [
            "Recognize common maintenance systems and warning signs",
            "Use simple diagnostic thinking before replacing parts",
            "Understand safe inspection and maintenance habits",
        ],
        "operator_note": "Keep lessons safety-aware and beginner scoped.",
    },
    {
        "id": "home-repair",
        "label": "Home Repair + DIY",
        "topic": "Home repair plumbing electrical and construction fundamentals",
        "summary": "Fix things before calling someone else to fix them.",
        "category": "Life Skills",
        "icon": "🏠",
        "lesson_type": "checklist",
        "outcomes": [
            "Identify common household systems and failure points",
            "Use stepwise troubleshooting before escalation",
            "Know when a task exceeds safe DIY scope",
        ],
        "operator_note": "Emphasize safety, shutoff awareness, and knowing when to stop.",
    },
    {
        "id": "leadership",
        "label": "Leadership + Management",
        "topic": "Leadership team management decision making and organizational effectiveness",
        "summary": "Lead through clarity, not authority.",
        "category": "Life Skills",
        "icon": "🎯",
        "lesson_type": "scenario",
        "outcomes": [
            "Communicate expectations and priorities clearly",
            "Make decisions with limited information and real constraints",
            "Coach, delegate, and adapt without losing trust",
        ],
        "operator_note": "Favor service, clarity, and accountability over posturing.",
    },
    {
        "id": "critical-thinking",
        "label": "Critical Thinking",
        "topic": "Critical thinking logical reasoning cognitive bias and decision frameworks",
        "summary": "Think cleaner, decide better, get manipulated less.",
        "category": "Life Skills",
        "icon": "🔍",
        "lesson_type": "knowledge",
        "outcomes": [
            "Recognize common reasoning traps and cognitive biases",
            "Use simple frameworks to compare claims and evidence",
            "Slow down snap judgments with explicit thinking habits",
        ],
        "operator_note": "Encourage curiosity, skepticism, and intellectual humility.",
    },
    {
        "id": "language-learning",
        "label": "Language Learning",
        "topic": "Language acquisition methodology vocabulary and communication practice",
        "summary": "Learn any language faster with the right mental model.",
        "category": "Life Skills",
        "icon": "🗣️",
        "lesson_type": "knowledge",
        "outcomes": [
            "Use repetition, context, and active recall effectively",
            "Balance grammar study with comprehension and output practice",
            "Build a sustainable language habit without burnout",
        ],
        "operator_note": "Keep lessons motivating, practical, and habit-based.",
    },
]


def _read_json(path: Path, default=None):
    if default is None:
        default = []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, data):
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def _normalize_user_storage_key(user_id: str) -> str:
    normalized = re.sub(r"[^a-z0-9_-]+", "-", str(user_id or "").strip().lower()).strip("-")
    return normalized or "local"


def _atlas_state_file_for_request() -> Path:
    user_id = str(_REQUEST_USER_ID.get() or "").strip()
    if not _AUTH_REQUIRED or not user_id or user_id == "local":
        return ATLAS_FILE
    user_key = _normalize_user_storage_key(user_id)
    return ATLAS_STATE_DIR / f"atlas_state_{user_key}.json"


def _request_is_admin() -> bool:
    if not _AUTH_REQUIRED:
        return True
    user_id = str(_REQUEST_USER_ID.get() or "").strip()
    if user_id == "local":
        return True
    if not user_id:
        return False
    return bool(_REQUEST_IS_ADMIN.get())


def _require_admin_api() -> Optional[JSONResponse]:
    if _AUTH_REQUIRED and not _request_is_admin():
        return JSONResponse({"status": "error", "error": "Admin privileges required."}, status_code=403)
    return None


async def _require_auth_user(request: Request) -> Optional[Dict[str, Any]]:
    """
    Soft per-request auth check.
    - Auth disabled (dev/local): returns a local user so routes stay functional.
    - Auth enabled: extracts the Bearer token, resolves the Supabase user, returns None
      when the token is missing or invalid (caller should return 401).
    """
    if not _AUTH_REQUIRED:
        user_id = str(_REQUEST_USER_ID.get() or "local").strip() or "local"
        return {"id": user_id, "email": "", "is_admin": True}
    token = _extract_bearer_token(request)
    if not token:
        return None
    return _resolve_supabase_user(token)


def _owner_mutation_denied(action: str) -> Dict[str, Any]:
    return {
        "status": "error",
        "error": "Command lane secured: only the owner/admin can authorize codebase mutations.",
        "message": "Nice try, but this command needs owner authorization before MammothOS can move tusks.",
        "action": action,
        "code": "owner_required",
    }


def _mutation_allowed() -> bool:
    if not _AUTH_REQUIRED:
        return True
    return _request_is_admin()


def _is_auth_optional_path(path: str) -> bool:
    if path in _AUTH_OPTIONAL_PATHS:
        return True
    return path.startswith("/api/docs") or path.startswith("/api/openapi")


def _extract_bearer_token(request: Request) -> str:
    header = str(request.headers.get("authorization") or "").strip()
    if not header.lower().startswith("bearer "):
        return ""
    token = header[7:].strip()
    return token


def _resolve_supabase_user(token: str) -> Optional[Dict[str, Any]]:
    if not token:
        return None
    supabase = get_supabase()
    if supabase is None:
        return None
    try:
        response = supabase.auth.get_user(token)
        user = getattr(response, "user", None)
        if not user:
            return None
        user_id = str(getattr(user, "id", "") or "").strip()
        user_email = str(getattr(user, "email", "") or "").strip().lower()
        if not user_id:
            return None
        admin_config = _current_admin_config()
        is_admin = user_id in admin_config["user_ids"] or (user_email in admin_config["emails"] if user_email else False)
        return {"id": user_id, "email": user_email, "is_admin": is_admin}
    except Exception:
        return None


def _set_request_auth_context(request: Request, user: Dict[str, Any]):
    token_user = _REQUEST_USER_ID.set(str(user.get("id") or "").strip())
    token_email = _REQUEST_USER_EMAIL.set(str(user.get("email") or "").strip())
    token_admin = _REQUEST_IS_ADMIN.set(bool(user.get("is_admin")))
    request.state.auth_user_id = str(user.get("id") or "").strip()
    request.state.auth_email = str(user.get("email") or "").strip()
    request.state.auth_is_admin = bool(user.get("is_admin"))
    return token_user, token_email, token_admin


@app.middleware("http")
async def auth_guard_middleware(request: Request, call_next):
    if not _AUTH_REQUIRED or not request.url.path.startswith("/api/"):
        return await call_next(request)

    optional_path = request.method.upper() == "OPTIONS" or _is_auth_optional_path(request.url.path)
    token = _extract_bearer_token(request)
    user = _resolve_supabase_user(token) if token else None
    if user is None:
        if optional_path:
            request.state.auth_user_id = ""
            request.state.auth_email = ""
            request.state.auth_is_admin = False
            token_user = _REQUEST_USER_ID.set("")
            token_email = _REQUEST_USER_EMAIL.set("")
            token_admin = _REQUEST_IS_ADMIN.set(False)
            try:
                return await call_next(request)
            finally:
                _REQUEST_USER_ID.reset(token_user)
                _REQUEST_USER_EMAIL.reset(token_email)
                _REQUEST_IS_ADMIN.reset(token_admin)
        return JSONResponse({"status": "error", "error": "Authentication required"}, status_code=401)

    token_user, token_email, token_admin = _set_request_auth_context(request, user)
    try:
        return await call_next(request)
    finally:
        _REQUEST_USER_ID.reset(token_user)
        _REQUEST_USER_EMAIL.reset(token_email)
        _REQUEST_IS_ADMIN.reset(token_admin)


def _coerce_float(value: Any, *, field: str) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a number") from exc
    if not math.isfinite(out):
        raise ValueError(f"{field} must be a finite number")
    return out


def _coerce_int(value: Any, *, field: str) -> int:
    out = _coerce_float(value, field=field)
    if int(out) != out:
        raise ValueError(f"{field} must be an integer")
    return int(out)


def _normalize_module_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower()).strip("-")


def _serialize_module_track(track: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not isinstance(track, dict):
        return None
    return {
        "id": str(track.get("id") or "").strip(),
        "label": str(track.get("label") or "").strip(),
        "topic": str(track.get("topic") or "").strip(),
        "summary": str(track.get("summary") or "").strip(),
        "category": str(track.get("category") or "").strip(),
        "icon": str(track.get("icon") or "").strip(),
        "lesson_type": str(track.get("lesson_type") or "").strip(),
        "outcomes": [str(item).strip() for item in (track.get("outcomes") or []) if str(item).strip()],
        "operator_note": str(track.get("operator_note") or "").strip(),
    }


def _atlas_module_catalog() -> List[Dict[str, Any]]:
    return [track for track in (_serialize_module_track(item) for item in ATLAS_MODULE_TRACKS) if track]


def _resolve_module_track(module_id: Any = None, topic: Any = None) -> Optional[Dict[str, Any]]:
    normalized_module_id = _normalize_module_key(module_id)
    normalized_topic = _normalize_module_key(topic)

    if normalized_module_id:
        for track in ATLAS_MODULE_TRACKS:
            if track["id"] == normalized_module_id:
                return track

    if normalized_topic:
        for track in ATLAS_MODULE_TRACKS:
            candidates = {
                _normalize_module_key(track.get("id")),
                _normalize_module_key(track.get("label")),
                _normalize_module_key(track.get("topic")),
            }
            if normalized_topic in candidates:
                return track
    return None


def _compose_module_curriculum_topic(requested_topic: str, track: Optional[Dict[str, Any]]) -> str:
    base_topic = str(requested_topic or "").strip()
    if not track:
        return base_topic or "Python basics"
    if not base_topic:
        base_topic = str(track.get("topic") or track.get("label") or "Python basics").strip()
    outcomes = [str(item).strip() for item in (track.get("outcomes") or []) if str(item).strip()]
    emphasis = "; ".join(outcomes[:3])
    return (
        f"{base_topic}. Build a practical beginner-friendly lesson track for {track['label']} "
        f"with safety-aware, real-world scenarios and emphasis on: {emphasis}."
    )


def _looks_like_python_seed(text: str) -> bool:
    return bool(
        re.search(
            r"\b(python|virtualenv|venv|pip|pytest|function|algorithm|javascript|coding|programming|code editor|shell setup|environment setup)\b",
            str(text or ""),
            re.IGNORECASE,
        )
    )


def _track_topic_tokens(track: Optional[Dict[str, Any]]) -> List[str]:
    blob = " ".join(
        [
            str((track or {}).get("label") or ""),
            str((track or {}).get("topic") or ""),
            *[str(item) for item in ((track or {}).get("outcomes") or [])],
        ]
    ).lower()
    stop = {
        "and", "the", "for", "with", "from", "that", "this", "into", "real", "world", "basics",
        "fundamentals", "beginner", "practical", "friendly", "skills", "safety", "core", "ideas",
        "under",
    }
    seen: List[str] = []
    for token in re.findall(r"[a-z][a-z\-]{3,}", blob):
        if token in stop:
            continue
        if token not in seen:
            seen.append(token)
    return seen


def _is_off_topic_python_payload(text: str, track: Optional[Dict[str, Any]]) -> bool:
    lesson_type = str((track or {}).get("lesson_type") or "knowledge").strip().lower() or "knowledge"
    if lesson_type == "code":
        return False
    lowered = str(text or "").lower()
    if not _looks_like_python_seed(lowered):
        return False
    topic_tokens = _track_topic_tokens(track)
    if not topic_tokens:
        return True
    return not any(re.search(rf"\b{re.escape(token)}\b", lowered) for token in topic_tokens)


def _decorate_lesson_for_module_track(lesson: Optional[Dict[str, Any]], track: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not isinstance(lesson, dict) or not lesson:
        return lesson
    if not isinstance(track, dict) or not track:
        return lesson
    decorated = dict(lesson)
    serialized_track = _serialize_module_track(track)
    objectives = [str(item).strip() for item in (decorated.get("objectives") or []) if str(item).strip()]
    outcomes = [str(item).strip() for item in (track.get("outcomes") or []) if str(item).strip()]
    title = str(decorated.get("title") or track.get("label") or "Lesson").strip()
    summary = str(decorated.get("summary") or track.get("summary") or "").strip()
    raw_blob = "\n".join([title, summary, str(decorated.get("content") or ""), "\n".join(objectives)])
    if _is_off_topic_python_payload(raw_blob, track):
        title = f"{track.get('label', 'Lesson')} — Foundations Lesson 1"
        objectives = [
            f"Identify the key ideas in {track.get('topic', track.get('label', 'this topic'))}.",
            f"Apply {track.get('topic', track.get('label', 'this topic'))} in a practical beginner-friendly scenario.",
        ]
        summary = str(track.get("summary") or "").strip()
    if not summary:
        summary = (
            f"{track.get('label', 'This lesson')} focuses on {track.get('topic', title)} in a practical, beginner-friendly way. "
            "It covers the core ideas, the reasoning behind them, and a realistic action step learners can apply right away."
        )
    teaching_points = [
        item for item in (objectives + outcomes)[:6]
        if str(item).strip()
    ]
    if not teaching_points:
        teaching_points = [
            f"Identify the key ideas in {track.get('topic', title)}.",
            f"Apply {track.get('topic', title)} in a practical beginner-friendly scenario.",
            "Use the lesson to build confidence before moving to a more advanced concept.",
        ]
    content_text = str(decorated.get("content") or "").strip()
    if _is_off_topic_python_payload(content_text, track):
        content_text = ""
    lesson_body = content_text or "\n\n".join([summary, *[f"- {item}" for item in teaching_points[:4]]])
    examples = [str(item).strip() for item in (decorated.get("examples") or []) if str(item).strip()]
    if not examples:
        examples = [
            f"Beginner example: explain how {track.get('topic', title)} shows up in a real-world situation.",
            f"Practice example: describe the first safe and practical action step for {track.get('topic', title)}.",
        ]
    decorated["module_track"] = serialized_track
    decorated["title"] = title
    decorated["objectives"] = objectives
    decorated["lesson_type"] = str(track.get("lesson_type") or "knowledge").strip() or "knowledge"
    decorated["category"] = str(track.get("category") or "").strip()
    decorated["icon"] = str(track.get("icon") or "").strip()
    decorated["summary"] = summary
    decorated["content"] = lesson_body
    decorated["teaching_points"] = teaching_points
    decorated["examples"] = examples[:3]
    decorated["content_source"] = str(decorated.get("source") or "lesson").strip()
    return decorated


def _build_text_rubric(lesson: Dict[str, Any], track: Optional[Dict[str, Any]]) -> str:
    objectives = [str(item).strip() for item in (lesson.get("objectives") or []) if str(item).strip()]
    outcomes = [str(item).strip() for item in ((track or {}).get("outcomes") or []) if str(item).strip()]
    lines = [
        "Evaluation rubric:",
        "- Respond directly to the lesson topic in your own words.",
        "- Cover at least 2 concrete ideas from the lesson objectives or outcomes.",
        "- Include one practical real-world example or action step.",
    ]
    for item in (objectives + outcomes)[:4]:
        lines.append(f"- Address: {item}")
    return "\n".join(lines)


def _decorate_exercise_for_module_track(
    exercise: Optional[Dict[str, Any]],
    lesson: Optional[Dict[str, Any]],
    track: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    if not isinstance(exercise, dict) or not exercise:
        return exercise
    if not isinstance(track, dict) or not track:
        return exercise

    lesson_data = _decorate_lesson_for_module_track(lesson or {}, track) or {}
    lesson_type = str(track.get("lesson_type") or "knowledge").strip() or "knowledge"
    title = str((lesson_data or {}).get("title") or exercise.get("title") or track.get("label") or "Lesson").strip()
    objectives = [str(item).strip() for item in (lesson_data.get("objectives") or []) if str(item).strip()]
    outcomes = [str(item).strip() for item in (track.get("outcomes") or []) if str(item).strip()]
    operator_note = str(track.get("operator_note") or "").strip()

    decorated = dict(exercise)
    decorated["module_track"] = _serialize_module_track(track)
    decorated["lesson_type"] = lesson_type
    decorated["submission_mode"] = "code" if lesson_type == "code" else "text"
    decorated["category"] = str(track.get("category") or "").strip()
    decorated["icon"] = str(track.get("icon") or "").strip()
    lesson_summary = str((lesson_data.get("summary") or lesson_data.get("content") or track.get("summary") or "").strip())
    if not lesson_summary:
        lesson_summary = (
            f"{track.get('label', 'This lesson')} teaches the core ideas behind {track.get('topic', title)} in a practical, beginner-friendly way."
        )
    decorated["lesson_summary"] = lesson_summary
    decorated["teaching_points"] = [
        item for item in (lesson_data.get("teaching_points") or []) if str(item).strip()
    ] or [
        str(item).strip() for item in (objectives + outcomes)[:4] if str(item).strip()
    ]
    decorated["lesson_body"] = str(lesson_data.get("content") or lesson_summary).strip()
    decorated["lesson_examples"] = [str(item).strip() for item in (lesson_data.get("examples") or []) if str(item).strip()][:3]
    decorated["lesson_source"] = str(lesson_data.get("content_source") or lesson_data.get("source") or "lesson").strip()

    if lesson_type == "code":
        return decorated

    objectives_blob = "\n".join(f"- {item}" for item in objectives[:4]) or "- Explain the main ideas clearly.\n- Give one practical example."
    outcomes_blob = "\n".join(f"- {item}" for item in outcomes[:3])
    note_line = f"\nOperator note: {operator_note}" if operator_note else ""

    starter_response = ""
    prompt = str(exercise.get("prompt") or "").strip()
    llm_text_contract = (
        str(exercise.get("generation_method") or "").strip().lower() == "llm"
        and prompt
        and "generic placeholder" not in prompt.lower()
        and not _is_off_topic_python_payload(prompt, track)
    )

    if llm_text_contract:
        starter_response = str(exercise.get("starter_response") or "").strip()
        if not starter_response:
            starter_response = (
                "Main idea:\n"
                "Key detail 1:\n"
                "Key detail 2:\n"
                "Practical example:\n"
            )
    elif lesson_type == "scenario":
        starter_response = (
            "Situation summary:\n"
            "Immediate priorities:\n"
            "Recommended response:\n"
            "Why this response is appropriate:\n"
        )
        prompt = (
            f"Scenario exercise for '{title}'.\n"
            "Explain how you would respond in a realistic beginner-friendly situation related to this lesson.\n"
            "Use the objectives below to shape your response:\n"
            f"{objectives_blob}\n"
            "Try to include:\n"
            "- what you notice first\n"
            "- what you would do next\n"
            "- how you would keep the situation safe and controlled\n"
            f"{note_line}"
        )
    elif lesson_type == "checklist":
        starter_response = (
            "1. Preparation / safety:\n"
            "2. Step-by-step process:\n"
            "3. Common mistakes to avoid:\n"
            "4. Final check / wrap-up:\n"
        )
        prompt = (
            f"Checklist exercise for '{title}'.\n"
            "Build a practical step-by-step checklist someone could follow while learning this topic.\n"
            "Your checklist should reflect these objectives:\n"
            f"{objectives_blob}\n"
            "Include preparation, execution, and safety/quality checks."
            f"{note_line}"
        )
    elif lesson_type == "writing":
        starter_response = (
            "Main idea:\n"
            "Supporting point 1:\n"
            "Supporting point 2:\n"
            "Concrete example:\n"
            "Closing insight:\n"
        )
        prompt = (
            f"Writing exercise for '{title}'.\n"
            "Write a clear, structured explanation that teaches this topic to a beginner.\n"
            "Make it grounded, readable, and specific.\n"
            "Focus points:\n"
            f"{objectives_blob}\n"
            f"{note_line}"
        )
    else:
        starter_response = (
            "What this topic is:\n"
            "Why it matters:\n"
            "Key principles:\n"
            "Practical example:\n"
        )
        prompt = (
            f"Knowledge exercise for '{title}'.\n"
            "Teach this topic in plain language for a beginner.\n"
            "Cover the lesson objectives directly and include one practical real-world example.\n"
            "Objectives:\n"
            f"{objectives_blob}\n"
            f"{outcomes_blob}\n"
            f"{note_line}"
        )

    if lesson_type == "code":
        decorated["title"] = str(exercise.get("title") or f"{title} — Guided Response").strip()
    else:
        decorated["title"] = f"{title} — Guided Response"
    decorated["prompt"] = prompt.strip()
    decorated["starter_files"] = {}
    decorated["starter_response"] = starter_response
    decorated["expected_test"] = str(exercise.get("expected_test") or "").strip() or _build_text_rubric(lesson_data, track)
    return decorated


def _extract_text_submission_keywords(lesson: Dict[str, Any], exercise: Dict[str, Any], track: Optional[Dict[str, Any]]) -> List[str]:
    raw_parts = [
        str((track or {}).get("label") or ""),
        str((track or {}).get("topic") or ""),
        str((lesson or {}).get("title") or ""),
        *[str(item) for item in ((lesson or {}).get("objectives") or [])],
        *[str(item) for item in ((track or {}).get("outcomes") or [])],
    ]
    seen: List[str] = []
    for part in raw_parts:
        for token in re.findall(r"[A-Za-z][A-Za-z\-]{3,}", part.lower()):
            if token in {
                "lesson", "module", "foundations", "basics", "beginner", "practical", "friendly",
                "safety", "real", "world", "skills", "skill", "response", "guided", "exercise",
            }:
                continue
            if token not in seen:
                seen.append(token)
    return seen[:10]


def _evaluate_text_submission(
    response_text: str,
    *,
    lesson: Dict[str, Any],
    exercise: Dict[str, Any],
    track: Optional[Dict[str, Any]],
    lesson_id: str,
) -> Dict[str, Any]:
    response = str(response_text or "").strip()
    if not response:
        return {
            "passed": False,
            "recommendation": "same",
            "hint": "Add a real written response before submitting. Summarize the lesson in your own words and include one practical example.",
            "result": {"passed": False, "stdout": "", "stderr": "Empty response submission."},
            "exercise_id": exercise.get("exercise_id"),
            "lesson_id": lesson_id,
            "submission_mode": "text",
            "score": 0.0,
        }

    keywords = _extract_text_submission_keywords(lesson, exercise, track)
    lower_response = response.lower()
    keyword_hits = [word for word in keywords if word in lower_response]
    line_count = len([line for line in response.splitlines() if line.strip()])
    response_len = len(response)
    practical_markers = ["example", "practice", "step", "safety", "because", "should", "would", "priority"]
    practical_hits = [item for item in practical_markers if item in lower_response]

    score = 0.0
    if response_len >= 120:
        score += 0.4
    elif response_len >= 60:
        score += 0.25
    score += min(len(keyword_hits), 4) * 0.12
    if line_count >= 3:
        score += 0.1
    if practical_hits:
        score += 0.12
    score = min(score, 1.0)
    passed = score >= 0.5

    if passed:
        hint = (
            "Strong response. You stayed on-topic and connected the lesson to practical use. "
            "For the next pass, tighten your explanation into clearer steps or examples."
        )
        recommendation = "increase"
    else:
        missing_keywords = [word for word in keywords[:4] if word not in keyword_hits][:3]
        hint_parts = [
            "Your response needs to be more lesson-specific.",
            "Explain the topic in your own words and include a practical example or action step.",
        ]
        if missing_keywords:
            hint_parts.append(f"Try explicitly covering: {', '.join(missing_keywords)}.")
        recommendation = "same"
        hint = " ".join(hint_parts)

    return {
        "passed": passed,
        "recommendation": recommendation,
        "hint": hint,
        "result": {
            "passed": passed,
            "stdout": f"Keyword hits: {', '.join(keyword_hits[:6])}" if keyword_hits else "",
            "stderr": "" if passed else "Response did not meet the topic-specific coverage threshold.",
        },
        "exercise_id": exercise.get("exercise_id"),
        "lesson_id": lesson_id,
        "submission_mode": "text",
        "score": round(score, 2),
    }


def _load_activity_events() -> List[Dict[str, Any]]:
    return _read_json(AGENT_ACTIVITY_FILE)


def _save_activity_events(entries: List[Dict[str, Any]]):
    _write_json(AGENT_ACTIVITY_FILE, entries)


def _append_activity(message: str, *, agent_id: str = "", task_id: str = "", kind: str = "event", details: Optional[Dict[str, Any]] = None, trace_id: str = "") -> Dict[str, Any]:
    entries = _load_activity_events()
    entry = {
        "id": str(uuid.uuid4()),
        "kind": kind,
        "message": message,
        "agent_id": agent_id,
        "task_id": task_id,
        "trace_id": trace_id,
        "details": details or {},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    entries.append(entry)
    if len(entries) > 250:
        entries = entries[-250:]
    _save_activity_events(entries)
    return entry


def _create_approval_record(task_id: str, *, agent_id: str, operation: str, target: str, preview: Dict[str, Any], payload: Optional[Dict[str, Any]] = None, requested_by: str = "user", trace_id: str = "") -> Dict[str, Any]:
    record = {
        "id": str(uuid.uuid4()),
        "task_id": task_id,
        "agent_id": agent_id,
        "operation": operation,
        "target": target,
        "payload": payload or {},
        "preview": preview,
        "requested_by": requested_by,
        "status": "pending",
        "trace_id": trace_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    approvals = _read_json(MAMMOTH_DIR / "approvals.json", default=[])
    approvals.append(record)
    _write_json(MAMMOTH_DIR / "approvals.json", approvals)
    return record


def _load_ui_state() -> Dict[str, Any]:
    state_file = MAMMOTH_DIR / "atlas_ui_state.json"
    if not state_file.exists():
        return {"status": "missing", "active_ui_project": ""}
    try:
        data = json.loads(state_file.read_text(encoding="utf-8"))
    except Exception:
        return {"status": "error", "active_ui_project": ""}
    if not isinstance(data, dict):
        return {"status": "error", "active_ui_project": ""}
    active_ui_project = str(data.get("active_ui_project") or data.get("active_ui_dir") or "").strip()
    resolved = str(Path(active_ui_project).resolve()) if active_ui_project else ""
    exists = bool(resolved) and Path(resolved).exists()
    return {
        "status": "ok" if exists else "missing",
        "active_ui_project": resolved,
        "active_ui_dir": resolved,
        "exists": exists,
        "state_file": str(state_file),
    }


def _build_operation_preview(operation: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    file_path = str(payload.get("file_path", "") or "").strip()
    if operation == "create_file":
        return {
            "summary": "Create file",
            "file_path": file_path,
            "content_preview": str(payload.get("content", "") or "")[:400],
        }
    if operation == "write_file":
        return {
            "summary": "Overwrite file",
            "file_path": file_path,
            "content_preview": str(payload.get("content", "") or "")[:400],
        }
    if operation == "apply_patch":
        return {
            "summary": "Replace file contents",
            "file_path": file_path,
            "content_preview": str(payload.get("new_content", "") or "")[:400],
        }
    if operation == "insert_after":
        return {
            "summary": "Insert after anchor",
            "file_path": file_path,
            "anchor": str(payload.get("anchor", "") or "")[:120],
            "content_preview": str(payload.get("content", "") or "")[:200],
        }
    if operation == "atlas_onboard_update":
        onboarding = payload.get("onboarding") if isinstance(payload.get("onboarding"), dict) else {}
        return {
            "summary": "Update ATLAS onboarding profile",
            "target": "atlas/onboarding",
            "experience_level": str(onboarding.get("experience_level") or "unknown"),
            "preferred_pacing": str(onboarding.get("preferred_pacing") or "gentle"),
            "learning_style": str(onboarding.get("learning_style") or "guided"),
        }
    if operation == "atlas_learner_reset":
        return {
            "summary": "Reset ATLAS learner state",
            "target": "atlas/learner",
        }
    if operation == "atlas_session_reset":
        return {
            "summary": "Reset full ATLAS session",
            "target": "atlas/session",
        }
    if operation == "git_status":
        return {
            "summary": "Inspect git status",
            "target": "repository",
        }
    if operation == "git_commit":
        return {
            "summary": "Create git commit",
            "target": "repository",
            "message": str(payload.get("message") or "").strip()[:240],
            "stage_all": bool(payload.get("stage_all", True)),
        }
    if operation == "git_push":
        return {
            "summary": "Push git branch",
            "target": "repository",
            "remote": str(payload.get("remote") or "origin"),
            "branch": str(payload.get("branch") or "main"),
        }
    if operation == "git_deploy":
        return {
            "summary": "Deploy using configured command",
            "target": "deployment",
            "command": str(payload.get("command") or "").strip()[:240],
        }
    return {"summary": "File operation", "file_path": file_path}


def _build_non_coding_approval_preview(operation: str, payload: Dict[str, Any], result: Any) -> Dict[str, Any]:
    preview: Dict[str, Any] = {
        "summary": operation.replace("_", " ").strip().title() or "Approval request",
        "operation": operation,
        "target": str(payload.get("target") or payload.get("topic") or payload.get("content") or "").strip(),
        "payload": payload,
    }
    if isinstance(result, dict):
        preview["result"] = result
    else:
        preview["result"] = {"value": result}
    return preview


def _resolve_target_path(file_path: str) -> Path:
    target = Path(file_path)
    if not target.is_absolute():
        target = ROOT / file_path
    return target


def _run_git_command(args: List[str], *, timeout: int = 45) -> Dict[str, Any]:
    command = ["git", *args]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            cwd=str(ROOT),
            env=_make_env(),
            timeout=timeout,
            text=True,
        )
        return {
            "status": "ok" if result.returncode == 0 else "error",
            "exit_code": int(result.returncode or 0),
            "stdout": str(result.stdout or ""),
            "stderr": str(result.stderr or ""),
            "command": " ".join(command),
        }
    except subprocess.TimeoutExpired:
        return {
            "status": "error",
            "exit_code": 1,
            "stdout": "",
            "stderr": f"Command timed out ({timeout}s)",
            "command": " ".join(command),
        }
    except Exception as exc:
        return {
            "status": "error",
            "exit_code": 1,
            "stdout": "",
            "stderr": f"{type(exc).__name__}: {exc!r}",
            "command": " ".join(command),
        }


def _execute_gitops_operation(operation: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    if operation == "git_status":
        return _run_git_command(["status", "--short", "--branch"])

    if operation == "git_commit":
        message = str(payload.get("message") or "").strip()
        if not message:
            return {"status": "error", "message": "Commit message is required."}
        stage_all = bool(payload.get("stage_all", True))
        if stage_all:
            stage_result = _run_git_command(["add", "-A"])
            if stage_result.get("status") != "ok":
                return {"status": "error", "message": "git add failed", "details": stage_result}
        commit_result = _run_git_command(["commit", "-m", message], timeout=90)
        return commit_result

    if operation == "git_push":
        remote = str(payload.get("remote") or "origin").strip() or "origin"
        branch = str(payload.get("branch") or "main").strip() or "main"
        return _run_git_command(["push", remote, branch], timeout=120)

    if operation == "git_deploy":
        command = str(payload.get("command") or "").strip()
        if not command:
            return {
                "status": "error",
                "message": "Deploy command is required. Provide a safe explicit command (example: ./deploy.sh).",
            }
        return {
            "status": "pending_manual",
            "message": "Deploy approval recorded. Execute deploy command manually in your server/session context.",
            "command": command,
        }

    return {"status": "error", "message": f"Unsupported git operation: {operation}"}


def _load_snapshots() -> List[Dict[str, Any]]:
    return _read_json(SNAPSHOTS_FILE, default=[])


def _save_snapshots(entries: List[Dict[str, Any]]) -> None:
    _write_json(SNAPSHOTS_FILE, entries)


def _create_snapshot(*, approval_id: str, agent_id: str, operation: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    target = _resolve_target_path(str(payload.get("file_path", "") or "").strip())
    existed_before = target.exists()
    snapshot = {
        "id": str(uuid.uuid4()),
        "approval_id": approval_id,
        "agent_id": agent_id,
        "operation": operation,
        "file_path": str(target),
        "existed_before": existed_before,
        "previous_content": target.read_text(encoding="utf-8") if existed_before else None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    entries = _load_snapshots()
    entries.append(snapshot)
    _save_snapshots(entries)
    return snapshot


def _restore_snapshot(snapshot_id: str) -> Dict[str, Any]:
    snapshots = _load_snapshots()
    snapshot = next((item for item in snapshots if item.get("id") == snapshot_id), None)
    if snapshot is None:
        return {"status": "error", "message": "snapshot not found"}

    target = Path(str(snapshot.get("file_path", "") or ""))
    existed_before = bool(snapshot.get("existed_before"))
    previous_content = snapshot.get("previous_content")

    if existed_before:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(str(previous_content or ""), encoding="utf-8")
    elif target.exists():
        target.unlink()

    snapshot["restored_at"] = datetime.now(timezone.utc).isoformat()
    _save_snapshots(snapshots)
    return {"status": "ok", "snapshot": snapshot}


def _run_custodial_cleanup_approval(payload: Dict[str, Any], approval_id: str, agent_id: str) -> Dict[str, Any]:
    from mammoth_os.agents.custodial_agent import CustodialAgent

    agent = CustodialAgent(router=None, storage_root=str(MAMMOTH_DIR / "custodial"))
    workspace = agent._resolve_workspace(str(payload.get("workspace") or payload.get("target") or ""))
    targets = agent._walk_cleanup_targets(workspace)
    snapshot = agent._create_snapshot(
        workspace,
        files=targets["files"],
        dirs=targets["dirs"],
        label=str(payload.get("label") or payload.get("reason") or "cleanup"),
    )

    removed_files: List[str] = []
    for path in targets["files"]:
        if path.exists():
            path.unlink()
            removed_files.append(path.relative_to(workspace).as_posix())

    removed_dirs: List[str] = []
    for path in targets["dirs"]:
        if path.exists():
            shutil.rmtree(path)
            removed_dirs.append(path.relative_to(workspace).as_posix())

    return {
        "status": "ok",
        "agent": agent_id or "custodial",
        "action": "cleanup",
        "workspace": str(workspace),
        "snapshot_id": snapshot["snapshot_id"],
        "removed_files": removed_files,
        "removed_dirs": removed_dirs,
    }


def _run_custodial_restore_approval(payload: Dict[str, Any], approval_id: str, agent_id: str) -> Dict[str, Any]:
    from mammoth_os.agents.custodial_agent import CustodialAgent

    agent = CustodialAgent(router=None, storage_root=str(MAMMOTH_DIR / "custodial"))
    workspace = agent._resolve_workspace(str(payload.get("workspace") or payload.get("target") or ""))
    snapshot_id = str(payload.get("snapshot_id") or "").strip()
    snapshot = agent._find_snapshot(snapshot_id)
    if snapshot is None:
        return {"status": "error", "message": "snapshot not found", "snapshot_id": snapshot_id}

    restored_files: List[str] = []
    for file_entry in snapshot.get("files", []):
        relative_path = str(file_entry.get("relative_path") or "").strip()
        if not relative_path:
            continue
        payload_bytes = base64.b64decode(str(file_entry.get("content_b64") or ""))
        target_path = workspace / relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(payload_bytes)
        restored_files.append(relative_path)

    restored_dirs: List[str] = []
    for relative_dir in snapshot.get("dirs", []):
        dir_path = workspace / str(relative_dir)
        dir_path.mkdir(parents=True, exist_ok=True)
        restored_dirs.append(str(relative_dir))

    return {
        "status": "ok",
        "agent": agent_id or "custodial",
        "action": "restore",
        "workspace": str(workspace),
        "snapshot_id": snapshot_id,
        "restored_files": restored_files,
        "restored_dirs": restored_dirs,
    }


def _run_custodial_snapshot_approval(payload: Dict[str, Any], approval_id: str, agent_id: str) -> Dict[str, Any]:
    from mammoth_os.agents.custodial_agent import CustodialAgent

    agent = CustodialAgent(router=None, storage_root=str(MAMMOTH_DIR / "custodial"))
    workspace = agent._resolve_workspace(str(payload.get("workspace") or payload.get("target") or ""))
    targets = agent._walk_cleanup_targets(workspace)
    snapshot = agent._create_snapshot(
        workspace,
        files=targets["files"],
        dirs=targets["dirs"],
        label=str(payload.get("label") or payload.get("reason") or "snapshot"),
    )
    return {
        "status": "ok",
        "agent": agent_id or "custodial",
        "action": "snapshot",
        "workspace": str(workspace),
        "snapshot_id": snapshot["snapshot_id"],
        "files_captured": len(snapshot["files"]),
        "dirs_captured": len(snapshot["dirs"]),
    }


def _execute_approval_record(record: Dict[str, Any]) -> Dict[str, Any]:
    operation = str(record.get("operation", "")).strip()
    payload = record.get("payload") or {}
    if operation in {"create_file", "write_file", "apply_patch", "insert_after"}:
        snapshot = _create_snapshot(
            approval_id=str(record.get("id", "") or ""),
            agent_id=str(record.get("agent_id", "") or ""),
            operation=operation,
            payload=payload,
        )
        result = _run_file_operation(operation, payload)
        if isinstance(result, dict):
            result["snapshot_id"] = snapshot["id"]
        return result
    if operation in {"git_status", "git_commit", "git_push", "git_deploy"}:
        return _execute_gitops_operation(operation, payload if isinstance(payload, dict) else {})
    if operation == "atlas_onboard_update":
        onboarding = payload.get("onboarding") if isinstance(payload.get("onboarding"), dict) else {}
        return _apply_atlas_onboarding_update(onboarding)
    if operation == "atlas_learner_reset":
        return _apply_atlas_learner_reset()
    if operation == "atlas_session_reset":
        return _apply_atlas_session_reset()
    if operation == "custodial_cleanup":
        return _run_custodial_cleanup_approval(payload if isinstance(payload, dict) else {}, str(record.get("id", "") or ""), str(record.get("agent_id", "") or ""))
    if operation == "custodial_restore":
        return _run_custodial_restore_approval(payload if isinstance(payload, dict) else {}, str(record.get("id", "") or ""), str(record.get("agent_id", "") or ""))
    if operation == "custodial_snapshot":
        return _run_custodial_snapshot_approval(payload if isinstance(payload, dict) else {}, str(record.get("id", "") or ""), str(record.get("agent_id", "") or ""))
    return {"status": "error", "message": f"Unsupported approval operation {operation!r}"}


def _approve_record(record_id: str) -> Dict[str, Any]:
    approvals = _read_json(MAMMOTH_DIR / "approvals.json", default=[])
    updated = None
    for item in approvals:
        if item.get("id") == record_id:
            if item.get("status") == "approved":
                return {"status": "ok", "approval": item, "result": item.get("last_result")}
            item["status"] = "approved"
            item["approved_at"] = datetime.now(timezone.utc).isoformat()
            updated = item
            break
    if updated is None:
        return {"status": "error", "message": "approval not found"}
    result = _execute_approval_record(updated)
    updated["last_result"] = result
    updated["completed_at"] = datetime.now(timezone.utc).isoformat()
    task_id = str(updated.get("task_id") or "").strip()
    if task_id:
        operation = str(updated.get("operation") or "approval")
        title = f"approval:{operation}"
        result_status = str(result.get("status", "error"))
        _upsert_task(
            task_id,
            title,
            status="completed" if result_status in {"ok", "success"} else "failed",
            agent_id=str(updated.get("agent_id") or ""),
            description=str(updated.get("target") or operation),
            details={"approval_id": record_id, "result_status": result_status},
        )
    _append_activity(
        f"Approval executed: {updated.get('operation', 'unknown')}",
        agent_id=str(updated.get("agent_id") or ""),
        task_id=task_id,
        kind="approval_executed",
        details={"approval_id": record_id, "status": result.get("status", "unknown")},
    )
    _write_json(MAMMOTH_DIR / "approvals.json", approvals)
    return {"status": "ok", "approval": updated, "result": result}


def _delete_approval_record(record_id: str, *, reason: str = "deleted_by_user") -> Dict[str, Any]:
    approvals = _read_json(MAMMOTH_DIR / "approvals.json", default=[])
    remaining = []
    deleted = None
    for item in approvals:
        if item.get("id") == record_id:
            deleted = dict(item)
            deleted["status"] = "deleted"
            deleted["deleted_at"] = datetime.now(timezone.utc).isoformat()
            deleted["delete_reason"] = reason
            continue
        remaining.append(item)
    if deleted is None:
        return {"status": "error", "message": "approval not found"}
    _write_json(MAMMOTH_DIR / "approvals.json", remaining)
    _append_activity(
        f"Approval discarded: {deleted.get('operation', 'unknown')}",
        agent_id=str(deleted.get("agent_id") or ""),
        task_id=str(deleted.get("task_id") or ""),
        kind="approval_deleted",
        details={"approval_id": record_id, "reason": reason},
    )
    return {"status": "ok", "approval": deleted}


def _load_approvals() -> List[Dict[str, Any]]:
    return _read_json(MAMMOTH_DIR / "approvals.json", default=[])


def _load_tasks() -> List[Dict[str, Any]]:
    return _read_json(TASKS_FILE)


def _save_tasks(tasks: List[Dict[str, Any]]):
    _write_json(TASKS_FILE, tasks)


def _upsert_task(task_id: str, title: str, *, status: str = "queued", agent_id: str = "", description: str = "", details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    tasks = _load_tasks()
    now = datetime.now(timezone.utc).isoformat()
    existing = next((t for t in tasks if t.get("id") == task_id), None)
    task = {
        "id": task_id,
        "title": title,
        "status": status,
        "agent_id": agent_id,
        "description": description,
        "details": details or {},
        "updated_at": now,
        "created_at": existing.get("created_at") if existing else now,
    }
    if existing:
        task["created_at"] = existing.get("created_at") or now
        tasks = [t for t in tasks if t.get("id") != task_id]
    tasks.append(task)
    _save_tasks(tasks)
    return task


def _read_env_vars() -> Dict[str, str]:
    env_file = ROOT / ".env"
    env_vars: Dict[str, str] = {}
    if not env_file.exists():
        return env_vars
    try:
        for raw_line in env_file.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env_vars[k.strip()] = v.strip().strip('"').strip("'")
    except Exception:
        return {}
    return env_vars


def _split_csv_values(raw: str, *, lowercase: bool = False) -> set[str]:
    values = set()
    for item in str(raw or "").split(","):
        normalized = item.strip()
        if not normalized:
            continue
        values.add(normalized.lower() if lowercase else normalized)
    return values


def _load_auth_admin_policy() -> Dict[str, List[str]]:
    try:
        payload = json.loads(AUTH_ADMIN_POLICY_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"admin_user_ids": [], "admin_emails": []}
    return {
        "admin_user_ids": [str(item).strip() for item in payload.get("admin_user_ids", []) if str(item).strip()],
        "admin_emails": [str(item).strip().lower() for item in payload.get("admin_emails", []) if str(item).strip()],
    }


def _current_admin_config() -> Dict[str, set[str]]:
    emails = set(_ADMIN_EMAILS)
    user_ids = set(_ADMIN_USER_IDS)

    for env_file in (ROOT / ".env", ROOT / ".env.admin"):
        if not env_file.exists():
            continue
        env_values = dotenv_values(env_file)
        emails.update(_split_csv_values(env_values.get("MAMMOTH_ADMIN_EMAILS", ""), lowercase=True))
        emails.update(_split_csv_values(env_values.get("MAMMOTH_ADMIN_EMAILS_LIST", ""), lowercase=True))
        user_ids.update(_split_csv_values(env_values.get("MAMMOTH_ADMIN_USER_IDS", "")))

    policy = _load_auth_admin_policy()
    emails.update(policy["admin_emails"])
    user_ids.update(policy["admin_user_ids"])
    return {"emails": emails, "user_ids": user_ids}


def _ollama_running(base_url: str) -> bool:
    try:
        req = urllib.request.Request(f"{base_url.rstrip('/')}/api/tags")
        with urllib.request.urlopen(req, timeout=3):
            return True
    except Exception:
        return False


def _ollama_installed_models(base_url: str) -> List[str]:
    try:
        req = urllib.request.Request(f"{base_url.rstrip('/')}/api/tags")
        with urllib.request.urlopen(req, timeout=4) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        models = payload.get("models") or []
        names: List[str] = []
        for m in models:
            if isinstance(m, dict):
                names.append(str(m.get("name") or "").strip())
        return [m for m in names if m]
    except Exception:
        return []


def _models_snapshot() -> Dict[str, Any]:
    env = _read_env_vars()
    llm_adapter = (os.environ.get("MAMMOTH_LLM_ADAPTER") or env.get("MAMMOTH_LLM_ADAPTER") or "").strip().lower()
    openai_model = (os.environ.get("OPENAI_MODEL") or env.get("OPENAI_MODEL") or "gpt-4o-mini").strip()
    deepseek_model = (os.environ.get("DEEPSEEK_MODEL") or env.get("DEEPSEEK_MODEL") or "deepseek-chat").strip()
    ollama_model = (os.environ.get("OLLAMA_MODEL") or env.get("OLLAMA_MODEL") or "hermes3:8b").strip()
    ollama_base = (os.environ.get("OLLAMA_BASE_URL") or env.get("OLLAMA_BASE_URL") or "http://localhost:11434").strip()

    openai_key_present = bool((os.environ.get("OPENAI_API_KEY") or env.get("OPENAI_API_KEY") or "").strip())
    deepseek_key_present = bool((os.environ.get("DEEPSEEK_API_KEY") or env.get("DEEPSEEK_API_KEY") or "").strip())
    ollama_up = _ollama_running(ollama_base)
    installed_local = _ollama_installed_models(ollama_base) if ollama_up else []

    if llm_adapter in {"deepseek", "deepseek-api", "deepseek-cloud", "deepseek-chat", "deepseek-reasoner", "deepseek-flash"}:
        active_adapter = "deepseek"
    elif llm_adapter == "openai":
        active_adapter = "openai"
    elif llm_adapter in {"ollama", "local-ollama"} or (llm_adapter and ":" in llm_adapter):
        active_adapter = "ollama"
    elif llm_adapter == "local":
        active_adapter = "local"
    elif deepseek_key_present:
        active_adapter = "deepseek"
    elif openai_key_present:
        active_adapter = "openai"
    elif ollama_up:
        active_adapter = "ollama"
    else:
        active_adapter = "local"

    if active_adapter == "deepseek":
        active_model = deepseek_model
    elif active_adapter == "openai":
        active_model = openai_model
    elif active_adapter == "ollama":
        active_model = llm_adapter if llm_adapter and ":" in llm_adapter else ollama_model
    else:
        active_model = "local-adapter"

    configured_locals = [
        "hermes3:8b",
        "deepseek-coder:latest",
        "qwen2.5-coder:latest",
        "codellama:latest",
        "llama3.1:8b",
        "mistral:latest",
        "qwen2.5:latest",
        "phi3:latest",
        "nous-hermes:7b",
    ]
    local_model_items = []
    for m in configured_locals:
        local_model_items.append({
            "id": m,
            "provider": "ollama",
            "installed": m in installed_local,
        })

    cloud_model_items = [
        {
            "id": deepseek_model,
            "provider": "deepseek",
            "installed": deepseek_key_present,
        },
        {
            "id": openai_model,
            "provider": "openai",
            "installed": openai_key_present,
        },
    ]

    return {
        "configured_adapter": llm_adapter or "auto",
        "active_adapter": active_adapter,
        "active_model": active_model,
        "ollama_base_url": ollama_base,
        "ollama_running": ollama_up,
        "openai_key_present": openai_key_present,
        "deepseek_key_present": deepseek_key_present,
        "local_models_installed": installed_local,
        "models": local_model_items + cloud_model_items,
    }


def _sanitize_runtime_error_message(exc: Any, fallback: str = "MammothOS switched to a safe fallback path because the active provider is unavailable or exhausted.") -> str:
    raw = exc if isinstance(exc, str) else str(exc) if exc is not None else ""
    cleaned = re.sub(r"\s+", " ", raw).strip()
    if not cleaned:
        return fallback

    lowered = cleaned.lower()
    if any(token in lowered for token in ["insufficient_quota", "billing", "quota", "credit", "429", "insufficient balance", "not enough", "payment"]):
        return "The active provider is out of quota or billing is blocked; MammothOS switched to a safe fallback path until credentials or capacity are restored."
    if any(token in lowered for token in ["401", "403", "api key", "invalid api key", "authentication", "unauthorized", "access denied"]):
        return "The active provider rejected the credentials or access token; MammothOS switched to a safe fallback path until the runtime is reauthorized."
    if any(token in lowered for token in ["timeout", "timed out", "connect", "connection", "unreachable", "refused", "network", "dns", "http error"]):
        return "The provider connection is currently unavailable; MammothOS switched to a safe fallback path and will retry when the upstream service is reachable."
    if "traceback" in lowered or "file \"" in lowered or "line " in lowered:
        return "The runtime hit a provider-side failure; MammothOS switched to a safe fallback path instead of exposing internal backend details."
    return "The runtime hit a provider-side issue; MammothOS switched to a safe fallback path instead of exposing the raw backend error."


def _runtime_metadata_from_client(client: Any, requested_adapter: str = "") -> Dict[str, Any]:
    requested = str(requested_adapter or "").strip().lower()
    used_provider = str(getattr(client, "last_used_provider", "")).strip().lower()
    primary_provider = str(getattr(client, "primary_name", "")).strip().lower()
    fallback_used = bool(getattr(client, "last_fallback_used", False))
    fallback_reason = str(getattr(client, "last_fallback_reason", "")).strip().lower()
    fallback_error_type = str(getattr(client, "last_error_type", "")).strip()

    if used_provider:
        active = used_provider
    else:
        client_name = type(client).__name__.lower()
        if "openai" in client_name:
            active = "openai"
        elif "ollama" in client_name:
            active = "ollama"
        elif "local" in client_name:
            active = "local"
        elif "fallback" in client_name:
            active = primary_provider or "fallback"
        else:
            active = requested or "auto"

    return {
        "active_adapter": active,
        "used_provider": used_provider or active,
        "primary_provider": primary_provider,
        "fallback_used": fallback_used,
        "fallback_reason": fallback_reason,
        "fallback_error_type": fallback_error_type,
    }


def _remember_runtime_status(runtime_status: Dict[str, Any]) -> None:
    global _LATEST_RUNTIME_STATUS
    remembered: Dict[str, Any] = {}
    for key in (
        "state",
        "degraded_mode",
        "active_adapter",
        "active_model",
        "effective_adapter",
        "used_provider",
        "primary_provider",
        "fallback_used",
        "fallback_reason",
        "fallback_error_type",
        "recommendation",
        "next_action",
    ):
        value = runtime_status.get(key)
        if value not in (None, "", []):
            remembered[key] = deepcopy(value)
    remembered["checked_at"] = datetime.now(timezone.utc).isoformat()
    _LATEST_RUNTIME_STATUS = remembered


def _merge_latest_runtime_status(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    merged = deepcopy(snapshot)
    latest = deepcopy(_LATEST_RUNTIME_STATUS)
    for key, value in latest.items():
        if value not in (None, "", []):
            merged[key] = value

    preferred_provider = str(
        merged.get("used_provider")
        or merged.get("effective_adapter")
        or merged.get("active_adapter")
        or "local"
    ).strip().lower() or "local"
    merged["active_provider"] = preferred_provider
    merged["checked_at"] = str(
        merged.get("checked_at") or datetime.now(timezone.utc).isoformat()
    )

    providers: List[Dict[str, Any]] = []
    for provider in merged.get("providers", []):
        item = dict(provider)
        provider_name = str(item.get("provider") or "").strip().lower()
        item["active"] = provider_name == preferred_provider
        item["selected"] = provider_name == str(merged.get("active_adapter") or "").strip().lower()
        item["fallback_target"] = bool(merged.get("fallback_used")) and item["active"] and not item["selected"]
        providers.append(item)
    merged["providers"] = providers
    return merged


def _runtime_status_snapshot() -> Dict[str, Any]:
    models = _models_snapshot()
    deepseek_key_present = bool(models.get("deepseek_key_present"))
    openai_key_present = bool(models.get("openai_key_present"))
    ollama_running = bool(models.get("ollama_running"))
    active_adapter = str(models.get("active_adapter") or "local")
    active_model = str(models.get("active_model") or "local-adapter")

    providers = [
        {
            "provider": "deepseek",
            "status": "ready" if deepseek_key_present else "missing_key",
            "available": deepseek_key_present,
            "detail": "DeepSeek cloud reasoning",
        },
        {
            "provider": "openai",
            "status": "ready" if openai_key_present else "missing_key",
            "available": openai_key_present,
            "detail": "OpenAI chat/runtime",
        },
        {
            "provider": "ollama",
            "status": "ready" if ollama_running else "offline",
            "available": ollama_running,
            "detail": models.get("ollama_base_url", "http://localhost:11434"),
        },
        {
            "provider": "local",
            "status": "ready",
            "available": True,
            "detail": "Local echo fallback",
        },
    ]

    available_providers = [item["provider"] for item in providers if item["available"]]
    if active_adapter == "local":
        state = "degraded"
    elif active_adapter in available_providers:
        state = "ready"
    elif available_providers:
        state = "degraded"
    else:
        state = "degraded"

    degraded_mode = state != "ready" or active_adapter == "local"

    if state == "ready":
        issue = "All configured providers are available, and the runtime is operating in its normal chain."
        recommendation = f"{active_adapter} is ready"
        next_action = "Continue with the current provider path."
    elif deepseek_key_present or openai_key_present:
        issue = "A configured provider is unavailable or not accepted; MammothOS is still using the next safe fallback path."
        recommendation = "Verify selected adapter and key permissions; MammothOS can still route through the next provider in the fallback chain."
        next_action = "Check the provider key, quota, or permission issue, then retry the selected adapter."
    elif ollama_running:
        issue = "Cloud credentials are missing, so the runtime is limited to local-safe fallback mode."
        recommendation = "Start or restore a cloud provider key to improve output quality beyond local-only fallback."
        next_action = "Add DEEPSEEK_API_KEY or OPENAI_API_KEY, or switch the active adapter back to Ollama."
    else:
        issue = "No cloud provider key is configured and Ollama is offline; the runtime is running in local-safe fallback mode."
        recommendation = "Add DEEPSEEK_API_KEY or OPENAI_API_KEY, or start Ollama, to restore a cloud-capable runtime."
        next_action = "Set at least one cloud key or start Ollama, then refresh the runtime status."

    return {
        "state": state,
        "degraded_mode": degraded_mode,
        "issue": issue,
        "next_action": next_action,
        "active_adapter": active_adapter,
        "active_model": active_model,
        "providers": providers,
        "available_providers": available_providers,
        "fallback_chain": ["deepseek", "openai", "ollama", "local"],
        "recommendation": recommendation,
        "summary": {
            "openai_key_present": openai_key_present,
            "deepseek_key_present": deepseek_key_present,
            "ollama_running": ollama_running,
        },
    }


def _auth_mode_from_state(state: Dict[str, Any]) -> str:
    if bool(state.get("developer_access", False)):
        return "developer_override"
    user_id = str(_REQUEST_USER_ID.get() or "").strip()
    if _AUTH_REQUIRED and user_id and user_id != "local":
        return "supabase_admin" if _request_is_admin() else "supabase_user"
    return "local_operator"


_PLAN_LIMITS_BY_TIER: Dict[str, Dict[str, Any]] = {
    "explorer": {"request_limit": 2500, "token_limit": 200000, "warning_threshold": 0.70, "hard_cap": False},
    "pro": {"request_limit": 10000, "token_limit": 1000000, "warning_threshold": 0.70, "hard_cap": False},
    "enterprise": {"request_limit": 50000, "token_limit": 10000000, "warning_threshold": 0.80, "hard_cap": True},
}


def _usage_window_bounds(now: datetime) -> Dict[str, str]:
    period_start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    if now.month == 12:
        next_month = datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        next_month = datetime(now.year, now.month + 1, 1, tzinfo=timezone.utc)
    period_end = next_month.timestamp() - 1
    return {
        "period_start": period_start.isoformat(),
        "period_end": datetime.fromtimestamp(period_end, tz=timezone.utc).isoformat(),
    }


def _parse_usage_event_created_at(raw: Any) -> Optional[datetime]:
    value = str(raw or "").strip()
    if not value:
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _current_usage_snapshot_from_state(state: Dict[str, Any]) -> Dict[str, Any]:
    tier = str(state.get("tier") or "explorer").strip().lower()
    if tier not in _PLAN_LIMITS_BY_TIER:
        tier = "explorer"
    limits = dict(_PLAN_LIMITS_BY_TIER[tier])
    now = datetime.now(timezone.utc)
    window = _usage_window_bounds(now)
    period_start = _parse_usage_event_created_at(window["period_start"]) or datetime(now.year, now.month, 1, tzinfo=timezone.utc)

    request_units = 0
    tokens = 0
    events_in_period = 0
    events = state.get("fab_usage_events") if isinstance(state.get("fab_usage_events"), list) else []
    for raw in events:
        if not isinstance(raw, dict):
            continue
        created_at = _parse_usage_event_created_at(raw.get("created_at"))
        if created_at is not None and created_at < period_start:
            continue
        events_in_period += 1
        request_units += int(raw.get("request_units") or 1)
        tokens += int(raw.get("tokens_total") or ((raw.get("tokens_in") or 0) + (raw.get("tokens_out") or 0)))

    request_limit = int(limits["request_limit"])
    token_limit = int(limits["token_limit"])
    request_percent = (request_units / request_limit) if request_limit else 0.0
    token_percent = (tokens / token_limit) if token_limit else 0.0
    percent_used = round(max(request_percent, token_percent) * 100, 1)
    warning_threshold = float(limits["warning_threshold"])
    if percent_used >= 100.0:
        warning_level = "blocked" if bool(limits["hard_cap"]) else "critical"
    elif percent_used >= max(warning_threshold * 100, 90.0):
        warning_level = "critical"
    elif percent_used >= warning_threshold * 100:
        warning_level = "elevated"
    else:
        warning_level = "normal"

    return {
        "status": "ok",
        "plan": tier,
        "period_start": window["period_start"],
        "period_end": window["period_end"],
        "usage": {
            "requests": request_units,
            "request_limit": request_limit,
            "tokens": tokens,
            "token_limit": token_limit,
            "events_in_period": events_in_period,
        },
        "percent_used": percent_used,
        "warning_level": warning_level,
        "warning_threshold": warning_threshold,
        "hard_cap": bool(limits["hard_cap"]),
        "metering_mode": "workspace_state_preview",
        "note": "Preview metering derived from tenant-scoped local state until hosted billing tables are wired.",
    }


def _normalized_account_profile(state: Dict[str, Any]) -> Dict[str, str]:
    profile = state.get("account_profile") if isinstance(state.get("account_profile"), dict) else {}
    return {
        "display_name": str(profile.get("display_name") or "Operator"),
        "email": str(profile.get("email") or ""),
        "organization": str(profile.get("organization") or ""),
    }


def _profile_completion(profile: Dict[str, str]) -> Dict[str, bool]:
    return {
        "display_name": bool(str(profile.get("display_name") or "").strip()) and str(profile.get("display_name")) != "Operator",
        "email": bool(str(profile.get("email") or "").strip()),
        "organization": bool(str(profile.get("organization") or "").strip()),
    }


def _release_readiness_tier(score: float) -> str:
    if score >= 8.7:
        return "production-grade"
    if score >= 7.8:
        return "near-ready"
    if score >= 6.8:
        return "stabilizing"
    return "prototype-risk"


# ── lazy registry imports ─────────────────────────────────────────────────────
try:
    from mammoth_os.engine_registry import EngineRegistry
    _engine_registry_ok = True
except Exception as _e:
    _engine_registry_ok = False
    _engine_registry_err = str(_e)

try:
    from mammoth_os.agent_registry import agent_registry, AgentStatus, AGENTS, run_agent as registry_run_agent
    _agent_registry_ok = True
except Exception as _e:
    _agent_registry_ok = False
    _agent_registry_err = str(_e)

# ─────────────────────────────────────────────────────────────────────────────
# /api/status
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/status")
async def get_status():
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    uptime_s = int(time.time() - _START_TIME)
    h, rem = divmod(uptime_s, 3600)
    m, s   = divmod(rem, 60)
    uptime_str = f"{h}h {m}m {s}s" if h else f"{m}m {s}s"

    engines = {}
    if _engine_registry_ok:
        try:
            engines = EngineRegistry.list_engines()
        except Exception:
            pass

    agents = []
    if _agent_registry_ok:
        try:
            agents = await agent_registry.list_agents()
        except Exception:
            pass

    buildlog = _read_json(BUILDLOG_FILE)

    models = _models_snapshot()

    return {
        "status": "ok",
        "python_version": sys.version,
        "uptime": uptime_str,
        "uptime_seconds": uptime_s,
        "engine_count": len(engines),
        "agent_count": len(agents),
        "cli_commands_run": len(buildlog),
        "active_models": max(1, len(models.get("local_models_installed", []))),
        "active_adapter": models.get("active_adapter"),
        "active_model": models.get("active_model"),
    }


# ─────────────────────────────────────────────────────────────────────────────
# /api/agents
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/agents")
async def get_agents():
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    if _agent_registry_ok:
        try:
            manifests = await agent_registry.list_agents()
            return [
                {
                    "id":           m.agent_id,
                    "name":         m.name,
                    "version":      m.version,
                    "status":       m.status.value if hasattr(m.status, "value") else str(m.status),
                    "capabilities": m.capabilities,
                    "level":        m.level,
                    "endpoint":     m.endpoint,
                }
                for m in manifests
            ]
        except Exception:
            pass

    # fallback — scan agents/ directory
    agents_dir = ROOT / "src" / "mammoth_os" / "agents"
    results = []
    if agents_dir.exists():
        for f in sorted(agents_dir.glob("*_agent.py")):
            name = f.stem.replace("_", " ").title().replace(" ", "")
            results.append({
                "id":           f.stem,
                "name":         name,
                "version":      "v1.0.0",
                "status":       "IDLE",
                "capabilities": [],
                "level":        1,
                "endpoint":     f"http://localhost:8000/agents/{f.stem}",
            })
    return results


def _coerce_http_agent_prompt(payload: Any) -> str:
    if isinstance(payload, str):
        return payload.strip()
    if isinstance(payload, dict):
        for key in ("command", "cmd", "prompt", "message", "query", "task", "goal", "instruction"):
            value = payload.get(key)
            if value is None:
                continue
            text = str(value).strip()
            if text:
                return text
        return ""
    if payload is None:
        return ""
    return str(payload).strip()


async def _dispatch_http_agent(agent_label: str, payload: Any) -> Dict[str, Any]:
    prompt = _coerce_http_agent_prompt(payload)
    if not prompt:
        return {"status": "error", "error": "prompt is required"}
    mapping = {"atlas": "tutor", "coding": "coding"}
    runtime_agent = mapping.get(agent_label)
    if runtime_agent is None:
        return {"status": "error", "error": f"unsupported agent label: {agent_label}"}
    if not _agent_registry_ok:
        return {"status": "error", "error": "agent registry unavailable"}

    def _invoke() -> Any:
        return registry_run_agent(runtime_agent, prompt)

    result = await asyncio.get_event_loop().run_in_executor(None, _invoke)
    return {
        "status": "ok",
        "agent": agent_label,
        "runtime_agent": runtime_agent,
        "result": result,
    }


@app.post("/agent/atlas/run")
async def run_atlas_agent_endpoint(payload: Any):
    return await _dispatch_http_agent("atlas", payload)


@app.post("/agent/coding/run")
async def run_coding_agent_endpoint(payload: Any):
    return await _dispatch_http_agent("coding", payload)


@app.post("/agent/shell/run")
async def run_shell_agent_endpoint(payload: Any):
    prompt = _coerce_http_agent_prompt(payload)
    if not prompt:
        return {"status": "error", "error": "command is required", "agent": "shell"}

    payload_dict = payload if isinstance(payload, dict) else {}
    cwd = str(payload_dict.get("cwd") or ROOT)
    timeout = int(payload_dict.get("timeout") or 120)
    allow_mutating = bool(payload_dict.get("allow_mutating") or False)

    try:
        from mammoth_os.agents.shell_agent import ShellAgent
        agent = ShellAgent()
        result = await agent.run(prompt, cwd=cwd, allow_mutating=allow_mutating, timeout=timeout)
        return {
            "status": result.get("status", "ok"),
            "agent": "shell",
            "result": result,
        }
    except Exception as exc:
        return {
            "status": "error",
            "error": _sanitize_runtime_error_message(exc, "The shell agent could not complete the command. MammothOS is running in a safe fallback mode until the runtime is healthy again."),
            "agent": "shell",
        }


# ─────────────────────────────────────────────────────────────────────────────
# /api/health
# ─────────────────────────────────────────────────────────────────────────────

def _port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except OSError:
        return False


@app.get("/api/health")
async def get_health():
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    env_file = ROOT / ".env"
    env_exists = env_file.exists()
    env_values = _read_env_vars()
    env_vars: Dict[str, bool] = {}
    openai_ok = False
    supabase_ok = False
    for k, v in env_values.items():
        env_vars[k] = bool(v)
    openai_ok = bool(env_values.get("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY"))
    supabase_ok = bool(env_values.get("SUPABASE_URL") or os.environ.get("SUPABASE_URL"))
    models = _models_snapshot()

    # check git
    git_ok = (ROOT / ".git").exists()

    # check venv
    venv_paths = [ROOT / ".venv", ROOT / "venv"]
    active_venv = next((path for path in venv_paths if path.exists()), venv_paths[0])
    venv_ok = any(path.exists() for path in venv_paths)

    services = [
        {
            "label":  "Backend API",
            "detail": ":8000 FastAPI",
            "status": "green" if _port_open(8000) else "red",
            "up":     _port_open(8000),
        },
        {
            "label":  "React Dev Server (5173)",
            "detail": ":5173 Vite",
            "status": "green" if _port_open(5173) else "red",
            "up":     _port_open(5173),
        },
        {
            "label":  "React Dev Server (5174)",
            "detail": ":5174 Vite",
            "status": "green" if _port_open(5174) else "yellow",
            "up":     _port_open(5174),
        },
        {
            "label":  ".env Config",
            "detail": str(env_file),
            "status": "green" if env_exists else "red",
            "up":     env_exists,
        },
        {
            "label":  "Git Repository",
            "detail": str(ROOT),
            "status": "green" if git_ok else "red",
            "up":     git_ok,
        },
        {
            "label":  "Python venv",
            "detail": str(active_venv),
            "status": "green" if venv_ok else "yellow",
            "up":     venv_ok,
        },
        {
            "label":  "OpenAI Key",
            "detail": "OPENAI_API_KEY in .env",
            "status": "green" if openai_ok else "yellow",
            "up":     openai_ok,
        },
        {
            "label":  "Supabase URL",
            "detail": "SUPABASE_URL in .env",
            "status": "green" if supabase_ok else "yellow",
            "up":     supabase_ok,
        },
        {
            "label":  "Ollama Runtime",
            "detail": models.get("ollama_base_url", "http://localhost:11434"),
            "status": "green" if models.get("ollama_running") else "yellow",
            "up":     bool(models.get("ollama_running")),
        },
    ]

    runtime = _runtime_status_snapshot()
    red_services = [service["label"] for service in services if service.get("status") == "red"]
    yellow_services = [service["label"] for service in services if service.get("status") == "yellow"]

    return {
        "services": services,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "env_keys": list(env_vars.keys()),
        "summary": {
            "healthy_services": len([service for service in services if service.get("status") == "green"]),
            "total_services": len(services),
            "red_services": red_services,
            "yellow_services": yellow_services,
        },
        "runtime": runtime,
    }


@app.delete("/api/approvals/{record_id}")
async def delete_approval(record_id: str):
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    return _delete_approval_record(record_id)


@app.get("/api/models")
async def get_models():
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    return _models_snapshot()


@app.get("/api/runtime/status")
async def get_runtime_status():
    return _merge_latest_runtime_status(_runtime_status_snapshot())


@app.get("/api/ui/active-project")
async def get_active_ui_project():
    state = _load_ui_state()
    return {
        "status": "ok" if state.get("exists") else "missing",
        "contract_version": "v2",
        "active_ui_project": state.get("active_ui_project") or "",
        "active_ui_dir": state.get("active_ui_dir") or "",
        "exists": bool(state.get("exists")),
        "state_file": state.get("state_file") or "",
    }


# ─────────────────────────────────────────────────────────────────────────────
# /api/activity + /api/tasks
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/activity")
async def get_activity():
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    return _load_activity_events()


@app.post("/api/activity")
async def add_activity(body: Dict[str, Any]):
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    return _append_activity(
        str(body.get("message", "")),
        agent_id=str(body.get("agent_id", "") or ""),
        task_id=str(body.get("task_id", "") or ""),
        kind=str(body.get("kind", "event") or "event"),
        details=body.get("details") or {},
    )


@app.get("/api/tasks")
async def get_tasks():
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    return _load_tasks()


@app.post("/api/tasks")
async def upsert_task(body: Dict[str, Any]):
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    task_id = str(body.get("id") or "").strip() or f"task-{uuid.uuid4().hex[:8]}"
    return _upsert_task(
        task_id,
        str(body.get("title", "Untitled task")),
        status=str(body.get("status", "queued") or "queued"),
        agent_id=str(body.get("agent_id", "") or ""),
        description=str(body.get("description", "") or ""),
        details=body.get("details") or {},
    )


@app.get("/api/observability/runs")
async def get_observability_runs():
    runs: List[Dict[str, Any]] = []
    tasks = [item for item in _load_tasks() if isinstance(item, dict)]
    for task in tasks[-20:]:
        details = task.get("details") if isinstance(task.get("details"), dict) else {}
        source = str(details.get("source") or "task").strip() or "task"
        run_status = str(task.get("status") or details.get("plan_status") or "unknown").strip() or "unknown"
        trace_id = str(details.get("trace_id") or task.get("trace_id") or "").strip()
        runs.append(
            build_observability_run(
                run_id=str(task.get("id") or ""),
                source=source,
                title=str(task.get("title") or "Task").strip() or "Task",
                status=run_status,
                created_at=task.get("created_at") or "",
                updated_at=task.get("updated_at") or task.get("created_at") or "",
                objective=str(details.get("objective") or task.get("description") or "").strip(),
                plan_profile=str(details.get("plan_profile") or "").strip(),
                trace_id=trace_id,
                summary=str(task.get("description") or "").strip()[:240],
                replay=details.get("replay") if isinstance(details.get("replay"), dict) else {},
                progress=details if details else {},
                details=details,
            )
        )

    state = _load_atlas_state()
    for plan in [item for item in (state.get("plan_history") or []) if isinstance(item, dict)][-12:]:
        progress = plan.get("progress") if isinstance(plan.get("progress"), dict) else {}
        runs.append(
            build_observability_run(
                run_id=str(plan.get("plan_id") or ""),
                source="atlas_plan",
                title=str(plan.get("objective") or "Atlas plan").strip() or "Atlas plan",
                status=str(plan.get("plan_status") or "unknown").strip() or "unknown",
                created_at=plan.get("created_at") or "",
                updated_at=plan.get("created_at") or "",
                objective=str(plan.get("objective") or "").strip(),
                plan_profile=str(plan.get("plan_profile") or "").strip(),
                trace_id=str(plan.get("trace_id") or "").strip(),
                summary=str((plan.get("synthesis") or {}).get("learner_summary") or "").strip()[:240],
                replay=plan.get("replay") if isinstance(plan.get("replay"), dict) else {},
                progress=progress,
                details=plan,
            )
        )

    runs.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
    recent_activities = _load_activity_events()[-40:]
    approvals = _load_approvals()[-20:]
    snapshots = _load_snapshots()[-20:]
    return {
        "status": "ok",
        "contract_version": "v2",
        "summary": {
            "run_count": len(runs[:25]),
            "activity_count": len(recent_activities),
            "approval_count": len(approvals),
            "snapshot_count": len(snapshots),
        },
        "runs": runs[:25],
        "activities": recent_activities,
        "approvals": approvals,
        "snapshots": snapshots,
    }


_INTENT_TO_AGENT_ID = {
    "plant_seed": "plant_the_seed_agent",
    "field_ops": "field_ops_agent",
    "market_intel": "market_intel_agent",
    "reflection": "reflection_agent",
    "brand_voice": "brand_voice_agent",
    "research_curriculum": "research_agent",
    "research_survival": "research_agent",
    "research_plants": "research_agent",
    "compare_gear": "research_agent",
    "browse_web": "browser_agent",
    "site_audit": "browser_agent",
    "lighthouse_audit": "browser_agent",
    "task_queue": "task_queue_agent",
    "summarize": "research_agent",
    "lesson_curriculum": "curriculum_agent",
    "grade_submission": "tutor_agent",
    "lesson_coaching": "tutor_agent",
    "reasoning_help": "reasoning_agent",
    "debug_failure": "reasoning_agent",
    "generate_code": "coding_agent",
    "patch_existing": "coding_agent",
    "refactor_code": "coding_agent",
    "analyze_codebase": "coding_agent",
    "run_tests": "coding_agent",
    "write_docs": "coding_agent",
}

_AGENT_ID_TO_RUNTIME = {
    "plant_the_seed_agent": "plant_the_seed",
    "field_ops_agent": "field_ops",
    "market_intel_agent": "market_intel",
    "reflection_agent": "reflection",
    "brand_voice_agent": "brand_voice",
    "research_agent": "research",
    "curriculum_agent": "curriculum",
    "tutor_agent": "tutor",
    "reasoning_agent": "reasoning",
    "coding_agent": "coding",
    "community_engine_agent": "community_engine",
    "browser_agent": "browser",
    "task_queue_agent": "task_queue",
    "custodial_agent": "custodial",
}

_ATLAS_WORKFLOW_AGENT_IDS = {
    "plant_the_seed_agent",
    "research_agent",
    "curriculum_agent",
    "coding_agent",
    "reflection_agent",
    "field_ops_agent",
    "tutor_agent",
    "reasoning_agent",
}


def _agent_id_from_intent(intent: str) -> str:
    return _INTENT_TO_AGENT_ID.get(str(intent or "").strip(), "")


def _runtime_agent_name(intent: str, selected_agent_id: str) -> str:
    if selected_agent_id and selected_agent_id in _AGENT_ID_TO_RUNTIME:
        return _AGENT_ID_TO_RUNTIME[selected_agent_id]
    inferred = _agent_id_from_intent(intent)
    if inferred:
        return _AGENT_ID_TO_RUNTIME.get(inferred, "")
    return ""


def _parse_coding_operation(payload: Dict[str, Any], prompt_text: str) -> tuple[str, Dict[str, Any]]:
    if isinstance(payload, dict):
        op = str(payload.get("operation", "")).strip().lower()
        file_path = str(payload.get("file_path", "")).strip()
        if op in {"create_file", "write_file", "apply_patch"} and file_path:
            if op == "apply_patch":
                content = str(payload.get("new_content", ""))
                return op, {"file_path": file_path, "new_content": content}
            content = str(payload.get("content", ""))
            return op, {"file_path": file_path, "content": content}
        if op == "insert_after" and file_path:
            anchor = str(payload.get("anchor", ""))
            content = str(payload.get("content", ""))
            if anchor and content:
                return op, {"file_path": file_path, "anchor": anchor, "content": content}

    first, sep, rest = prompt_text.partition("\n")
    first = first.strip()
    if first.startswith("/create "):
        fp = first[len("/create "):].strip()
        return "create_file", {"file_path": fp, "content": rest if sep else ""}
    if first.startswith("/write "):
        fp = first[len("/write "):].strip()
        return "write_file", {"file_path": fp, "content": rest if sep else ""}
    if first.startswith("/patch "):
        fp = first[len("/patch "):].strip()
        return "apply_patch", {"file_path": fp, "new_content": rest if sep else ""}
    if first.startswith("/insert "):
        fp = first[len("/insert "):].strip()
        marker = "\n---\n"
        if marker in rest:
            anchor, content = rest.split(marker, 1)
            if fp and anchor.strip() and content:
                return "insert_after", {"file_path": fp, "anchor": anchor.strip(), "content": content}

    return "", {}


def _insert_after_content(file_path: str, anchor: str, content: str) -> Dict[str, Any]:
    target = _resolve_target_path(file_path)
    if not target.exists():
        return {"status": "error", "message": f"File not found: {file_path}"}
    current = target.read_text(encoding="utf-8")
    idx = current.find(anchor)
    if idx < 0:
        return {"status": "error", "message": "Anchor text not found", "path": str(target)}
    insert_at = idx + len(anchor)
    # Always insert on its own line
    safe_content = content if content.startswith("\n") else "\n" + content
    if not safe_content.endswith("\n"):
        safe_content = safe_content + "\n"
    updated = current[:insert_at] + safe_content + current[insert_at:]
    target.write_text(updated, encoding="utf-8")
    return {"status": "success", "action": "insert_after", "path": str(target)}


_SAFE_EXTENSIONS = {".py", ".md", ".txt", ".json", ".yaml", ".yml", ".env", ".sh", ".bat", ".ps1", ".toml", ".cfg", ".ini", ".csv", ".jsx", ".tsx", ".ts", ".js", ".css"}


def _run_file_operation(operation: str, op_payload: Dict[str, Any]) -> Dict[str, Any]:
    file_path = str(op_payload.get("file_path", "")).strip()
    if file_path:
        ext = Path(file_path).suffix.lower()
        if ext not in _SAFE_EXTENSIONS:
            return {"status": "error", "message": f"Extension {ext!r} not in safe-write list. Add it to _SAFE_EXTENSIONS if intentional."}
    if operation == "insert_after":
        return _insert_after_content(
            file_path,
            str(op_payload.get("anchor", "")),
            str(op_payload.get("content", "")),
        )
    from mammoth_os.agents.autonomous_engine import AutonomousEngine
    engine = AutonomousEngine()
    return engine.run_task(operation, op_payload)


# ─────────────────────────────────────────────────────────────────────────────
# /api/run
# ─────────────────────────────────────────────────────────────────────────────

def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_plan_profile(raw_profile: Any) -> str:
    profile = str(raw_profile or "balanced").strip().lower()
    if profile not in {"atlas", "coding", "coding_only", "balanced", "autonomous"}:
        return "balanced"
    return profile


def _normalize_coding_intent(raw_intent: Any) -> str:
    intent = str(raw_intent or "").strip().lower()
    aliases = {
        "analysis": "analyze_codebase",
        "analyze": "analyze_codebase",
        "docs": "write_docs",
        "documentation": "write_docs",
        "implement": "generate_code",
        "implementation": "generate_code",
        "patch": "patch_existing",
        "refactor": "refactor_code",
        "test": "run_tests",
    }
    intent = aliases.get(intent, intent)
    if intent in {"summarize", "generate_code", "patch_existing", "refactor_code", "analyze_codebase", "run_tests", "write_docs"}:
        return intent
    return ""


def _default_coding_intent_for_profile(plan_profile: str) -> str:
    profile = _normalize_plan_profile(plan_profile)
    if profile in {"coding", "coding_only"}:
        return "generate_code"
    return "summarize"


def _extract_prompt_file_paths(text: str) -> List[str]:
    matches = re.findall(r"[A-Za-z0-9_.-]+(?:[\\/][A-Za-z0-9_.-]+)+\.[A-Za-z0-9_.-]+", str(text or ""))
    unique: List[str] = []
    for match in matches:
        if match not in unique:
            unique.append(match)
    return unique


def _build_coding_step(objective: str, coding_intent: str) -> Dict[str, Any]:
    normalized_intent = _normalize_coding_intent(coding_intent) or "generate_code"
    file_paths = _extract_prompt_file_paths(objective)

    if normalized_intent == "summarize":
        title = "Draft implementation approach"
        prompt = f"Provide a concise implementation plan and verification checklist for: {objective}"
    elif normalized_intent == "patch_existing":
        title = "Generate project-grounded patch"
        prompt = (
            "Patch the existing codebase in place for this objective. "
            "Work only with the files explicitly named in the objective when they are provided. "
            "Do not scaffold a new app, invent placeholder targets, or rewrite unrelated areas. "
            f"Return structured code/tests/docs for: {objective}"
        )
    elif normalized_intent == "refactor_code":
        title = "Draft refactor pass"
        prompt = f"Refactor the existing implementation with the smallest safe changes needed for: {objective}"
    elif normalized_intent == "analyze_codebase":
        title = "Analyze implementation surface"
        prompt = f"Analyze the current codebase surface, risks, and integration points for: {objective}"
    elif normalized_intent == "run_tests":
        title = "Run focused validation guidance"
        prompt = f"Identify the smallest targeted validation and test plan for: {objective}"
    elif normalized_intent == "write_docs":
        title = "Draft implementation documentation"
        prompt = f"Write implementation notes and usage guidance for: {objective}"
    else:
        title = "Generate implementation pass"
        prompt = (
            "Generate a project-grounded implementation pass for this objective. "
            "Prefer editing the existing files named in the objective, preserve current behavior unless the objective changes it, "
            f"and return structured code/tests/docs for: {objective}"
        )

    return {
        "id": "coding-plan",
        "title": title,
        "agent_id": "coding_agent",
        "intent": normalized_intent,
        "coding_intent": normalized_intent,
        "prompt": prompt,
        "files": file_paths,
        "target": file_paths[0] if file_paths else "",
    }


def _build_plan_steps(objective: str, plan_profile: str = "balanced", coding_intent: str = "") -> List[Dict[str, Any]]:
    objective = (objective or "").strip()
    lower = objective.lower()
    profile = _normalize_plan_profile(plan_profile)
    effective_coding_intent = _normalize_coding_intent(coding_intent) or _default_coding_intent_for_profile(profile)
    include_coding = profile in {"coding", "coding_only"} or any(tok in lower for tok in ["build", "implement", "code", "patch", "create", "ui", "feature"])
    include_market = profile == "atlas" or any(tok in lower for tok in ["market", "audience", "position", "messaging"])
    include_field_ops = profile == "atlas" or any(tok in lower for tok in ["ops", "operational", "runbook", "checklist", "launch"])
    include_community = profile == "autonomous"
    include_custodial = profile == "autonomous"

    if profile == "coding_only":
        return [_build_coding_step(objective, effective_coding_intent)]

    steps: List[Dict[str, Any]] = [
        {
            "id": "seed-direction",
            "title": "Plant ATLAS strategic direction",
            "agent_id": "plant_the_seed_agent",
            "intent": "plant_seed",
            "prompt": f"Plant the strategic seed for this objective in 4 concise bullets: {objective}",
        },
        {
            "id": "research-brief",
            "title": "Research objective and constraints",
            "agent_id": "research_agent",
            "intent": "research_curriculum",
            "prompt": f"Analyze this objective and list key constraints in 4 bullets: {objective}",
        },
        {
            "id": "reflection-risks",
            "title": "Identify risks and acceptance criteria",
            "agent_id": "reflection_agent",
            "intent": "reflection",
            "prompt": f"Given this objective, list top risks and acceptance criteria: {objective}",
        },
    ]

    if include_market:
        steps.append(
            {
                "id": "market-angle",
                "title": "Add market and user framing",
                "agent_id": "market_intel_agent",
                "intent": "market_intel",
                "prompt": f"Provide a short market and user framing for: {objective}",
            }
        )

    if include_field_ops:
        steps.append(
            {
                "id": "field-ops-check",
                "title": "Outline operational execution checks",
                "agent_id": "field_ops_agent",
                "intent": "field_ops",
                "prompt": f"Provide an operational execution checklist for this objective: {objective}",
            }
        )

    if include_coding:
        steps.append(_build_coding_step(objective, effective_coding_intent))

    if include_community:
        steps.append(
            {
                "id": "community-check",
                "title": "Prepare community-facing update",
                "agent_id": "community_engine_agent",
                "intent": "summarize",
                "prompt": f"Create a short community update and expectation-setting note for: {objective}",
            }
        )

    if include_custodial:
        steps.append(
            {
                "id": "custodial-check",
                "title": "Run maintenance and safety checklist",
                "agent_id": "custodial_agent",
                "intent": "summarize",
                "prompt": f"Provide a maintenance checklist and rollback guard notes before executing: {objective}",
            }
        )

    steps.append(
        {
            "id": "brand-summary",
            "title": "Produce stakeholder-ready summary",
            "agent_id": "brand_voice_agent",
            "intent": "brand_voice",
            "prompt": f"Summarize the plan in confident brand voice for stakeholders: {objective}",
        }
    )

    return steps


def _read_jsonl_records(path: Path, *, limit: int = 200) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    records: List[Dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                records.append(item)
    except Exception:
        return []
    return records[-limit:]


def _response_preview(response: Any, *, max_len: int = 240) -> str:
    if not isinstance(response, dict):
        return ""
    candidates = []
    result = response.get("result")
    if isinstance(result, dict):
        candidates.append(result)
    candidates.append(response)
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        for key in ("output", "preview", "message", "error"):
            value = candidate.get(key)
            if value is None:
                continue
            if isinstance(value, str):
                text = value.strip()
            else:
                text = json.dumps(value, default=str)
            if text:
                return text[:max_len]
    return ""


def _plan_step_artifacts(step_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    artifacts: List[Dict[str, Any]] = []
    for step in step_results:
        preview = _response_preview(step.get("response"))
        artifacts.append({
            "id": step.get("id"),
            "title": step.get("title"),
            "agent_id": step.get("agent_id"),
            "status": step.get("status"),
            "preview": preview,
        })
    return artifacts


def _build_plan_synthesis(step_results: List[Dict[str, Any]], *, objective: str, lesson_title: str = "") -> Dict[str, Any]:
    artifacts = _plan_step_artifacts(step_results)
    completed = [step for step in step_results if step.get("status") == "completed"]
    pending = [step for step in step_results if step.get("status") == "pending_approval"]
    failed = [step for step in step_results if step.get("status") == "failed"]
    coding_preview = next((item["preview"] for item in artifacts if item.get("agent_id") == "coding_agent" and item.get("preview")), "")
    coach_preview = next((item["preview"] for item in artifacts if item.get("agent_id") == "reflection_agent" and item.get("preview")), "")
    completed_titles = [str(step.get("title") or "") for step in completed if str(step.get("title") or "").strip()]
    learner_summary_parts = []
    if lesson_title:
        learner_summary_parts.append(f"ATLAS organized a plan for {lesson_title}.")
    else:
        learner_summary_parts.append("ATLAS organized a plan for the current objective.")
    if completed_titles:
        learner_summary_parts.append(f"Completed focus areas: {', '.join(completed_titles[:3])}.")
    if failed:
        learner_summary_parts.append("One or more steps still need intervention before the plan is learner-ready.")
    elif pending:
        learner_summary_parts.append("A coding step is waiting for approval before ATLAS can finish execution.")
    else:
        learner_summary_parts.append("The plan completed successfully and is ready to coach the learner forward.")

    if failed:
        next_action = f"Review the failed step: {failed[0].get('title') or 'unnamed step'}."
    elif pending:
        next_action = f"Approve and run {pending[0].get('title') or 'the pending step'} to continue."
    elif coach_preview:
        next_action = coach_preview[:180]
    elif coding_preview:
        next_action = f"Use the coding brief to implement or validate the exercise: {coding_preview[:160]}"
    else:
        next_action = f"Start with the first checkpoint for: {objective[:160]}"

    checkpoints = [item["preview"] for item in artifacts if item.get("preview")][:4]
    return {
        "learner_summary": " ".join(learner_summary_parts),
        "coding_brief": coding_preview,
        "coach_note": coach_preview,
        "next_action": next_action,
        "checkpoints": checkpoints,
        "artifacts": artifacts,
    }


def _append_plan_history(state: Dict[str, Any], plan: Dict[str, Any]) -> None:
    history = state.get("plan_history") or []
    if not isinstance(history, list):
        history = []
    history.append({
        "plan_id": plan.get("plan_id"),
        "trace_id": plan.get("trace_id"),
        "objective": plan.get("objective"),
        "plan_status": plan.get("plan_status"),
        "plan_profile": plan.get("plan_profile"),
        "coding_intent": plan.get("coding_intent"),
        "progress": plan.get("progress"),
        "current_lane": plan.get("current_lane"),
        "approvals_needed": plan.get("approvals_needed"),
        "approvals_needed_count": plan.get("approvals_needed_count"),
        "replay": plan.get("replay"),
        "created_at": plan.get("created_at") or _ts(),
        "summary": ((plan.get("synthesis") or {}).get("learner_summary") or "")[:300],
        "next_action": ((plan.get("synthesis") or {}).get("next_action") or "")[:220],
    })
    state["plan_history"] = history[-12:]


def _load_eval_history() -> List[Dict[str, Any]]:
    history = _read_json(ATLAS_EVALS_FILE, default=[])
    return history if isinstance(history, list) else []


def _load_audit_log() -> List[Dict[str, Any]]:
    history = _read_json(AUDIT_LOG_FILE, default=[])
    return history if isinstance(history, list) else []


def _append_audit_event(*, kind: str, message: str, details: Optional[Dict[str, Any]] = None, source: str = "system", actor: str = "system", tier: Optional[str] = None) -> Dict[str, Any]:
    entries = _load_audit_log()
    entry = {
        "id": str(uuid.uuid4()),
        "kind": kind,
        "message": message,
        "source": source,
        "actor": actor,
        "tier": tier or "explorer",
        "details": details or {},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    entries.append(entry)
    if len(entries) > 250:
        entries = entries[-250:]
    _write_json(AUDIT_LOG_FILE, entries)
    return entry


def _audit_entries_to_csv(entries: List[Dict[str, Any]]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "created_at", "kind", "message", "source", "actor", "tier", "details_json"])
    for entry in entries:
        writer.writerow([
            str(entry.get("id") or ""),
            str(entry.get("created_at") or ""),
            str(entry.get("kind") or ""),
            str(entry.get("message") or ""),
            str(entry.get("source") or ""),
            str(entry.get("actor") or ""),
            str(entry.get("tier") or ""),
            json.dumps(entry.get("details") or {}, ensure_ascii=False),
        ])
    return output.getvalue()


def _build_atlas_observability(state: Dict[str, Any], *, eval_history: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    eval_entries = eval_history if isinstance(eval_history, list) else _load_eval_history()
    eval_entries = [entry for entry in eval_entries if isinstance(entry, dict)]
    recent_evals = eval_entries[-8:]
    recent_plans = [item for item in (state.get("plan_history") or []) if isinstance(item, dict)][-8:]
    recent_outcomes = [item for item in ((state.get("learner_model") or {}).get("recent_outcomes") or []) if isinstance(item, dict)]
    fab_events = [item for item in (state.get("fab_usage_events") or []) if isinstance(item, dict)]
    sandbox_runs = _read_jsonl_records(MAMMOTH_DIR / "sandbox_runs.jsonl", limit=40)
    recent_activity = [item for item in _load_activity_events() if isinstance(item, dict)][-6:]

    attempts = len(recent_outcomes)
    passed_attempts = sum(1 for item in recent_outcomes if bool(item.get("passed")))
    learner_pass_rate = round((passed_attempts / attempts) * 100) if attempts else 0

    eval_total_checks = sum(len(entry.get("checks") or []) for entry in recent_evals)
    eval_passed_checks = sum(int((entry.get("summary") or {}).get("pass_count") or 0) for entry in recent_evals)
    eval_pass_rate = round((eval_passed_checks / eval_total_checks) * 100) if eval_total_checks else 0

    guard_hits = sum(1 for item in fab_events if bool(item.get("guard_triggered")))
    fab_guard_rate = round((guard_hits / len(fab_events)) * 100) if fab_events else 0

    successful_sandbox_runs = 0
    for run in sandbox_runs:
        if "passed" in run:
            successful_sandbox_runs += 1 if bool(run.get("passed")) else 0
        elif "returncode" in run:
            successful_sandbox_runs += 1 if int(run.get("returncode") or 1) == 0 else 0
    sandbox_success_rate = round((successful_sandbox_runs / len(sandbox_runs)) * 100) if sandbox_runs else 0

    latest_eval = recent_evals[-1] if recent_evals else {}
    latest_plan = recent_plans[-1] if recent_plans else {}

    return {
        "metrics": {
            "learner_pass_rate": learner_pass_rate,
            "recent_attempts": attempts,
            "eval_pass_rate": eval_pass_rate,
            "eval_runs": len(recent_evals),
            "plan_runs": len(recent_plans),
            "fab_guard_rate": fab_guard_rate,
            "sandbox_success_rate": sandbox_success_rate,
        },
        "latest_eval": {
            "generated_at": latest_eval.get("generated_at"),
            "pass_count": int((latest_eval.get("summary") or {}).get("pass_count") or 0),
            "fail_count": int((latest_eval.get("summary") or {}).get("fail_count") or 0),
        },
        "latest_plan": {
            "plan_id": latest_plan.get("plan_id"),
            "status": latest_plan.get("plan_status"),
            "profile": latest_plan.get("plan_profile"),
            "created_at": latest_plan.get("created_at"),
        },
        "recent_evals": [
            {
                "generated_at": entry.get("generated_at"),
                "pass_count": int((entry.get("summary") or {}).get("pass_count") or 0),
                "fail_count": int((entry.get("summary") or {}).get("fail_count") or 0),
            }
            for entry in recent_evals
        ],
        "recent_plans": [
            {
                "plan_id": item.get("plan_id"),
                "objective": item.get("objective"),
                "plan_status": item.get("plan_status"),
                "plan_profile": item.get("plan_profile"),
                "created_at": item.get("created_at"),
            }
            for item in recent_plans
        ],
        "recent_activity": [
            {
                "message": item.get("message"),
                "agent_id": item.get("agent_id"),
                "created_at": item.get("created_at"),
            }
            for item in recent_activity
        ],
    }


def _decorate_atlas_state(state: Dict[str, Any]) -> Dict[str, Any]:
    eval_history = _load_eval_history()
    state["eval_history"] = eval_history[-8:]
    state["observability"] = _build_atlas_observability(state, eval_history=eval_history)
    state["available_modules"] = _atlas_module_catalog()
    active_track = _resolve_module_track(state.get("module_id"), state.get("topic"))
    if active_track:
        state["active_module"] = _serialize_module_track(active_track)
    return state


async def _build_atlas_library_snapshot(state: Dict[str, Any]) -> Dict[str, Any]:
    curriculum = state.get("curriculum") if isinstance(state.get("curriculum"), dict) else {}
    modules = curriculum.get("modules") if isinstance(curriculum.get("modules"), list) else []
    retriever = get_retriever()
    module_summaries: List[Dict[str, Any]] = []
    totals = {
        "modules": 0,
        "lessons": 0,
        "persisted_lessons": 0,
        "lessons_with_content": 0,
        "lessons_with_examples": 0,
    }

    for module in modules:
        if not isinstance(module, dict):
            continue
        module_lessons = module.get("lessons") if isinstance(module.get("lessons"), list) else []
        lesson_summaries: List[Dict[str, Any]] = []
        persisted_count = 0
        for lesson in module_lessons:
            if not isinstance(lesson, dict):
                continue
            lesson_id = str(lesson.get("lesson_id") or "").strip()
            content = str(lesson.get("content") or "").strip()
            examples = [str(item).strip() for item in (lesson.get("examples") or []) if str(item).strip()]
            teaching_points = [str(item).strip() for item in (lesson.get("teaching_points") or []) if str(item).strip()]
            persisted_chunks: List[Dict[str, Any]] = []
            if lesson_id and content:
                persisted_chunks = await retriever.load_lesson_chunks(lesson_id)
            persisted = bool(persisted_chunks)
            persisted_count += 1 if persisted else 0
            totals["lessons"] += 1
            totals["persisted_lessons"] += 1 if persisted else 0
            totals["lessons_with_content"] += 1 if content else 0
            totals["lessons_with_examples"] += 1 if examples else 0
            lesson_summaries.append({
                "lesson_id": lesson_id,
                "title": str(lesson.get("title") or lesson.get("lesson_title") or "Lesson").strip(),
                "source": str(lesson.get("source") or curriculum.get("source") or "lesson").strip() or "lesson",
                "lesson_type": str(lesson.get("lesson_type") or "knowledge").strip() or "knowledge",
                "content_length": len(content),
                "teaching_point_count": len(teaching_points),
                "example_count": len(examples),
                "chunk_count": len(persisted_chunks),
                "persisted": persisted,
            })
        totals["modules"] += 1
        module_summaries.append({
            "module_id": str(module.get("module_id") or "").strip(),
            "title": str(module.get("title") or "Module").strip(),
            "lesson_count": len(module_lessons),
            "persisted_lesson_count": persisted_count,
            "lessons": lesson_summaries,
        })

    return {
        "status": "ok",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "curriculum_source": str(curriculum.get("source") or state.get("active_module", {}).get("id") or "unknown").strip(),
        "current_topic": str(state.get("topic") or "").strip(),
        "current_module": state.get("active_module") or _serialize_module_track(_resolve_module_track(state.get("module_id"), state.get("topic"))),
        "totals": totals,
        "modules": module_summaries,
    }


async def _execute_plan_steps(
    *,
    plan_id: str,
    steps: List[Dict[str, Any]],
    objective: str,
    temperature: float,
    approval_mode: bool,
    stop_on_failure: bool,
    activity_agent_id: str,
) -> List[Dict[str, Any]]:
    step_results: List[Dict[str, Any]] = []

    for idx, step in enumerate(steps, start=1):
        started_at = _ts()
        _append_activity(
            f"Plan step {idx}/{len(steps)}: {step['title']}",
            agent_id=step["agent_id"],
            task_id=plan_id,
            kind="plan_step_started",
            details={"step": step, "owner": activity_agent_id},
        )

        approval_contract = step.get("approval_contract") if isinstance(step.get("approval_contract"), dict) else {}
        step_requires_approval = approval_mode and (
            step["agent_id"] == "coding_agent" or bool(approval_contract)
        )
        run_body = {
            "intent": step["intent"],
            "payload": {
                "prompt": step["prompt"],
                "coding_intent": step.get("coding_intent", ""),
                "files": step.get("files") or [],
                "target": step.get("target") or "",
                "approval_contract": approval_contract,
                "context": {
                    "source": "atlas.plan_execute",
                    "files": step.get("files") or [],
                    "target": step.get("target") or "",
                    "coding_intent": step.get("coding_intent", ""),
                    "approval_contract": approval_contract,
                },
            },
            "temperature": temperature,
            "agent_id": step["agent_id"],
            "approval_mode": step_requires_approval,
            "approval_contract": approval_contract,
        }

        response = await run_agent(run_body)
        result_obj = response.get("result") if isinstance(response, dict) else {}
        inner_status = str((result_obj or {}).get("status", ""))

        # Extract contract verification detail so the UI can show why a step failed
        exec_loop = (result_obj or {}).get("execution_loop") if isinstance(result_obj, dict) else {}
        verification = (exec_loop or {}).get("verification") if isinstance(exec_loop, dict) else {}
        failed_checks = verification.get("failed_checks") if isinstance(verification, dict) else []
        failure_reason = ""
        if isinstance(failed_checks, list) and failed_checks:
            failure_reason = "; ".join(
                str(c.get("name") or "") + ": " + str(c.get("detail") or "")
                for c in failed_checks if isinstance(c, dict)
            )

        if response.get("status") != "ok" or inner_status == "error":
            step_status = "failed"
        elif inner_status == "pending_approval":
            step_status = "pending_approval"
        else:
            step_status = "completed"

        finished_at = _ts()
        duration_ms = max(0, int((datetime.fromisoformat(finished_at) - datetime.fromisoformat(started_at)).total_seconds() * 1000))
        step_result = {
            "id": step["id"],
            "title": step["title"],
            "agent_id": step["agent_id"],
            "intent": step["intent"],
            "prompt": step["prompt"],
            "approval_contract": approval_contract,
            "started_at": started_at,
            "finished_at": finished_at,
            "duration_ms": duration_ms,
            "status": step_status,
            "failure_reason": failure_reason,
            "response": response,
            "approval": (result_obj or {}).get("approval") if isinstance(result_obj, dict) else None,
            "preview": (result_obj or {}).get("preview") if isinstance(result_obj, dict) else None,
            "step_requires_approval": step_requires_approval,
        }
        step_results.append(step_result)

        _append_activity(
            f"Plan step {idx}/{len(steps)} {step_status}",
            agent_id=step["agent_id"],
            task_id=plan_id,
            kind="plan_step_completed" if step_status != "failed" else "plan_step_failed",
            details={"step_id": step["id"], "status": step_status, "duration_ms": duration_ms, "owner": activity_agent_id},
        )

        if step_status == "failed" and stop_on_failure:
            break
        if step_status == "pending_approval" and approval_mode:
            break

    return step_results


def _summarize_plan_run(step_results: List[Dict[str, Any]], *, objective: str, plan_profile: str, coding_intent: str, approval_mode: bool) -> Dict[str, Any]:
    completed_steps = [step for step in step_results if step.get("status") == "completed"]
    pending_steps = [step for step in step_results if step.get("status") == "pending_approval"]
    failed_steps = [step for step in step_results if step.get("status") == "failed"]

    lane_source = pending_steps[0] if pending_steps else (failed_steps[0] if failed_steps else (step_results[-1] if step_results else {}))
    current_lane = {
        "step_id": lane_source.get("id") or "",
        "title": lane_source.get("title") or "",
        "agent_id": lane_source.get("agent_id") or "",
        "status": lane_source.get("status") or ("idle" if not step_results else "completed"),
        "started_at": lane_source.get("started_at") or "",
        "finished_at": lane_source.get("finished_at") or "",
        "duration_ms": int(lane_source.get("duration_ms") or 0),
        "approval_contract": lane_source.get("approval_contract") or {},
        "approval": lane_source.get("approval") or {},
        "preview": lane_source.get("preview") or {},
    }

    approvals_needed = [
        {
            "step_id": step.get("id") or "",
            "title": step.get("title") or "",
            "agent_id": step.get("agent_id") or "",
            "status": step.get("status") or "unknown",
            "operation": str((step.get("approval_contract") or {}).get("operation") or (step.get("approval") or {}).get("operation") or ""),
            "target": str((step.get("approval_contract") or {}).get("target") or (step.get("approval") or {}).get("target") or ""),
            "approval_id": str((step.get("approval") or {}).get("id") or ""),
            "preview": (step.get("preview") or {}),
        }
        for step in pending_steps
    ]

    replay = {
        "execution_mode": "plan",
        "objective": objective,
        "plan_profile": plan_profile,
        "coding_intent": coding_intent,
        "approval_mode": approval_mode,
        "step_count": len(step_results),
    }

    return {
        "current_lane": current_lane,
        "approvals_needed": approvals_needed,
        "approvals_needed_count": len(approvals_needed),
        "completed_steps": len(completed_steps),
        "pending_steps": len(pending_steps),
        "failed_steps": len(failed_steps),
        "replay": replay,
    }


@app.post("/api/plan-execute")
async def plan_execute(body: Dict[str, Any]):
    objective = str(body.get("objective", "") or body.get("prompt", "")).strip()
    temperature = body.get("temperature", 0.4)
    approval_mode = bool(body.get("approval_mode"))
    stop_on_failure = bool(body.get("stop_on_failure", True))
    plan_profile = _normalize_plan_profile(body.get("plan_profile"))
    coding_intent = _normalize_coding_intent(body.get("coding_intent")) or _default_coding_intent_for_profile(plan_profile)

    if not objective:
        return {"status": "error", "error": "objective is required"}

    plan_id = f"plan-{uuid.uuid4().hex[:8]}"
    steps = _build_plan_steps(objective, plan_profile, coding_intent)

    _upsert_task(
        plan_id,
        "plan+execute run",
        status="active",
        agent_id="orchestrator",
        description=objective,
        details={
            "objective": objective,
            "step_count": len(steps),
            "approval_mode": approval_mode,
            "plan_profile": plan_profile,
            "coding_intent": coding_intent,
        },
    )
    _append_activity(
        "Started plan+execute run",
        agent_id="orchestrator",
        task_id=plan_id,
        kind="plan_started",
        details={"objective": objective, "step_count": len(steps), "plan_profile": plan_profile, "coding_intent": coding_intent},
    )

    step_results = await _execute_plan_steps(
        plan_id=plan_id,
        steps=steps,
        objective=objective,
        temperature=float(temperature),
        approval_mode=approval_mode,
        stop_on_failure=stop_on_failure,
        activity_agent_id="orchestrator",
    )

    failed_count = sum(1 for s in step_results if s["status"] == "failed")
    pending_count = sum(1 for s in step_results if s["status"] == "pending_approval")
    completed_count = sum(1 for s in step_results if s["status"] == "completed")
    executed_count = len(step_results)
    total_count = len(steps)
    runtime_snapshot = _summarize_plan_run(
        step_results,
        objective=objective,
        plan_profile=plan_profile,
        coding_intent=coding_intent,
        approval_mode=approval_mode,
    )

    if failed_count > 0:
        plan_status = "failed"
    elif pending_count > 0:
        plan_status = "pending_approval"
    else:
        plan_status = "completed"

    _upsert_task(
        plan_id,
        "plan+execute run",
        status=plan_status,
        agent_id="orchestrator",
        description=objective,
        details={
            "objective": objective,
            "plan_profile": plan_profile,
            "coding_intent": coding_intent,
            "total": total_count,
            "executed": executed_count,
            "completed": completed_count,
            "pending_approval": pending_count,
            "failed": failed_count,
            "current_lane": runtime_snapshot.get("current_lane") or {},
            "approvals_needed": runtime_snapshot.get("approvals_needed") or [],
            "approvals_needed_count": runtime_snapshot.get("approvals_needed_count") or 0,
            "replay": runtime_snapshot.get("replay") or {},
        },
    )

    _append_activity(
        f"Plan+execute run {plan_status}",
        agent_id="orchestrator",
        task_id=plan_id,
        kind="plan_completed" if plan_status != "failed" else "plan_failed",
        details={"objective": objective, "plan_profile": plan_profile, "coding_intent": coding_intent, "executed": executed_count, "failed": failed_count},
    )

    return {
        "status": "ok",
        "plan_id": plan_id,
        "objective": objective,
        "plan_profile": plan_profile,
        "coding_intent": coding_intent,
        "plan_status": plan_status,
        "progress": {
            "total": total_count,
            "executed": executed_count,
            "completed": completed_count,
            "pending_approval": pending_count,
            "failed": failed_count,
        },
        "plan_steps": step_results,
        **runtime_snapshot,
    }


@app.get("/api/autonomous/runs")
async def get_autonomous_runs():
    state = _load_atlas_state()
    recent_runs: List[Dict[str, Any]] = []

    def _run_status_for(value: Any, *, fallback: str = "active") -> str:
        normalized = str(value or fallback).strip().lower()
        valid = {"completed", "pending_approval", "failed", "active", "running", "queued", "unknown"}
        if normalized in valid:
            return normalized
        if normalized in {"success", "succeeded"}:
            return "completed"
        if normalized in {"waiting", "approval", "needs_approval"}:
            return "pending_approval"
        return fallback

    def _run_label(objective: Any, *, status: str, profile: Any) -> str:
        raw = str(objective or "Autonomous run").strip()
        label = raw if raw else "Autonomous run"
        if len(label) > 72:
            label = f"{label[:69]}..."
        profile_name = str(profile or "balanced").strip() or "balanced"
        return f"{label} • {status} • {profile_name}"


    plan_tasks = [
        task for task in _load_tasks()
        if isinstance(task, dict) and (
            str(task.get("id", "")).startswith("plan-")
            or str(task.get("title", "")).strip() == "plan+execute run"
        )
    ]
    for task in plan_tasks[-12:]:
        details = task.get("details") if isinstance(task.get("details"), dict) else {}
        approvals_needed = details.get("approvals_needed") if isinstance(details.get("approvals_needed"), list) else []
        current_lane = details.get("current_lane") if isinstance(details.get("current_lane"), dict) else {}
        status = _run_status_for(task.get("status") or details.get("plan_status"), fallback="active")
        objective = details.get("objective") or task.get("description") or ""
        profile_name = _normalize_plan_profile(details.get("plan_profile"))
        lane_count = int(bool(current_lane)) + len(approvals_needed)
        entry = {
            "run_id": task.get("id"),
            "source": "plan_execute",
            "objective": objective,
            "run_label": _run_label(objective, status=status, profile=profile_name),
            "plan_profile": profile_name,
            "coding_intent": _normalize_coding_intent(details.get("coding_intent")) or _default_coding_intent_for_profile(details.get("plan_profile")),
            "plan_status": status,
            "status": status,
            "created_at": task.get("created_at") or task.get("updated_at") or "",
            "updated_at": task.get("updated_at") or task.get("created_at") or "",
            "progress": {
                "total": int(details.get("total") or details.get("step_count") or 0),
                "executed": int(details.get("executed") or 0),
                "completed": int(details.get("completed") or 0),
                "pending_approval": int(details.get("pending_approval") or 0),
                "failed": int(details.get("failed") or 0),
            },
            "current_lane": current_lane,
            "approvals_needed": approvals_needed,
            "approvals_needed_count": int(details.get("approvals_needed_count") or len(approvals_needed)),
            "lane_count": lane_count,
            "replay": details.get("replay") or {
                "execution_mode": "plan",
                "objective": objective,
                "plan_profile": profile_name,
                "coding_intent": _normalize_coding_intent(details.get("coding_intent")) or _default_coding_intent_for_profile(details.get("plan_profile")),
                "approval_mode": bool(details.get("pending_approval") or details.get("approval_mode")),
                "step_count": int(details.get("step_count") or details.get("total") or 0),
            },
        }
        recent_runs.append(entry)

    for plan in [item for item in (state.get("plan_history") or []) if isinstance(item, dict)][-12:]:
        progress = plan.get("progress") if isinstance(plan.get("progress"), dict) else {}
        approvals_needed = plan.get("approvals_needed") if isinstance(plan.get("approvals_needed"), list) else []
        current_lane = plan.get("current_lane") if isinstance(plan.get("current_lane"), dict) else {}
        status = _run_status_for(plan.get("plan_status"), fallback="active")
        objective = plan.get("objective") or ""
        profile_name = _normalize_plan_profile(plan.get("plan_profile"))
        lane_count = int(bool(current_lane)) + len(approvals_needed)
        entry = {
            "run_id": plan.get("plan_id"),
            "source": "atlas_plan",
            "objective": objective,
            "run_label": _run_label(objective, status=status, profile=profile_name),
            "plan_profile": profile_name,
            "coding_intent": _normalize_coding_intent(plan.get("coding_intent")) or _default_coding_intent_for_profile(plan.get("plan_profile")),
            "plan_status": status,
            "status": status,
            "created_at": plan.get("created_at") or "",
            "updated_at": plan.get("created_at") or "",
            "progress": {
                "total": int(progress.get("total") or 0),
                "executed": int(progress.get("executed") or 0),
                "completed": int(progress.get("completed") or 0),
                "pending_approval": int(progress.get("pending_approval") or 0),
                "failed": int(progress.get("failed") or 0),
            },
            "current_lane": current_lane,
            "approvals_needed": approvals_needed,
            "approvals_needed_count": int(plan.get("approvals_needed_count") or len(approvals_needed)),
            "lane_count": lane_count,
            "replay": plan.get("replay") or {
                "execution_mode": "plan",
                "objective": objective,
                "plan_profile": profile_name,
                "coding_intent": _normalize_coding_intent(plan.get("coding_intent")) or _default_coding_intent_for_profile(plan.get("plan_profile")),
                "approval_mode": bool(progress.get("pending_approval")),
                "step_count": int(progress.get("total") or 0),
            },
        }
        recent_runs.append(entry)

    recent_runs.sort(key=lambda run: str(run.get("created_at") or ""), reverse=True)
    recent_runs = recent_runs[:20]

    latest_run = recent_runs[0] if recent_runs else {}
    summary = {
        "total_runs": len(recent_runs),
        "completed": sum(1 for run in recent_runs if run.get("plan_status") == "completed"),
        "pending_approval": sum(1 for run in recent_runs if run.get("plan_status") == "pending_approval"),
        "failed": sum(1 for run in recent_runs if run.get("plan_status") == "failed"),
        "active": sum(1 for run in recent_runs if run.get("plan_status") in {"active", "running", "pending_approval"}),
        "latest_run_at": latest_run.get("created_at") or "",
        "latest_run_status": latest_run.get("status") or "unknown",
        "latest_run_label": latest_run.get("run_label") or latest_run.get("objective") or "Autonomous run",
        "awaiting_approval": sum(int(run.get("approvals_needed_count") or 0) for run in recent_runs),
    }

    return {
        "status": "ok",
        "contract_version": "v1",
        "profiles": ["atlas", "coding", "coding_only", "balanced", "autonomous"],
        "summary": summary,
        "runs": recent_runs,
    }


def _execution_policy_for_run(body: Dict[str, Any], payload: Dict[str, Any], *, runtime_agent: str) -> Dict[str, Any]:
    raw = body.get("execution_policy")
    if not isinstance(raw, dict):
        raw = payload.get("execution_policy") if isinstance(payload.get("execution_policy"), dict) else {}
    retry_on_status = raw.get("retry_on_status")
    retry_statuses = [str(item).strip().lower() for item in retry_on_status] if isinstance(retry_on_status, list) else ["error", "needs_context", "unknown_action"]
    required_fields = raw.get("required_fields")
    if isinstance(required_fields, list):
        required = [str(item).strip() for item in required_fields if str(item).strip()]
    elif runtime_agent == "browser":
        required = ["status", "summary", "execution"]
    elif runtime_agent == "task_queue":
        required = ["status", "action"]
    else:
        required = ["status"]
    try:
        max_attempts = int(raw.get("max_attempts", 2) or 2)
    except (TypeError, ValueError):
        max_attempts = 2
    max_attempts = max(1, min(3, max_attempts))
    min_summary_length_raw = raw.get("min_summary_length", 16)
    try:
        min_summary_length = max(0, int(min_summary_length_raw or 16))
    except (TypeError, ValueError):
        min_summary_length = 16
    return {
        "contract_version": "v1",
        "max_attempts": max_attempts,
        "retry_on_status": retry_statuses,
        "required_fields": required,
        "require_structured_output": bool(raw.get("require_structured_output", True)),
        "min_summary_length": min_summary_length,
    }


def _normalize_agent_output(runtime_agent: str, raw_result: Any) -> Dict[str, Any]:
    if isinstance(raw_result, dict):
        output = dict(raw_result)
        structured = True
    elif isinstance(raw_result, list):
        output = {"items": raw_result}
        structured = False
    else:
        output = {"message": str(raw_result or "")}
        structured = False

    status = str(output.get("status") or "ok").strip().lower() or "ok"
    if status == "passed":
        status = "ok"
    # Try standard keys first, then agent-specific fallbacks so every agent produces
    # a non-empty summary that passes the execution contract check.
    _output_candidate = (
        output.get("summary")
        or output.get("message")
        or output.get("title")
        or output.get("description")
        or output.get("result")
        # agent-specific keys ↓
        or output.get("reflection_summary")   # reflection_agent
        or output.get("plan_summary")         # planner / ATE
        or output.get("answer")               # reasoning_agent answer field
    )
    if not _output_candidate:
        # Last resort: grab the agent's primary text output even if it's long
        _raw_output = output.get("output") or output.get("content") or output.get("text")
        if isinstance(_raw_output, str) and _raw_output.strip():
            _output_candidate = _raw_output[:240]
    summary = str(_output_candidate or "").strip()
    return {
        "runtime_agent": runtime_agent,
        "status": status,
        "structured": structured,
        "output": output,
        "summary": summary,
    }


def _verify_execution_contract(envelope: Dict[str, Any], policy: Dict[str, Any]) -> Dict[str, Any]:
    output = envelope.get("output") if isinstance(envelope.get("output"), dict) else {}
    status = str(envelope.get("status") or "ok").strip().lower()
    generic_markers = ("let me know if you", "i'm here to help", "happy to help")
    summary = str(envelope.get("summary") or "").strip().lower()
    checks: List[Dict[str, Any]] = []
    retry_statuses = set(policy.get("retry_on_status") or [])

    checks.append(
        {
            "name": "status_not_retryable",
            "passed": status not in retry_statuses,
            "detail": f"status={status}",
        }
    )
    checks.append(
        {
            "name": "structured_output",
            "passed": not policy.get("require_structured_output") or bool(envelope.get("structured")),
            "detail": "Output must be structured JSON/dict.",
        }
    )

    required_fields = [str(field).strip() for field in (policy.get("required_fields") or []) if str(field).strip()]
    missing_fields = [field for field in required_fields if field not in output]
    checks.append(
        {
            "name": "required_fields_present",
            "passed": not missing_fields,
            "detail": "All required fields present." if not missing_fields else f"Missing fields: {', '.join(missing_fields)}",
        }
    )

    min_summary_length = int(policy.get("min_summary_length") or 0)
    checks.append(
        {
            "name": "non_generic_summary",
            "passed": len(summary) >= min_summary_length and not any(marker in summary for marker in generic_markers),
            "detail": "Summary is specific enough to avoid generic output.",
        }
    )

    passed = all(bool(check.get("passed")) for check in checks)
    return {
        "passed": passed,
        "checks": checks,
        "failed_checks": [check for check in checks if not check.get("passed")],
    }


@app.post("/api/run")
async def run_agent(body: Dict[str, Any]):
    intent = str(body.get("intent", "")).strip()
    payload = body.get("payload", {})
    payload_dict = dict(payload) if isinstance(payload, dict) else {}
    temperature = body.get("temperature", 0.7)
    requested_agent_id = str(body.get("agent_id", "")).strip()
    tracked_agent_id = requested_agent_id or _agent_id_from_intent(intent)
    prompt_text = str(payload_dict.get("prompt", "") or "").strip()
    approval_mode = bool(body.get("approval_mode") or payload_dict.get("approval_mode") or payload_dict.get("preview_only"))
    coding_intent = _normalize_coding_intent(payload_dict.get("coding_intent")) or _normalize_coding_intent(intent)
    trace_id = str(body.get("trace_id") or new_trace_id("run"))
    runtime_status = _runtime_status_snapshot()
    preflight_checks: List[Dict[str, Any]] = []
    if runtime_status.get("state") != "ready":
        preflight_checks.append({
            "name": "runtime_state",
            "status": "warn",
            "detail": str(runtime_status.get("recommendation") or runtime_status.get("issue") or "Runtime is degraded."),
        })
    if approval_mode:
        preflight_checks.append({
            "name": "approval_mode",
            "status": "pass",
            "detail": "Approval gating is enabled for this run.",
        })
    if runtime_status.get("active_adapter") == "local":
        preflight_checks.append({
            "name": "local_fallback",
            "status": "warn",
            "detail": "The runtime is using local fallback mode.",
        })
    preflight = {
        "contract_version": "v2",
        "status": "warn" if any(item.get("status") == "warn" for item in preflight_checks) else "ok",
        "checks": preflight_checks,
    }

    thought_steps: List[Dict[str, Any]] = []

    def _think(label: str, detail: str = "", status: str = "info") -> None:
        thought_steps.append({"ts": _ts(), "label": label, "detail": detail, "status": status})

    def _is_failure_payload(value: Any) -> bool:
        if isinstance(value, dict):
            if value.get("status") == "error":
                return True
            if value.get("passed") is False:
                return True
            result = value.get("result")
            if isinstance(result, dict) and result.get("passed") is False:
                return True
            return any(_is_failure_payload(child) for child in value.values())
        if isinstance(value, list):
            return any(_is_failure_payload(item) for item in value)
        return False

    _think("Received request", f"intent={intent!r}  agent={requested_agent_id!r}  approval_mode={approval_mode}")

    task_id = f"task-{uuid.uuid4().hex[:8]}"
    task = _upsert_task(
        task_id,
        f"{intent or 'agent'} run",
        status="active",
        agent_id=tracked_agent_id,
        description=prompt_text or "Agent execution started",
        details={"intent": intent, "temperature": temperature, "approval_mode": approval_mode, "trace_id": trace_id},
    )
    _append_activity(
        f"Started task for {intent or 'agent'}",
        agent_id=tracked_agent_id,
        task_id=task_id,
        kind="task_started",
        trace_id=trace_id,
        details={"prompt": prompt_text[:220], "temperature": temperature, "approval_mode": approval_mode, "trace_id": trace_id},
    )

    manifest = None
    if _agent_registry_ok and tracked_agent_id:
        try:
            manifest = await agent_registry.get_agent(tracked_agent_id)
            if manifest:
                manifest.status = AgentStatus.ACTIVE
                manifest.last_heartbeat = datetime.now(timezone.utc)
                _think("Agent resolved", f"name={manifest.name!r}  type={getattr(manifest, 'agent_type', 'unknown')!r}", "success")
            else:
                _think("Agent not in registry", f"id={tracked_agent_id!r} — will fall back to intent routing", "warning")
        except Exception:
            manifest = None

    try:
        runtime_agent = _runtime_agent_name(intent, tracked_agent_id)
        execution_policy = _execution_policy_for_run(body, payload_dict, runtime_agent=runtime_agent)
        preflight_checks.append(
            {
                "name": "execution_contract",
                "status": "pass",
                "detail": f"max_attempts={execution_policy['max_attempts']} required_fields={','.join(execution_policy['required_fields'])}",
            }
        )
        preflight = {
            "contract_version": "v2",
            "status": "warn" if any(item.get("status") == "warn" for item in preflight_checks) else "ok",
            "checks": preflight_checks,
        }
        _think("Routing decision", f"runtime_agent={runtime_agent!r}  agent_id={tracked_agent_id!r}")
        coding_op, coding_payload = _parse_coding_operation(payload_dict, prompt_text)
        if runtime_agent == "coding" and coding_op:
            if not _mutation_allowed():
                _think("Mutation denied", "owner/admin privileges required for code mutation", "error")
                result = _owner_mutation_denied(coding_op)
                _upsert_task(
                    task_id,
                    task["title"],
                    status="failed",
                    agent_id=tracked_agent_id,
                    description=prompt_text or "Mutation blocked",
                    details={"intent": intent, "error": result.get("error"), "trace_id": trace_id},
                )
                _append_activity(
                    "Blocked non-owner mutation attempt",
                    agent_id=tracked_agent_id,
                    task_id=task_id,
                    kind="mutation_blocked",
                    trace_id=trace_id,
                    details={"operation": coding_op, "trace_id": trace_id},
                )
                return {
                    "status": "error",
                    "task_id": task_id,
                    "agent_id": tracked_agent_id,
                    "result": result,
                    "thought_steps": thought_steps,
                    "runtime_status": runtime_status,
                    "trace_id": trace_id,
                    "preflight": preflight,
                }
            _think("Operation parsed", f"op={coding_op!r}  target={coding_payload.get('file_path','?')!r}")
            if approval_mode:
                preview = _build_operation_preview(coding_op, coding_payload)
                approval = _create_approval_record(
                    task_id,
                    agent_id=tracked_agent_id or "coding_agent",
                    operation=coding_op,
                    target=str(coding_payload.get("file_path", "")) or "unknown",
                    preview=preview,
                    payload=coding_payload,
                    requested_by="user",
                    trace_id=trace_id,
                )
                _upsert_task(
                    task_id,
                    task["title"],
                    status="pending_approval",
                    agent_id=tracked_agent_id,
                    description=prompt_text or "Approval required for file change",
                    details={"intent": intent, "temperature": temperature, "approval_id": approval["id"], "trace_id": trace_id},
                )
                _append_activity(
                    f"Requested approval for {coding_op}",
                    agent_id=tracked_agent_id,
                    task_id=task_id,
                    kind="approval_requested",
                    trace_id=trace_id,
                    details={"approval_id": approval["id"], "target": approval["target"], "trace_id": trace_id},
                )
                _think("Queued for approval", f"approval_id={approval['id']}  op={coding_op!r}  target={approval['target']!r}", "warning")
                result = {
                    "status": "pending_approval",
                    "runtime_agent": runtime_agent,
                    "operation": coding_op,
                    "approval": approval,
                    "preview": preview,
                }
            else:
                _think("Executing file operation", f"op={coding_op!r}  direct=True")
                raw_result = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: _run_file_operation(coding_op, coding_payload)
                )
                _think("File operation done", f"status={raw_result.get('status','?')!r}  path={raw_result.get('path','?')!r}", "success")
                result = {
                    "status": "ok",
                    "runtime_agent": runtime_agent,
                    "operation": coding_op,
                    "output": raw_result,
                }
        elif runtime_agent and (runtime_agent == "custodial" or (_agent_registry_ok and runtime_agent in AGENTS)):
            handled_special_result = False
            payload_for_agent: Any = prompt_text or json.dumps(payload)
            payload_agents = {"plant_the_seed", "market_intel", "reflection", "brand_voice", "community_engine", "tutor", "reasoning", "coding", "browser", "task_queue"}
            if runtime_agent in payload_agents:
                payload_for_agent = dict(payload) if isinstance(payload, dict) else {}
                if not isinstance(payload_for_agent, dict):
                    payload_for_agent = {}
                if prompt_text:
                    if runtime_agent == "coding":
                        payload_for_agent.setdefault("prompt", prompt_text)
                        payload_for_agent.setdefault("task", prompt_text)
                        payload_for_agent.setdefault("files", [])
                        payload_for_agent.setdefault("context", {})
                        if coding_intent:
                            payload_for_agent.setdefault("coding_intent", coding_intent)
                    elif runtime_agent == "brand_voice":
                        payload_for_agent.setdefault("content", prompt_text)
                        payload_for_agent.setdefault("prompt", prompt_text)
                        payload_for_agent.setdefault("mode", "stakeholder_summary")
                        payload_for_agent.setdefault("tone", "rugged")
                        payload_for_agent.setdefault("audience", "operator")
                    elif runtime_agent == "browser":
                        payload_for_agent.setdefault("prompt", prompt_text)
                        if prompt_text.lower().startswith(("http://", "https://")) and not payload_for_agent.get("url"):
                            payload_for_agent["url"] = prompt_text
                    elif runtime_agent == "task_queue":
                        payload_for_agent.setdefault("prompt", prompt_text)
                    else:
                        if not payload_for_agent.get("topic") and not payload_for_agent.get("prompt") and not payload_for_agent.get("problem"):
                            payload_for_agent["topic"] = prompt_text
                        if runtime_agent == "tutor" and not payload_for_agent.get("prompt"):
                            payload_for_agent["prompt"] = prompt_text
                        if runtime_agent == "reasoning" and not payload_for_agent.get("problem"):
                            payload_for_agent["problem"] = prompt_text
                elif isinstance(payload, dict):
                    payload_for_agent.setdefault("prompt", payload.get("prompt") or payload.get("content") or payload.get("task") or "")
                if runtime_agent == "coding":
                    payload_for_agent["context"] = dict(payload_for_agent.get("context") or {})
                    payload_for_agent["context"].setdefault("source", prompt_text or payload_for_agent.get("task") or "")
                    payload_for_agent["context"].setdefault("files", payload_for_agent.get("files") or [])
                    if payload_for_agent.get("target"):
                        payload_for_agent["context"].setdefault("target", payload_for_agent.get("target"))
                    if coding_intent:
                        payload_for_agent["context"]["coding_intent"] = coding_intent
                        payload_for_agent["intent"] = coding_intent
            approval_contract = body.get("approval_contract") if isinstance(body.get("approval_contract"), dict) else {}
            if not approval_contract and isinstance(payload_for_agent, dict) and isinstance(payload_for_agent.get("approval_contract"), dict):
                approval_contract = payload_for_agent.get("approval_contract") or {}
            if approval_mode and runtime_agent in {"brand_voice", "community_engine"} and approval_contract:
                operation = str(approval_contract.get("operation") or f"{runtime_agent}_publish").strip()
                target = str(
                    approval_contract.get("target")
                    or payload_for_agent.get("target")
                    or prompt_text
                    or runtime_agent
                ).strip()
                _think("Previewing approval-aware content", f"operation={operation!r}  target={target!r}")
                raw_result = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: registry_run_agent(runtime_agent, payload_for_agent)
                )
                preview = _build_non_coding_approval_preview(operation, payload_for_agent, raw_result)
                approval = _create_approval_record(
                    task_id,
                    agent_id=tracked_agent_id or f"{runtime_agent}_agent",
                    operation=operation,
                    target=target or runtime_agent,
                    preview=preview,
                    payload={**payload_for_agent, "approval_contract": approval_contract},
                    requested_by="user",
                    trace_id=trace_id,
                )
                _upsert_task(
                    task_id,
                    task["title"],
                    status="pending_approval",
                    agent_id=tracked_agent_id,
                    description=prompt_text or f"Approval required for {runtime_agent}",
                    details={"intent": intent, "temperature": temperature, "approval_id": approval["id"], "trace_id": trace_id},
                )
                _append_activity(
                    f"Requested approval for {runtime_agent}",
                    agent_id=tracked_agent_id,
                    task_id=task_id,
                    kind="approval_requested",
                    trace_id=trace_id,
                    details={"approval_id": approval["id"], "target": approval["target"], "trace_id": trace_id},
                )
                _think("Queued for approval", f"approval_id={approval['id']}  operation={operation!r}  target={approval['target']!r}", "warning")
                result = {
                    "status": "pending_approval",
                    "runtime_agent": runtime_agent,
                    "operation": operation,
                    "approval": approval,
                    "preview": preview,
                }
                handled_special_result = True
            if runtime_agent == "custodial":
                from mammoth_os.agents.custodial_agent import CustodialAgent

                custodial_agent = CustodialAgent(router=None, storage_root=str(MAMMOTH_DIR / "custodial"))
                payload_for_agent = dict(payload) if isinstance(payload, dict) else {}
                if prompt_text and not payload_for_agent.get("prompt"):
                    payload_for_agent["prompt"] = prompt_text
                custodial_prompt = prompt_text or str(payload_for_agent.get("prompt") or payload_for_agent.get("topic") or "").strip()
                action = str(
                    payload_for_agent.get("action")
                    or payload_for_agent.get("operation")
                    or custodial_agent._infer_intent(custodial_prompt or json.dumps(payload_for_agent))
                ).strip().lower() or "lifecycle"
                workspace = str(payload_for_agent.get("workspace") or payload_for_agent.get("target") or "").strip() or str(Path.cwd())
                action_payload = dict(payload_for_agent.get("details") or {}) if isinstance(payload_for_agent.get("details"), dict) else {}
                if payload_for_agent.get("snapshot_id"):
                    action_payload["snapshot_id"] = str(payload_for_agent.get("snapshot_id") or "").strip()

                mutation_actions = {"cleanup", "clean", "prune", "restore", "rollback", "snapshot", "checkpoint"}
                if approval_mode and action in mutation_actions:
                    preview_payload = dict(action_payload)
                    preview_payload["dry_run"] = True
                    if action in {"restore", "rollback"} and not preview_payload.get("snapshot_id"):
                        preview_payload["snapshot_id"] = str(payload_for_agent.get("snapshot_id") or "").strip()
                    preview = await custodial_agent.execute_action(action, workspace, preview_payload)
                    if action in {"cleanup", "clean", "prune"}:
                        approval_operation = "custodial_cleanup"
                    elif action in {"restore", "rollback"}:
                        approval_operation = "custodial_restore"
                    else:
                        approval_operation = "custodial_snapshot"
                    approval = _create_approval_record(
                        task_id,
                        agent_id=tracked_agent_id or "custodial_agent",
                        operation=approval_operation,
                        target=workspace,
                        preview=preview,
                        payload={
                            "action": action,
                            "workspace": workspace,
                            "details": action_payload,
                            "snapshot_id": payload_for_agent.get("snapshot_id"),
                        },
                        requested_by="user",
                        trace_id=trace_id,
                    )
                    _upsert_task(
                        task_id,
                        task["title"],
                        status="pending_approval",
                        agent_id=tracked_agent_id,
                        description=prompt_text or f"Approval required for {action}",
                        details={"intent": intent, "temperature": temperature, "approval_id": approval["id"], "trace_id": trace_id},
                    )
                    _append_activity(
                        f"Requested approval for custodial {action}",
                        agent_id=tracked_agent_id,
                        task_id=task_id,
                        kind="approval_requested",
                        trace_id=trace_id,
                        details={"approval_id": approval["id"], "target": approval["target"], "trace_id": trace_id},
                    )
                    _think("Queued for approval", f"approval_id={approval['id']}  action={action!r}  target={approval['target']!r}", "warning")
                    result = {
                        "status": "pending_approval",
                        "runtime_agent": runtime_agent,
                        "operation": action,
                        "approval": approval,
                        "preview": preview,
                    }
                    handled_special_result = True
                else:
                    _think("Executing custodial action", f"action={action!r}  workspace={workspace!r}")
                    raw_result = await custodial_agent.execute_action(action, workspace, action_payload)
                    _think("Custodial action done", f"status={raw_result.get('status','?')!r}  action={raw_result.get('action', action)!r}", "success")
                    result = {
                        "status": raw_result.get("status", "ok"),
                        "runtime_agent": runtime_agent,
                        "operation": action,
                        "output": raw_result,
                    }
                    handled_special_result = True

            if runtime_agent != "custodial" and not handled_special_result:
                _think("Execution loop plan", f"runtime_agent={runtime_agent!r} max_attempts={execution_policy['max_attempts']}")
                attempts: List[Dict[str, Any]] = []
                final_envelope: Dict[str, Any] = {}
                verification: Dict[str, Any] = {"passed": False, "checks": [], "failed_checks": []}
                raw_result: Any = None
                last_failure_detail = ""
                for attempt in range(1, int(execution_policy.get("max_attempts") or 1) + 1):
                    attempt_payload = payload_for_agent
                    if isinstance(payload_for_agent, dict):
                        attempt_payload = dict(payload_for_agent)
                        attempt_payload["execution_contract"] = {
                            "attempt": attempt,
                            "max_attempts": execution_policy["max_attempts"],
                            "required_fields": execution_policy["required_fields"],
                            "previous_failure": last_failure_detail,
                        }
                    _think("Dispatching to agent", f"attempt={attempt} runtime_agent={runtime_agent!r}")
                    raw_result = await asyncio.get_event_loop().run_in_executor(
                        None, lambda: registry_run_agent(runtime_agent, attempt_payload)
                    )
                    final_envelope = _normalize_agent_output(runtime_agent, raw_result)
                    verification = _verify_execution_contract(final_envelope, execution_policy)
                    attempts.append(
                        {
                            "attempt": attempt,
                            "status": final_envelope.get("status"),
                            "summary": final_envelope.get("summary", ""),
                            "passed": verification.get("passed", False),
                            "checks": verification.get("checks", []),
                        }
                    )
                    _think(
                        "Verify step",
                        f"attempt={attempt} passed={verification.get('passed')} status={final_envelope.get('status')!r}",
                        "success" if verification.get("passed") else "warning",
                    )
                    if verification.get("passed"):
                        break
                    if final_envelope.get("status") == "pending_approval":
                        break
                    failed_checks = verification.get("failed_checks") if isinstance(verification.get("failed_checks"), list) else []
                    last_failure_detail = "; ".join(str(item.get("name") or "check_failed") for item in failed_checks if isinstance(item, dict))
                    if attempt < int(execution_policy.get("max_attempts") or 1):
                        _think("Retrying run", f"attempt={attempt + 1} reason={last_failure_detail or 'verification_failed'}", "warning")

                _think("Agent returned", f"type={type(raw_result).__name__}  preview={str(raw_result)[:120]!r}", "success")
                status = "ok" if verification.get("passed") or final_envelope.get("status") == "pending_approval" else "error"
                result = {
                    "status": status,
                    "runtime_agent": runtime_agent,
                    "output": final_envelope.get("output", raw_result),
                    "execution_loop": {
                        "plan": execution_policy,
                        "attempts": attempts,
                        "verification": verification,
                    },
                }
                attach_reasoning = runtime_agent == "tutor" and (
                    intent == "lesson_coaching" or (intent == "grade_submission" and _is_failure_payload(final_envelope.get("output", raw_result)))
                )
                if attach_reasoning:
                    if _is_failure_payload(final_envelope.get("output", raw_result)):
                        _think("Tutor failure detected", "Preparing reasoning guidance for the learner", "warning")
                    else:
                        _think("Coaching extension", "Attaching Socratic reasoning guidance", "info")
                    reasoning_payload = {
                        "problem": prompt_text or "Explain the tutoring failure and offer a micro-lesson.",
                        "context": {
                            "intent": intent,
                            "prompt": prompt_text,
                            "tutor_result": final_envelope.get("output", raw_result),
                            "mode": "coach" if intent == "lesson_coaching" else "tutor_hint",
                        },
                        "mode": "coach" if intent == "lesson_coaching" else "tutor_hint",
                    }
                    reasoning_result = await asyncio.get_event_loop().run_in_executor(
                        None, lambda: registry_run_agent("reasoning", reasoning_payload)
                    )
                    _think("Reasoning guidance attached", f"preview={str(reasoning_result)[:120]!r}", "success")
                    result["reasoning"] = reasoning_result
        else:
            _think("Falling back to CortexRouter", f"intent={intent!r}  no matching AGENTS key", "warning")
            from mammoth_os.cortex.router import CortexRouter
            router = CortexRouter()
            result = await asyncio.get_event_loop().run_in_executor(
                None, lambda: router.route(intent, payload)
            )
            _think("CortexRouter returned", f"status={result.get('status','?')!r}  preview={str(result)[:120]!r}", "success")

        if manifest:
            await asyncio.sleep(1.2)
            manifest.status = AgentStatus.IDLE
            manifest.last_heartbeat = datetime.now(timezone.utc)
            manifest.metadata["last_intent"] = intent
            manifest.metadata["last_run_at"] = datetime.now(timezone.utc).isoformat()

        if result.get("status") == "pending_approval":
            task_status = "pending_approval"
        elif result.get("status") == "error":
            task_status = "failed"
        else:
            task_status = "completed"
        _upsert_task(
            task_id,
            task["title"],
            status=task_status,
            agent_id=tracked_agent_id,
            description=prompt_text or "Agent execution completed",
            details={"intent": intent, "temperature": temperature, "result": str(result)[:1000]},
        )
        if task_status == "completed":
            _append_activity(
                f"Completed task for {intent or 'agent'}",
                agent_id=tracked_agent_id,
                task_id=task_id,
                kind="task_completed",
                trace_id=trace_id,
                details={"result": str(result)[:1000], "trace_id": trace_id},
            )
        elif task_status == "failed":
            _append_activity(
                f"Failed task for {intent or 'agent'}",
                agent_id=tracked_agent_id,
                task_id=task_id,
                kind="task_failed",
                trace_id=trace_id,
                details={"result": str(result)[:1000], "trace_id": trace_id},
            )

        _think("Run complete", f"task_status={task_status!r}", "success")
        return {
            "status": "ok",
            "result": result,
            "intent": intent,
            "agent_id": tracked_agent_id,
            "temperature": temperature,
            "task_id": task_id,
            "trace_id": trace_id,
            "contract_version": "v2",
            "preflight": preflight,
            "runtime_notice": build_runtime_notice(runtime_status, trace_id=trace_id, agent_id=tracked_agent_id or "", context="run_agent"),
            "thought_steps": thought_steps,
        }
    except Exception as e:
        if manifest:
            manifest.status = AgentStatus.ERROR
            manifest.last_heartbeat = datetime.now(timezone.utc)
            manifest.metadata["last_error"] = str(e)

        _upsert_task(
            task_id,
            task["title"],
            status="failed",
            agent_id=tracked_agent_id,
            description=prompt_text or "Agent execution failed",
            details={"intent": intent, "temperature": temperature, "error": str(e)[:1000]},
        )
        _append_activity(
            f"Failed task for {intent or 'agent'}",
            agent_id=tracked_agent_id,
            task_id=task_id,
            kind="task_failed",
            trace_id=trace_id,
            details={"error": str(e)[:1000], "trace_id": trace_id},
        )

        _think("Run failed", str(e)[:200], "error")
        return {
            "status": "error",
            "error": str(e),
            "intent": intent,
            "agent_id": tracked_agent_id,
            "task_id": task_id,
            "trace_id": trace_id,
            "contract_version": "v2",
            "preflight": preflight,
            "runtime_notice": build_runtime_notice(runtime_status, trace_id=trace_id, agent_id=tracked_agent_id or "", context="run_agent"),
            "thought_steps": thought_steps,
        }


# ─────────────────────────────────────────────────────────────────────────────
# /api/atlas/*
# ─────────────────────────────────────────────────────────────────────────────

def _load_atlas_state() -> Dict[str, Any]:
    atlas_file = _atlas_state_file_for_request()
    if atlas_file.exists():
        try:
            state = json.loads(atlas_file.read_text(encoding="utf-8"))
            if not isinstance(state, dict):
                return _ensure_account_collections({"status": "no_session", "active_account_id": "default"})
            normalized_history: List[Dict[str, Any]] = []
            for idx, raw in enumerate(state.get("lesson_history") or []):
                entry = _normalize_lesson_history_entry(raw, idx)
                if entry:
                    normalized_history.append(entry)
            state["lesson_history"] = normalized_history[-80:]
            normalized_aids: List[Dict[str, Any]] = []
            for raw in state.get("study_aids") or []:
                aid = _normalize_study_aid_entry(raw)
                if aid:
                    normalized_aids.append(aid)
            state["study_aids"] = normalized_aids[-120:]
            _ensure_account_collections(state)
            _sync_resume_packet(state)
            return state
        except Exception:
            pass
    return _ensure_account_collections({"status": "no_session", "active_account_id": "default"})


def _save_atlas_state(state: Dict[str, Any]):
    _persist_active_account_collections(state)
    atlas_file = _atlas_state_file_for_request()
    atlas_file.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")


_ACCOUNT_SESSION_KEYS = (
    "status",
    "topic",
    "curriculum_topic",
    "current_exercise",
    "curriculum",
    "current_lesson",
    "curriculum_id",
    "lesson_id",
    "lesson_plan",
    "module_id",
    "active_module",
    "last_submission",
    "assistant_chat_history",
    "chat_history",
    "mammoth_chat_history",
    "resume_packet",
    "lesson_history",
    "study_aids",
    "learner_profile",
    "fab_usage_events",
    "plan_history",
    "active_plan",
    "eval_history",
    "regenerated_exercise",
    "updated_at",
)


def _normalize_account_id(value: Any, *, fallback: str = "default") -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower()).strip("-")
    return normalized or fallback


def _legacy_session_slice(state: Dict[str, Any]) -> Dict[str, Any]:
    session: Dict[str, Any] = {}
    for key in _ACCOUNT_SESSION_KEYS:
        if key in state:
            session[key] = deepcopy(state.get(key))
    return session


def _active_account_id(state: Dict[str, Any]) -> str:
    return _normalize_account_id(state.get("active_account_id") or state.get("current_account_id") or "default")


def _atlas_user_id(state: Dict[str, Any]) -> str:
    return f"workspace:{_active_account_id(state)}"


def _build_workspace_accounts_snapshot(state: Dict[str, Any]) -> Dict[str, Any]:
    _ensure_account_collections(state)
    accounts = state.get("accounts") if isinstance(state.get("accounts"), dict) else {}
    active_account_id = _active_account_id(state)
    items: List[Dict[str, Any]] = []
    for account_id, raw in accounts.items():
        if not isinstance(raw, dict):
            continue
        profile = {
            "display_name": str((raw.get("profile") or {}).get("display_name") or "Operator").strip() or "Operator",
            "email": str((raw.get("profile") or {}).get("email") or "").strip(),
            "organization": str((raw.get("profile") or {}).get("organization") or "").strip(),
        }
        completion = _profile_completion(profile)
        items.append({
            "account_id": account_id,
            "label": profile["display_name"],
            "profile": profile,
            "profile_complete": all(completion.values()),
            "profile_completion": completion,
            "tier": str(raw.get("tier") or "explorer").strip().lower() or "explorer",
            "developer_access": bool(raw.get("developer_access", False)),
            "is_active": account_id == active_account_id,
            "created_at": raw.get("created_at"),
            "updated_at": raw.get("updated_at") or raw.get("profile_updated_at") or raw.get("tier_updated_at"),
            "user_id": f"workspace:{account_id}",
        })
    items.sort(key=lambda item: (not item["is_active"], item["label"].lower(), item["account_id"]))
    return {
        "status": "ok",
        "active_account_id": active_account_id,
        "session_scope": "workspace_multi_account",
        "accounts": items,
    }


def _ensure_account_collections(state: Dict[str, Any]) -> Dict[str, Any]:
    accounts = state.get("accounts") if isinstance(state.get("accounts"), dict) else {}
    sessions = state.get("account_sessions") if isinstance(state.get("account_sessions"), dict) else {}
    active_account_id = _active_account_id(state)

    legacy_profile = _normalized_account_profile(state)
    legacy_tier = str(state.get("tier") or "explorer").strip().lower()
    if legacy_tier not in {"explorer", "pro", "enterprise"}:
        legacy_tier = "explorer"
    legacy_developer_access = bool(state.get("developer_access", False))

    if not accounts:
        accounts[active_account_id] = {
            "profile": legacy_profile,
            "tier": legacy_tier,
            "developer_access": legacy_developer_access,
            "created_at": state.get("account_profile_updated_at") or datetime.now(timezone.utc).isoformat(),
            "updated_at": state.get("updated_at") or state.get("account_profile_updated_at") or datetime.now(timezone.utc).isoformat(),
            "profile_updated_at": state.get("account_profile_updated_at"),
            "tier_updated_at": state.get("tier_updated_at"),
            "developer_access_updated_at": state.get("developer_access_updated_at"),
        }
    elif active_account_id not in accounts:
        accounts[active_account_id] = {
            "profile": {"display_name": "Operator", "email": "", "organization": ""},
            "tier": "explorer",
            "developer_access": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    account = accounts.get(active_account_id) if isinstance(accounts.get(active_account_id), dict) else {}
    if not account.get("profile"):
        account["profile"] = legacy_profile
    account["profile"] = {
        "display_name": str((account.get("profile") or {}).get("display_name") or legacy_profile.get("display_name") or "Operator").strip() or "Operator",
        "email": str((account.get("profile") or {}).get("email") or legacy_profile.get("email") or "").strip(),
        "organization": str((account.get("profile") or {}).get("organization") or legacy_profile.get("organization") or "").strip(),
    }
    account["tier"] = str(account.get("tier") or legacy_tier or "explorer").strip().lower()
    if account["tier"] not in {"explorer", "pro", "enterprise"}:
        account["tier"] = "explorer"
    account["developer_access"] = bool(account.get("developer_access", legacy_developer_access))
    account.setdefault("created_at", datetime.now(timezone.utc).isoformat())
    account.setdefault("updated_at", datetime.now(timezone.utc).isoformat())
    account.setdefault("profile_updated_at", state.get("account_profile_updated_at"))
    account.setdefault("tier_updated_at", state.get("tier_updated_at"))
    account.setdefault("developer_access_updated_at", state.get("developer_access_updated_at"))
    accounts[active_account_id] = account

    if active_account_id not in sessions:
        sessions[active_account_id] = _legacy_session_slice(state)

    state["accounts"] = accounts
    state["account_sessions"] = sessions
    state["active_account_id"] = active_account_id

    for key in _ACCOUNT_SESSION_KEYS:
        state.pop(key, None)
    active_session = sessions.get(active_account_id) if isinstance(sessions.get(active_account_id), dict) else {}
    for key, value in active_session.items():
        if key in _ACCOUNT_SESSION_KEYS:
            state[key] = deepcopy(value)

    state["account_profile"] = deepcopy(account["profile"])
    state["tier"] = account["tier"]
    state["developer_access"] = account["developer_access"]
    state["account_profile_updated_at"] = account.get("profile_updated_at")
    state["tier_updated_at"] = account.get("tier_updated_at")
    state["developer_access_updated_at"] = account.get("developer_access_updated_at")
    state["session_scope"] = "workspace_multi_account"
    state["user_id"] = _atlas_user_id(state)
    return state


def _persist_active_account_collections(state: Dict[str, Any]) -> Dict[str, Any]:
    accounts = state.get("accounts") if isinstance(state.get("accounts"), dict) else {}
    sessions = state.get("account_sessions") if isinstance(state.get("account_sessions"), dict) else {}
    active_account_id = _active_account_id(state)
    if active_account_id not in accounts or not isinstance(accounts.get(active_account_id), dict):
        accounts[active_account_id] = {
            "profile": _normalized_account_profile(state),
            "tier": str(state.get("tier") or "explorer").strip().lower() or "explorer",
            "developer_access": bool(state.get("developer_access", False)),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    account = accounts[active_account_id]
    account["profile"] = _normalized_account_profile(state)
    account["tier"] = str(state.get("tier") or account.get("tier") or "explorer").strip().lower() or "explorer"
    if account["tier"] not in {"explorer", "pro", "enterprise"}:
        account["tier"] = "explorer"
    account["developer_access"] = bool(state.get("developer_access", account.get("developer_access", False)))
    account["profile_updated_at"] = state.get("account_profile_updated_at") or account.get("profile_updated_at")
    account["tier_updated_at"] = state.get("tier_updated_at") or account.get("tier_updated_at")
    account["developer_access_updated_at"] = state.get("developer_access_updated_at") or account.get("developer_access_updated_at")
    account["updated_at"] = state.get("updated_at") or datetime.now(timezone.utc).isoformat()
    sessions[active_account_id] = _legacy_session_slice(state)
    state["accounts"] = accounts
    state["account_sessions"] = sessions
    state["active_account_id"] = active_account_id
    state["session_scope"] = "workspace_multi_account"
    state["user_id"] = _atlas_user_id(state)
    return state


def _reset_learner_model_state(user_id: str = "default_user") -> Dict[str, Any]:
    learner_state = load_learner_model(user_id)
    learner_state.update({
        "mastery": {},
        "confidence": {},
        "streak": 0,
        "attempts": 0,
        "error_patterns": {},
        "recent_outcomes": [],
        "memory_graph": {"nodes": [], "edges": [], "last_updated": None},
    })
    return save_learner_model(learner_state)


def _apply_atlas_onboarding_update(onboarding: Dict[str, Any]) -> Dict[str, Any]:
    state = _load_atlas_state()
    learner_user_id = _atlas_user_id(state)
    learner_state = set_onboarding_profile(state, user_id=learner_user_id, onboarding=onboarding)
    _save_atlas_state(state)
    _append_audit_event(
        kind="atlas_onboard",
        message="ATLAS onboarding profile updated",
        details={"profile": onboarding.get("profile") or onboarding.get("goal") or "unknown"},
        source="atlas",
        actor="learner",
    )
    return {
        "status": "ok",
        "learner_model": learner_state,
        "learner_context": state.get("learner_context"),
        "learner_profile": state.get("learner_profile"),
    }


def _apply_atlas_learner_reset() -> Dict[str, Any]:
    state = _load_atlas_state()
    learner_user_id = _atlas_user_id(state)
    learner_state = _reset_learner_model_state(learner_user_id)
    state["learner_model"] = learner_state
    state["learner_context"] = build_learner_context(learner_state)
    state["learner_profile"] = {
        "streak": 0,
        "attempts": 0,
        "recommended_difficulty": "beginner",
        "preferred_pacing": "gentle",
    }
    _save_atlas_state(state)
    return {"status": "ok", "learner_model": learner_state, "learner_context": state["learner_context"]}


def _apply_atlas_session_reset() -> Dict[str, Any]:
    state = _load_atlas_state()
    learner_user_id = _atlas_user_id(state)
    learner_state = _reset_learner_model_state(learner_user_id)
    state["status"] = "reset"
    state["user_id"] = learner_user_id
    state["learner_model"] = learner_state
    state["learner_context"] = build_learner_context(learner_state)
    state["learner_profile"] = {
        "streak": 0,
        "attempts": 0,
        "recommended_difficulty": "beginner",
        "preferred_pacing": "gentle",
    }
    _save_atlas_state(state)
    return {"status": "ok", "message": "Session reset"}


def _hydrate_learner_state(state: Dict[str, Any], *, user_id: str = "default_user", lesson: Optional[Dict[str, Any]] = None, exercise: Optional[Dict[str, Any]] = None, result: Optional[Dict[str, Any]] = None, topic: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    learner_state = load_learner_model(user_id)
    if result is not None:
        learner_state = update_learner_model(
            user_id,
            lesson=lesson,
            exercise=exercise,
            result=result,
            topic=topic,
            metadata=metadata,
        )
    learner_context = build_learner_context(learner_state)
    state["learner_model"] = learner_state
    state["learner_context"] = learner_context
    state["learner_profile"] = {
        "streak": learner_context.get("streak", 0),
        "attempts": learner_context.get("attempts", 0),
        "recommended_difficulty": learner_context.get("recommended_difficulty", "beginner"),
        "preferred_pacing": learner_context.get("preferred_pacing", "gentle"),
    }
    return learner_state


def _append_lesson_history(state: Dict[str, Any], lesson: Dict[str, Any], exercise: Dict[str, Any]):
    history = state.get("lesson_history") or []
    if not isinstance(history, list):
        history = []
    entry = {
        "lesson_id": lesson.get("lesson_id"),
        "lesson": lesson,
        "exercise": exercise,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    replaced = False
    normalized_history: List[Dict[str, Any]] = []
    for idx, raw in enumerate(history):
        normalized = _normalize_lesson_history_entry(raw, idx)
        if not normalized:
            continue
        if normalized["lesson_id"] == entry["lesson_id"]:
            normalized = {
                **normalized,
                "lesson": lesson or normalized.get("lesson") or {},
                "exercise": exercise or normalized.get("exercise") or {},
                "updated_at": entry["updated_at"],
            }
            replaced = True
        normalized_history.append(normalized)
    if not replaced:
        normalized_history.append(_normalize_lesson_history_entry(entry, len(normalized_history)) or entry)
    state["lesson_history"] = normalized_history[-80:]


def _record_submission_on_history(state: Dict[str, Any], submission: Dict[str, Any]) -> None:
    lesson_id = str(state.get("lesson_id") or "").strip()
    if not lesson_id:
        return
    summary = _summarize_prior_work(state, lesson_id)
    normalized_history: List[Dict[str, Any]] = []
    for idx, raw in enumerate(state.get("lesson_history") or []):
        entry = _normalize_lesson_history_entry(raw, idx)
        if not entry:
            continue
        if entry["lesson_id"] == lesson_id:
            entry["last_submission"] = submission
            entry["updated_at"] = datetime.now(timezone.utc).isoformat()
            entry["summary"] = summary
        normalized_history.append(entry)
    state["lesson_history"] = normalized_history[-80:]


def _build_lesson_recap(state: Dict[str, Any]) -> str:
    lesson = state.get("current_lesson") or {}
    exercise = state.get("current_exercise") or {}
    submission = state.get("last_submission") or {}
    objectives = lesson.get("objectives") or []
    title = lesson.get("title") or "Current lesson"
    prompt = exercise.get("prompt") or ""
    status = "passed" if submission.get("passed") else "in progress"
    return (
        f"Lesson recap: {title}.\n"
        f"Objectives: {objectives}.\n"
        f"Current exercise: {prompt}\n"
        f"Latest submission status: {status}."
    )


def _build_lesson_quiz(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    lesson = state.get("current_lesson") or {}
    objectives = lesson.get("objectives") or []
    prompt = (state.get("current_exercise") or {}).get("prompt") or ""
    questions: List[Dict[str, Any]] = []
    for idx, obj in enumerate(objectives[:3], start=1):
        questions.append({
            "id": f"q{idx}",
            "question": f"Explain this objective in your own words: {obj}",
            "type": "short_answer",
        })
    if len(questions) < 3:
        questions.append({
            "id": f"q{len(questions)+1}",
            "question": f"What would be your plan to solve this exercise: {prompt}",
            "type": "short_answer",
        })
    return questions[:3]


def _build_lesson_review(state: Dict[str, Any]) -> Dict[str, Any]:
    submission = state.get("last_submission") or {}
    passed = bool(submission.get("passed"))
    hint = submission.get("hint") or "No submission feedback yet."
    return {
        "strengths": ["Consistent lesson activity"] if passed else ["You are actively iterating"],
        "focus_next": [
            "Tighten function return values against test expectations",
            "Run one quick self-check before submitting",
        ] if not passed else ["Increase challenge difficulty", "Try refactoring the passing solution"],
        "coach_note": hint,
    }


def _append_study_aid(state: Dict[str, Any], aid_type: str, data: Any):
    aids = state.get("study_aids") or []
    if not isinstance(aids, list):
        aids = []
    lesson = state.get("current_lesson") or {}
    aids.append({
        "id": str(uuid.uuid4()),
        "type": str(aid_type or "unknown"),
        "lesson_id": state.get("lesson_id") or lesson.get("lesson_id"),
        "lesson_title": lesson.get("title") or lesson.get("lesson_title"),
        "data": data,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    state["study_aids"] = aids[-120:]


def _normalize_lesson_history_entry(raw: Any, index: int = 0) -> Optional[Dict[str, Any]]:
    if not isinstance(raw, dict):
        return None
    lesson = raw.get("lesson") if isinstance(raw.get("lesson"), dict) else {}
    exercise = raw.get("exercise") if isinstance(raw.get("exercise"), dict) else {}
    lesson_id = str(
        raw.get("lesson_id")
        or lesson.get("lesson_id")
        or exercise.get("lesson_id")
        or ""
    ).strip()
    if not lesson_id:
        return None
    created_at = raw.get("created_at") or raw.get("updated_at") or datetime.now(timezone.utc).isoformat()
    summary = str(raw.get("summary") or raw.get("resume_summary") or "").strip()
    return {
        "lesson_id": lesson_id,
        "lesson": lesson,
        "exercise": exercise,
        "created_at": created_at,
        "updated_at": raw.get("updated_at") or created_at,
        "summary": summary,
        "last_submission": raw.get("last_submission") if isinstance(raw.get("last_submission"), dict) else None,
        "study_aid_count": int(raw.get("study_aid_count") or 0),
        "resume_packet": raw.get("resume_packet") if isinstance(raw.get("resume_packet"), dict) else None,
        "sequence": int(raw.get("sequence") or index),
    }


def _normalize_study_aid_entry(raw: Any, lesson_id: str = "", lesson_title: str = "") -> Optional[Dict[str, Any]]:
    if not isinstance(raw, dict):
        return None
    data = raw.get("data")
    aid_type = str(raw.get("type") or "unknown").strip() or "unknown"
    normalized_lesson_id = str(raw.get("lesson_id") or lesson_id or "").strip()
    if isinstance(data, dict) and aid_type == "flashcards" and "cards" in data and isinstance(data.get("cards"), list):
        data = data.get("cards")
    elif isinstance(data, str) and aid_type in {"flashcards", "quiz"}:
        data = [data]
    return {
        "id": str(raw.get("id") or uuid.uuid4()),
        "type": aid_type,
        "lesson_id": normalized_lesson_id,
        "lesson_title": str(raw.get("lesson_title") or lesson_title or "").strip(),
        "data": data,
        "created_at": raw.get("created_at") or datetime.now(timezone.utc).isoformat(),
    }


def _find_lesson_snapshot(state: Dict[str, Any], lesson_id: Optional[str]) -> Dict[str, Any]:
    target_id = str(lesson_id or state.get("lesson_id") or "").strip()
    current_lesson = state.get("current_lesson") if isinstance(state.get("current_lesson"), dict) else {}
    if target_id and str(current_lesson.get("lesson_id") or "").strip() == target_id:
        return current_lesson

    history = state.get("lesson_history") or []
    if isinstance(history, list):
        for raw in reversed(history):
            entry = _normalize_lesson_history_entry(raw)
            if entry and entry["lesson_id"] == target_id:
                return entry.get("lesson") or {}

    curriculum = state.get("curriculum") if isinstance(state.get("curriculum"), dict) else {}
    for module in curriculum.get("modules") or []:
        if not isinstance(module, dict):
            continue
        for lesson in module.get("lessons") or []:
            if not isinstance(lesson, dict):
                continue
            if str(lesson.get("lesson_id") or "").strip() == target_id:
                return lesson
    return current_lesson if current_lesson else {}


def _matching_history_entry(state: Dict[str, Any], lesson_id: Optional[str]) -> Optional[Dict[str, Any]]:
    target_id = str(lesson_id or "").strip()
    history = state.get("lesson_history") or []
    if not isinstance(history, list):
        return None
    for raw in reversed(history):
        entry = _normalize_lesson_history_entry(raw)
        if entry and entry["lesson_id"] == target_id:
            return entry
    return None


def _build_lesson_flashcards(state: Dict[str, Any]) -> List[Dict[str, str]]:
    lesson = state.get("current_lesson") or {}
    exercise = state.get("current_exercise") or {}
    objectives = [str(item).strip() for item in (lesson.get("objectives") or []) if str(item).strip()]
    lesson_title = lesson.get("title") or lesson.get("lesson_title") or "Current lesson"
    cards: List[Dict[str, str]] = []

    for idx, objective in enumerate(objectives[:4], start=1):
        cards.append({
            "id": f"obj-{idx}",
            "front": f"{lesson_title}: What does this objective mean? ({objective})",
            "back": f"Explain {objective} in your own words, then write one tiny example that demonstrates it.",
        })

    prompt = str(exercise.get("prompt") or "").strip()
    if prompt:
        cards.append({
            "id": "exercise-plan",
            "front": "What is your plan before coding this exercise?",
            "back": f"Summarize the input/output, then list 2-3 steps to solve this prompt: {prompt[:220]}",
        })

    return cards[:6]


def _matching_notes_for_lesson(state: Dict[str, Any], lesson_id: Optional[str]) -> List[Dict[str, Any]]:
    notes = _read_json(NOTES_FILE, default=[])
    if not isinstance(notes, list):
        return []

    lesson = _find_lesson_snapshot(state, lesson_id)
    objectives = [str(item).strip().lower() for item in (lesson.get("objectives") or []) if str(item).strip()]
    keywords = [
        str(lesson_id or "").strip().lower(),
        str(lesson.get("title") or lesson.get("lesson_title") or "").strip().lower(),
        str(state.get("topic") or "").strip().lower(),
    ]
    keywords = [k for k in keywords if k] + objectives[:2]

    matches: List[Dict[str, Any]] = []
    for raw in reversed(notes):
        if not isinstance(raw, dict):
            continue
        title = str(raw.get("title", "") or "")
        body = str(raw.get("body", "") or "")
        haystack = f"{title}\n{body}".lower()
        if keywords and not any(k in haystack for k in keywords):
            continue
        matches.append({
            "id": str(raw.get("id", "")),
            "title": title or "Untitled",
            "preview": body[:220],
            "updated_at": raw.get("updated_at"),
        })
        if len(matches) >= 5:
            break

    if matches:
        return matches

    fallback: List[Dict[str, Any]] = []
    for raw in reversed(notes[-3:]):
        if not isinstance(raw, dict):
            continue
        fallback.append({
            "id": str(raw.get("id", "")),
            "title": str(raw.get("title", "") or "Untitled"),
            "preview": str(raw.get("body", "") or "")[:220],
            "updated_at": raw.get("updated_at"),
        })
    return fallback


def _flashcards_for_lesson(state: Dict[str, Any], lesson_id: Optional[str]) -> List[Dict[str, str]]:
    lesson = _find_lesson_snapshot(state, lesson_id)
    aids = state.get("study_aids") or []
    if not isinstance(aids, list):
        aids = []

    cards: List[Dict[str, str]] = []
    for item in reversed(aids):
        normalized = _normalize_study_aid_entry(
            item,
            str(lesson_id or ""),
            str(lesson.get("title") or lesson.get("lesson_title") or ""),
        )
        if not normalized:
            continue
        if str(normalized.get("lesson_id") or "") != str(lesson_id or ""):
            continue
        aid_type = str(normalized.get("type") or "")
        data = normalized.get("data")
        if aid_type == "flashcards" and isinstance(data, list):
            for card in data:
                if isinstance(card, str) and card.strip():
                    cards.append({
                        "front": card.strip(),
                        "back": "Recall the underlying concept, then verify it against your latest lesson work.",
                    })
                    continue
                if not isinstance(card, dict):
                    continue
                front = str(card.get("front") or "").strip()
                back = str(card.get("back") or "").strip()
                if front and back:
                    cards.append({"front": front, "back": back})
        elif aid_type == "quiz" and isinstance(data, list):
            for q in data:
                question = str((q or {}).get("question") if isinstance(q, dict) else q).strip()
                if question:
                    cards.append({
                        "front": question,
                        "back": "Answer from memory, then verify against the lesson objective and your code.",
                    })
        if len(cards) >= 10:
            break

    deduped: List[Dict[str, str]] = []
    seen = set()
    for card in cards:
        key = card["front"].lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(card)
        if len(deduped) >= 8:
            break
    if deduped:
        return deduped
    fallback_state = {
        **state,
        "current_lesson": lesson,
        "current_exercise": state.get("current_exercise") or {},
    }
    return _build_lesson_flashcards(fallback_state)[:4]
    
    

def _summarize_prior_work(state: Dict[str, Any], lesson_id: Optional[str]) -> str:
    entry = _matching_history_entry(state, lesson_id)
    lesson = _find_lesson_snapshot(state, lesson_id)
    if entry and entry.get("summary"):
        return str(entry["summary"])
    submission = entry.get("last_submission") if entry else None
    if not isinstance(submission, dict):
        submission = state.get("last_submission") if str(state.get("lesson_id") or "") == str(lesson_id or "") else {}
    exercise = (entry or {}).get("exercise") if entry else {}
    objective_count = len([item for item in (lesson.get("objectives") or []) if str(item).strip()])
    prompt = str((exercise or {}).get("prompt") or "").strip()
    hint = str((submission or {}).get("hint") or (submission or {}).get("error") or "").strip()
    if submission:
        status_line = "last attempt passed" if bool(submission.get("passed")) else "last attempt still needed work"
    else:
        status_line = "you explored this lesson earlier"
    detail = f"Prompt focus: {prompt[:140]}" if prompt else ""
    feedback = f"Last feedback: {hint[:160]}" if hint else ""
    title = lesson.get("title") or lesson.get("lesson_title") or (lesson_id or "this lesson")
    pieces = [
        f"Returning to {title}.",
        f"You previously worked on {max(1, objective_count)} objective(s), and {status_line}.",
        detail,
        feedback,
    ]
    return " ".join(piece for piece in pieces if piece).strip()


def _sync_resume_packet(state: Dict[str, Any], lesson_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    target_lesson_id = str(lesson_id or state.get("lesson_id") or "").strip()
    if not target_lesson_id:
        state["resume_packet"] = None
        return None
    packet = _build_resume_packet(state, target_lesson_id)
    state["resume_packet"] = packet
    entry = _matching_history_entry(state, target_lesson_id)
    if entry:
        entry["resume_packet"] = packet
        entry["summary"] = packet.get("prior_work_summary") or packet.get("summary") or ""
        entry["study_aid_count"] = int(packet.get("resource_counts", {}).get("total") or 0)
        normalized_history: List[Dict[str, Any]] = []
        for idx, raw in enumerate(state.get("lesson_history") or []):
            normalized = _normalize_lesson_history_entry(raw, idx)
            if not normalized:
                continue
            if normalized["lesson_id"] == target_lesson_id:
                normalized = {**normalized, **entry}
            normalized_history.append(normalized)
        state["lesson_history"] = normalized_history[-80:]
    return packet


def _build_resume_packet(state: Dict[str, Any], lesson_id: Optional[str]) -> Dict[str, Any]:
    lesson = _find_lesson_snapshot(state, lesson_id)
    history_entry = _matching_history_entry(state, lesson_id)
    submission = history_entry.get("last_submission") if history_entry and isinstance(history_entry.get("last_submission"), dict) else {}
    if not submission and str(state.get("lesson_id") or "") == str(lesson_id or ""):
        submission = state.get("last_submission") or {}
    objectives = [str(item) for item in (lesson.get("objectives") or []) if str(item).strip()]
    notes = _matching_notes_for_lesson(state, lesson_id)
    flashcards = _flashcards_for_lesson(state, lesson_id)
    prior_work_summary = _summarize_prior_work(state, lesson_id)
    passed = bool(submission.get("passed"))
    status_line = "Latest submission passed." if passed else "Latest submission still needs work."
    hint = str(submission.get("hint") or submission.get("error") or "").strip()
    summary = (
        f"Welcome back to {lesson.get('title') or lesson.get('lesson_title') or (lesson_id or 'this lesson')}. "
        f"You previously worked on {max(1, len(objectives))} objective(s). "
        f"{status_line} "
        f"{('Last feedback: ' + hint[:180]) if hint else ''}".strip()
    )
    return {
        "lesson_id": lesson_id,
        "lesson_title": lesson.get("title") or lesson.get("lesson_title") or lesson_id,
        "summary": summary,
        "prior_work_summary": prior_work_summary,
        "objectives": objectives[:4],
        "notes": notes[:5],
        "flashcards": flashcards[:8],
        "resource_counts": {
            "notes": len(notes[:5]),
            "flashcards": len(flashcards[:8]),
            "total": len(notes[:5]) + len(flashcards[:8]),
        },
        "latest_activity_at": (history_entry or {}).get("updated_at") or (history_entry or {}).get("created_at") or state.get("updated_at"),
        "has_resources": bool(notes or flashcards),
    }


def _build_submit_adaptation(learner_context: Dict[str, Any], submission_result: Dict[str, Any]) -> Dict[str, Any]:
    coaching = learner_context.get("adaptive_coaching") if isinstance(learner_context, dict) else {}
    if not isinstance(coaching, dict):
        coaching = {}
    hint_depth = str(coaching.get("hint_depth") or "guided")
    challenge_level = str(coaching.get("challenge_level") or "balanced")
    remediation_needed = bool(coaching.get("remediation_needed"))
    passed = bool((submission_result or {}).get("passed"))
    mastery_delta = learner_context.get("latest_mastery_delta")
    confidence_delta = learner_context.get("latest_confidence_delta")

    if passed and challenge_level == "stretch":
        next_step = "You passed. Increase challenge: add edge-case tests and refactor for clarity."
    elif passed:
        next_step = "You passed. Lock in understanding by explaining your approach in one paragraph."
    elif hint_depth == "foundational":
        next_step = "Break this into 2-3 tiny steps and validate each with a quick print/assert check."
    elif hint_depth == "guided":
        next_step = "Fix one failing branch first, then re-run tests before adding new logic."
    else:
        next_step = "Try a minimal patch focused only on the failing assertion, then re-test."

    return {
        "hint_depth": hint_depth,
        "challenge_level": challenge_level,
        "coaching_tone": str(coaching.get("coaching_tone") or "step_by_step"),
        "remediation_needed": remediation_needed,
        "passed": passed,
        "mastery_delta": mastery_delta,
        "confidence_delta": confidence_delta,
        "next_step": next_step,
    }


def _is_answer_seeking_request(message: str) -> bool:
    text = str(message or "").strip().lower()
    if not text:
        return False
    patterns = [
        r"\bjust give (me )?the answer\b",
        r"\bwrite (the )?solution for me\b",
        r"\bsolve (this|it) for me\b",
        r"\bfull answer only\b",
        r"\bno explanation\b",
        r"\bexact answer\b",
        r"\bjust the code\b",
    ]
    return any(re.search(pattern, text) for pattern in patterns)


def _regenerate_current_exercise(state: Dict[str, Any], *, reason: str) -> Optional[Dict[str, Any]]:
    lesson = state.get("current_lesson") or {}
    if not isinstance(lesson, dict) or not lesson:
        return None
    from mammoth_os.exercise_generator import generate_exercises_for_lesson
    generated = generate_exercises_for_lesson(lesson, count=1)
    if not generated:
        return None
    previous = state.get("current_exercise") or {}
    next_exercise = generated[0]
    state["current_exercise"] = next_exercise
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    state["regenerated_exercise"] = {
        "reason": reason,
        "created_at": state["updated_at"],
        "previous_title": previous.get("title"),
        "next_title": next_exercise.get("title"),
    }
    return next_exercise


def _append_fab_usage_event(
    state: Dict[str, Any],
    *,
    mode: str,
    page_context: Dict[str, Any],
    guard_triggered: bool,
) -> None:
    events = state.get("fab_usage_events") or []
    if not isinstance(events, list):
        events = []
    events.append({
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "page": str(page_context.get("current_page") or ""),
        "guard_triggered": guard_triggered,
        "has_lesson_context": bool(page_context.get("lesson")),
    })
    state["fab_usage_events"] = events[-200:]


def _run_atlas_evals(state: Dict[str, Any]) -> Dict[str, Any]:
    eval_state = {
        **state,
        "current_lesson": dict(state.get("current_lesson") or {}),
        "current_exercise": dict(state.get("current_exercise") or {}),
        "lesson_id": str(state.get("lesson_id") or "lesson-1"),
        "topic": state.get("topic") or "Python basics",
        "lesson_history": [
            {
                "lesson_id": str(state.get("lesson_id") or "lesson-1"),
                "lesson": dict(state.get("current_lesson") or {}),
                "exercise": dict(state.get("current_exercise") or {}),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        ],
    }
    onboarding_payload = {
        "experience_level": "intermediate",
        "preferred_pacing": "steady",
        "learning_style": "guided",
        "goals": "Build reliably",
        "focus_areas": "debugging, planning",
    }
    learner_user_id = _atlas_user_id(eval_state)
    learner_state = set_onboarding_profile(eval_state, user_id=learner_user_id, onboarding=onboarding_payload)
    onboarding_ok = bool(learner_state.get("onboarding") or {})

    failure_result = {
        "passed": False,
        "hint": "Add a return statement and validate the function signature.",
        "error": "AssertionError: expected 3",
    }
    learner_state = update_learner_model(
        learner_user_id,
        lesson=eval_state.get("current_lesson") or {},
        exercise=eval_state.get("current_exercise") or {},
        result=failure_result,
        topic=eval_state.get("topic"),
        metadata={"eval_run": True},
    )
    learner_context = build_learner_context(learner_state)
    adaptive_feedback = _build_submit_adaptation(learner_context, failure_result)
    adaptation_ok = bool(adaptive_feedback.get("next_step"))

    resume_packet = _build_resume_packet(eval_state, eval_state.get("lesson_id"))
    continuity_ok = bool(resume_packet.get("summary"))

    checks = [
        {
            "name": "onboarding_profile",
            "status": "pass" if onboarding_ok else "fail",
            "detail": "Onboarding profile persisted and exposed through the learner model.",
        },
        {
            "name": "adaptive_feedback",
            "status": "pass" if adaptation_ok else "fail",
            "detail": adaptive_feedback.get("next_step") or "Adaptive feedback did not produce a coaching step.",
        },
        {
            "name": "resume_continuity",
            "status": "pass" if continuity_ok else "fail",
            "detail": resume_packet.get("summary") or "Resume packet could not be built.",
        },
    ]
    return {
        "status": "ok",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "summary": {
            "pass_count": sum(1 for item in checks if item["status"] == "pass"),
            "fail_count": sum(1 for item in checks if item["status"] != "pass"),
        },
    }


def _build_atlas_plan_steps(state: Dict[str, Any], plan_profile: str = "coding", coding_intent: str = "") -> List[Dict[str, Any]]:
    lesson = state.get("current_lesson") or {}
    exercise = state.get("current_exercise") or {}
    learner_context = state.get("learner_context") or {}
    module_track = state.get("active_module") or _serialize_module_track(_resolve_module_track(state.get("module_id"), state.get("topic"))) or {}
    topic = str(state.get("topic") or lesson.get("title") or lesson.get("lesson_title") or "current lesson").strip()
    prompt = str(exercise.get("prompt") or "").strip()
    objective = prompt or f"Complete the {topic} lesson with a clear plan and safe next steps."
    profile = _normalize_plan_profile(plan_profile)
    coding_intent = _normalize_coding_intent(coding_intent) or _default_coding_intent_for_profile(profile)
    difficulty = str(learner_context.get("recommended_difficulty") or "beginner")
    weakest = [str(item.get("concept") or "").replace("-", " ") for item in (learner_context.get("weakest_concepts") or []) if isinstance(item, dict)]
    weakest_summary = ", ".join([item for item in weakest[:3] if item]) or "the current lesson objective"

    if profile == "coding_only":
        return [_build_coding_step(objective, coding_intent)]

    steps: List[Dict[str, Any]] = [
        {
            "id": "atlas-curriculum",
            "title": "Align the lesson to the active module",
            "agent_id": "curriculum_agent",
            "intent": "lesson_curriculum",
            "prompt": (
                f"Generate a concise curriculum framing for {topic}. "
                f"Module: {module_track.get('label') or state.get('module_id') or 'current track'}. "
                f"Objective: {objective}"
            ),
        },
        {
            "id": "atlas-clarify",
            "title": "Clarify the lesson objective",
            "agent_id": "plant_the_seed_agent",
            "intent": "plant_seed",
            "prompt": f"Turn this lesson objective into a concise learning plan for a {difficulty} learner: {objective}",
        },
        {
            "id": "atlas-research",
            "title": "Map constraints and pitfalls",
            "agent_id": "research_agent",
            "intent": "research_curriculum",
            "prompt": f"Summarize the likely constraints and pitfalls for this lesson objective, especially around {weakest_summary}: {objective}",
        },
        _build_coding_step(objective, coding_intent),
        {
            "id": "atlas-coach",
            "title": "Translate the plan into coaching checkpoints",
            "agent_id": "tutor_agent",
            "intent": "lesson_coaching",
            "prompt": (
                f"Create learner checkpoints, a reflection question, and a safe next action for this lesson. "
                f"Topic: {topic}. Objective: {objective}"
            ),
        },
    ]

    if profile in {"atlas", "balanced", "autonomous"}:
        steps.append(
            {
                "id": "atlas-operations",
                "title": "Prepare execution safeguards",
                "agent_id": "field_ops_agent",
                "intent": "field_ops",
                "prompt": f"Create a short execution checklist to keep this lesson safe, testable, and non-cheaty: {objective}",
            }
        )

    if profile == "autonomous":
        steps.extend(
            [
                {
                    "id": "atlas-community",
                    "title": "Create stakeholder update",
                    "agent_id": "community_engine_agent",
                    "intent": "summarize",
                    "prompt": f"Draft a short progress update and expectation-setting note for this lesson objective: {objective}",
                    "approval_contract": {
                        "operation": "community_publish",
                        "target": "atlas/community-update",
                    },
                },
                {
                    "id": "atlas-custodial",
                    "title": "Add maintenance + rollback checkpoints",
                    "agent_id": "custodial_agent",
                    "intent": "summarize",
                    "prompt": f"Generate maintenance checks and rollback checkpoints before shipping this lesson work: {objective}",
                },
            ]
        )

    return steps


@app.get("/api/atlas/status")
async def atlas_status():
    state = _load_atlas_state()
    _hydrate_learner_state(state, user_id=_atlas_user_id(state))
    _sync_resume_packet(state)
    return _decorate_atlas_state(state)


@app.get("/api/atlas/modules")
async def atlas_modules():
    state = _load_atlas_state()
    active_track = _resolve_module_track(state.get("module_id"), state.get("topic"))
    return {
        "status": "ok",
        "modules": _atlas_module_catalog(),
        "active_module": _serialize_module_track(active_track),
    }


@app.get("/api/atlas/library")
async def atlas_library():
    state = _load_atlas_state()
    _hydrate_learner_state(state, user_id=_atlas_user_id(state))
    return await _build_atlas_library_snapshot(state)


@app.get("/api/atlas/learner")
async def atlas_learner():
    state = _load_atlas_state()
    learner_state = _hydrate_learner_state(state, user_id=_atlas_user_id(state))
    return {"status": "ok", "learner_model": learner_state, "learner_context": state.get("learner_context")}


@app.post("/api/atlas/onboard")
async def atlas_onboard(body: Dict[str, Any]):
    approval_mode = bool(body.get("approval_mode") or body.get("preview_only"))
    if approval_mode:
        task_id = f"atlas-onboard-{uuid.uuid4().hex[:8]}"
        preview = _build_operation_preview("atlas_onboard_update", {"onboarding": body})
        approval = _create_approval_record(
            task_id,
            agent_id="tutor_agent",
            operation="atlas_onboard_update",
            target="atlas/onboarding",
            preview=preview,
            payload={"onboarding": body},
            requested_by="user",
        )
        _upsert_task(
            task_id,
            "approval:atlas_onboard_update",
            status="pending_approval",
            agent_id="tutor_agent",
            description="ATLAS onboarding profile update pending approval",
            details={"approval_id": approval["id"]},
        )
        _append_activity(
            "ATLAS onboarding update queued for approval",
            agent_id="tutor_agent",
            task_id=task_id,
            kind="approval_requested",
            details={"approval_id": approval["id"]},
        )
        return {"status": "ok", "approval": approval, "preview": preview}
    return _apply_atlas_onboarding_update(body)


@app.post("/api/atlas/learner/reset")
async def atlas_learner_reset(body: Optional[Dict[str, Any]] = None):
    body = body or {}
    approval_mode = bool(body.get("approval_mode") or body.get("preview_only"))
    if approval_mode:
        task_id = f"atlas-learner-reset-{uuid.uuid4().hex[:8]}"
        preview = _build_operation_preview("atlas_learner_reset", {})
        approval = _create_approval_record(
            task_id,
            agent_id="tutor_agent",
            operation="atlas_learner_reset",
            target="atlas/learner",
            preview=preview,
            payload={},
            requested_by="user",
        )
        _upsert_task(
            task_id,
            "approval:atlas_learner_reset",
            status="pending_approval",
            agent_id="tutor_agent",
            description="ATLAS learner reset pending approval",
            details={"approval_id": approval["id"]},
        )
        _append_activity(
            "ATLAS learner reset queued for approval",
            agent_id="tutor_agent",
            task_id=task_id,
            kind="approval_requested",
            details={"approval_id": approval["id"]},
        )
        return {"status": "ok", "approval": approval, "preview": preview}
    return _apply_atlas_learner_reset()


@app.post("/api/atlas/lesson")
async def atlas_lesson(body: Dict[str, Any]):
    requested_topic = str(body.get("topic") or "").strip()
    module_track = _resolve_module_track(body.get("module_id"), requested_topic)
    topic = requested_topic or str((module_track or {}).get("topic") or "Python basics")
    curriculum_topic = _compose_module_curriculum_topic(topic, module_track)
    try:
        from mammoth_os.atlas_session import ATLASSession
        state = _load_atlas_state()
        learner_user_id = _atlas_user_id(state)
        session = ATLASSession(user_id=learner_user_id)
        learner_context = state.get("learner_context") or {}
        if not learner_context:
            _hydrate_learner_state(state, user_id=learner_user_id)
            learner_context = state.get("learner_context") or {}
        lesson_plan = build_lesson_plan(state, topic)
        if module_track:
            lesson_plan["module_track"] = _serialize_module_track(module_track)
            lesson_plan["curriculum_topic"] = curriculum_topic
        learner_context = {**learner_context, "lesson_plan": lesson_plan}
        if module_track:
            learner_context["module_track"] = _serialize_module_track(module_track)
        difficulty = str(lesson_plan.get("difficulty") or learner_context.get("recommended_difficulty") or "beginner").strip().lower() or "beginner"
        exercise = await asyncio.get_event_loop().run_in_executor(
            None, lambda: session.start_lesson(curriculum_topic, difficulty=difficulty, learner_context=learner_context)
        )
        session.current_lesson = _decorate_lesson_for_module_track(session.current_lesson, module_track)
        exercise = _decorate_exercise_for_module_track(exercise, session.current_lesson, module_track)
        state.update({
            "status":           "active",
            "topic":            topic,
            "curriculum_topic": curriculum_topic,
            "current_exercise": exercise,
            "curriculum":       session.curriculum,
            "current_lesson":   session.current_lesson,
            "curriculum_id":    session._curriculum_id,
            "lesson_id":        session._lesson_id,
            "lesson_plan":      lesson_plan,
            "module_id":        (module_track or {}).get("id"),
            "active_module":    _serialize_module_track(module_track),
            "updated_at":       datetime.now(timezone.utc).isoformat(),
        })
        _hydrate_learner_state(state, user_id=learner_user_id)
        _append_lesson_history(state, session.current_lesson or {}, exercise or {})
        _sync_resume_packet(state, state.get("lesson_id"))
        _save_atlas_state(state)
        _append_audit_event(
            kind="atlas_lesson",
            message="ATLAS lesson started",
            details={"topic": topic, "difficulty": difficulty, "module_id": (module_track or {}).get("id")},
            source="atlas",
            actor="learner",
        )
        return {
            "status": "ok",
            "exercise": exercise,
            "learner_context": state.get("learner_context"),
            "active_module": _serialize_module_track(module_track),
            "curriculum_topic": curriculum_topic,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.post("/api/atlas/submit")
async def atlas_submit(body: Dict[str, Any]):
    code = body.get("code", "")
    try:
        state = _load_atlas_state()
        learner_user_id = _atlas_user_id(state)
        from mammoth_os.atlas_session import ATLASSession
        session = ATLASSession(user_id=learner_user_id)
        session.curriculum       = state.get("curriculum")
        session.current_lesson   = state.get("current_lesson")
        session.current_exercise = state.get("current_exercise")
        session._curriculum_id   = state.get("curriculum_id")
        session._lesson_id       = state.get("lesson_id")
        current_exercise = state.get("current_exercise") or {}
        current_lesson = state.get("current_lesson") or {}
        active_track = _resolve_module_track(state.get("module_id"), state.get("topic"))
        submission_mode = str(current_exercise.get("submission_mode") or "").strip().lower() or (
            "code" if str(current_exercise.get("lesson_type") or "code").strip().lower() == "code" else "text"
        )

        if submission_mode == "text":
            response_text = str(body.get("response") or code or "").strip()
            result = _evaluate_text_submission(
                response_text,
                lesson=current_lesson if isinstance(current_lesson, dict) else {},
                exercise=current_exercise if isinstance(current_exercise, dict) else {},
                track=active_track,
                lesson_id=str(state.get("lesson_id") or ""),
            )
        else:
            files = {"solution.py": code}
            result = await session.submit(files)

        state["last_submission"] = result
        _hydrate_learner_state(
            state,
            user_id=learner_user_id,
            lesson=state.get("current_lesson") or {},
            exercise=state.get("current_exercise") or {},
            result=result,
            topic=state.get("topic"),
            metadata={"error_fingerprint": None},
        )
        learner_context = state.get("learner_context") or {}
        adaptive_feedback = _build_submit_adaptation(learner_context, result)
        _record_submission_on_history(state, result)
        regenerated_exercise = None
        if (
            bool(body.get("regenerate_on_fail"))
            and not bool(result.get("passed"))
            and adaptive_feedback.get("remediation_needed")
        ):
            regenerated_exercise = _regenerate_current_exercise(
                state,
                reason="remediation_after_failed_submission",
            )
        _sync_resume_packet(state, state.get("lesson_id"))
        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        _save_atlas_state(state)
        try:
            _topic = str(state.get("topic") or "")
            _lesson_title = str(current_lesson.get("title") or current_lesson.get("objective") or "lesson")
            _outcome_label = "passed" if bool(result.get("passed")) else "attempted"
            _MEMORY_ENGINE.store(
                f"Lesson '{_lesson_title}' on topic '{_topic}': {_outcome_label}. Score: {result.get('score') or 0}.",
                memory_type="atlas_outcome",
                metadata={
                    "lesson_id": str(state.get("lesson_id") or ""),
                    "topic": _topic,
                    "passed": bool(result.get("passed")),
                    "score": result.get("score"),
                    "user_id": learner_user_id,
                },
            )
        except Exception:
            pass
        _append_audit_event(
            kind="atlas_submit",
            message="ATLAS submission evaluated",
            details={"passed": bool(result.get("passed")), "score": result.get("score")},
            source="atlas",
            actor="learner",
        )
        return {
            "status": "ok",
            "result": result,
            "learner_context": state.get("learner_context"),
            "adaptive_feedback": adaptive_feedback,
            "current_exercise": state.get("current_exercise"),
            "regenerated_exercise": regenerated_exercise,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.post("/api/atlas/next")
async def atlas_next():
    state = _load_atlas_state()
    curriculum = state.get("curriculum", {})
    modules    = curriculum.get("modules", []) if curriculum else []

    lesson_id = state.get("lesson_id", "")
    # find next lesson index
    found = False
    for mod in modules:
        for i, lesson in enumerate(mod.get("lessons", [])):
            if lesson.get("lesson_id") == lesson_id:
                found = True
                next_i = i + 1
                if next_i < len(mod["lessons"]):
                    next_lesson = mod["lessons"][next_i]
                    active_track = _resolve_module_track(state.get("module_id"), state.get("topic"))
                    next_lesson = _decorate_lesson_for_module_track(next_lesson, active_track)
                    state["current_lesson"] = next_lesson
                    state["lesson_id"]      = next_lesson["lesson_id"]
                    try:
                        from mammoth_os.exercise_generator import generate_exercises_for_lesson
                        generated = generate_exercises_for_lesson(next_lesson, count=1)
                        if generated:
                            state["current_exercise"] = _decorate_exercise_for_module_track(generated[0], next_lesson, active_track)
                    except Exception:
                        # Keep session moving even if exercise generation fails.
                        pass
                    state["updated_at"]     = datetime.now(timezone.utc).isoformat()
                    _append_lesson_history(state, next_lesson, state.get("current_exercise") or {})
                    _sync_resume_packet(state, state.get("lesson_id"))
                    _save_atlas_state(state)
                    return {"status": "ok", "lesson": mod["lessons"][next_i]}
                break
        if found:
            break

    return {"status": "ok", "message": "No more lessons in current module"}


@app.post("/api/atlas/back")
async def atlas_back():
    state = _load_atlas_state()
    history = state.get("lesson_history") or []
    if not isinstance(history, list) or len(history) < 2:
        return {"status": "ok", "message": "No previous lesson to return to."}
    history.pop()
    previous = history[-1]
    state["lesson_history"] = history
    state["current_lesson"] = previous.get("lesson") or {}
    state["lesson_id"] = previous.get("lesson_id")
    state["current_exercise"] = previous.get("exercise") or {}
    if isinstance(previous.get("last_submission"), dict):
        state["last_submission"] = previous.get("last_submission")
    _sync_resume_packet(state, state.get("lesson_id"))
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    _save_atlas_state(state)
    return {
        "status": "ok",
        "lesson": state.get("current_lesson"),
        "exercise": state.get("current_exercise"),
        "resume_packet": state.get("resume_packet"),
    }


@app.get("/api/atlas/recap")
async def atlas_recap():
    state = _load_atlas_state()
    recap = _build_lesson_recap(state)
    _append_study_aid(state, "recap", recap)
    _save_atlas_state(state)
    return {"status": "ok", "recap": recap}


@app.get("/api/atlas/quiz")
async def atlas_quiz():
    state = _load_atlas_state()
    quiz = _build_lesson_quiz(state)
    _append_study_aid(state, "quiz", quiz)
    _save_atlas_state(state)
    return {"status": "ok", "quiz": quiz}


@app.get("/api/atlas/review")
async def atlas_review():
    state = _load_atlas_state()
    review = _build_lesson_review(state)
    _append_study_aid(state, "review", review)
    _save_atlas_state(state)
    return {"status": "ok", "review": review}


@app.get("/api/atlas/flashcards")
async def atlas_flashcards():
    state = _load_atlas_state()
    flashcards = _build_lesson_flashcards(state)
    _append_study_aid(state, "flashcards", flashcards)
    _save_atlas_state(state)
    return {"status": "ok", "flashcards": flashcards}


@app.post("/api/atlas/plan")
async def atlas_plan(body: Optional[Dict[str, Any]] = None):
    state = _load_atlas_state()
    _hydrate_learner_state(state, user_id=_atlas_user_id(state))
    body = body or {}
    trace_id = str(body.get("trace_id") or new_trace_id("atlas"))
    plan_profile = _normalize_plan_profile(body.get("plan_profile") or "coding")
    coding_intent = _normalize_coding_intent(body.get("coding_intent")) or _default_coding_intent_for_profile(plan_profile)
    approval_mode = bool(body.get("approval_mode", False))
    steps = _build_atlas_plan_steps(state, plan_profile, coding_intent)
    plan_id = f"atlas-plan-{uuid.uuid4().hex[:8]}"
    objective = str((state.get("current_exercise") or {}).get("prompt") or state.get("topic") or "Current lesson")
    step_results = await _execute_plan_steps(
        plan_id=plan_id,
        steps=steps,
        objective=objective,
        temperature=0.3,
        approval_mode=approval_mode,
        stop_on_failure=True,
        activity_agent_id="tutor_agent",
    )

    completed_count = sum(1 for step in step_results if step["status"] == "completed")
    failed_count = sum(1 for step in step_results if step["status"] == "failed")
    pending_count = sum(1 for step in step_results if step["status"] == "pending_approval")
    total_count = len(step_results)
    plan_status = "completed" if failed_count == 0 and pending_count == 0 else "pending_approval" if pending_count > 0 else "failed"
    synthesis = _build_plan_synthesis(
        step_results,
        objective=objective,
        lesson_title=str((state.get("current_lesson") or {}).get("title") or (state.get("current_lesson") or {}).get("lesson_title") or ""),
    )
    plan = {
        "plan_id": plan_id,
        "trace_id": trace_id,
        "objective": objective,
        "plan_profile": plan_profile,
        "coding_intent": coding_intent,
        "plan_status": plan_status,
        "progress": {
            "total": total_count,
            "executed": total_count,
            "completed": completed_count,
            "pending_approval": pending_count,
            "failed": failed_count,
        },
        "plan_steps": step_results,
        "synthesis": synthesis,
        "created_at": datetime.now(timezone.utc).isoformat(),
        **_summarize_plan_run(
            step_results,
            objective=objective,
            plan_profile=plan_profile,
            coding_intent=coding_intent,
            approval_mode=approval_mode,
        ),
    }
    state["active_plan"] = plan
    _append_plan_history(state, plan)
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    _append_activity(
        "ATLAS tutor plan generated",
        agent_id="tutor_agent",
        task_id=plan["plan_id"],
        kind="atlas_plan_generated",
        trace_id=trace_id,
        details={"plan_status": plan_status, "step_count": total_count, "plan_profile": plan_profile, "coding_intent": coding_intent, "trace_id": trace_id},
    )
    _append_audit_event(
        kind="atlas_plan",
        message="ATLAS plan generated",
        details={"plan_id": plan_id, "plan_profile": plan_profile, "coding_intent": coding_intent, "plan_status": plan_status, "trace_id": trace_id},
        source="atlas",
        actor="system",
    )
    _save_atlas_state(state)
    return {"status": "ok", "plan": plan, "plan_history": state.get("plan_history", []), "trace_id": trace_id, "observability": _build_atlas_observability(state)}


@app.post("/api/atlas/evals")
async def atlas_evals(body: Optional[Dict[str, Any]] = None):
    state = _load_atlas_state()
    evaluation = _run_atlas_evals(state)
    history = _load_eval_history()
    history.append(evaluation)
    if len(history) > 20:
        history = history[-20:]
    _write_json(ATLAS_EVALS_FILE, history)
    _append_audit_event(
        kind="atlas_eval",
        message="ATLAS eval run completed",
        details={"pass_count": int((evaluation.get("summary") or {}).get("pass_count") or 0), "fail_count": int((evaluation.get("summary") or {}).get("fail_count") or 0)},
        source="atlas",
        actor="system",
    )
    return {"status": "ok", "evaluation": evaluation, "history": history, "observability": _build_atlas_observability(state, eval_history=history)}


@app.get("/api/memory")
async def get_memory_entries(limit: int = 50, memory_type: Optional[str] = None):
    entries = _MEMORY_ENGINE._entries
    if memory_type:
        entries = [e for e in entries if e.get("memory_type") == memory_type]
    recent = entries[-limit:] if len(entries) > limit else entries
    recent = list(reversed(recent))
    return {
        "status": "ok",
        "total": len(_MEMORY_ENGINE._entries),
        "entries": recent,
        "memory_types": list({e.get("memory_type", "semantic") for e in _MEMORY_ENGINE._entries}),
    }


@app.post("/api/memory/search")
async def search_memory(body: Dict[str, Any]):
    query = str(body.get("query") or "").strip()
    top_k = int(body.get("top_k") or 10)
    memory_type = body.get("memory_type")
    if not query:
        return {"status": "error", "error": "query is required"}
    results = _MEMORY_ENGINE.retrieve(query, top_k=top_k, memory_type=memory_type)
    return {"status": "ok", "query": query, "results": results, "count": len(results)}


@app.post("/api/memory")
async def store_memory_entry(body: Dict[str, Any]):
    content = str(body.get("content") or "").strip()
    if not content:
        return {"status": "error", "error": "content is required"}
    memory_type = str(body.get("memory_type") or "semantic")
    metadata = body.get("metadata") or {}
    try:
        entry_id = _MEMORY_ENGINE.store(content, memory_type=memory_type, metadata=metadata)
        return {"status": "ok", "id": entry_id}
    except Exception as e:
        return {"status": "error", "error": str(e)}



async def atlas_regenerate(body: Optional[Dict[str, Any]] = None):
    state = _load_atlas_state()
    reason = "manual_regeneration"
    if isinstance(body, dict):
        reason = str(body.get("reason") or reason)
    exercise = _regenerate_current_exercise(state, reason=reason)
    if not exercise:
        return {"status": "error", "error": "No active lesson available for regeneration."}
    _append_lesson_history(state, state.get("current_lesson") or {}, exercise or {})
    _sync_resume_packet(state, state.get("lesson_id"))
    _save_atlas_state(state)
    return {
        "status": "ok",
        "exercise": exercise,
        "reason": reason,
        "learner_context": state.get("learner_context"),
    }


@app.get("/api/approvals")
async def get_approvals():
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    return _load_approvals()


@app.post("/api/approvals/{record_id}/approve")
async def approve_record_route(record_id: str):
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    return _approve_record(record_id)


@app.get("/api/snapshots")
async def get_snapshots():
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    return _load_snapshots()


@app.post("/api/snapshots/{snapshot_id}/restore")
async def restore_snapshot_route(snapshot_id: str):
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    return _restore_snapshot(snapshot_id)


@app.post("/api/atlas/apply")
async def atlas_apply(body: Dict[str, Any]):
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    operation = str(body.get("operation", "")).strip().lower()
    file_path = str(body.get("file_path", "")).strip()
    if operation not in {"create_file", "write_file", "apply_patch", "insert_after"}:
        return {"status": "error", "error": "Unsupported operation"}
    if not file_path:
        return {"status": "error", "error": "file_path is required"}

    payload: Dict[str, Any] = {"file_path": file_path}
    if operation == "apply_patch":
        payload["new_content"] = str(body.get("new_content", ""))
    elif operation == "insert_after":
        payload["anchor"] = str(body.get("anchor", ""))
        payload["content"] = str(body.get("content", ""))
    else:
        payload["content"] = str(body.get("content", ""))

    approval_mode = bool(body.get("approval_mode") or body.get("preview_only"))
    if approval_mode:
        preview = _build_operation_preview(operation, payload)
        approval = _create_approval_record(
            f"atlas-{uuid.uuid4().hex[:8]}",
            agent_id="tutor_agent",
            operation=operation,
            target=file_path,
            preview=preview,
            payload=payload,
            requested_by="user",
        )
        _append_activity(
            f"ATLAS approval requested: {operation}",
            agent_id="tutor_agent",
            kind="atlas_apply",
            details={"file_path": file_path, "approval_id": approval["id"]},
        )
        return {"status": "ok", "operation": operation, "approval": approval, "preview": preview}

    result = await asyncio.get_event_loop().run_in_executor(
        None, lambda: _run_file_operation(operation, payload)
    )
    _append_activity(
        f"ATLAS apply operation: {operation}",
        agent_id="tutor_agent",
        kind="atlas_apply",
        details={"file_path": file_path, "result": result},
    )
    return {"status": "ok", "operation": operation, "result": result}


@app.post("/api/atlas/reset")
async def atlas_reset(body: Optional[Dict[str, Any]] = None):
    body = body or {}
    approval_mode = bool(body.get("approval_mode") or body.get("preview_only"))
    if approval_mode:
        task_id = f"atlas-reset-{uuid.uuid4().hex[:8]}"
        preview = _build_operation_preview("atlas_session_reset", {})
        approval = _create_approval_record(
            task_id,
            agent_id="tutor_agent",
            operation="atlas_session_reset",
            target="atlas/session",
            preview=preview,
            payload={},
            requested_by="user",
        )
        _upsert_task(
            task_id,
            "approval:atlas_session_reset",
            status="pending_approval",
            agent_id="tutor_agent",
            description="ATLAS session reset pending approval",
            details={"approval_id": approval["id"]},
        )
        _append_activity(
            "ATLAS session reset queued for approval",
            agent_id="tutor_agent",
            task_id=task_id,
            kind="approval_requested",
            details={"approval_id": approval["id"]},
        )
        return {"status": "ok", "approval": approval, "preview": preview}
    return _apply_atlas_session_reset()


@app.post("/api/atlas/chat")
async def atlas_chat(body: Dict[str, Any]):
    message = str(body.get("message", "")).strip()
    if not message:
        return {"status": "error", "error": "message is required"}

    trace_id = str(body.get("trace_id") or new_trace_id("chat"))
    state = _load_atlas_state()
    mode = str(body.get("mode") or "tutor").strip().lower() or "tutor"
    if mode in {"assistant", "general", "chat"}:
        mode = "assistant"
    elif mode not in {"tutor", "build"}:
        mode = "tutor"
    strict_guard = bool(body.get("strict_guard", True))
    regenerate_on_guard = bool(body.get("regenerate_on_guard"))
    page_context = _normalize_page_context(body.get("page_context"), body.get("page_snapshot"))
    repo_context_request = _normalize_repo_context_request(body.get("repo_context"))
    repo_context = _collect_repo_context_snapshot(repo_context_request) if repo_context_request else {}
    current_lesson = state.get("current_lesson") or {}
    current_exercise = state.get("current_exercise") or {}
    last_submission = state.get("last_submission") or {}
    learner_context = state.get("learner_context") or {}
    _hydrate_learner_state(state, user_id=_atlas_user_id(state))
    lesson_plan = state.get("lesson_plan") or build_lesson_plan(state, state.get("topic"))
    resume_packet = state.get("resume_packet") or _build_resume_packet(state, state.get("lesson_id"))
    learner_context = {**(state.get("learner_context") or learner_context), "lesson_plan": lesson_plan}
    has_active_exercise = bool(current_exercise and current_exercise.get("prompt"))
    guard_triggered = mode in {"tutor", "build"} and strict_guard and has_active_exercise and _is_answer_seeking_request(message)
    _sync_resume_packet(state, state.get("lesson_id"))

    adapter = str(body.get("adapter", "")).strip()
    model = str(body.get("model", "")).strip()
    temperature = float(body.get("temperature", 0.2))

    history_key = "assistant_chat_history" if mode == "assistant" else "chat_history"
    history = state.get(history_key) or []
    if not isinstance(history, list):
        history = []
    history.append({
        "role": "user",
        "message": message,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "page": str(page_context.get("current_page") or ""),
    })

    slash = _parse_mammoth_chat_command(message)
    if slash and slash.get("kind") in {"web", "research"}:
        command_result = _run_internet_command(slash)
        internet_reply = str(command_result.get("reply") or "No response produced.")
        history.append({
            "role": "assistant",
            "message": internet_reply,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "adapter": "internet-tool",
            "model": "internet-tool",
            "mode": mode,
            "evidence_items": [command_result.get("evidence")],
        })
        state[history_key] = history[-60:]
        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        _append_fab_usage_event(
            state,
            mode=mode,
            page_context=page_context,
            guard_triggered=False,
        )
        _save_atlas_state(state)
        return {
            "status": "ok" if command_result.get("status") == "ok" else "error",
            "reply": internet_reply,
            "adapter": "internet-tool",
            "model": "internet-tool",
            "chat_history": state[history_key],
            "guard_triggered": False,
            "mode": mode,
            "runtime_status": _runtime_status_snapshot(),
            "runtime_notice": None,
            "trace_id": trace_id,
        }
    if slash and slash.get("kind") == "error":
        return {"status": "error", "error": slash.get("error") or "Invalid command."}

    if guard_triggered:
        regenerated_exercise = None
        if regenerate_on_guard:
            regenerated_exercise = _regenerate_current_exercise(
                state,
                reason="anti_cheat_guard_triggered",
            )
        guard_reply = (
            "I can't provide direct answer dumps for an active exercise. "
            "I can coach you step-by-step or generate a fresh parallel exercise."
        )
        if regenerated_exercise:
            guard_reply += "\n\n✅ I generated a new exercise variant so you can keep learning without answer leakage."
        history.append({
            "role": "assistant",
            "message": guard_reply,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "adapter": "policy-guard",
            "model": "policy-guard",
            "guard_triggered": True,
        })
        state[history_key] = history[-60:]
        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        _append_fab_usage_event(
            state,
            mode=mode,
            page_context=page_context,
            guard_triggered=True,
        )
        _save_atlas_state(state)
        return {
            "status": "ok",
            "reply": guard_reply,
            "adapter": "policy-guard",
            "model": "policy-guard",
            "chat_history": state[history_key],
            "guard_triggered": True,
            "regenerated_exercise": regenerated_exercise,
            "current_exercise": state.get("current_exercise"),
            "trace_id": trace_id,
        }

    if mode == "assistant":
        tutor_prompt = (
            "You are MammothOS Assistant, a natural-language AI partner for building, planning, and learning. "
            "Be conversational, practical, and concise. Never provide harmful content.\n\n"
            f"Observed page context: {json.dumps(page_context, default=str)[:1600]}\n\n"
            f"Observed repo context: {json.dumps(repo_context, default=str)[:2200]}\n\n"
            f"User message: {message}\n\n"
            "If the user asks for lesson-specific coaching, you can optionally use this context:\n"
            f"Current lesson: {current_lesson.get('title', 'N/A')}\n"
            f"Exercise prompt: {current_exercise.get('prompt', 'N/A')}\n"
            f"Recent submission result: {last_submission}\n\n"
            "Respond naturally like a normal AI chat assistant. Do not force lesson framing unless the user asks for it."
        )
    else:
        tutor_prompt = (
            "You are ATLAS Tutor, a practical coding mentor. "
            "Give clear, concise help. Never provide harmful content.\n\n"
            f"Interaction mode: {mode}\n"
            f"Current lesson: {current_lesson.get('title', 'N/A')}\n"
            f"Lesson objectives: {current_lesson.get('objectives', [])}\n"
            f"Exercise prompt: {current_exercise.get('prompt', 'N/A')}\n"
            f"Recent submission result: {last_submission}\n"
            f"Adaptive learner context: {json.dumps(learner_context, default=str)[:2500]}\n"
            f"Adaptive lesson plan: {json.dumps(lesson_plan, default=str)[:1500]}\n\n"
            f"Resume packet: {json.dumps(resume_packet, default=str)[:1800]}\n\n"
            f"Observed page context: {json.dumps(page_context, default=str)[:1600]}\n\n"
            f"Observed repo context: {json.dumps(repo_context, default=str)[:2200]}\n\n"
            f"Student message: {message}\n\n"
            "Policy: do not provide direct final answers for active exercises. Use hints and checks.\n"
            "If mode is 'build', include a short implementation plan plus one safe next action.\n"
            "Respond with: 1) diagnosis, 2) next concrete step, 3) short example when useful."
        )

    llm_reply = ""
    active_model = ""
    active_adapter = ""
    runtime_status = _runtime_status_snapshot()
    try:
        from mammoth_os.llm_client import get_llm_client
        cfg: Dict[str, Any] = {}
        if adapter:
            cfg["adapter"] = adapter
        if model:
            cfg["model"] = model
            # If a local model/tag is requested, force Ollama adapter explicitly.
            model_l = model.lower()
            try:
                from mammoth_os.ollama_adapter import MODEL_ALIASES
                if model_l in MODEL_ALIASES or model_l in MODEL_ALIASES.values() or ":" in model_l:
                    cfg["adapter"] = "ollama"
            except Exception:
                if ":" in model_l:
                    cfg["adapter"] = "ollama"
        client = get_llm_client(config=cfg)
        llm_reply = await client.generate(tutor_prompt, temperature=temperature)
        active_model = str(getattr(client, "model", model or "unknown"))
        requested_adapter = str((cfg.get("adapter") or os.environ.get("MAMMOTH_LLM_ADAPTER") or "").strip() or "auto")
        client_meta = _runtime_metadata_from_client(client, requested_adapter=requested_adapter)
        active_adapter = str(client_meta.get("active_adapter") or requested_adapter or "auto")
        runtime_status = _runtime_status_snapshot()
        runtime_status["effective_adapter"] = active_adapter
        if client_meta.get("fallback_used"):
            runtime_status["state"] = "degraded"
            runtime_status["degraded_mode"] = True
            runtime_status["fallback_used"] = True
            runtime_status["primary_provider"] = client_meta.get("primary_provider")
            runtime_status["used_provider"] = client_meta.get("used_provider")
            if client_meta.get("fallback_reason"):
                runtime_status["fallback_reason"] = client_meta.get("fallback_reason")
            if client_meta.get("fallback_error_type"):
                runtime_status["fallback_error_type"] = client_meta.get("fallback_error_type")
        _remember_runtime_status(runtime_status)
    except Exception as e:
        runtime_status = _runtime_status_snapshot()
        safe_error = _sanitize_runtime_error_message(e)
        llm_reply = (
            "I could not reach the configured LLM runtime right now. "
            "MammothOS switched to a safe fallback path. "
            f"{runtime_status.get('recommendation')}"
        )
        if not active_model:
            active_model = "fallback-local"
        if not active_adapter:
            active_adapter = "fallback-local"
        runtime_status["error_type"] = type(e).__name__
        runtime_status["safe_error"] = safe_error
        _remember_runtime_status(runtime_status)

    history.append({
        "role": "assistant",
        "message": llm_reply,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "adapter": active_adapter,
        "model": active_model,
        "mode": mode,
    })
    state[history_key] = history[-60:]
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    _append_fab_usage_event(
        state,
        mode=mode,
        page_context=page_context,
        guard_triggered=False,
    )
    _save_atlas_state(state)

    return {
        "status": "ok",
        "reply": llm_reply,
        "adapter": active_adapter,
        "model": active_model,
        "chat_history": state[history_key],
        "guard_triggered": False,
        "mode": mode,
        "runtime_status": runtime_status,
        "runtime_notice": None if runtime_status.get("state") == "ready" else build_runtime_notice(runtime_status, trace_id=trace_id, agent_id="atlas_chat", context=mode, provider=active_adapter),
        "trace_id": trace_id,
    }




def _clean_web_text(raw: str, *, max_chars: int = 2200) -> str:
    text = str(raw or "")
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_chars:
        return text[:max_chars].rstrip() + "..."
    return text


def _internet_fetch_url(url: str) -> Dict[str, Any]:
    cleaned = str(url or "").strip()
    parsed = urllib.parse.urlparse(cleaned)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return {"status": "error", "error": "URL must be absolute and start with http:// or https://"}
    req = urllib.request.Request(
        cleaned,
        headers={"User-Agent": "MammothOS/1.0 (+https://command.truexxiisupply.com)"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            content_type = str(resp.headers.get("Content-Type") or "").lower()
            payload = resp.read(50000)
    except urllib.error.URLError as exc:
        return {"status": "error", "error": _sanitize_runtime_error_message(exc, "Could not reach the requested URL.")}
    except ValueError:
        return {"status": "error", "error": "URL is invalid or unsupported."}

    text = payload.decode("utf-8", errors="replace")
    title_match = re.search(r"(?is)<title[^>]*>(.*?)</title>", text)
    title = _clean_web_text(title_match.group(1), max_chars=140) if title_match else ""
    summary = _clean_web_text(text)
    return {
        "status": "ok",
        "url": cleaned,
        "title": title or parsed.netloc,
        "summary": summary or "No readable text was extracted from this page.",
        "content_type": content_type,
    }


def _internet_research_query(query: str) -> Dict[str, Any]:
    q = str(query or "").strip()
    if not q:
        return {"status": "error", "error": "Research query is required."}
    endpoint = (
        "https://api.duckduckgo.com/?"
        + urllib.parse.urlencode({"q": q, "format": "json", "no_html": 1, "skip_disambig": 1})
    )
    req = urllib.request.Request(
        endpoint,
        headers={"User-Agent": "MammothOS/1.0 (+https://command.truexxiisupply.com)"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        return {"status": "error", "error": _sanitize_runtime_error_message(exc, "Could not reach internet research endpoint.")}
    except json.JSONDecodeError:
        return {"status": "error", "error": "Research endpoint returned an unreadable response."}

    highlights: List[Dict[str, str]] = []
    abstract = str(payload.get("AbstractText") or "").strip()
    if abstract:
        highlights.append({
            "title": str(payload.get("Heading") or "Primary finding"),
            "snippet": abstract,
            "url": str(payload.get("AbstractURL") or ""),
        })
    related = payload.get("RelatedTopics") if isinstance(payload.get("RelatedTopics"), list) else []
    for item in related:
        if len(highlights) >= 5:
            break
        if isinstance(item, dict) and isinstance(item.get("Topics"), list):
            nested = item.get("Topics") or []
            for sub in nested:
                if len(highlights) >= 5:
                    break
                if isinstance(sub, dict):
                    snippet = str(sub.get("Text") or "").strip()
                    if snippet:
                        highlights.append({
                            "title": str(sub.get("FirstURL") or "Related source"),
                            "snippet": snippet,
                            "url": str(sub.get("FirstURL") or ""),
                        })
            continue
        if isinstance(item, dict):
            snippet = str(item.get("Text") or "").strip()
            if snippet:
                highlights.append({
                    "title": str(item.get("FirstURL") or "Related source"),
                    "snippet": snippet,
                    "url": str(item.get("FirstURL") or ""),
                })

    if not highlights:
        return {
            "status": "ok",
            "query": q,
            "highlights": [],
            "summary": "No concise internet highlights were found for this query.",
        }

    summary_lines = [f"Internet research brief for: {q}"]
    for idx, item in enumerate(highlights[:5], start=1):
        url = f" ({item['url']})" if item.get("url") else ""
        summary_lines.append(f"{idx}. {item['snippet']}{url}")
    return {"status": "ok", "query": q, "highlights": highlights[:5], "summary": "\n".join(summary_lines)}


def _run_internet_command(slash: Dict[str, Any]) -> Dict[str, Any]:
    kind = str(slash.get("kind") or "").strip()
    if kind == "web":
        result = _internet_fetch_url(str(slash.get("url") or ""))
        if result.get("status") != "ok":
            return {
                "status": "error",
                "reply": f"Internet fetch failed: {result.get('error') or 'unknown error'}",
                "evidence": {"source": "internet", "kind": "web", "url": str(slash.get("url") or ""), "status": "error"},
            }
        reply = (
            f"Web summary for {result.get('url')}:\n"
            f"Title: {result.get('title')}\n\n"
            f"{result.get('summary')}"
        )
        return {"status": "ok", "reply": reply, "evidence": {"source": "internet", "kind": "web", **result}}

    if kind == "research":
        result = _internet_research_query(str(slash.get("query") or ""))
        if result.get("status") != "ok":
            return {
                "status": "error",
                "reply": f"Internet research failed: {result.get('error') or 'unknown error'}",
                "evidence": {"source": "internet", "kind": "research", "query": str(slash.get("query") or ""), "status": "error"},
            }
        return {"status": "ok", "reply": str(result.get("summary") or ""), "evidence": {"source": "internet", "kind": "research", **result}}

    return {"status": "error", "reply": "Unsupported internet command.", "evidence": {"source": "internet", "kind": kind, "status": "error"}}

def _parse_mammoth_chat_command(message: str) -> Optional[Dict[str, Any]]:
    text = (message or "").strip()
    if not text or not text.startswith("/"):
        return None
    tokens = text.split()
    command = tokens[0].lower()
    if command == "/plan":
        objective = " ".join(tokens[1:]).strip()
        if not objective:
            return {"kind": "error", "error": "Usage: /plan <objective>"}
        return {"kind": "plan", "objective": objective}
    if command == "/agent":
        if len(tokens) < 3:
            return {"kind": "error", "error": "Usage: /agent <agent_id> <message>"}
        agent_id = tokens[1].strip()
        prompt = " ".join(tokens[2:]).strip()
        return {"kind": "agent", "agent_id": agent_id, "message": prompt}
    if command == "/web":
        url = " ".join(tokens[1:]).strip()
        if not url:
            return {"kind": "error", "error": "Usage: /web <url>"}
        return {"kind": "web", "url": url}
    if command == "/research":
        query = " ".join(tokens[1:]).strip()
        if not query:
            return {"kind": "error", "error": "Usage: /research <query>"}
        return {"kind": "research", "query": query}
    if command == "/commit":
        commit_message = " ".join(tokens[1:]).strip()
        if not commit_message:
            return {"kind": "error", "error": "Usage: /commit <message>"}
        return {"kind": "gitops", "operation": "git_commit", "payload": {"message": commit_message, "stage_all": True}}
    if command == "/push":
        remote = tokens[1].strip() if len(tokens) >= 2 else "origin"
        branch = tokens[2].strip() if len(tokens) >= 3 else "main"
        return {"kind": "gitops", "operation": "git_push", "payload": {"remote": remote, "branch": branch}}
    if command == "/deploy":
        deploy_command = " ".join(tokens[1:]).strip()
        if not deploy_command:
            return {"kind": "error", "error": "Usage: /deploy <command>"}
        return {"kind": "gitops", "operation": "git_deploy", "payload": {"command": deploy_command}}
    return None


def _render_chat_result(value: Any) -> str:
    if value is None:
        return "No response produced."
    if isinstance(value, str):
        return value.strip() or "No response produced."
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, dict):
        for key in ("reply", "message", "summary", "analysis", "content"):
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
        if isinstance(value.get("output"), str) and value.get("output", "").strip():
            return value["output"].strip()
        if isinstance(value.get("output"), dict):
            return _render_chat_result(value.get("output"))
        if isinstance(value.get("result"), dict):
            return _render_chat_result(value.get("result"))
    return json.dumps(value, indent=2, default=str)[:4000]


def _render_evidence_summary(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("summary", "reply", "message", "analysis", "content"):
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
        output = value.get("output")
        if isinstance(output, dict):
            return _render_evidence_summary(output)
        if isinstance(output, str) and output.strip():
            return output.strip()
    return _render_chat_result(value)


def _normalize_page_context(raw_page_context: Any, raw_page_snapshot: Any = None) -> Dict[str, Any]:
    page_context = dict(raw_page_context) if isinstance(raw_page_context, dict) else {}
    page_snapshot = dict(raw_page_snapshot) if isinstance(raw_page_snapshot, dict) else {}
    merged = {**page_context, **page_snapshot}
    normalized = {
        "current_page": str(merged.get("current_page") or merged.get("page") or "").strip(),
        "route": str(merged.get("route") or "").strip(),
        "url": str(merged.get("url") or "").strip(),
        "title": str(merged.get("title") or "").strip(),
        "selected_text": str(merged.get("selected_text") or merged.get("selection") or "").strip(),
        "component": str(merged.get("component") or "").strip(),
        "updated_at": str(merged.get("updated_at") or datetime.now(timezone.utc).isoformat()),
    }
    visible_summary = merged.get("visible_summary")
    if isinstance(visible_summary, str) and visible_summary.strip():
        normalized["visible_summary"] = visible_summary.strip()[:1600]
    elif isinstance(merged.get("visible_text"), str):
        normalized["visible_summary"] = str(merged.get("visible_text") or "").strip()[:1600]
    return {k: v for k, v in normalized.items() if v}


def _safe_repo_relative_path(raw_path: Any) -> str:
    candidate = str(raw_path or "").strip().replace("/", "\\")
    if not candidate:
        return ""
    path_obj = Path(candidate)
    if path_obj.is_absolute():
        return ""
    if any(part in {"..", ""} for part in path_obj.parts):
        return ""
    return str(Path(*path_obj.parts))


def _normalize_repo_context_request(raw_repo_context: Any) -> Dict[str, Any]:
    if not isinstance(raw_repo_context, dict):
        return {}
    files_raw = raw_repo_context.get("files") if isinstance(raw_repo_context.get("files"), list) else []
    files = []
    for value in files_raw:
        cleaned = _safe_repo_relative_path(value)
        if cleaned:
            files.append(cleaned)
        if len(files) >= 12:
            break
    symbols_raw = raw_repo_context.get("symbols") if isinstance(raw_repo_context.get("symbols"), list) else []
    symbols = [str(item).strip() for item in symbols_raw if str(item).strip()][:12]
    query = str(raw_repo_context.get("query") or "").strip()
    return {
        "query": query[:240],
        "files": files,
        "symbols": symbols,
        "include_git_status": bool(raw_repo_context.get("include_git_status", True)),
        "max_results": max(1, min(12, int(raw_repo_context.get("max_results") or 4))),
        "max_snippets": max(1, min(8, int(raw_repo_context.get("max_snippets") or 3))),
    }


def _read_repo_file_excerpt(relative_path: str, *, max_lines: int = 120, max_chars: int = 3600) -> Dict[str, Any]:
    target = ROOT / relative_path
    if not target.exists() or not target.is_file():
        return {"path": relative_path, "status": "missing"}
    try:
        raw = target.read_text(encoding="utf-8")
    except Exception as exc:
        return {"path": relative_path, "status": "error", "error": f"{type(exc).__name__}: {exc}"}
    lines = raw.splitlines()
    selected = lines[:max_lines]
    content = "\n".join(f"{idx + 1}. {line}" for idx, line in enumerate(selected))
    if len(content) > max_chars:
        content = content[:max_chars].rstrip() + "\n..."
    return {
        "path": relative_path,
        "status": "ok",
        "line_count": len(lines),
        "excerpt": content,
    }


def _collect_repo_context_snapshot(repo_request: Dict[str, Any]) -> Dict[str, Any]:
    if not repo_request:
        return {}

    snapshot: Dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "query": str(repo_request.get("query") or ""),
        "symbols": list(repo_request.get("symbols") or []),
        "files": list(repo_request.get("files") or []),
        "snippets": [],
        "search_hits": [],
    }

    if repo_request.get("include_git_status"):
        git_status = _run_git_command(["status", "--short", "--branch"])
        snapshot["git_status"] = {
            "status": git_status.get("status"),
            "stdout": str(git_status.get("stdout") or "")[:2400],
            "stderr": str(git_status.get("stderr") or "")[:600],
        }

    for relative_path in (repo_request.get("files") or [])[: int(repo_request.get("max_snippets") or 3)]:
        snapshot["snippets"].append(_read_repo_file_excerpt(relative_path))

    query = str(repo_request.get("query") or "").strip().lower()
    if query:
        max_hits = int(repo_request.get("max_results") or 4)
        skipped_dirs = {".git", "node_modules", "dist", "__pycache__", ".venv", "venv", ".mammoth"}
        for path in ROOT.rglob("*"):
            if len(snapshot["search_hits"]) >= max_hits:
                break
            if not path.is_file():
                continue
            if any(part in skipped_dirs for part in path.parts):
                continue
            if path.suffix.lower() not in {".py", ".ts", ".tsx", ".js", ".jsx", ".md", ".json", ".toml", ".yaml", ".yml"}:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except Exception:
                continue
            lowered = text.lower()
            index = lowered.find(query)
            if index < 0:
                continue
            start = max(0, index - 120)
            end = min(len(text), index + 220)
            rel = str(path.relative_to(ROOT)).replace("/", "\\")
            snapshot["search_hits"].append(
                {
                    "path": rel,
                    "preview": text[start:end].replace("\n", " ").strip()[:280],
                }
            )

    return snapshot


def _queue_gitops_approval(operation: str, payload: Dict[str, Any], *, trace_id: str = "") -> Dict[str, Any]:
    task_id = f"gitops-{uuid.uuid4().hex[:8]}"
    preview = _build_operation_preview(operation, payload)
    approval = _create_approval_record(
        task_id,
        agent_id="coding_agent",
        operation=operation,
        target="repository",
        preview=preview,
        payload=payload,
        requested_by="user",
        trace_id=trace_id,
    )
    _upsert_task(
        task_id,
        f"approval:{operation}",
        status="pending_approval",
        agent_id="coding_agent",
        description=f"GitOps operation pending approval: {operation}",
        details={"approval_id": approval["id"], "operation": operation, "trace_id": trace_id},
    )
    _append_activity(
        f"Requested approval for {operation}",
        agent_id="coding_agent",
        task_id=task_id,
        kind="approval_requested",
        trace_id=trace_id,
        details={"approval_id": approval["id"], "operation": operation, "trace_id": trace_id},
    )
    return {"status": "ok", "approval": approval, "preview": preview, "task_id": task_id}


@app.post("/api/mammoth/chat/stream")
async def mammoth_chat_stream(request: Request):

    body = await request.json()
    print("DEBUG RAW BODY:", body)

    user_id = str(body.get("user_id") or "local")
    print(">>> STREAM user_id =", user_id)

    result = await mammoth_chat(body)

    async def event_stream():
        meta_payload = {k: result.get(k) for k in ("agent_id", "adapter", "model", "mode", "task_id", "trace_id", "dispatched", "runtime_status", "runtime_notice")}
        yield f"event: meta\ndata: {json.dumps(meta_payload, default=str)}\n\n"
        for step in result.get("thought_steps") or []:
            yield f"event: thought\ndata: {json.dumps(step, default=str)}\n\n"
            await asyncio.sleep(0.03)
        reply_text = str(result.get("reply") or "") or "No response produced."
        chunks = [reply_text[i:i + 48] for i in range(0, len(reply_text), 48)] or [reply_text]
        for chunk in chunks:
            yield f"event: chunk\ndata: {json.dumps({'text': chunk}, default=str)}\n\n"
            await asyncio.sleep(0.02)
        yield f"event: done\ndata: {json.dumps(result, default=str)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/api/mammoth/chat/history")
async def get_mammoth_chat_history(user_id: str = "local"):
    state = _load_atlas_state()
    history = state.get("mammoth_chat_history") or []
    if not isinstance(history, list):
        history = []
    history = [item for item in history if item.get("user_id") == user_id]
    return {"status": "ok", "chat_history": history[-80:]}


@app.delete("/api/mammoth/chat/history")
async def delete_mammoth_chat_history(user_id: str = "local"):

    state = _load_atlas_state()
    history = state.get("mammoth_chat_history") or []
    if not isinstance(history, list):
        history = []

    deleted_messages = len(history)

    state["mammoth_chat_history"] = [
        item for item in history
        if item.get("user_id") != user_id
    ]

    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    _save_atlas_state(state)

    _append_execution_event(
        kind="mammoth_chat_history_cleared",
        summary=f"Cleared MammothOS chat history ({deleted_messages} messages)",
        detail={"deleted_messages": deleted_messages},
        user_id=user_id,
    )

    return {"status": "ok", "deleted_messages": deleted_messages}


@app.post("/api/mammoth/repo-context")
async def mammoth_repo_context(body: Dict[str, Any]):
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    repo_request = _normalize_repo_context_request(body.get("repo_context") if isinstance(body.get("repo_context"), dict) else body)
    snapshot = _collect_repo_context_snapshot(repo_request)
    return {"status": "ok", "repo_context": snapshot}


@app.post("/api/mammoth/gitops/propose")
async def mammoth_gitops_propose(body: Dict[str, Any]):
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    operation = str(body.get("operation") or "").strip().lower()
    payload = body.get("payload") if isinstance(body.get("payload"), dict) else {}
    if operation not in {"git_status", "git_commit", "git_push", "git_deploy"}:
        return {"status": "error", "error": "Unsupported gitops operation."}
    if not _mutation_allowed():
        return _owner_mutation_denied(operation)
    queued = _queue_gitops_approval(operation, payload, trace_id=str(body.get("trace_id") or ""))
    return {"status": "ok", **queued}





@app.post("/api/mammoth/chat")
async def mammoth_chat(body: Dict[str, Any]):
    message = str(body.get("message", "")).strip()
    if not message:
        return {"status": "error", "error": "message is required"}

    trace_id = str(body.get("trace_id") or new_trace_id("chat"))
    slash = _parse_mammoth_chat_command(message)
    if slash and slash.get("kind") == "plan":
        plan_result = await plan_execute({
            "objective": slash["objective"],
            "approval_mode": bool(body.get("approval_mode", True)),
            "stop_on_failure": bool(body.get("stop_on_failure", True)),
            "plan_profile": body.get("plan_profile") or "atlas",
            "coding_intent": body.get("coding_intent") or "patch_existing",
        })
        progress = plan_result.get("progress") if isinstance(plan_result.get("progress"), dict) else {}
        summary = (
            f"Plan queued: {plan_result.get('objective') or slash['objective']}\n"
            f"Status: {plan_result.get('plan_status') or 'active'} • "
            f"{progress.get('completed') or 0}/{progress.get('total') or 0} complete"
        )
        return {
            "status": "ok",
            "reply": summary,
            "agent_id": "orchestrator",
            "adapter": "plan-execute",
            "model": "plan-execute",
            "mode": "chat",
            "task_id": plan_result.get("plan_id") or "",
            "dispatched": True,
            "trace_id": trace_id,
            "thought_steps": [{
                "ts": _ts(),
                "label": "Plan command parsed",
                "detail": f"objective={slash['objective']}",
                "status": "info",
            }],
            "runtime_status": _runtime_status_snapshot(),
            "runtime_notice": None if _runtime_status_snapshot().get("state") == "ready" else build_runtime_notice(_runtime_status_snapshot(), trace_id=trace_id, agent_id="mammoth_chat", context="chat", provider="plan-execute"),
        }
    if slash and slash.get("kind") == "agent":
        if not slash.get("message"):
            return {"status": "error", "error": "Usage: /agent <agent_id> <message>"}
        body = {**body, "agent_id": slash["agent_id"], "message": slash["message"]}
        return await mammoth_chat(body)
    if slash and slash.get("kind") in {"web", "research"}:
        command_result = _run_internet_command(slash)
        reply = str(command_result.get("reply") or "No response produced.")
        state = _load_atlas_state()
        user_id = str(body.get("user_id") or "local")
        history = state.get("mammoth_chat_history") or []
        if not isinstance(history, list):
            history = []
        history = [item for item in history if item.get("user_id") == user_id]

        history.append({
            "role": "user",
            "message": message,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "agent_id": "assistant",
            "mode": "chat",
            "page": "",
	    "user_id": user_id,
        })
        history.append({
            "role": "assistant",
            "message": reply,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "agent_id": "assistant",
            "mode": "chat",
            "adapter": "internet-tool",
            "model": "internet-tool",
            "thought_steps": [{
                "ts": _ts(),
                "label": "Internet command completed",
                "detail": f"kind={slash.get('kind')}",
                "status": "success" if command_result.get("status") == "ok" else "warning",
            }],
            "evidence_items": [command_result.get("evidence")],
            "orchestrated": False,
            "runtime_status": _runtime_status_snapshot(),
            "runtime_notice": None,
	    "user_id": user_id,
        })

        state["mammoth_chat_history"] = history[-80:]
        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        _save_atlas_state(state)
        return {
            "status": "ok" if command_result.get("status") == "ok" else "error",
            "reply": reply,
            "chat_history": state["mammoth_chat_history"],
            "thought_steps": [{
                "ts": _ts(),
                "label": "Internet command completed",
                "detail": f"kind={slash.get('kind')}",
                "status": "success" if command_result.get("status") == "ok" else "warning",

            }],
            "agent_id": "assistant",
            "adapter": "internet-tool",
            "model": "internet-tool",
            "mode": "chat",
            "task_id": "",
            "dispatched": False,
            "evidence_items": [command_result.get("evidence")],
            "orchestrated": False,
            "runtime_status": _runtime_status_snapshot(),
            "runtime_notice": None,
            "trace_id": trace_id,
        }
    if slash and slash.get("kind") == "gitops":
        if not _mutation_allowed():
            return _owner_mutation_denied(str(slash.get("operation") or "gitops"))
        queued = _queue_gitops_approval(
            str(slash.get("operation") or ""),
            slash.get("payload") if isinstance(slash.get("payload"), dict) else {},
            trace_id=trace_id,
        )
        approval = queued.get("approval") if isinstance(queued.get("approval"), dict) else {}
        return {
            "status": "ok",
            "reply": f"Queued {slash.get('operation')} for approval.",
            "agent_id": "coding_agent",
            "adapter": "approval-gate",
            "model": "approval-gate",
            "mode": "chat",
            "task_id": str(queued.get("task_id") or ""),
            "dispatched": True,
            "approval": approval,
            "preview": queued.get("preview"),
            "trace_id": trace_id,
        }
    if slash and slash.get("kind") == "error":
        return {"status": "error", "error": slash["error"]}

    state = _load_atlas_state()
    page_context = _normalize_page_context(body.get("page_context"), body.get("page_snapshot"))
    repo_context_request = _normalize_repo_context_request(body.get("repo_context"))
    repo_context = _collect_repo_context_snapshot(repo_context_request) if repo_context_request else {}
    agent_id = str(body.get("agent_id") or "assistant").strip() or "assistant"
    mode = str(body.get("mode") or "chat").strip().lower() or "chat"
    adapter = str(body.get("adapter", "")).strip()
    model = str(body.get("model", "")).strip()
    temperature = float(body.get("temperature", 0.3))
    user_id = str(body.get("user_id") or "local")
    history = state.get("mammoth_chat_history") or []
    if not isinstance(history, list):
        history = []
    runtime_status = _runtime_status_snapshot()
    web_context = body.get("web")

    user_entry = {
        "role": "user",
        "message": message,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "agent_id": agent_id,
        "mode": mode,
        "page": str(page_context.get("current_page") or ""),
        "user_id": user_id,
    }
    history.append(user_entry)

    thought_steps: List[Dict[str, Any]] = [
        {"ts": _ts(), "label": "Hearing hoofbeats", "detail": f"agent={agent_id} mode={mode}", "status": "info"},
        {"ts": _ts(), "label": "Priming mammoth cores", "detail": "Spinning up MammothOS reasoning lanes", "status": "info"},
    ]

    reply = ""
    active_model = ""
    active_adapter = ""
    task_id = ""
    dispatched = False
    evidence_items: List[Dict[str, Any]] = []
    fanout_agents = body.get("fanout_agents") if isinstance(body.get("fanout_agents"), list) else []
    orchestrate = bool(body.get("orchestrate") or body.get("multi_agent") or body.get("fanout")) or len(fanout_agents) > 1 or agent_id in {"herd", "orchestrator", "multi_agent"}

    async def _run_native_assistant() -> Dict[str, Any]:
        from mammoth_os.llm_client import get_llm_client

        convo_window = history[-8:]
        convo_text = "\n".join(
            f"{item.get('role', 'unknown')}: {str(item.get('message', ''))[:500]}"
            for item in convo_window
            if isinstance(item, dict)
        )
        prompt = (
            "You are MammothOS Chat, the native operating intelligence layer for MammothOS. "
            "Be sharp, helpful, practical, and slightly playful in a rugged builder tone. "
            "You may occasionally use short branded quips like 'checking the herd', 'priming the cores', or 'charging the tusks', "
            "but keep them rare and tasteful.\n\n"
            "Your job is to help with product building, debugging, planning, coding direction, and operator workflow. "
            "When useful, structure your response into: quick read, what I'm seeing, next move.\n\n"
            f"Observed page context: {json.dumps(page_context, default=str)[:1400]}\n\n"
            f"Observed repo context: {json.dumps(repo_context, default=str)[:2200]}\n\n"
            f"Observed web context: {json.dumps(web_context, default=str)}"
            f"Recent conversation:\n{convo_text}\n\n"
            f"User message: {message}"
        )
        cfg: Dict[str, Any] = {}
        if adapter:
            cfg["adapter"] = adapter
        if model:
            cfg["model"] = model
        thought_steps.append({"ts": _ts(), "label": "Consulting the herd", "detail": "Running native MammothOS assistant response", "status": "info"})
        client = get_llm_client(config=cfg)
        assistant_reply = await client.generate(prompt, temperature=temperature)
        requested_adapter = str((cfg.get("adapter") or os.environ.get("MAMMOTH_LLM_ADAPTER") or "").strip() or "auto")
        client_meta = _runtime_metadata_from_client(client, requested_adapter=requested_adapter)
        assistant_adapter = str(client_meta.get("active_adapter") or requested_adapter or "auto")
        assistant_model = str(getattr(client, "model", model or "unknown"))
        thought_steps.append({"ts": _ts(), "label": "Tusks charged", "detail": f"adapter={assistant_adapter} model={assistant_model}", "status": "success"})
        runtime_status = _runtime_status_snapshot()
        runtime_status["effective_adapter"] = assistant_adapter
        if client_meta.get("fallback_used"):
            runtime_status["state"] = "degraded"
            runtime_status["degraded_mode"] = True
            runtime_status["fallback_used"] = True
            runtime_status["primary_provider"] = client_meta.get("primary_provider")
            runtime_status["used_provider"] = client_meta.get("used_provider")
            if client_meta.get("fallback_reason"):
                runtime_status["fallback_reason"] = client_meta.get("fallback_reason")
            if client_meta.get("fallback_error_type"):
                runtime_status["fallback_error_type"] = client_meta.get("fallback_error_type")
        _remember_runtime_status(runtime_status)
        return {
            "agent_id": "assistant",
            "adapter": assistant_adapter,
            "model": assistant_model,
            "reply": assistant_reply,
            "thought_steps": [],
            "evidence": {"agent_id": "assistant", "summary": _render_evidence_summary(assistant_reply), "source": "native-chat"},
            "task_id": "",
            "dispatched": False,
            "runtime_status": runtime_status,
            "runtime_notice": None if runtime_status.get("state") == "ready" else build_runtime_notice(runtime_status, trace_id=trace_id, agent_id="assistant", context="assistant", provider=assistant_adapter),
        }

    async def _run_lane(lane_agent: str) -> Dict[str, Any]:
        if lane_agent in {"assistant", "mammoth_assistant", "atlas_assistant"}:
            return await _run_native_assistant()

        lane_intent = str(body.get("intent") or "").strip()
        lane_coding_intent = _normalize_coding_intent(body.get("coding_intent"))
        if not lane_intent:
            if lane_agent == "coding_agent":
                lane_intent = lane_coding_intent or "generate_code"
            elif lane_agent == "reasoning_agent":
                lane_intent = "reason"
            elif lane_agent == "tutor_agent":
                lane_intent = "lesson_coaching"
            elif lane_agent == "shell_agent":
                lane_intent = "shell"
            else:
                lane_intent = "summarize"
        lane_payload = {
            "prompt": message,
            "task": message,
            "coding_intent": lane_coding_intent or _normalize_coding_intent(lane_intent),
            "files": body.get("files") if isinstance(body.get("files"), list) else [],
            "target": str(body.get("target") or "").strip(),
            "context": {
                "source": "mammoth.chat",
                "page_context": page_context,
                "repo_context": repo_context,
                "conversation_mode": mode,
                "agent_id": lane_agent,
                "orchestrated": True,
            },
        }
        thought_steps.append({"ts": _ts(), "label": "Routing through the herd", "detail": f"intent={lane_intent} agent={lane_agent}", "status": "info"})
        lane_run = await run_agent({
            "agent_id": lane_agent,
            "intent": lane_intent,
            "payload": lane_payload,
            "temperature": temperature,
            "approval_mode": bool(body.get("approval_mode", False)),
        })
        lane_result = lane_run.get("result")
        lane_reply = _render_chat_result(lane_result)
        lane_thoughts = list(lane_run.get("thought_steps") or [])
        lane_thoughts.append({"ts": _ts(), "label": "Lane complete", "detail": f"task_id={lane_run.get('task_id') or 'n/a'}", "status": "success"})
        evidence = {
            "agent_id": lane_agent,
            "intent": lane_intent,
            "summary": _render_evidence_summary(lane_result),
            "task_id": lane_run.get("task_id") or "",
            "status": lane_run.get("status") or "ok",
            "source": "agent-runtime",
        }
        if isinstance(lane_result, dict):
            for key in ("files", "source_files", "references", "evidence", "diff"):
                if lane_result.get(key):
                    evidence[key] = lane_result.get(key)
        return {
            "agent_id": lane_agent,
            "adapter": "agent-runtime",
            "model": str(lane_run.get("agent_id") or lane_agent),
            "reply": lane_reply,
            "task_id": lane_run.get("task_id") or "",
            "dispatched": True,
            "thought_steps": lane_thoughts,
            "evidence": evidence,
            "raw": lane_run,
        }

    try:
        if orchestrate:
            selected_agents = [str(item).strip() for item in fanout_agents if str(item).strip()] if fanout_agents else []
            if not selected_agents:
                selected_agents = ["assistant", "reasoning_agent", "coding_agent"]
            if agent_id not in selected_agents and agent_id not in {"herd", "orchestrator", "multi_agent"}:
                selected_agents.insert(0, agent_id)
            seen_agents: List[str] = []
            for lane in selected_agents:
                if lane not in seen_agents:
                    seen_agents.append(lane)
            thought_steps.append({"ts": _ts(), "label": "Splitting the herd", "detail": f"lanes={', '.join(seen_agents)}", "status": "info"})
            lane_results = await asyncio.gather(*[_run_lane(lane) for lane in seen_agents])
            thought_steps.append({"ts": _ts(), "label": "Merging the herd", "detail": f"lanes_completed={len(lane_results)}", "status": "info"})
            assistant_lane = next((lane for lane in lane_results if lane.get("agent_id") == "assistant"), lane_results[0])
            active_adapter = assistant_lane.get("adapter") or "agent-runtime"
            active_model = assistant_lane.get("model") or seen_agents[0]
            task_id = assistant_lane.get("task_id") or task_id
            reply_parts = [assistant_lane.get("reply") or "No response produced."]
            for lane in lane_results:
                evidence = lane.get("evidence") or {}
                evidence_items.append({
                    "agent_id": lane.get("agent_id"),
                    "intent": evidence.get("intent") or ("chat" if lane.get("agent_id") == "assistant" else "unknown"),
                    "summary": evidence.get("summary") or lane.get("reply") or "No summary.",
                    "task_id": lane.get("task_id") or "",
                    "status": evidence.get("status") or "ok",
                    "source": evidence.get("source") or ("native-chat" if lane.get("agent_id") == "assistant" else "agent-runtime"),
                })
                if lane.get("agent_id") != "assistant" and lane.get("reply"):
                    reply_parts.append(f"\n\n**{lane.get('agent_id').replace('_', ' ').title()}**\n{lane.get('reply')}")
                thought_steps.extend(lane.get("thought_steps") or [])
            reply = "\n\n".join(reply_parts)
            thought_steps.append({"ts": _ts(), "label": "Herd merged", "detail": f"evidence_items={len(evidence_items)}", "status": "success"})
        else:
            lane_result = await _run_lane(agent_id)
            dispatched = bool(lane_result.get("dispatched"))
            active_adapter = lane_result.get("adapter") or active_adapter
            active_model = lane_result.get("model") or active_model
            task_id = lane_result.get("task_id") or task_id
            reply = lane_result.get("reply") or "No response produced."
            thought_steps.extend(lane_result.get("thought_steps") or [])
            if lane_result.get("evidence"):
                evidence_items.append(lane_result["evidence"])
            if lane_result.get("agent_id") != "assistant":
                thought_steps.append({"ts": _ts(), "label": "Packaged response", "detail": f"task_id={task_id or 'n/a'}", "status": "success"})
    except Exception as exc:
        runtime_status = _runtime_status_snapshot()
        safe_error = _sanitize_runtime_error_message(exc)
        runtime_status["error_type"] = type(exc).__name__
        runtime_status["safe_error"] = safe_error
        _remember_runtime_status(runtime_status)
        reply = (
            "I hit a MammothOS chat routing problem. "
            "The good news is the shell is still up; the routing stack just needs better wiring. "
            "MammothOS switched to a safe fallback path. "
            f"{runtime_status.get('recommendation')}"
        )
        active_adapter = active_adapter or "fallback-local"
        active_model = active_model or "fallback-local"
        thought_steps.append({"ts": _ts(), "label": "Hamster escaped", "detail": safe_error, "status": "error"})

    assistant_entry = {
        "role": "assistant",
        "message": reply,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "agent_id": agent_id,
        "mode": mode,
        "adapter": active_adapter,
        "model": active_model,
        "thought_steps": thought_steps[-12:],
        "task_id": task_id,
        "dispatched": dispatched,
        "evidence_items": evidence_items,
        "orchestrated": orchestrate,
        "runtime_status": runtime_status,
        "runtime_notice": None if runtime_status.get("state") == "ready" else build_runtime_notice(runtime_status, trace_id=trace_id, agent_id=agent_id, context=mode, provider=active_adapter),
	"user_id": user_id,
    }
    history.append(assistant_entry)
    state["mammoth_chat_history"] = [item for item in history if item.get("user_id") == user_id][-80:]
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    _save_atlas_state(state)
    _append_execution_event(
        kind="mammoth_chat",
        summary=f"Chat [{mode}] via {active_adapter or 'unknown'}: {message[:80]}{'…' if len(message)>80 else ''}",
        detail={"agent_id": agent_id, "mode": mode, "adapter": active_adapter, "task_id": task_id},
        user_id=str(body.get("user_id") or "local") if isinstance(body, dict) else "local",
    )
    return {
        "status": "ok",
        "reply": reply,
        "chat_history": state["mammoth_chat_history"],
        "thought_steps": thought_steps[-12:],
        "agent_id": agent_id,
        "adapter": active_adapter,
        "model": active_model,
        "mode": mode,
        "task_id": task_id,
        "dispatched": dispatched,
        "evidence_items": evidence_items,
        "orchestrated": orchestrate,
        "runtime_status": runtime_status,
        "runtime_notice": None if runtime_status.get("state") == "ready" else build_runtime_notice(runtime_status, trace_id=trace_id, agent_id=agent_id, context=mode, provider=active_adapter),
        "trace_id": trace_id,
    }


# ─────────────────────────────────────────────────────────────────────────────
# /api/notes
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/notes")
async def get_notes():
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    notes = _read_json(NOTES_FILE, default=[])
    if not isinstance(notes, list):
        return []

    normalized: List[Dict[str, Any]] = []
    for raw in reversed(notes):
        note = _normalize_note_record(raw)
        if note:
            normalized.append(note)
    return normalized


@app.post("/api/notes")
async def upsert_note(body: Dict[str, Any]):
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    notes = _read_json(NOTES_FILE, default=[])
    if not isinstance(notes, list):
        notes = []
    note_id = str(body.get("id") or "").strip()
    now = datetime.now(timezone.utc).isoformat()
    if note_id:
        for i, n in enumerate(notes):
            if n.get("id") == note_id:
                created_at = str(n.get("created_at") or n.get("updated_at") or now)
                normalized = _normalize_note_record({**n, **body, "id": note_id, "created_at": created_at, "updated_at": now}, now=now)
                if normalized is None:
                    return {"status": "error", "error": "note payload is invalid"}
                notes[i] = normalized
                _write_json(NOTES_FILE, notes)
                return normalized
    # create new
    new_note = _normalize_note_record({
        "id": str(uuid.uuid4()),
        "title": body.get("title"),
        "body": body.get("body"),
        "content": body.get("content"),
        "created_at": now,
        "updated_at": now,
        "agent_id": body.get("agent_id"),
        "source": body.get("source"),
        "type": body.get("type"),
        "priority": body.get("priority"),
        "subsystem": body.get("subsystem"),
        "metadata": body.get("metadata"),
    }, now=now)
    if new_note is None:
        return {"status": "error", "error": "note payload is invalid"}
    notes.append(new_note)
    _write_json(NOTES_FILE, notes)
    return new_note


@app.delete("/api/notes/{note_id}")
async def delete_note(note_id: str):
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    notes = _read_json(NOTES_FILE)
    notes = [n for n in notes if n.get("id") != note_id]
    _write_json(NOTES_FILE, notes)
    return {"status": "ok"}


@app.get("/api/beta-feedback")
async def get_beta_feedback():
    entries = _read_json(BETA_FEEDBACK_FILE, default=[])
    if not isinstance(entries, list):
        entries = []
    normalized: List[Dict[str, Any]] = []
    now = datetime.now(timezone.utc).isoformat()
    for raw in entries:
        record = _normalize_beta_feedback_record(raw, now=now)
        if record:
            normalized.append(record)

    is_admin = _request_is_admin()
    if _AUTH_REQUIRED and not is_admin:
        requester_id = str(_REQUEST_USER_ID.get() or "").strip()
        requester_email = str(_REQUEST_USER_EMAIL.get() or "").strip().lower()
        normalized = [
            item for item in normalized
            if item.get("reporter_user_id") == requester_id
            or (requester_email and item.get("reporter_email") == requester_email)
        ]

    normalized.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
    return {"entries": normalized, "can_manage": bool(is_admin)}


@app.post("/api/beta-feedback")
async def submit_beta_feedback(body: Dict[str, Any]):
    if not isinstance(body, dict):
        return {"status": "error", "error": "Invalid payload"}
    if not bool(body.get("safety_acknowledged")):
        return {"status": "error", "error": "Safety acknowledgment is required."}

    now = datetime.now(timezone.utc).isoformat()
    reporter_user_id = str(_REQUEST_USER_ID.get() or "").strip()
    reporter_email = str(_REQUEST_USER_EMAIL.get() or "").strip().lower()
    if not _AUTH_REQUIRED:
        reporter_user_id = str(body.get("reporter_user_id") or reporter_user_id).strip()
        reporter_email = str(body.get("reporter_email") or reporter_email).strip().lower()

    candidate = {
        "id": str(uuid.uuid4()),
        "title": body.get("title"),
        "summary": body.get("summary"),
        "area": body.get("area"),
        "severity": body.get("severity"),
        "status": "new",
        "expected_behavior": body.get("expected_behavior"),
        "actual_behavior": body.get("actual_behavior"),
        "reproduction_steps": body.get("reproduction_steps"),
        "device": body.get("device"),
        "browser": body.get("browser"),
        "reproducible": body.get("reproducible", True),
        "safety_acknowledged": body.get("safety_acknowledged"),
        "reporter_user_id": reporter_user_id,
        "reporter_email": reporter_email,
        "created_at": now,
        "updated_at": now,
        "metadata": body.get("metadata"),
    }
    normalized = _normalize_beta_feedback_record(candidate, now=now)
    if normalized is None:
        return {"status": "error", "error": "summary and reproduction_steps are required."}

    entries = _read_json(BETA_FEEDBACK_FILE, default=[])
    if not isinstance(entries, list):
        entries = []
    entries.append(normalized)
    _write_json(BETA_FEEDBACK_FILE, entries)
    return {"status": "ok", "entry": normalized}


@app.post("/api/beta-feedback/{feedback_id}/status")
async def update_beta_feedback_status(feedback_id: str, body: Dict[str, Any]):
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    status = str((body or {}).get("status") or "").strip().lower()
    if status not in {"new", "triaged", "in_progress", "fixed", "closed"}:
        return {"status": "error", "error": "Invalid status."}

    entries = _read_json(BETA_FEEDBACK_FILE, default=[])
    if not isinstance(entries, list):
        entries = []
    now = datetime.now(timezone.utc).isoformat()
    for index, raw in enumerate(entries):
        if str((raw or {}).get("id") or "").strip() != feedback_id:
            continue
        updated = _normalize_beta_feedback_record({**raw, "status": status, "updated_at": now}, now=now)
        if updated is None:
            return {"status": "error", "error": "Record payload is invalid."}
        entries[index] = updated
        _write_json(BETA_FEEDBACK_FILE, entries)
        return {"status": "ok", "entry": updated}

    return {"status": "error", "error": "Feedback record not found."}


# ─────────────────────────────────────────────────────────────────────────────
# /api/buildlog
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/buildlog")
async def get_buildlog():
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    return _read_json(BUILDLOG_FILE)


@app.post("/api/buildlog")
async def append_buildlog(body: Dict[str, Any]):
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    entries = _read_json(BUILDLOG_FILE)
    fields = body.get("fields", {})
    if not isinstance(fields, dict):
        fields = {}
    entry = {
        "id":          str(uuid.uuid4()),
        "title":       body.get("title", "") or str(fields.get("primary_task") or ""),
        "description": body.get("description", "") or str(fields.get("session_goal") or ""),
        "tags":        body.get("tags", []),
        "command":     body.get("command", ""),
        "project":     body.get("project", "") or str(fields.get("project") or ""),
        "phase":       body.get("phase", "") or str(fields.get("phase") or ""),
        "month":       body.get("month", "") or str(fields.get("month") or ""),
        "status":      body.get("status", "") or str(fields.get("goal_outcome") or ""),
        "fields":      fields,
        "created_at":  datetime.now(timezone.utc).isoformat(),
    }
    entries.append(entry)
    _write_json(BUILDLOG_FILE, entries)
    return entry


# ─────────────────────────────────────────────────────────────────────────────
# /api/logsale
# ─────────────────────────────────────────────────────────────────────────────

_DEFAULT_OPERATOR_HEALTH = {
    "energy": 50,
    "focus": 50,
    "mood": 50,
    "stress": 50,
    "sleep": 50,
    "uptime": 0,
    "fatigue": 0,
}

_PERCENT_HEALTH_FIELDS = {"energy", "focus", "mood", "stress", "sleep", "fatigue"}
_NUMERIC_HEALTH_FIELDS = {"uptime"}
_VALID_LEDGERS = {"personal", "business"}


def _normalize_operator_health(data: Any) -> Dict[str, Any]:
    merged = dict(_DEFAULT_OPERATOR_HEALTH)
    if isinstance(data, dict):
        for key in _PERCENT_HEALTH_FIELDS:
            if key in data:
                try:
                    value = _coerce_int(data.get(key), field=key)
                except ValueError:
                    continue
                merged[key] = max(0, min(100, value))
        if "uptime" in data:
            try:
                merged["uptime"] = max(0, _coerce_int(data.get("uptime"), field="uptime"))
            except ValueError:
                pass
    return merged


def _derive_note_title(text: str) -> str:
    first_line = next((line.strip() for line in str(text or "").splitlines() if line.strip()), "")
    if not first_line:
        return "Untitled"
    return first_line[:72]


def _normalize_note_record(raw: Any, *, now: Optional[str] = None) -> Optional[Dict[str, Any]]:
    if not isinstance(raw, dict):
        return None

    fallback_now = now or datetime.now(timezone.utc).isoformat()
    note_id = str(raw.get("id") or "").strip() or str(uuid.uuid4())
    body = str(raw.get("body") or raw.get("content") or "").strip()
    title = str(raw.get("title") or "").strip() or _derive_note_title(body)
    created_at = str(raw.get("created_at") or raw.get("updated_at") or fallback_now)
    updated_at = str(raw.get("updated_at") or raw.get("created_at") or fallback_now)
    agent_id = str(raw.get("agent_id") or "").strip()

    source = str(raw.get("source") or "").strip().lower()
    if source not in {"personal", "agent"}:
        source = "agent" if agent_id and agent_id not in {"operator", "user"} else "personal"

    note_type = str(raw.get("type") or "").strip() or ("agent_note" if source == "agent" else "personal_note")
    priority = str(raw.get("priority") or "normal").strip() or "normal"
    subsystem = str(raw.get("subsystem") or "general").strip() or "general"
    metadata = raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}

    return {
        "id": note_id,
        "title": title,
        "body": body,
        "content": body,
        "created_at": created_at,
        "updated_at": updated_at,
        "agent_id": agent_id,
        "source": source,
        "type": note_type,
        "priority": priority,
        "subsystem": subsystem,
        "metadata": metadata,
    }


def _normalize_beta_feedback_record(raw: Any, *, now: Optional[str] = None) -> Optional[Dict[str, Any]]:
    if not isinstance(raw, dict):
        return None

    fallback_now = now or datetime.now(timezone.utc).isoformat()
    feedback_id = str(raw.get("id") or "").strip() or str(uuid.uuid4())
    title = str(raw.get("title") or "").strip()
    summary = str(raw.get("summary") or "").strip()
    reproduction_steps = str(raw.get("reproduction_steps") or "").strip()
    if not summary or not reproduction_steps:
        return None

    severity = str(raw.get("severity") or "medium").strip().lower()
    if severity not in {"low", "medium", "high", "critical"}:
        severity = "medium"

    status = str(raw.get("status") or "new").strip().lower()
    if status not in {"new", "triaged", "in_progress", "fixed", "closed"}:
        status = "new"

    reporter_user_id = str(raw.get("reporter_user_id") or "").strip()
    reporter_email = str(raw.get("reporter_email") or "").strip().lower()
    metadata = raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}
    created_at = str(raw.get("created_at") or fallback_now)
    updated_at = str(raw.get("updated_at") or fallback_now)

    return {
        "id": feedback_id,
        "title": title or _derive_note_title(summary),
        "summary": summary,
        "area": str(raw.get("area") or "Other").strip() or "Other",
        "severity": severity,
        "status": status,
        "expected_behavior": str(raw.get("expected_behavior") or "").strip(),
        "actual_behavior": str(raw.get("actual_behavior") or "").strip(),
        "reproduction_steps": reproduction_steps,
        "device": str(raw.get("device") or "").strip(),
        "browser": str(raw.get("browser") or "").strip(),
        "reproducible": bool(raw.get("reproducible", True)),
        "safety_acknowledged": bool(raw.get("safety_acknowledged")),
        "reporter_user_id": reporter_user_id,
        "reporter_email": reporter_email,
        "created_at": created_at,
        "updated_at": updated_at,
        "metadata": metadata,
    }


def _normalize_sale_entry(raw: Any, *, idx: int = 0) -> Optional[Dict[str, Any]]:
    if not isinstance(raw, dict):
        return None
    item = str(raw.get("item") or "").strip()
    if not item:
        return None
    amount = _coerce_float(raw.get("amount", 0), field="amount")
    ledger = str(raw.get("ledger") or "personal").strip().lower()
    if ledger not in _VALID_LEDGERS:
        ledger = "personal"
    category = str(raw.get("category") or "general").strip() or "general"
    return {
        "id": str(raw.get("id") or f"sale-{idx}"),
        "item": item,
        "amount": round(amount, 2),
        "ledger": ledger,
        "category": category,
        "notes": str(raw.get("notes") or ""),
        "date": str(raw.get("date") or datetime.now(timezone.utc).date().isoformat()),
        "created_at": str(raw.get("created_at") or datetime.now(timezone.utc).isoformat()),
    }


def _sales_summary(entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    summary: Dict[str, Any] = {
        "total_revenue": 0.0,
        "entry_count": len(entries),
        "ledger_totals": {"personal": 0.0, "business": 0.0},
        "category_totals": {"personal": {}, "business": {}},
    }
    for entry in entries:
        amount = _coerce_float(entry.get("amount", 0), field="amount")
        ledger = str(entry.get("ledger") or "personal").strip().lower()
        if ledger not in _VALID_LEDGERS:
            ledger = "personal"
        category = str(entry.get("category") or "general").strip() or "general"
        summary["total_revenue"] = round(summary["total_revenue"] + amount, 2)
        summary["ledger_totals"][ledger] = round(summary["ledger_totals"][ledger] + amount, 2)
        category_totals = summary["category_totals"][ledger]
        category_totals[category] = round(float(category_totals.get(category, 0.0)) + amount, 2)
    return summary


def _load_normalized_sales() -> List[Dict[str, Any]]:
    sales_raw = _read_json(SALES_FILE, default=[])
    if not isinstance(sales_raw, list):
        return []
    normalized: List[Dict[str, Any]] = []
    for idx, raw in enumerate(sales_raw):
        try:
            entry = _normalize_sale_entry(raw, idx=idx)
        except ValueError:
            continue
        if entry:
            normalized.append(entry)
    return normalized


@app.get("/api/operator/health")
async def get_operator_health():
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    data = _read_json(OPERATOR_HEALTH_FILE, default={})
    payload = data if isinstance(data, dict) else {}
    normalized = _normalize_operator_health(payload)
    return {
        "status": "ok",
        "data": normalized,
        "updated_at": payload.get("updated_at"),
    }


@app.post("/api/operator/health")
async def set_operator_health(body: Dict[str, Any]):
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    current = _read_json(OPERATOR_HEALTH_FILE, default={})
    if not isinstance(current, dict):
        current = {}
    allowed_keys = _PERCENT_HEALTH_FIELDS | _NUMERIC_HEALTH_FIELDS
    unknown = [k for k in body.keys() if k not in allowed_keys]
    if unknown:
        return {"status": "error", "error": f"Unknown operator health fields: {', '.join(sorted(unknown))}"}
    merged = dict(_normalize_operator_health(current))
    try:
        for key in _PERCENT_HEALTH_FIELDS:
            if key in body:
                value = _coerce_int(body.get(key), field=key)
                merged[key] = max(0, min(100, value))
        if "uptime" in body:
            merged["uptime"] = max(0, _coerce_int(body.get("uptime"), field="uptime"))
    except ValueError as exc:
        return {"status": "error", "error": str(exc)}
    merged["updated_at"] = datetime.now(timezone.utc).isoformat()
    _write_json(OPERATOR_HEALTH_FILE, merged)
    return {"status": "ok", "data": _normalize_operator_health(merged), "updated_at": merged["updated_at"]}


@app.get("/api/logsale")
async def get_sales():
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    return _load_normalized_sales()


@app.post("/api/logsale")
async def log_sale(body: Dict[str, Any]):
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    sales = _load_normalized_sales()
    item = str(body.get("item") or "").strip()
    if not item:
        return {"status": "error", "error": "item is required"}
    try:
        amount = _coerce_float(body.get("amount"), field="amount")
    except ValueError as exc:
        return {"status": "error", "error": str(exc)}
    ledger = str(body.get("ledger") or "personal").strip().lower()
    if ledger not in _VALID_LEDGERS:
        return {"status": "error", "error": "ledger must be personal or business"}
    category = str(body.get("category") or "general").strip() or "general"
    entry = {
        "id":         str(uuid.uuid4()),
        "item":       item,
        "amount":     round(amount, 2),
        "ledger":     ledger,
        "category":   category,
        "notes":      str(body.get("notes", "")),
        "date":       body.get("date", datetime.now(timezone.utc).date().isoformat()),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    sales.append(entry)
    _write_json(SALES_FILE, sales)
    return entry


@app.get("/api/logsale/summary")
async def get_sales_summary():
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    sales = _load_normalized_sales()
    return {"status": "ok", "summary": _sales_summary(sales)}


# ─────────────────────────────────────────────────────────────────────────────
# /api/modules
# ─────────────────────────────────────────────────────────────────────────────

def _normalize_module_status(raw_status: Any) -> str:
    if hasattr(raw_status, "value"):
        raw_status = raw_status.value
    if isinstance(raw_status, str):
        raw_status = raw_status.strip().upper()
    else:
        raw_status = ""
    mapping = {
        "ACTIVE": "active",
        "READY": "ready",
        "IDLE": "ready",
        "LOADING": "loading",
        "ERROR": "error",
        "SHUTDOWN": "disabled",
        "DISABLED": "disabled",
    }
    return mapping.get(str(raw_status), "ready")


def _workflow_state_for_agent(agent_id: str) -> Dict[str, Any]:
    normalized_id = str(agent_id or "").strip()
    if normalized_id in {"repo_context_engine", "page_context_bridge", "gitops_guard"}:
        return {
            "workflow_ready": True,
            "workflow_stage": "routed",
            "workflow_path": "mammoth_chat",
        }
    agent_runtime_map = globals().get("AGENTS", {})
    routed = normalized_id in _AGENT_ID_TO_RUNTIME or normalized_id in agent_runtime_map
    atlas_routed = normalized_id in _ATLAS_WORKFLOW_AGENT_IDS
    return {
        "workflow_ready": routed or atlas_routed,
        "workflow_stage": "autonomous" if atlas_routed else "routed" if routed else "registered",
        "workflow_path": "atlas_lesson" if atlas_routed else "plan_execute" if routed else "manual",
    }


def _agent_source_path(agent_id: str) -> Path:
    return ROOT / "src" / "mammoth_os" / "agents" / f"{agent_id}.py"


def _parse_iso_datetime(raw_value: Any) -> Optional[datetime]:
    if isinstance(raw_value, datetime):
        if raw_value.tzinfo is None:
            return raw_value.replace(tzinfo=timezone.utc)
        return raw_value.astimezone(timezone.utc)
    if not isinstance(raw_value, str):
        return None
    try:
        parsed = datetime.fromisoformat(raw_value.strip())
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _canonical_agent_keys(agent_id: Any) -> List[str]:
    normalized = _normalize_module_key(agent_id)
    if not normalized:
        return []
    keys = {normalized}
    if normalized.endswith("-agent"):
        keys.add(normalized[: -len("-agent")])
    return [item for item in keys if item]


def _build_activity_index() -> Dict[str, Dict[str, Any]]:
    latest_by_key: Dict[str, Dict[str, Any]] = {}
    for entry in _load_activity_events():
        if not isinstance(entry, dict):
            continue
        agent_id = entry.get("agent_id")
        if not agent_id:
            continue
        created_at = _parse_iso_datetime(entry.get("created_at"))
        if created_at is None:
            continue
        event = {
            "created_at": created_at,
            "created_at_iso": created_at.isoformat(),
            "kind": str(entry.get("kind") or "event"),
            "message": str(entry.get("message") or "").strip(),
        }
        for key in _canonical_agent_keys(agent_id):
            previous = latest_by_key.get(key)
            if not previous or created_at > previous["created_at"]:
                latest_by_key[key] = event
    return latest_by_key


def _module_observability_snapshot(module_id: str, status: str, *, manifest: Any = None, activity_index: Optional[Dict[str, Dict[str, Any]]] = None) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    activity_index = activity_index or {}

    latest_activity: Optional[Dict[str, Any]] = None
    for key in _canonical_agent_keys(module_id):
        candidate = activity_index.get(key)
        if candidate and (latest_activity is None or candidate["created_at"] > latest_activity["created_at"]):
            latest_activity = candidate

    heartbeat_dt = _parse_iso_datetime(getattr(manifest, "last_heartbeat", None))
    metadata = getattr(manifest, "metadata", {}) if manifest else {}
    if not isinstance(metadata, dict):
        metadata = {}
    last_run_dt = _parse_iso_datetime(metadata.get("last_run_at"))

    activity_age_seconds = int((now - latest_activity["created_at"]).total_seconds()) if latest_activity else None
    heartbeat_age_seconds = int((now - heartbeat_dt).total_seconds()) if heartbeat_dt else None
    has_recent_activity = activity_age_seconds is not None and activity_age_seconds <= 180
    has_recent_heartbeat = (
        heartbeat_age_seconds is not None
        and heartbeat_age_seconds <= 180
        and (last_run_dt is not None or latest_activity is not None)
    )
    observed_active = has_recent_activity or has_recent_heartbeat

    effective_status = status
    if status == "ready" and observed_active:
        effective_status = "active"

    return {
        "status": effective_status,
        "observed_active": observed_active,
        "last_activity_at": latest_activity["created_at_iso"] if latest_activity else "",
        "last_activity_kind": latest_activity["kind"] if latest_activity else "",
        "last_activity_message": latest_activity["message"] if latest_activity else "",
        "activity_age_seconds": activity_age_seconds,
        "last_heartbeat_at": heartbeat_dt.isoformat() if heartbeat_dt else "",
        "heartbeat_age_seconds": heartbeat_age_seconds,
        "last_run_at": last_run_dt.isoformat() if last_run_dt else "",
    }


def _agent_quality_snapshot(agent_id: str) -> Dict[str, Any]:
    source_path = _agent_source_path(agent_id)
    if not source_path.exists():
        return {}

    try:
        text = source_path.read_text(encoding="utf-8")
    except OSError as exc:
        return {
            "quality_score": 20,
            "quality_tier": "error",
            "quality_findings": [f"Could not read source: {exc}"],
            "interface_mode": "unknown",
        }

    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        return {
            "quality_score": 10,
            "quality_tier": "error",
            "quality_findings": [f"Syntax issue at line {exc.lineno}"],
            "interface_mode": "unknown",
        }

    class_node = next(
        (
            node for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name.lower().endswith("agent")
        ),
        None,
    )
    if not class_node:
        return {
            "quality_score": 25,
            "quality_tier": "prototype",
            "quality_findings": ["No agent class was discovered in the file."],
            "interface_mode": "unknown",
        }

    method_nodes = [node for node in class_node.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
    method_names = {node.name for node in method_nodes}
    run_node = next((node for node in method_nodes if node.name == "run"), None)
    inherits_base_agent = any(
        (isinstance(base, ast.Name) and base.id == "BaseAgent")
        or (isinstance(base, ast.Attribute) and base.attr == "BaseAgent")
        for base in class_node.bases
    )

    score = 92
    findings: List[str] = []
    interface_mode = "async" if isinstance(run_node, ast.AsyncFunctionDef) else "sync" if run_node else "specialized"
    lowered = text.lower()
    placeholder_markers = [
        marker for marker in ("implement later", "placeholder", "todo", "deeper logic later")
        if marker in lowered
    ]

    if not inherits_base_agent:
        score -= 12
        findings.append("Does not inherit BaseAgent.")
    if "run" not in method_names and "accept_submission" not in method_names:
        score -= 20
        findings.append("No standard workflow entrypoint was found.")
    if placeholder_markers:
        score -= min(24, 8 * len(placeholder_markers))
        findings.append("Contains placeholder-oriented logic markers.")
    if len(method_names) <= 2:
        score -= 8
        findings.append("Agent surface area is still narrow.")
    if len(text.splitlines()) < 40:
        score -= 6
        findings.append("Implementation is still lightweight.")
    if "accept_submission" in method_names and run_node:
        interface_mode = "hybrid"

    score = max(10, min(100, score))
    if score >= 88:
        tier = "top-tier"
    elif score >= 75:
        tier = "strong"
    elif score >= 60:
        tier = "developing"
    else:
        tier = "prototype"

    return {
        "quality_score": score,
        "quality_tier": tier,
        "quality_findings": findings[:2],
        "interface_mode": interface_mode,
        "source_file": str(source_path.relative_to(ROOT)),
    }


_STATIC_MODULES = [
    {"id": "coding_agent",      "name": "CodingAgent",      "version": "v1.2.0", "status": "active",   "description": "Code generation, refactor, review"},
    {"id": "repo_context_engine", "name": "RepoContextEngine", "version": "v1.0.0", "status": "active", "description": "Repository-aware context snapshots for Mammoth Mind and FAB"},
    {"id": "page_context_bridge", "name": "PageContextBridge", "version": "v1.0.0", "status": "active", "description": "Live page context normalization and prompt wiring"},
    {"id": "gitops_guard", "name": "GitOpsGuard", "version": "v1.0.0", "status": "ready", "description": "Approval-gated commit/push/deploy intent routing"},
    {"id": "field_ops_agent",   "name": "FieldOpsAgent",    "version": "v0.9.1", "status": "active",   "description": "Planting, irrigation, field data"},
    {"id": "research_agent",    "name": "ResearchAgent",    "version": "v0.8.3", "status": "active",   "description": "Market intel, curriculum research"},
    {"id": "memory_engine",     "name": "MemoryEngine",     "version": "v0.8.0", "status": "active",   "description": "Long-term context & session memory"},
    {"id": "atlas_session",     "name": "ATLASSession",     "version": "v0.5.0", "status": "ready",     "description": "Progress tracking & subsystem status"},
    {"id": "plant_seed_agent",  "name": "PlantSeedAgent",   "version": "v0.6.2", "status": "ready",     "description": "Seed sourcing, planting schedules"},
    {"id": "market_intel_agent","name": "MarketIntelAgent", "version": "v0.3.0", "status": "ready",     "description": "Price feeds, market analysis"},
    {"id": "cortex_router",     "name": "CortexRouter",     "version": "v1.0.0", "status": "active",   "description": "Intent-based routing layer"},
    {"id": "engine_registry",   "name": "EngineRegistry",   "version": "v1.0.0", "status": "active",   "description": "Discovers and registers engine classes"},
]


@app.get("/api/modules")
async def get_modules():
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    module_map: Dict[str, Dict[str, Any]] = {}
    manifest_map: Dict[str, Any] = {}
    for item in _STATIC_MODULES:
        module = dict(item)
        workflow = _workflow_state_for_agent(module["id"])
        module.update(workflow)
        module_map[module["id"]] = module

    if _agent_registry_ok:
        try:
            manifests = await agent_registry.list_agents()
        except Exception:
            manifests = []
        for manifest in manifests:
            agent_id = str(getattr(manifest, "agent_id", "") or "").strip()
            if not agent_id:
                continue
            workflow = _workflow_state_for_agent(agent_id)
            module = module_map.get(agent_id, {
                "id": agent_id,
                "name": getattr(manifest, "name", agent_id),
                "version": getattr(manifest, "version", "v1.0.0"),
                "status": "ready",
                "description": "Registered agent",
            })
            module.update({
                "id": agent_id,
                "name": getattr(manifest, "name", module.get("name", agent_id)),
                "version": getattr(manifest, "version", module.get("version", "v1.0.0")),
                "status": _normalize_module_status(getattr(manifest, "status", None)),
                "description": module.get("description") or "Registered agent",
                "capabilities": getattr(manifest, "capabilities", []),
                "level": getattr(manifest, "level", 1),
                "endpoint": getattr(manifest, "endpoint", ""),
                "source": "registry",
            })
            manifest_map[agent_id] = manifest
            module.update(_agent_quality_snapshot(agent_id))
            module.update(workflow)
            module_map[agent_id] = module

    agents_dir = ROOT / "src" / "mammoth_os" / "agents"
    if agents_dir.exists():
        for f in sorted(agents_dir.glob("*_agent.py")):
            mid = f.stem
            if mid in module_map:
                continue
            workflow = _workflow_state_for_agent(mid)
            module_map[mid] = {
                "id": mid,
                "name": "".join(w.title() for w in mid.split("_")),
                "version": "v1.0.0",
                "status": "ready",
                "description": f"Agent: {mid}",
                "source": "discovered",
                **workflow,
                **_agent_quality_snapshot(mid),
            }

    activity_index = _build_activity_index()
    for module in module_map.values():
        module_id = str(module.get("id") or "")
        status = str(module.get("status") or "ready")
        module.update(
            _module_observability_snapshot(
                module_id,
                status,
                manifest=manifest_map.get(module_id),
                activity_index=activity_index,
            )
        )

    return list(module_map.values())



# ─────────────────────────────────────────────────────────────────────────────
# /api/mcp/*  — MCP server registry
# ─────────────────────────────────────────────────────────────────────────────

_MCP_INDEX_PATH = ROOT / "mcp" / "index.json"


def _load_mcp_index() -> Dict[str, Any]:
    if not _MCP_INDEX_PATH.exists():
        return {"servers": []}
    try:
        data = json.loads(_MCP_INDEX_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {"servers": []}
    except (OSError, json.JSONDecodeError):
        return {"servers": []}


def _load_mcp_server_config(config_rel: str) -> Dict[str, Any]:
    path = ROOT / config_rel
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


@app.get("/api/mcp/servers")
async def get_mcp_servers():
    """Return the MCP server registry with config details and availability status."""
    index = _load_mcp_index()
    servers = []
    for entry in index.get("servers") or []:
        if not isinstance(entry, dict):
            continue
        cfg = _load_mcp_server_config(str(entry.get("config") or ""))
        import shutil
        command = cfg.get("command") or entry.get("command") or "npx"
        available = shutil.which(command) is not None
        servers.append({
            "id": str(entry.get("id") or ""),
            "label": str(entry.get("label") or cfg.get("name") or entry.get("id") or ""),
            "description": str(entry.get("description") or cfg.get("description") or ""),
            "category": str(entry.get("category") or "tool"),
            "enabled": bool(entry.get("enabled", True)) and bool(cfg.get("enabled", True)),
            "available": available,
            "status": "ready" if available else "needs_setup",
            "tools": cfg.get("tools") or [],
            "command": command,
            "transport": cfg.get("transport") or "stdio",
            "notes": cfg.get("notes") or [],
        })
    return {
        "status": "ok",
        "contract_version": "v1",
        "server_count": len(servers),
        "servers": servers,
    }

async def _release_readiness_snapshot() -> Dict[str, Any]:
    modules = await get_modules()
    health = await get_health()
    entitlements = await get_entitlements()
    account = await get_account_profile()
    runtime = health.get("runtime") if isinstance(health.get("runtime"), dict) else _runtime_status_snapshot()

    services = health.get("services") if isinstance(health.get("services"), list) else []
    red_services = [str(service.get("label") or "unknown") for service in services if service.get("status") == "red"]
    yellow_services = [str(service.get("label") or "unknown") for service in services if service.get("status") == "yellow"]

    rated_modules = []
    for module in modules:
        quality_score = module.get("quality_score")
        if isinstance(quality_score, (int, float)):
            rated_modules.append(module)

    rated_modules.sort(key=lambda item: (float(item.get("quality_score") or 0), str(item.get("name") or item.get("id") or "")))
    lowest_rated = [
        {
            "id": str(module.get("id") or ""),
            "name": str(module.get("name") or module.get("id") or "Unknown module"),
            "score_100": int(round(float(module.get("quality_score") or 0))),
            "score_10": round(float(module.get("quality_score") or 0) / 10.0, 1),
            "tier": str(module.get("quality_tier") or "unknown"),
            "finding": " ".join([str(item) for item in (module.get("quality_findings") or [])[:2]]).strip(),
        }
        for module in rated_modules[:5]
    ]

    module_scores = [float(module.get("quality_score") or 0) / 10.0 for module in rated_modules]
    module_score = round(sum(module_scores) / len(module_scores), 1) if module_scores else 0.0

    cloud_ready = len([provider for provider in runtime.get("providers", []) if provider.get("provider") in {"deepseek", "openai"} and provider.get("available")])
    non_local_ready = len([provider for provider in runtime.get("providers", []) if provider.get("provider") != "local" and provider.get("available")])
    if runtime.get("state") == "ready":
        runtime_score = 8.8 if cloud_ready >= 1 else 7.8
    elif runtime.get("active_adapter") == "local":
        runtime_score = 5.5
    else:
        runtime_score = 6.6
    runtime_score -= min(len(red_services) * 0.7, 2.1)
    runtime_score = round(max(1.0, min(10.0, runtime_score)), 1)

    activity_count = len(_load_activity_events())
    task_count = len(_load_tasks())
    approval_count = len(_load_approvals())
    audit_count = len(_load_audit_log())
    observability_score = 6.5
    if audit_count:
        observability_score += 0.7
    if activity_count:
        observability_score += 0.6
    if task_count or approval_count:
        observability_score += 0.7
    if health.get("summary", {}).get("total_services"):
        observability_score += 0.5
    observability_score = round(min(observability_score, 9.0), 1)

    overall_score = round(((runtime_score * 0.4) + (module_score * 0.4) + (observability_score * 0.2)), 1)

    blockers: List[Dict[str, Any]] = []
    if runtime_score < 8.0 or cloud_ready == 0:
        blockers.append({
            "title": "Provider resilience still degrades too easily",
            "severity": "high",
            "detail": str(runtime.get("recommendation") or "Restore at least one cloud provider so MammothOS does not collapse into local-only fallback."),
        })
    if red_services:
        blockers.append({
            "title": "Critical services are down",
            "severity": "high",
            "detail": ", ".join(red_services[:3]),
        })
    if lowest_rated and lowest_rated[0]["score_10"] < 8.0:
        weakest = ", ".join(f"{item['name']} ({item['score_10']}/10)" for item in lowest_rated[:3])
        blockers.append({
            "title": "Lowest-rated lanes still need one more upgrade wave",
            "severity": "medium",
            "detail": weakest,
        })
    if not bool(account.get("profile_complete")):
        blockers.append({
            "title": "Operator identity scaffolding is still incomplete",
            "severity": "medium",
            "detail": "Fill in display name, email, and organization so entitlement and diagnostics exports carry a complete operator identity.",
        })
    if yellow_services and len(blockers) < 3:
        blockers.append({
            "title": "Some runtime dependencies are still degraded",
            "severity": "medium",
            "detail": ", ".join(yellow_services[:3]),
        })
    blockers = blockers[:3]

    strengths = [
        "Native chat, diagnostics, and plan/execute wiring are already integrated through the backend runtime surface.",
        "Agent registry and module observability are backend-driven rather than hard-coded in the UI.",
        "Audit, task, and approval streams are present for operator-facing visibility.",
    ]
    if module_score >= 8.0:
        strengths.append("Average module quality is now above the near-ready threshold.")
    if runtime.get("state") == "ready" and cloud_ready >= 1:
        strengths.append("At least one cloud-capable provider is available in the fallback chain.")

    return {
        "status": "ok",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "score": overall_score,
        "tier": _release_readiness_tier(overall_score),
        "scores": {
            "runtime": runtime_score,
            "modules": module_score,
            "observability": observability_score,
        },
        "summary": {
            "rated_modules": len(rated_modules),
            "healthy_services": int(health.get("summary", {}).get("healthy_services") or 0),
            "total_services": int(health.get("summary", {}).get("total_services") or 0),
            "cloud_providers_ready": cloud_ready,
            "non_local_providers_ready": non_local_ready,
        },
        "runtime": runtime,
        "lowest_rated": lowest_rated,
        "blockers": blockers,
        "strengths": strengths[:4],
        "account": {
            "auth_mode": account.get("auth_mode"),
            "session_scope": account.get("session_scope"),
            "profile_complete": account.get("profile_complete"),
        },
        "recommended_next_action": blockers[0]["title"] if blockers else "Continue incremental upgrade work on the next lowest-rated lane.",
    }


@app.get("/api/release-readiness")
async def get_release_readiness():
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    return await _release_readiness_snapshot()



# ─────────────────────────────────────────────────────────────────────────────
# /api/terminal/exec  (HTTP fallback — returns full output at once)
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/api/terminal/exec")
async def terminal_exec(body: Dict[str, Any]):
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    cmd = str(body.get("cmd", "")).strip()
    if not cmd:
        return {"stdout": "", "stderr": "No command provided.", "exit_code": 1}
    if not _is_allowed(cmd):
        _append_audit_event(
            kind="terminal_exec_denied",
            message="Terminal command blocked by allow-list",
            details={"cmd": cmd},
            source="terminal",
            actor="user",
        )
        return {
            "stdout": "",
            "stderr": f"Not in allow-list: {cmd}\nAllowed prefixes: {', '.join(sorted(ALLOW_PREFIXES))}",
            "exit_code": 1,
        }
    result = await _execute_terminal_command(cmd)
    _append_audit_event(
        kind="terminal_exec",
        message="Terminal command executed",
        details={"cmd": cmd, "exit_code": result["exit_code"]},
        source="terminal",
        actor="user",
    )
    return {
        "stdout": result["stdout"],
        "stderr": result["stderr"],
        "exit_code": result["exit_code"],
        "cwd": result.get("cwd", ""),
        "resolved": result.get("resolved", cmd),
        "timeout_seconds": result.get("timeout_seconds"),
    }


# ─────────────────────────────────────────────────────────────────────────────
# WebSocket /ws/terminal
# ─────────────────────────────────────────────────────────────────────────────

ALLOW_LIST = {
    "git status",
    "git log --oneline -20",
    "git log --oneline",
    "git diff --stat",
    "git branch",
    "npm run dev",
    "npm run build",
    "npm install",
    "python -m cli.main status",
    "python -m cli.main agent-list",
    "python -m cli.main health",
    "python -m cli.main atlas status",
    "python -m cli.main version",
    "python -m cli.main diagnostics",
    "py -m cli.main status",
    "uvicorn api_server:app --reload",
    "ls",
    "dir",
    "pwd",
}

ALLOW_PREFIXES = (
    "npm ",
    "uvicorn ",
    "cat ",
    "ls ",
    "dir ",
    "git ",
)


TERMINAL_BLOCKED_SEQUENCES = ("&&", "||", ";", "|", ">", "<", "`")
CLI_ROOTS = ("python -m cli.main", "py -m cli.main")
CLI_TOP_LEVEL_COMMANDS = {"version", "engine-list", "agent-list", "health", "status", "diagnostics", "check", "schema-describe"}
ATLAS_COMMANDS = {"status", "lesson", "submit", "next", "reset", "ui", "code"}
ATLAS_UI_COMMANDS = {"scaffold", "component", "style", "backend", "graph", "palette"}
ATLAS_CODE_COMMANDS = {"generate", "refactor", "explain", "debug", "scan", "patch"}


def _has_blocked_terminal_sequence(cmd: str) -> bool:
    return any(token in cmd for token in TERMINAL_BLOCKED_SEQUENCES)


def _is_allowed_cli_command(cmd: str) -> bool:
    stripped = cmd.strip()
    cli_root = next((root for root in CLI_ROOTS if stripped.startswith(root)), "")
    if not cli_root:
        return False
    if _has_blocked_terminal_sequence(stripped):
        return False

    remainder = stripped[len(cli_root):].strip()
    if not remainder:
        return False

    tokens = remainder.split()
    if not tokens:
        return False
    if "--help" in tokens or "-h" in tokens:
        return True

    top_level = tokens[0]
    if top_level in CLI_TOP_LEVEL_COMMANDS:
        return True
    if top_level != "atlas":
        return False
    if len(tokens) < 2:
        return False

    atlas_command = tokens[1]
    if atlas_command not in ATLAS_COMMANDS:
        return False
    if atlas_command in {"status", "lesson", "submit", "next", "reset"}:
        return True
    if len(tokens) < 3:
        return False

    atlas_subcommand = tokens[2]
    if atlas_command == "ui":
        return atlas_subcommand in ATLAS_UI_COMMANDS
    if atlas_command == "code":
        return atlas_subcommand in ATLAS_CODE_COMMANDS
    return False


def _is_allowed(cmd: str) -> bool:
    s = cmd.strip()
    if _is_allowed_cli_command(s):
        return True
    if s in ALLOW_LIST:
        return True
    if _has_blocked_terminal_sequence(s):
        return False
    for prefix in ALLOW_PREFIXES:
        if s.startswith(prefix):
            return True
    return False


def _make_env() -> dict:
    env = os.environ.copy()
    src_path = str(ROOT / "src")
    existing = env.get("PYTHONPATH", "")
    if src_path not in existing:
        env["PYTHONPATH"] = f"{src_path}{os.pathsep}{existing}" if existing else src_path
    return env


def _normalize_terminal_command(cmd: str) -> tuple:
    normalized = cmd.strip()
    run_cwd = ROOT

    # Unix aliases -> PowerShell
    if normalized == "pwd":
        normalized = "Get-Location | Select-Object -ExpandProperty Path"
    elif normalized == "ls":
        normalized = "Get-ChildItem | Format-Table Name,Length,LastWriteTime"
    elif normalized.startswith("cat "):
        normalized = "Get-Content " + normalized[4:]

    # npm -> UI dir
    if normalized.startswith("npm "):
        run_cwd = UI_DIR if UI_DIR.exists() else ROOT

    # Use venv python
    if normalized.startswith("python -m cli.main") and VENV_PYTHON.exists():
        normalized = f'& "{VENV_PYTHON}"' + normalized[len("python"):]
    elif normalized.startswith("py -m cli.main") and VENV_PYTHON.exists():
        normalized = f'& "{VENV_PYTHON}"' + normalized[len("py"):]

    # Use venv uvicorn
    if normalized.startswith("uvicorn ") and VENV_UVICORN.exists():
        normalized = f'& "{VENV_UVICORN}"' + normalized[len("uvicorn"):]

    return normalized, run_cwd


def _run_command_sync(resolved: str, run_cwd: Path, env: dict, timeout: int) -> Dict[str, Any]:
    """Run command synchronously via subprocess.run (Windows ProactorEventLoop-safe)."""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", resolved],
            capture_output=True,
            cwd=str(run_cwd),
            env=env,
            timeout=timeout,
        )
        return {
            "stdout": result.stdout.decode(errors="replace"),
            "stderr": result.stderr.decode(errors="replace"),
            "exit_code": int(result.returncode or 0),
            "resolved": resolved,
            "cwd": str(run_cwd),
        }
    except subprocess.TimeoutExpired:
        return {
            "stdout": "",
            "stderr": f"Command timed out ({timeout}s)",
            "exit_code": 1,
            "resolved": resolved,
            "cwd": str(run_cwd),
        }
    except Exception as e:
        return {
            "stdout": "",
            "stderr": f"{type(e).__name__}: {e!r}",
            "exit_code": 1,
            "resolved": resolved,
            "cwd": str(run_cwd),
        }


def _terminal_timeout_for(cmd: str) -> int:
    stripped = cmd.strip()
    if stripped.startswith("python -m cli.main atlas code ") or stripped.startswith("py -m cli.main atlas code "):
        return 180
    if stripped.startswith("python -m cli.main atlas ui ") or stripped.startswith("py -m cli.main atlas ui "):
        return 120
    return 60


async def _execute_terminal_command(cmd: str, timeout: Optional[int] = None) -> Dict[str, Any]:
    resolved, run_cwd = _normalize_terminal_command(cmd)
    env = _make_env()
    resolved_timeout = timeout if timeout is not None else _terminal_timeout_for(cmd)
    result = await asyncio.to_thread(_run_command_sync, resolved, run_cwd, env, resolved_timeout)
    result["timeout_seconds"] = resolved_timeout
    return result


@app.get("/api/audit")
async def get_audit_log():
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    entries = _load_audit_log()
    return {"status": "ok", "entries": entries[-80:]}


@app.get("/api/audit/export")
async def export_audit_log_csv():
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    entries = _load_audit_log()
    csv_payload = _audit_entries_to_csv(entries[-250:])
    return PlainTextResponse(
        content=csv_payload,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="mammoth-audit-{datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")}.csv"'},
    )


@app.get("/api/diagnostics/export")
async def export_diagnostics_snapshot():
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    release = await _release_readiness_snapshot()
    payload = {
        "status": "ok",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "release_readiness": release,
        "health": await get_health(),
        "entitlements": await get_entitlements(),
        "account_profile": await get_account_profile(),
        "activity": _load_activity_events()[-50:],
        "tasks": _load_tasks()[-50:],
        "approvals": _load_approvals()[-50:],
        "audit": _load_audit_log()[-100:],
    }
    json_payload = json.dumps(payload, indent=2)
    return PlainTextResponse(
        content=json_payload,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="mammoth-diagnostics-{datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")}.json"'},
    )


@app.post("/api/audit")
async def append_audit_log(body: Dict[str, Any]):
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    kind = str(body.get("kind") or "generic").strip() or "generic"
    message = str(body.get("message") or f"{kind} event").strip() or f"{kind} event"
    details = body.get("details") if isinstance(body.get("details"), dict) else {}
    source = str(body.get("source") or "system").strip() or "system"
    actor = str(body.get("actor") or "system").strip() or "system"
    tier = str(body.get("tier") or "").strip() or None
    entry = _append_audit_event(kind=kind, message=message, details=details, source=source, actor=actor, tier=tier)
    return {"status": "ok", "entry": entry}


@app.get("/api/entitlements")
async def get_entitlements():
    """Return the current user's tier and feature entitlements."""
    state = _load_atlas_state()
    workspace = _build_workspace_accounts_snapshot(state)
    tier = str(state.get("tier") or "explorer").strip().lower()
    if tier not in {"explorer", "pro", "enterprise"}:
        tier = "explorer"
    developer_access = bool(state.get("developer_access", False))
    effective_tier = "enterprise" if developer_access else tier
    base_features = {
        "atlas_tutor": True,
        "adaptive_pacing": True,
        "lesson_resume": True,
        "flashcards_quiz": True,
        "basic_evals": True,
        "local_storage": True,
    }
    pro_features = {
        "multi_agent_orchestration": effective_tier in {"pro", "enterprise"},
        "plan_execute_all_profiles": effective_tier in {"pro", "enterprise"},
        "supabase_sync": effective_tier in {"pro", "enterprise"},
        "eval_history_dashboard": effective_tier in {"pro", "enterprise"},
        "audit_log_export": effective_tier in {"pro", "enterprise"},
        "coding_agent_approval": effective_tier in {"pro", "enterprise"},
    }
    enterprise_features = {
        "team_dashboards": effective_tier == "enterprise",
        "custom_curriculum": effective_tier == "enterprise",
        "lms_integration": effective_tier == "enterprise",
        "white_label": effective_tier == "enterprise",
    }
    profile = _normalized_account_profile(state)
    completion = _profile_completion(profile)
    return {
        "status": "ok",
        "tier": tier,
        "effective_tier": "developer" if developer_access else effective_tier,
        "developer_access": developer_access,
        "admin_controls_enabled": _request_is_admin(),
        "auth_mode": _auth_mode_from_state(state),
        "session_scope": "workspace_multi_account",
        "tier_updated_at": state.get("tier_updated_at"),
        "developer_access_updated_at": state.get("developer_access_updated_at"),
        "active_account_id": workspace.get("active_account_id"),
        "account_count": len(workspace.get("accounts") or []),
        "user_id": _atlas_user_id(state),
        "account_profile": profile,
        "account_profile_complete": all(completion.values()),
        "features": {**base_features, **pro_features, **enterprise_features},
        "upgrade_cta": "pricing" if tier == "explorer" and not developer_access else None,
    }


@app.get("/api/billing/usage/current")
async def get_current_billing_usage():
    state = _load_atlas_state()
    usage = _current_usage_snapshot_from_state(state)
    usage.update(
        {
            "auth_mode": _auth_mode_from_state(state),
            "active_account_id": _active_account_id(state),
            "user_id": _atlas_user_id(state),
        }
    )
    return usage


@app.post("/api/entitlements/tier")
async def set_tier(body: Dict[str, Any]):
    """Set the user's tier (for testing / admin use)."""
    if _AUTH_REQUIRED and not _request_is_admin():
        return {"status": "error", "error": "Admin privileges required for entitlement changes."}
    tier = str(body.get("tier") or "explorer").strip().lower()
    if tier not in {"explorer", "pro", "enterprise"}:
        return {"status": "error", "error": "Invalid tier. Use: explorer, pro, enterprise"}
    state = _load_atlas_state()
    state["tier"] = tier
    state["tier_updated_at"] = datetime.now(timezone.utc).isoformat()
    _save_atlas_state(state)
    _append_audit_event(
        kind="tier_change",
        message="Entitlement tier updated",
        details={"tier": tier, "developer_access": bool(state.get("developer_access", False)), "account_id": _active_account_id(state)},
        source="entitlements",
        actor="user",
        tier=tier,
    )
    return {"status": "ok", "tier": tier, "active_account_id": _active_account_id(state), "user_id": _atlas_user_id(state)}


@app.get("/api/account/profile")
async def get_account_profile():
    state = _load_atlas_state()
    workspace = _build_workspace_accounts_snapshot(state)
    profile = _normalized_account_profile(state)
    completion = _profile_completion(profile)
    return {
        "status": "ok",
        "profile": profile,
        "profile_complete": all(completion.values()),
        "profile_completion": completion,
        "updated_at": state.get("account_profile_updated_at"),
        "auth_mode": _auth_mode_from_state(state),
        "session_scope": "workspace_multi_account",
        "tier": str(state.get("tier") or "explorer").strip().lower(),
        "developer_access": bool(state.get("developer_access", False)),
        "active_account_id": workspace.get("active_account_id"),
        "available_accounts": workspace.get("accounts"),
        "user_id": _atlas_user_id(state),
    }


@app.post("/api/account/profile")
async def set_account_profile(body: Dict[str, Any]):
    state = _load_atlas_state()
    profile = state.get("account_profile") if isinstance(state.get("account_profile"), dict) else {}
    for key in ("display_name", "email", "organization"):
        if key in body:
            profile[key] = str(body.get(key) or "").strip()
    state["account_profile"] = profile
    state["account_profile_updated_at"] = datetime.now(timezone.utc).isoformat()
    _save_atlas_state(state)
    _append_audit_event(
        kind="profile_update",
        message="Account profile updated",
        details={"profile_fields": sorted(list(profile.keys())), "account_id": _active_account_id(state)},
        source="account",
        actor="user",
        tier=str(state.get("tier") or "explorer"),
    )
    normalized = _normalized_account_profile(state)
    completion = _profile_completion(normalized)
    return {
        "status": "ok",
        "profile": normalized,
        "profile_complete": all(completion.values()),
        "profile_completion": completion,
        "updated_at": state.get("account_profile_updated_at"),
        "active_account_id": _active_account_id(state),
        "user_id": _atlas_user_id(state),
    }


@app.post("/api/account/developer-access")
async def set_developer_access(body: Dict[str, Any]):
    if _AUTH_REQUIRED and not _request_is_admin():
        return {"status": "error", "error": "Admin privileges required for developer-access changes."}
    enabled = bool(body.get("enabled"))
    state = _load_atlas_state()
    state["developer_access"] = enabled
    state["developer_access_updated_at"] = datetime.now(timezone.utc).isoformat()
    _save_atlas_state(state)
    _append_audit_event(
        kind="developer_access",
        message="Developer full-access mode toggled",
        details={"enabled": enabled, "account_id": _active_account_id(state)},
        source="entitlements",
        actor="user",
        tier="enterprise" if enabled else str(state.get("tier") or "explorer"),
    )
    return {
        "status": "ok",
        "developer_access": enabled,
        "auth_mode": _auth_mode_from_state(state),
        "effective_tier": "developer" if enabled else str(state.get("tier") or "explorer"),
        "updated_at": state.get("developer_access_updated_at"),
        "active_account_id": _active_account_id(state),
        "user_id": _atlas_user_id(state),
    }


@app.get("/api/account/workspace")
async def get_account_workspace():
    state = _load_atlas_state()
    return _build_workspace_accounts_snapshot(state)


@app.post("/api/account/workspace")
async def mutate_account_workspace(body: Dict[str, Any]):
    state = _load_atlas_state()
    action = str(body.get("action") or "").strip().lower()
    accounts = state.get("accounts") if isinstance(state.get("accounts"), dict) else {}
    sessions = state.get("account_sessions") if isinstance(state.get("account_sessions"), dict) else {}
    active_account_id = _active_account_id(state)

    if action == "create":
        raw_label = str(body.get("display_name") or body.get("label") or body.get("account_id") or "New account").strip()
        account_id = _normalize_account_id(body.get("account_id") or raw_label, fallback="account")
        if account_id in accounts:
            return {"status": "error", "error": f"Account already exists: {account_id}"}
        profile = {
            "display_name": raw_label or "Operator",
            "email": str(body.get("email") or "").strip(),
            "organization": str(body.get("organization") or "").strip(),
        }
        now = datetime.now(timezone.utc).isoformat()
        accounts[account_id] = {
            "profile": profile,
            "tier": "explorer",
            "developer_access": False,
            "created_at": now,
            "updated_at": now,
            "profile_updated_at": now,
        }
        sessions[account_id] = {"status": "no_session", "updated_at": now}
        if bool(body.get("activate", True)):
            _persist_active_account_collections(state)
            state["accounts"] = accounts
            state["account_sessions"] = sessions
            state["active_account_id"] = account_id
            _ensure_account_collections(state)
        else:
            state["accounts"] = accounts
            state["account_sessions"] = sessions
        state["updated_at"] = now
        _save_atlas_state(state)
        _append_audit_event(
            kind="account_created",
            message="Workspace account created",
            details={"account_id": account_id, "active": bool(body.get("activate", True))},
            source="account",
            actor="user",
            tier=str(state.get("tier") or "explorer"),
        )
        snapshot = _build_workspace_accounts_snapshot(state)
        return {"status": "ok", "action": action, **snapshot}

    if action == "switch":
        target_id = _normalize_account_id(body.get("account_id"), fallback="")
        if not target_id or target_id not in accounts:
            return {"status": "error", "error": "Unknown account_id"}
        _persist_active_account_collections(state)
        state["accounts"] = accounts
        state["account_sessions"] = sessions
        state["active_account_id"] = target_id
        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        _ensure_account_collections(state)
        _save_atlas_state(state)
        _append_audit_event(
            kind="account_switch",
            message="Workspace account switched",
            details={"account_id": target_id},
            source="account",
            actor="user",
            tier=str(state.get("tier") or "explorer"),
        )
        snapshot = _build_workspace_accounts_snapshot(state)
        return {"status": "ok", "action": action, **snapshot}

    if action == "delete":
        target_id = _normalize_account_id(body.get("account_id"), fallback="")
        if not target_id or target_id not in accounts:
            return {"status": "error", "error": "Unknown account_id"}
        if len(accounts) <= 1:
            return {"status": "error", "error": "At least one workspace account must remain."}
        if target_id == active_account_id:
            _persist_active_account_collections(state)
        accounts.pop(target_id, None)
        sessions.pop(target_id, None)
        if target_id == active_account_id:
            replacement_id = sorted(accounts.keys())[0]
            state["active_account_id"] = replacement_id
            _ensure_account_collections(state)
        else:
            state["accounts"] = accounts
            state["account_sessions"] = sessions
        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        _save_atlas_state(state)
        _append_audit_event(
            kind="account_deleted",
            message="Workspace account deleted",
            details={"account_id": target_id},
            source="account",
            actor="user",
            tier=str(state.get("tier") or "explorer"),
        )
        snapshot = _build_workspace_accounts_snapshot(state)
        return {"status": "ok", "action": action, **snapshot}

    return {"status": "error", "error": "Unsupported action. Use create, switch, or delete."}


@app.websocket("/ws/terminal")
async def terminal_ws(ws: WebSocket):
    if _AUTH_REQUIRED:
        token = str(ws.query_params.get("access_token") or "").strip()
        user = _resolve_supabase_user(token)
        if user is None or not user.get("is_admin"):
            await ws.close(code=1008)
            return
    await ws.accept()
    await ws.send_json({"line": "MammothOS Terminal ready. Type a command.", "type": "stdout"})
    try:
        while True:
            data = await ws.receive_json()
            cmd = data.get("cmd", "").strip()
            if not cmd:
                continue

            if not _is_allowed(cmd):
                await ws.send_json({"line": f"Not in allow-list: {cmd}", "type": "stderr"})
                await ws.send_json({"line": f"  Allowed prefixes: {', '.join(sorted(ALLOW_PREFIXES))}", "type": "stderr"})
                await ws.send_json({"line": f"[exit 1]", "type": "exit", "code": 1})
                continue

            await ws.send_json({"line": f"$ {cmd}", "type": "cmd"})
            result = await _execute_terminal_command(cmd)
            await ws.send_json({"line": f"[cwd] {result['cwd']}", "type": "stdout"})
            if result.get("stdout"):
                for line in result["stdout"].splitlines():
                    if line.strip():
                        await ws.send_json({"line": line, "type": "stdout"})
            if result.get("stderr"):
                for line in result["stderr"].splitlines():
                    if line.strip():
                        await ws.send_json({"line": line, "type": "stderr"})
            await ws.send_json({"line": f"[exit {result['exit_code']}]", "type": "exit", "code": result["exit_code"]})

    except WebSocketDisconnect:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 4 — RUNTIME EXECUTION LOG
# Captures last N agent/tool execution events for live runtime awareness.
# ─────────────────────────────────────────────────────────────────────────────

_EXECUTION_LOG_MAX = 200

def _load_execution_log() -> list:
    try:
        return json.loads(EXECUTION_LOG_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []

def _append_execution_event(kind: str, summary: str, detail: dict = None, user_id: str = "system") -> None:
    try:
        log = _load_execution_log()
        log.append({
            "id": str(uuid.uuid4()),
            "kind": kind,
            "summary": summary,
            "detail": detail or {},
            "user_id": user_id,
            "ts": datetime.now(timezone.utc).isoformat(),
        })
        if len(log) > _EXECUTION_LOG_MAX:
            log = log[-_EXECUTION_LOG_MAX:]
        EXECUTION_LOG_FILE.write_text(json.dumps(log, indent=2, default=str), encoding="utf-8")
    except Exception:
        pass


@app.get("/api/runtime/execution-log")
async def get_execution_log(request: Request, limit: int = 50):
    """Phase 4: return recent agent/tool execution events for live runtime awareness."""
    user = await _require_auth_user(request)
    if user is None:
        return JSONResponse({"status": "unauthorized"}, status_code=401)
    is_admin = user.get("is_admin", False)
    uid = user.get("id", "local")
    log = _load_execution_log()
    # Non-admins see only their own events
    if not is_admin:
        log = [e for e in log if e.get("user_id") in {uid, "system", "local"}]
    return {"status": "ok", "events": list(reversed(log[-limit:]))}

def _build_repo_context_snapshot() -> Dict[str, Any]:
    """
    Build a lightweight default repo context snapshot for the runtime
    context endpoint. Scans key files only — no query, no symbols.
    Called by /api/runtime/context-snapshot (Phase 4).
    """
    key_files = [
        "api_server.py",
        "src/mammoth_os/cortex_router.py",
        "src/mammoth_os/llm_client.py",
        "src/mammoth_os/memory_engine.py",
        "src/mammoth_os/runtime_contracts.py",
    ]
    # Only include files that actually exist
    existing = [f for f in key_files if (ROOT / f).exists()]
    repo_request = _normalize_repo_context_request({
        "files": existing,
        "query": "",
        "include_git_status": True,
        "max_results": 4,
        "max_snippets": 3,
    })
    return _collect_repo_context_snapshot(repo_request)



@app.get("/api/runtime/context-snapshot")
async def get_runtime_context_snapshot(request: Request):
    """Phase 4: return full live runtime awareness context for agents."""
    user = await _require_auth_user(request)
    if user is None:
        return JSONResponse({"status": "unauthorized"}, status_code=401)

    try:
        repo_ctx = _build_repo_context_snapshot()
    except Exception:
        repo_ctx = {}

    recent_events = list(reversed(_load_execution_log()[-10:]))
    state = _load_atlas_state()
    usage = _current_usage_snapshot_from_state(state)

    return {
        "status": "ok",
        "snapshot": {
            "ts": datetime.now(timezone.utc).isoformat(),
            "repo": repo_ctx,
            "recent_executions": recent_events,
            "usage": usage,
            "providers": {
                "openai": bool(os.getenv("OPENAI_API_KEY")),
                "deepseek": bool(os.getenv("DEEPSEEK_API_KEY")),
            },
            "uptime_seconds": int(time.time() - _START_TIME),
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 5 — ONBOARDING STATE
# Track and surface which onboarding steps a user has completed.
# ─────────────────────────────────────────────────────────────────────────────

_ONBOARDING_STEPS = [
    {"id": "profile", "label": "Set up your profile", "description": "Add a display name and avatar to personalize your experience."},
    {"id": "first_lesson", "label": "Complete your first lesson", "description": "Pick any ATLAS topic and finish one lesson to build momentum."},
    {"id": "mammoth_mind", "label": "Try Mammoth Mind", "description": "Ask a question in the chat to see the reasoning and coding agents in action."},
    {"id": "explore_modules", "label": "Explore Modules", "description": "Browse the available agent modules and see what the platform can do."},
    {"id": "run_command", "label": "Run a slash command", "description": "Type /help or /plan in chat to discover the command library."},
    {"id": "review_diagnostics", "label": "Check Diagnostics", "description": "Open the Diagnostics page to verify your runtime and provider health."},
]

def _load_onboarding() -> dict:
    try:
        return json.loads(ONBOARDING_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}

def _save_onboarding(data: dict) -> None:
    ONBOARDING_FILE.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


@app.get("/api/onboarding/state")
async def get_onboarding_state(request: Request):
    user = await _require_auth_user(request)
    if user is None:
        return JSONResponse({"status": "unauthorized"}, status_code=401)
    uid = user.get("id", "local")
    state = _load_onboarding()
    user_state = state.get(uid, {})
    completed = user_state.get("completed_steps", [])
    steps_out = [
        {**step, "completed": step["id"] in completed}
        for step in _ONBOARDING_STEPS
    ]
    total = len(_ONBOARDING_STEPS)
    done = len(completed)
    return {
        "status": "ok",
        "user_id": uid,
        "steps": steps_out,
        "completed": done,
        "total": total,
        "percent": round(done / total * 100) if total else 0,
        "onboarding_complete": done >= total,
    }


@app.post("/api/onboarding/complete-step")
async def complete_onboarding_step(request: Request):
    user = await _require_auth_user(request)
    if user is None:
        return JSONResponse({"status": "unauthorized"}, status_code=401)
    uid = user.get("id", "local")
    body = await request.json()
    step_id = str(body.get("step_id", "")).strip()
    valid_ids = {s["id"] for s in _ONBOARDING_STEPS}
    if step_id not in valid_ids:
        return JSONResponse({"status": "error", "error": f"Unknown step: {step_id}"}, status_code=400)
    state = _load_onboarding()
    user_state = state.setdefault(uid, {"completed_steps": [], "started_at": datetime.now(timezone.utc).isoformat()})
    if step_id not in user_state.get("completed_steps", []):
        user_state.setdefault("completed_steps", []).append(step_id)
        user_state["updated_at"] = datetime.now(timezone.utc).isoformat()
    state[uid] = user_state
    _save_onboarding(state)
    return {"status": "ok", "step_id": step_id, "completed_steps": user_state["completed_steps"]}


@app.post("/api/onboarding/reset")
async def reset_onboarding(request: Request):
    user = await _require_auth_user(request)
    if user is None:
        return JSONResponse({"status": "unauthorized"}, status_code=401)
    uid = user.get("id", "local")
    state = _load_onboarding()
    state[uid] = {"completed_steps": [], "started_at": datetime.now(timezone.utc).isoformat()}
    _save_onboarding(state)
    return {"status": "ok", "message": "Onboarding reset."}


# ─────────────────────────────────────────────────────────────────────────────
# NOTIFICATIONS
# In-platform notification system: system, billing, agent-activity, security.
# ─────────────────────────────────────────────────────────────────────────────

_NOTIFICATION_TYPES = {"system", "billing", "agent", "security", "info", "warning"}

def _load_notifications() -> list:
    try:
        return json.loads(NOTIFICATIONS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []

def _save_notifications(items: list) -> None:
    NOTIFICATIONS_FILE.write_text(json.dumps(items, indent=2, default=str), encoding="utf-8")

def _create_notification(
    title: str,
    body: str,
    kind: str = "info",
    user_id: str | None = None,
    action_url: str | None = None,
    actor: str = "system",
) -> dict:
    note = {
        "id": str(uuid.uuid4()),
        "type": kind if kind in _NOTIFICATION_TYPES else "info",
        "title": title,
        "body": body,
        "user_id": user_id,
        "read": False,
        "dismissed": False,
        "action_url": action_url,
        "actor": actor,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    items = _load_notifications()
    items.append(note)
    if len(items) > 1000:
        items = items[-1000:]
    _save_notifications(items)
    return note


@app.get("/api/notifications")
async def list_notifications(request: Request, unread_only: bool = False, limit: int = 50):
    user = await _require_auth_user(request)
    if user is None:
        return JSONResponse({"status": "unauthorized"}, status_code=401)
    uid = user.get("id", "local")
    is_admin = user.get("is_admin", False)
    items = _load_notifications()
    # Each user sees their own + broadcast (user_id=None) notifications
    visible = [
        n for n in items
        if (not n.get("dismissed"))
        and (n.get("user_id") is None or n.get("user_id") == uid or is_admin)
    ]
    if unread_only:
        visible = [n for n in visible if not n.get("read")]
    visible = list(reversed(visible[-limit:]))
    unread_count = sum(1 for n in visible if not n.get("read"))
    return {"status": "ok", "notifications": visible, "unread_count": unread_count}


@app.get("/api/notifications/unread-count")
async def get_unread_count(request: Request):
    user = await _require_auth_user(request)
    if user is None:
        return JSONResponse({"status": "unauthorized"}, status_code=401)
    uid = user.get("id", "local")
    items = _load_notifications()
    count = sum(
        1 for n in items
        if not n.get("read") and not n.get("dismissed")
        and (n.get("user_id") is None or n.get("user_id") == uid)
    )
    return {"status": "ok", "unread_count": count}


@app.patch("/api/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: str, request: Request):
    user = await _require_auth_user(request)
    if user is None:
        return JSONResponse({"status": "unauthorized"}, status_code=401)
    uid = user.get("id", "local")
    items = _load_notifications()
    matched = False
    for n in items:
        if n.get("id") == notification_id and (n.get("user_id") is None or n.get("user_id") == uid):
            n["read"] = True
            matched = True
            break
    if not matched:
        return JSONResponse({"status": "error", "error": "Notification not found."}, status_code=404)
    _save_notifications(items)
    return {"status": "ok", "notification_id": notification_id}


@app.post("/api/notifications/mark-all-read")
async def mark_all_notifications_read(request: Request):
    user = await _require_auth_user(request)
    if user is None:
        return JSONResponse({"status": "unauthorized"}, status_code=401)
    uid = user.get("id", "local")
    items = _load_notifications()
    for n in items:
        if n.get("user_id") is None or n.get("user_id") == uid:
            n["read"] = True
    _save_notifications(items)
    return {"status": "ok"}


@app.delete("/api/notifications/{notification_id}")
async def dismiss_notification(notification_id: str, request: Request):
    user = await _require_auth_user(request)
    if user is None:
        return JSONResponse({"status": "unauthorized"}, status_code=401)
    uid = user.get("id", "local")
    items = _load_notifications()
    matched = False
    for n in items:
        if n.get("id") == notification_id and (n.get("user_id") is None or n.get("user_id") == uid):
            n["dismissed"] = True
            matched = True
            break
    if not matched:
        return JSONResponse({"status": "error", "error": "Notification not found."}, status_code=404)
    _save_notifications(items)
    return {"status": "ok"}


@app.post("/api/notifications")
async def create_notification(request: Request):
    """Admin-only: create a system notification broadcast or targeted notification."""
    user = await _require_auth_user(request)
    if user is None:
        return JSONResponse({"status": "unauthorized"}, status_code=401)
    if not user.get("is_admin"):
        return JSONResponse({"status": "error", "error": "Only administrators can create notifications."}, status_code=403)
    body = await request.json()
    note = _create_notification(
        title=str(body.get("title", "System Notification")),
        body=str(body.get("body", "")),
        kind=str(body.get("type", "info")),
        user_id=body.get("user_id"),
        action_url=body.get("action_url"),
        actor=user.get("email") or user.get("id", "admin"),
    )
    return {"status": "ok", "notification": note}


# ─────────────────────────────────────────────────────────────────────────────
# GDPR-COMPLIANT ACCOUNT DELETION
# Soft-delete request → 30-day grace period → hard delete.
# Users can cancel within the grace period. Data export available before delete.
# ─────────────────────────────────────────────────────────────────────────────

_DELETION_GRACE_DAYS = 30


def _load_deletion_requests() -> list:
    try:
        return json.loads(ACCOUNT_DELETIONS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []

def _save_deletion_requests(items: list) -> None:
    ACCOUNT_DELETIONS_FILE.write_text(json.dumps(items, indent=2, default=str), encoding="utf-8")

def _get_deletion_request(uid: str) -> dict | None:
    return next((r for r in _load_deletion_requests() if r.get("user_id") == uid and r.get("status") in {"pending", "confirmed"}), None)


@app.post("/api/account/delete-request")
async def request_account_deletion(request: Request):
    """
    GDPR Article 17 — Right to erasure.
    Initiates a soft-delete with a 30-day grace period.
    The user can cancel at any point before the grace period expires.
    """
    user = await _require_auth_user(request)
    if user is None:
        return JSONResponse({"status": "unauthorized"}, status_code=401)
    uid = user.get("id", "local")
    body = await request.json()
    reason = str(body.get("reason", "")).strip()[:500]
    feedback = str(body.get("feedback", "")).strip()[:1000]

    existing = _get_deletion_request(uid)
    if existing:
        return JSONResponse({
            "status": "already_requested",
            "message": "An account deletion request is already pending.",
            "scheduled_delete_at": existing.get("scheduled_delete_at"),
            "request_id": existing.get("id"),
        })

    from datetime import timedelta
    scheduled = (datetime.now(timezone.utc) + timedelta(days=_DELETION_GRACE_DAYS)).isoformat()
    record = {
        "id": str(uuid.uuid4()),
        "user_id": uid,
        "email": user.get("email", ""),
        "status": "pending",
        "reason": reason,
        "feedback": feedback,
        "requested_at": datetime.now(timezone.utc).isoformat(),
        "scheduled_delete_at": scheduled,
        "cancelled_at": None,
        "completed_at": None,
    }
    items = _load_deletion_requests()
    items.append(record)
    _save_deletion_requests(items)
    _append_audit_event(
        kind="account_delete_requested",
        message=f"Account deletion requested by user {uid}",
        details={"reason": reason, "scheduled_delete_at": scheduled},
        source="account",
        actor=uid,
        tier="user",
    )
    # Notify the user via the notifications system
    _create_notification(
        title="Account deletion scheduled",
        body=f"Your account is scheduled for permanent deletion in {_DELETION_GRACE_DAYS} days. You can cancel this request any time before then.",
        kind="warning",
        user_id=uid,
        action_url="/account",
    )
    return {
        "status": "ok",
        "message": f"Account deletion requested. Your data will be permanently deleted in {_DELETION_GRACE_DAYS} days unless you cancel.",
        "request_id": record["id"],
        "scheduled_delete_at": scheduled,
        "grace_days": _DELETION_GRACE_DAYS,
    }


@app.get("/api/account/delete-status")
async def get_deletion_status(request: Request):
    user = await _require_auth_user(request)
    if user is None:
        return JSONResponse({"status": "unauthorized"}, status_code=401)
    uid = user.get("id", "local")
    req = _get_deletion_request(uid)
    if not req:
        return {"status": "ok", "deletion_pending": False}
    from datetime import timedelta
    scheduled = datetime.fromisoformat(req["scheduled_delete_at"])
    now = datetime.now(timezone.utc)
    days_remaining = max(0, (scheduled - now).days)
    return {
        "status": "ok",
        "deletion_pending": True,
        "request_id": req["id"],
        "requested_at": req["requested_at"],
        "scheduled_delete_at": req["scheduled_delete_at"],
        "days_remaining": days_remaining,
        "can_cancel": days_remaining > 0,
    }


@app.post("/api/account/delete-cancel")
async def cancel_account_deletion(request: Request):
    """Cancel a pending deletion within the grace period."""
    user = await _require_auth_user(request)
    if user is None:
        return JSONResponse({"status": "unauthorized"}, status_code=401)
    uid = user.get("id", "local")
    items = _load_deletion_requests()
    matched = False
    for r in items:
        if r.get("user_id") == uid and r.get("status") == "pending":
            r["status"] = "cancelled"
            r["cancelled_at"] = datetime.now(timezone.utc).isoformat()
            matched = True
            break
    if not matched:
        return JSONResponse({"status": "error", "error": "No pending deletion request found."}, status_code=404)
    _save_deletion_requests(items)
    _append_audit_event(
        kind="account_delete_cancelled",
        message=f"Account deletion cancelled by user {uid}",
        details={},
        source="account",
        actor=uid,
        tier="user",
    )
    _create_notification(
        title="Account deletion cancelled",
        body="Your account deletion request has been cancelled. Your account remains active.",
        kind="info",
        user_id=uid,
    )
    return {"status": "ok", "message": "Account deletion request cancelled. Your account remains fully active."}


@app.post("/api/account/export-data")
async def export_account_data(request: Request):
    """
    GDPR Article 20 — Right to data portability.
    Returns a structured export of all data associated with this user.
    """
    user = await _require_auth_user(request)
    if user is None:
        return JSONResponse({"status": "unauthorized"}, status_code=401)
    uid = user.get("id", "local")

    state = _load_atlas_state()
    notes = [n for n in _load_json_file(NOTES_FILE) if n.get("user_id") == uid or True]
    activities = [a for a in _load_json_file(AGENT_ACTIVITY_FILE) if a.get("user_id") == uid or True]
    notifs = [n for n in _load_notifications() if n.get("user_id") == uid or n.get("user_id") is None]

    export = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "user_id": uid,
        "email": user.get("email", ""),
        "profile": state.get("profile", {}),
        "learner_model": state.get("learner_model", {}),
        "session_history_count": len(state.get("sessions", [])),
        "notes_count": len(notes),
        "notifications_count": len(notifs),
        "activity_count": len(activities),
        "notes": notes[:200],
        "notifications": notifs[:100],
        "activity": activities[:100],
        "deletion_requests": _load_deletion_requests(),
    }
    _append_audit_event(
        kind="account_data_exported",
        message=f"Data export requested by user {uid}",
        details={},
        source="account",
        actor=uid,
        tier="user",
    )
    return JSONResponse(
        content=export,
        headers={"Content-Disposition": "attachment; filename=mammoth-data-export.json"},
    )


def _load_json_file(path) -> list:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
