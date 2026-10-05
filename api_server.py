"""
MammothOS Command Center — FastAPI Server
Run: uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload
"""

import ast
import logging
import asyncio
import base64
from copy import deepcopy
import csv
import inspect
import io
import json
import math
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple
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

logger = logging.getLogger("mammoth_os.api")

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse

from mammoth_os.learner_model import build_learner_context, build_lesson_plan, load_learner_model, save_learner_model, set_onboarding_profile, update_learner_model
from mammoth_os.runtime_contracts import build_observability_run, build_runtime_notice, new_trace_id
from mammoth_os.rag_retrieval import get_retriever
from mammoth_os import tutor_delivery
from mammoth_os import message_feedback
from mammoth_os.supabase_client import get_supabase
from mammoth_os.memory_engine import MemoryEngine
from mammoth_os.rag_context_store import get_rag_context_store
from mammoth_os.audit_engine import AuditEngine
from mammoth_os.team_workflows import TeamWorkflowManager, RunbookStep
from mammoth_os.repo_access import RepoAccessPolicy
from mammoth_os.research_quality import strip_reasoning, trim_to_last_sentence
from mammoth_os.telemetry_engine import TelemetryEngine
from mammoth_os.provenance_contract import (
    validate_response,
    enforce_on_release,
    add_trust_metadata,
)

_audit = AuditEngine()
_telemetry = TelemetryEngine(db_path=None)

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
_REPO_POLICY = RepoAccessPolicy.from_env(ROOT, MAMMOTH_DIR)

NOTES_FILE     = MAMMOTH_DIR / "notes.json"
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
GENERATED_DOCS_DIR = Path(os.environ.get("MAMMOTH_GENERATED_DOCS_DIR") or (ROOT / "generated_docs"))
GENERATED_DOC_OWNERS_FILE = MAMMOTH_DIR / "generated_doc_owners.json"
NOTIFICATIONS_FILE = MAMMOTH_DIR / "notifications.json"
ACCOUNT_DELETIONS_FILE = MAMMOTH_DIR / "account_deletion_requests.json"
ONBOARDING_FILE = MAMMOTH_DIR / "onboarding_state.json"
EXECUTION_LOG_FILE = MAMMOTH_DIR / "execution_log.json"
TRUST_METRICS_FILE = MAMMOTH_DIR / "trust_metrics.json"
MESSAGE_FEEDBACK_FILE = MAMMOTH_DIR / "message_feedback.json"

for _f in [NOTES_FILE, BUILDLOG_FILE, SALES_FILE, AGENT_ACTIVITY_FILE, TASKS_FILE, SNAPSHOTS_FILE, ATLAS_EVALS_FILE, AUDIT_LOG_FILE, BETA_FEEDBACK_FILE, NOTIFICATIONS_FILE, ACCOUNT_DELETIONS_FILE, EXECUTION_LOG_FILE, TRUST_METRICS_FILE, MESSAGE_FEEDBACK_FILE]:
    if not _f.exists():
        _f.write_text("[]")
if not AUTH_ADMIN_POLICY_FILE.exists():
    AUTH_ADMIN_POLICY_FILE.write_text(json.dumps({"admin_user_ids": [], "admin_emails": []}, indent=2), encoding="utf-8")
if not ONBOARDING_FILE.exists():
    ONBOARDING_FILE.write_text(json.dumps({}, indent=2), encoding="utf-8")
ATLAS_STATE_DIR.mkdir(exist_ok=True)

_MEMORY_ENGINE = MemoryEngine(config={"storage_path": str(MAMMOTH_DIR / "memory_store.json"), "max_entries": 5000})
_TEAM_WORKFLOW_MANAGER = TeamWorkflowManager(MAMMOTH_DIR)

_AUTH_REQUIRED = str(os.environ.get("MAMMOTH_REQUIRE_AUTH", "")).strip().lower() in {"1", "true", "yes", "on"}
_OWNER_EMAIL = str(os.environ.get("MAMMOTH_OWNER_EMAIL", "")).strip().lower()
_ADMIN_EMAIL_SOURCES = ",".join(
    item for item in [
        str(os.environ.get("MAMMOTH_ADMIN_EMAILS", "")),
        str(os.environ.get("MAMMOTH_ADMIN_EMAILS_LIST", "")),
        _OWNER_EMAIL,
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
    if not user_id or user_id == "local":
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


_TIER_RANK = {"explorer": 0, "pro": 1, "enterprise": 2}


def _require_workspace_tier_api(minimum: str = "pro") -> Optional[JSONResponse]:
    """Server-side twin of the UI tier gates for user-scoped workspace surfaces.

    Admins always pass. Other callers must be signed in and hold ``minimum`` tier
    (or developer access) on their own account state.
    """
    if not _AUTH_REQUIRED or _request_is_admin():
        return None
    if _current_request_user_id("") in {"", "anonymous"}:
        return JSONResponse({"status": "error", "error": "Authentication required"}, status_code=401)
    state = _load_atlas_state()
    tier = str(state.get("tier") or "explorer").strip().lower()
    if bool(state.get("developer_access")) or _TIER_RANK.get(tier, 0) >= _TIER_RANK.get(minimum, 1):
        return None
    return JSONResponse(
        {"status": "error", "error": f"This workspace surface requires the {minimum} tier.", "code": "tier_required", "minimum_tier": minimum},
        status_code=403,
    )


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


# Agents that execute on, or write to, the backend host. Owner/admin only.
_PRIVILEGED_AGENT_IDS = {
    "shell_agent",
    "filesystem_agent",
    "deploy_agent",
    "build_agent",
    "executor_agent",
    "ui_builder_agent",
    "database_agent",
    "config_manager_agent",
    "custodial_agent",
}
_PRIVILEGED_RUNTIME_AGENTS = {"custodial", "shell", "filesystem", "deploy", "build", "executor", "ui_builder", "database"}
_PRIVILEGED_INTENTS = {"shell", "run_tests", "deploy", "build"}


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


def _current_request_user_id(default: str = "local") -> str:
    user_id = str(_REQUEST_USER_ID.get() or "").strip()
    return user_id or default


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


def _run_git_command(args: List[str], *, timeout: int = 45, cwd: str = "") -> Dict[str, Any]:
    command = ["git", *args]
    effective_cwd = cwd.strip() if cwd.strip() else str(ROOT)
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            cwd=effective_cwd,
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
        "owner_id": (existing or {}).get("owner_id") or _current_request_user_id("local"),
        "updated_at": now,
        "created_at": existing.get("created_at") if existing else now,
    }
    if existing:
        task["created_at"] = existing.get("created_at") or now
        tasks = [t for t in tasks if t.get("id") != task_id]
    tasks.append(task)
    _save_tasks(tasks)
    return task


def _visible_tasks() -> List[Dict[str, Any]]:
    """Tasks the current caller may see: all for admins, only their own otherwise.
    Legacy tasks without an ``owner_id`` stay admin-only."""
    tasks = [item for item in _load_tasks() if isinstance(item, dict)]
    if _request_is_admin():
        return tasks
    user_id = _current_request_user_id("")
    if not user_id or user_id == "anonymous":
        return []
    return [task for task in tasks if str(task.get("owner_id") or "") == user_id]


_DOC_OWNERS_LOCK = threading.Lock()


def _record_generated_doc_owner(filename: str) -> None:
    safe = os.path.basename(str(filename or ""))
    if not safe.endswith(".docx"):
        return
    owner = _current_request_user_id("local")
    with _DOC_OWNERS_LOCK:
        owners = _read_json(GENERATED_DOC_OWNERS_FILE, default={})
        owners = owners if isinstance(owners, dict) else {}
        owners.setdefault(safe, owner)
        if len(owners) > 2000:
            owners = dict(list(owners.items())[-2000:])
        _write_json(GENERATED_DOC_OWNERS_FILE, owners)


def _generated_doc_visible(filename: str) -> bool:
    """Admins see every generated doc; others only docs recorded as theirs.
    Docs generated before ownership tracking stay admin-only."""
    if _request_is_admin():
        return True
    user_id = _current_request_user_id("")
    if not user_id or user_id == "anonymous":
        return False
    owners = _read_json(GENERATED_DOC_OWNERS_FILE, default={})
    return isinstance(owners, dict) and str(owners.get(filename) or "") == user_id


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

    # MAMMOTH_OWNER_EMAIL is always admin — owner of the deployment
    if _OWNER_EMAIL:
        emails.add(_OWNER_EMAIL)

    for env_file in (ROOT / ".env", ROOT / ".env.admin"):
        if not env_file.exists():
            continue
        env_values = dotenv_values(env_file)
        emails.update(_split_csv_values(env_values.get("MAMMOTH_ADMIN_EMAILS", ""), lowercase=True))
        emails.update(_split_csv_values(env_values.get("MAMMOTH_ADMIN_EMAILS_LIST", ""), lowercase=True))
        emails.update(_split_csv_values(env_values.get("MAMMOTH_OWNER_EMAIL", ""), lowercase=True))
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

    fallback_used = bool(merged.get("fallback_used"))
    if fallback_used or str(merged.get("active_adapter") or "").strip().lower() == "local":
        merged["state"] = "degraded"
        merged["degraded_mode"] = True
        fallback_reason = str(merged.get("fallback_reason") or "").strip().replace("_", " ")
        if fallback_reason:
            merged["issue"] = (
                "A configured provider fell back to a safe path due to "
                f"{fallback_reason}. MammothOS is still operating, but the runtime is degraded."
            )
        elif not merged.get("issue"):
            merged["issue"] = "MammothOS is operating on a safe fallback path and the runtime is degraded."
        if not merged.get("recommendation"):
            merged["recommendation"] = "Restore the primary provider or credential path to return the runtime to ready mode."
        if not merged.get("next_action"):
            merged["next_action"] = "Inspect provider quota, billing, credentials, or network availability before retrying."

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


def _usage_warning_message(level: str, percent_used: float) -> str:
    if level == "blocked":
        return f"Usage is at {percent_used:.1f}% and hard-cap enforcement is active. New high-cost requests may be blocked."
    if level == "critical":
        return f"Usage is at {percent_used:.1f}%. You are close to the plan limit and should reduce load or upgrade."
    if level == "elevated":
        return f"Usage is at {percent_used:.1f}%, above the warning threshold."
    return f"Usage is at {percent_used:.1f}% and currently within a healthy range."


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

    elapsed_days = max(1.0, float(now.day))
    percent_per_day = round(percent_used / elapsed_days, 3)
    days_to_limit: Optional[float] = None
    projected_limit_at: Optional[str] = None
    if percent_used > 0 and percent_per_day > 0:
        days_to_limit = max(0.0, round((100.0 - percent_used) / percent_per_day, 1))
        projected_dt = now + timedelta(days=days_to_limit)
        projected_limit_at = projected_dt.isoformat()

    remaining_requests = max(0, request_limit - request_units)
    remaining_tokens = max(0, token_limit - tokens)
    recommended_action = (
        "Continue normal usage."
        if warning_level == "normal"
        else "Trim request volume, reduce prompt size, or move to a higher tier."
        if warning_level == "elevated"
        else "Prioritize only essential runs and upgrade capacity as soon as possible."
        if warning_level == "critical"
        else "Usage cap reached. Reduce demand or upgrade before continuing heavy usage."
    )

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
        "warning_message": _usage_warning_message(warning_level, percent_used),
        "warning_threshold": warning_threshold,
        "near_limit": warning_level in {"elevated", "critical", "blocked"},
        "remaining": {
            "requests": remaining_requests,
            "tokens": remaining_tokens,
        },
        "forecast": {
            "percent_per_day": percent_per_day,
            "days_to_limit": days_to_limit,
            "projected_limit_at": projected_limit_at,
        },
        "recommended_action": recommended_action,
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


def _release_gate_snapshot(*, score: float, blockers: List[Dict[str, Any]]) -> Dict[str, Any]:
    threshold = 8.0
    blocker_titles = [str(item.get("title") or "unknown") for item in blockers if isinstance(item, dict)]
    passed = score >= threshold and not blocker_titles
    return {
        "threshold": threshold,
        "passed": passed,
        "status": "ready" if passed else "blocked",
        "score": round(float(score), 1),
        "blocker_count": len(blocker_titles),
        "blocker_titles": blocker_titles,
        "reason": blocker_titles[0] if blocker_titles else ("Release readiness score is below threshold." if score < threshold else ""),
    }


def _health_gate_snapshot(*, services: List[Dict[str, Any]], runtime: Dict[str, Any], env_exists: bool, venv_ok: bool, git_ok: bool) -> Dict[str, Any]:
    red_services = [str(service.get("label") or "unknown") for service in services if service.get("status") == "red"]
    passed = env_exists and venv_ok and git_ok and not red_services and str(runtime.get("state") or "").lower() == "ready"
    blockers = []
    if not env_exists:
        blockers.append("Missing .env configuration")
    if not venv_ok:
        blockers.append("Python virtualenv is unavailable")
    if not git_ok:
        blockers.append("Git repository metadata is unavailable")
    blockers.extend(red_services[:3])
    return {
        "passed": passed,
        "status": "ready" if passed else "blocked",
        "blockers": blockers,
        "healthy_services": len([service for service in services if service.get("status") == "green"]),
        "total_services": len(services),
        "runtime_state": str(runtime.get("state") or "unknown"),
    }


def _eval_gate_snapshot(*, observability: Dict[str, Any]) -> Dict[str, Any]:
    metrics = observability.get("metrics") if isinstance(observability.get("metrics"), dict) else {}
    latest_eval = observability.get("latest_eval") if isinstance(observability.get("latest_eval"), dict) else {}
    eval_runs = int(metrics.get("eval_runs") or 0)
    eval_pass_rate = int(metrics.get("eval_pass_rate") or 0)
    threshold = 80
    if eval_runs <= 0:
        passed = False
        reason = "No ATLAS eval history is available for release gating."
    elif eval_pass_rate >= threshold:
        passed = True
        reason = ""
    else:
        passed = False
        reason = f"Eval pass rate is {eval_pass_rate}% and must reach at least {threshold}% for release."
    blocker_detail = reason or "Eval history is healthy enough for release."
    return {
        "passed": passed,
        "status": "ready" if passed else "blocked",
        "threshold": threshold,
        "eval_runs": eval_runs,
        "eval_pass_rate": eval_pass_rate,
        "latest_eval": latest_eval,
        "reason": reason,
        "blocker_detail": blocker_detail,
    }


def _research_eval_gate_snapshot() -> Dict[str, Any]:
    try:
        from mammoth_os.agents.research_agent import ResearchAgent
    except Exception as exc:
        return {
            "passed": False,
            "status": "blocked",
            "threshold": {"min_sources": 2, "min_citation_coverage": 0.66},
            "reason": f"ResearchAgent import failed: {exc}",
            "blocker_detail": "Research quality gate could not import ResearchAgent.",
            "summary": {},
        }

    try:
        probe = ResearchAgent(router=None).run(
            {
                "prompt": "Validate release-quality evidence synthesis for ATLAS tutor recommendations.",
                "allow_web_lookup": False,
                "max_sources": 2,
                "sources": [
                    {
                        "title": "Release checklist guideline",
                        "summary": "Recommendations should be linked to evidence and explicit validation steps.",
                        "publisher": "Mammoth Internal QA",
                    },
                    {
                        "title": "Research protocol note",
                        "summary": "Conflicting source claims should be surfaced before publishing guidance.",
                        "publisher": "Mammoth Research Ops",
                    },
                ],
            }
        )
    except Exception as exc:
        return {
            "passed": False,
            "status": "blocked",
            "threshold": {"min_sources": 2, "min_citation_coverage": 0.66},
            "reason": f"ResearchAgent probe failed: {exc}",
            "blocker_detail": "Research quality gate execution failed.",
            "summary": {},
        }

    coverage = probe.get("source_coverage") if isinstance(probe.get("source_coverage"), dict) else {}
    contradiction_report = probe.get("contradiction_report") if isinstance(probe.get("contradiction_report"), dict) else {}
    source_count = int(coverage.get("source_count") or 0)
    citation_coverage = float(coverage.get("citation_coverage") or 0.0)
    findings = probe.get("findings") if isinstance(probe.get("findings"), list) else []
    quality_flags = probe.get("quality_flags") if isinstance(probe.get("quality_flags"), list) else []
    alignment_score = float(contradiction_report.get("alignment_score") or 0.0)
    contradiction_scan_enabled = bool(probe.get("workflow_hints", {}).get("contradiction_scan_enabled"))

    passed = (
        source_count >= 2
        and citation_coverage >= 0.66
        and len(findings) >= 2
        and contradiction_scan_enabled
        and "evidence_ranked" in quality_flags
    )
    reason = ""
    if not passed:
        reason = (
            "Research eval gate requires >=2 sources, citation coverage >=0.66, "
            ">=2 findings, ranked evidence, and contradiction scan support."
        )

    return {
        "passed": passed,
        "status": "ready" if passed else "blocked",
        "threshold": {
            "min_sources": 2,
            "min_citation_coverage": 0.66,
            "min_findings": 2,
            "requires_contradiction_scan": True,
        },
        "reason": reason,
        "blocker_detail": reason or "Research quality gate is healthy enough for release.",
        "summary": {
            "source_count": source_count,
            "citation_coverage": citation_coverage,
            "findings": len(findings),
            "alignment_score": alignment_score,
            "quality_flags": quality_flags,
        },
    }


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

# ── Trust Metrics Management ──────────────────────────────────────────────────
def _record_trust_metric(
    endpoint: str,
    response_type: str,
    provider: str,
    confidence: float,
    validation_issues: List[str],
    validation_passed: bool,
) -> None:
    """Record a trust validation metric for telemetry."""
    try:
        metrics = _read_json(TRUST_METRICS_FILE)
        if not isinstance(metrics, list):
            metrics = []
        
        # Keep only last 1000 entries
        if len(metrics) >= 1000:
            metrics = metrics[-900:]
        
        metric = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "endpoint": endpoint,
            "response_type": response_type,
            "provider": provider,
            "confidence": confidence,
            "issue_count": len(validation_issues),
            "validation_passed": validation_passed,
            "issues_sample": validation_issues[:2],  # First 2 issues for trending
        }
        metrics.append(metric)
        TRUST_METRICS_FILE.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    except Exception:
        pass  # Fail silently on telemetry


def _wrap_response_with_trust(
    response: Dict[str, Any],
    endpoint: str,
    response_type: str = "general"
) -> Dict[str, Any]:
    """
    Validate response and add trust metadata before sending to client.
    
    In conservative mode: wraps response with trust info and warnings
    In strict mode: may block low-trust responses
    """
    # Ensure response is a dict
    if not isinstance(response, dict):
        response = {"result": response}
    
    # Make a copy to avoid modifying original
    wrapped = dict(response)
    
    # Run validation and enforcement
    should_release, block_reason, trust_metadata = enforce_on_release(
        response,
        response_type=response_type
    )
    
    # Record telemetry
    _record_trust_metric(
        endpoint=endpoint,
        response_type=response_type,
        provider=trust_metadata.get("provider", "unknown"),
        confidence=float(trust_metadata.get("confidence", 0.0)),
        validation_issues=trust_metadata.get("validation_issues", []),
        validation_passed=trust_metadata.get("validation_passed", False),
    )
    
    # If blocked in strict mode, return error
    if not should_release:
        return {
            "status": "error",
            "error": f"Response blocked: {block_reason}",
            "trust_metadata": trust_metadata,
            "original_response": wrapped,
        }
    
    # In non-strict mode (default), add trust metadata to response
    wrapped["trust_metadata"] = trust_metadata
    
    # Add warning if issues were found
    if trust_metadata.get("trust_warning"):
        wrapped["trust_warning"] = True
        wrapped["trust_warning_reason"] = trust_metadata.get("warning_reason", "Low trust metrics")
    
    return wrapped

# ─────────────────────────────────────────────────────────────────────────────
# /api/status
# ─────────────────────────────────────────────────────────────────────────────





# ─────────────────────────────────────────────────────────────────────────────
# /api/agents
# ─────────────────────────────────────────────────────────────────────────────



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








# ─────────────────────────────────────────────────────────────────────────────
# /api/health
# ─────────────────────────────────────────────────────────────────────────────

def _port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except OSError:
        return False


def _dev_server_port() -> int:
    try:
        return int(str(os.environ.get("MAMMOTH_DEV_SERVER_PORT") or "5173").strip())
    except ValueError:
        return 5173








# ─────────────────────────────────────────────────────────────────────────────
# /api/telemetry/* — Release-gate trust metrics
# ─────────────────────────────────────────────────────────────────────────────















# ─────────────────────────────────────────────────────────────────────────────
# /api/activity + /api/tasks
# ─────────────────────────────────────────────────────────────────────────────





def _require_signed_in_api() -> Optional[JSONResponse]:
    if _AUTH_REQUIRED and not _request_is_admin() and _current_request_user_id("") in {"", "anonymous"}:
        return JSONResponse({"status": "error", "error": "Authentication required"}, status_code=401)
    return None








_INTENT_TO_AGENT_ID = {
    "plant_the_seed": "plant_the_seed_agent",
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
    "research": "research_agent",
    "summarize": "research_agent",
    "research_long_form": "research_agent",
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
    "guide_platform": "mammoth_guide",
    "planning": "planner_agent",
    "plan_goal": "planner_agent",
    "guide": "mammoth_guide",
    "classifier": "classifier_agent",
    "community": "community_engine_agent",
    "search":        "search_agent",
    "coding":        "coding_agent",
    "curriculum":    "curriculum_agent",
    "orchestrator":  "orchestrator_agent",
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
    "mammoth_guide": "mammoth_guide",
    "classifier_agent": "classifier",
    "planner_agent":       "planner",
    "search_agent":        "search",
    "orchestrator_agent":  "orchestrator",
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


_HISTORY_MAX_TURNS = 8
_HISTORY_TURN_CHARS = 1200
_HISTORY_TOTAL_CHARS = 6000
_BACKGROUND_MAX_CHARS = 8000
# Agents whose prompt doubles as a web search query: anchor follow-ups to the thread's subject.
# Every other agent keeps its prompt verbatim; earlier turns reach the model through
# llm_client.conversation_context so agent templates never echo the transcript.
_HISTORY_QUERY_AGENTS = {"research", "search"}
_FOLLOW_UP_MAX_WORDS = 12


def _normalize_conversation_history(raw: Any) -> List[Dict[str, str]]:
    """Validate client-supplied turns and clip them to a bounded window (newest kept)."""
    if not isinstance(raw, list):
        return []
    turns: List[Dict[str, str]] = []
    for item in raw[-_HISTORY_MAX_TURNS:]:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "").strip().lower()
        if role not in {"user", "agent", "assistant"}:
            continue
        text = re.sub(r"\s+", " ", str(item.get("text") or item.get("content") or "")).strip()
        if not text:
            continue
        turns.append({
            "role": "user" if role == "user" else "agent",
            "agent_id": str(item.get("agent_id") or "")[:64],
            "text": _clip_words(text, _HISTORY_TURN_CHARS),
        })
    while turns and sum(len(turn["text"]) for turn in turns) > _HISTORY_TOTAL_CHARS:
        turns.pop(0)
    return turns


def _render_conversation_history(turns: List[Dict[str, str]]) -> str:
    lines = []
    for turn in turns:
        speaker = "User" if turn["role"] == "user" else (turn.get("agent_id") or "Agent")
        lines.append(f"{speaker}: {turn['text']}")
    return "\n".join(lines)


def _apply_conversation_history(payload: Dict[str, Any], turns: List[Dict[str, str]], runtime_agent: str) -> Dict[str, Any]:
    """Expose earlier turns as structured context without rewriting the agent's prompt."""
    updated = dict(payload)
    updated.pop("history", None)
    if not turns:
        return updated
    context = dict(updated.get("context") or {}) if isinstance(updated.get("context"), dict) else {}
    context["conversation"] = _render_conversation_history(turns)
    updated["context"] = context
    prompt = str(updated.get("prompt") or "").strip()
    # Only short prompts lean on the earlier topic; a full question stands on its own.
    is_follow_up = 0 < len(prompt.split()) <= _FOLLOW_UP_MAX_WORDS
    if is_follow_up and runtime_agent in _HISTORY_QUERY_AGENTS:
        subject = next((turn["text"] for turn in turns if turn["role"] == "user"), "")
        if subject and subject.lower() not in prompt.lower():
            updated["prompt"] = f"{prompt} (follow-up on: {_clip_words(subject, 160)})"
    return updated


def _compose_llm_background(turns: List[Dict[str, str]], extra: Any = "") -> str:
    """Background the model sees alongside each agent call: earlier turns and/or earlier plan steps."""
    parts = []
    if turns:
        parts.append(f"Conversation so far:\n{_render_conversation_history(turns)}")
    extra_text = str(extra or "").strip()
    if extra_text:
        parts.append(extra_text)
    return _clip_words("\n\n".join(parts), _BACKGROUND_MAX_CHARS) if parts else ""


def _with_llm_background(background: str, fn: Callable[..., Any], *args: Any) -> Any:
    """Run an agent call (typically in a worker thread) with background scoped to its LLM calls."""
    if not background:
        return fn(*args)
    from mammoth_os.llm_client import conversation_context

    with conversation_context(background):
        return fn(*args)


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


_PLAN_CODING_WORDS = ("build", "implement", "code", "patch", "create", "ui", "feature", "fix", "bug", "refactor", "endpoint", "component")
_PLAN_MARKET_WORDS = ("market", "audience", "position", "messaging", "competitor", "pricing", "customer")
_PLAN_FIELD_OPS_WORDS = ("ops", "operational", "operations", "runbook", "checklist", "launch", "rollout", "deploy")
_PLAN_BRAND_WORDS = ("brand", "stakeholder", "announce", "announcement", "caption", "tagline", "copy", "newsletter", "pitch")


def _objective_mentions(lower_text: str, words: Iterable[str]) -> bool:
    """Whole-word prefix match so 'ops' does not fire on 'stops' or 'ui' on 'build'."""
    pattern = r"\b(?:" + "|".join(re.escape(word) for word in words) + r")"
    return re.search(pattern, lower_text) is not None


def _build_plan_steps(objective: str, plan_profile: str = "balanced", coding_intent: str = "") -> List[Dict[str, Any]]:
    objective = (objective or "").strip()
    lower = objective.lower()
    profile = _normalize_plan_profile(plan_profile)
    effective_coding_intent = _normalize_coding_intent(coding_intent) or _default_coding_intent_for_profile(profile)
    include_coding = profile in {"coding", "coding_only"} or _objective_mentions(lower, _PLAN_CODING_WORDS)
    include_market = profile == "atlas" or _objective_mentions(lower, _PLAN_MARKET_WORDS)
    include_field_ops = profile == "atlas" or _objective_mentions(lower, _PLAN_FIELD_OPS_WORDS)
    include_brand = _objective_mentions(lower, _PLAN_BRAND_WORDS)
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
            "chain_context": True,
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
                "chain_context": True,
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
                "chain_context": True,
            }
        )

    if include_brand:
        steps.append(
            {
                "id": "brand-summary",
                "title": "Produce stakeholder-ready copy",
                "agent_id": "brand_voice_agent",
                "intent": "brand_voice",
                "prompt": f"Write stakeholder-ready copy in brand voice for: {objective}",
                "chain_context": True,
            }
        )

    steps.append(_build_synthesis_step(objective))

    return steps


def _build_synthesis_step(objective: str) -> Dict[str, Any]:
    return {
        "id": "team-synthesis",
        "title": "Synthesize the team's results",
        "agent_id": "orchestrator",
        "intent": "synthesize",
        "kind": "synthesis",
        "prompt": f"Combine every completed step into one brief that answers: {objective}",
    }


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
    recent_activity = [item for item in _load_activity_events() if isinstance(item, dict)][-6:] if _request_is_admin() else []

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


def _lesson_telemetry(state: Dict[str, Any]) -> Dict[str, Any]:
    telemetry = state.get("lesson_telemetry")
    if not isinstance(telemetry, dict):
        telemetry = {}
        state["lesson_telemetry"] = telemetry
    return telemetry


def _attach_delivery_state(state: Dict[str, Any]) -> Dict[str, Any]:
    """Derive the lesson manifest + stall signal for the active lesson (never stored stale)."""
    lesson_id = str(state.get("lesson_id") or "").strip()
    lesson = state.get("current_lesson") if isinstance(state.get("current_lesson"), dict) else {}
    if not lesson_id and not lesson:
        state["lesson_manifest"] = None
        state["lesson_stall"] = None
        return state
    state["lesson_manifest"] = tutor_delivery.build_lesson_manifest(
        lesson,
        state.get("current_exercise") if isinstance(state.get("current_exercise"), dict) else {},
        state.get("curriculum") if isinstance(state.get("curriculum"), dict) else {},
    )
    telemetry = state.get("lesson_telemetry") if isinstance(state.get("lesson_telemetry"), dict) else {}
    state["lesson_stall"] = tutor_delivery.stall_signal(telemetry.get(lesson_id))
    return state


def _decorate_atlas_state(state: Dict[str, Any]) -> Dict[str, Any]:
    _attach_delivery_state(state)
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


_PLAN_DIGEST_SUMMARY_KEYS = (
    "executive_summary", "summary", "synthesis", "hypothesis", "insight", "reflection_summary",
    "market_summary", "situation_summary", "verdict", "answer", "explanation", "output", "response", "text",
)
_PLAN_DIGEST_LIST_KEYS = (
    "findings", "key_facts", "risks", "acceptance_criteria", "recommendations", "recommended_next_steps",
    "validation_steps", "key_trends", "opportunities", "checklist", "highlights", "next_steps",
)
_PLAN_DIGEST_ITEM_KEYS = ("title", "finding", "fact", "risk", "recommendation", "step", "item", "text", "summary", "description", "name")
_PLAN_DIGEST_CHARS = 700
_PLAN_PRIOR_CONTEXT_CHARS = 3600
_PLAN_SYNTHESIS_TIMEOUT_S = 90.0
_PLAN_SYNTHESIS_SYSTEM = (
    "You merge the results of several specialist agents into one brief for the person who asked. "
    "Use only the step results provided. Do not invent facts, sources, or numbers. "
    "Write plain, direct language with no filler. Respond with JSON only: "
    '{"summary": "3-5 sentences that directly answer the objective", '
    '"highlights": ["up to 5 concrete takeaways"], "next_steps": ["up to 5 concrete actions"]}'
)


def _plan_step_output(step_result: Dict[str, Any]) -> Any:
    response = step_result.get("response") if isinstance(step_result, dict) else None
    result = response.get("result") if isinstance(response, dict) else None
    if isinstance(result, dict):
        return result.get("output")
    return None


def _plan_item_text(item: Any) -> str:
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, dict):
        for key in _PLAN_DIGEST_ITEM_KEYS:
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


def _clip_words(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0].rstrip(",;:") + "…"


def _plan_step_digest(step_result: Dict[str, Any], limit: int = _PLAN_DIGEST_CHARS) -> str:
    """Short readable digest of a step's artifact, used to chain context and synthesize."""
    if step_result.get("status") != "completed":
        return ""
    output = _plan_step_output(step_result)
    parts: List[str] = []
    if isinstance(output, str):
        parts.append(output)
    elif isinstance(output, dict):
        if output.get("status") == "error":
            return ""
        for key in _PLAN_DIGEST_SUMMARY_KEYS:
            value = output.get(key)
            if isinstance(value, str) and value.strip():
                parts.append(value.strip())
                break
        for key in _PLAN_DIGEST_LIST_KEYS:
            value = output.get(key)
            if isinstance(value, list):
                items = [text for text in (_plan_item_text(item) for item in value[:3]) if text]
                if items:
                    parts.append(f"{key.replace('_', ' ')}: " + "; ".join(items))
    text = strip_reasoning("\n".join(parts))[0]
    text = re.sub(r"\s+", " ", text).strip()
    if text.startswith("[LOCAL_ADAPTER]"):
        text = text[len("[LOCAL_ADAPTER]"):].strip()
    return _clip_words(text, limit)


def _plan_prior_context(prior: List[Dict[str, Any]], limit: int = _PLAN_PRIOR_CONTEXT_CHARS) -> str:
    """Render earlier step digests, dropping the oldest entries first when over budget."""
    lines = [f"- {entry['title']}: {entry['digest']}" for entry in prior if entry.get("digest")]
    while lines and sum(len(line) + 1 for line in lines) > limit:
        lines.pop(0)
    return "\n".join(lines)


def _plan_fallback_synthesis(objective: str, prior: List[Dict[str, Any]]) -> Dict[str, Any]:
    highlights = []
    for entry in prior:
        digest = str(entry.get("digest") or "")
        first = re.split(r"(?<=[.!?])\s", digest, maxsplit=1)[0]
        if first:
            highlights.append(f"{entry['title']}: {_clip_words(first, 220)}")
    summary = (
        f"{len(prior)} step{'s' if len(prior) != 1 else ''} completed for: {objective}. "
        "The model synthesis was unavailable, so the highlights below come straight from each step."
    )
    return {"summary": summary, "highlights": highlights[:6], "next_steps": [], "method": "digest"}


def _parse_synthesis_json(text: str) -> Dict[str, Any]:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return {}
    try:
        parsed = json.loads(match.group(0))
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _string_list(value: Any, limit: int = 5) -> List[str]:
    if not isinstance(value, list):
        return []
    return [text for text in (_plan_item_text(item) for item in value) if text][:limit]


async def _synthesize_plan_results(objective: str, prior: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Merge completed step digests into one brief; deterministic fallback if the model is unavailable."""
    usable = [entry for entry in prior if entry.get("digest")]
    if not usable:
        return {"summary": "", "highlights": [], "next_steps": [], "method": "none"}
    fallback = _plan_fallback_synthesis(objective, usable)
    message = f"Objective: {objective}\n\nStep results:\n{_plan_prior_context(usable, limit=6000)}"
    try:
        from mammoth_os.llm_client import get_llm_client

        raw = await asyncio.wait_for(
            get_llm_client().generate(
                message,
                system_prompt=_PLAN_SYNTHESIS_SYSTEM,
                max_tokens=700,
                temperature=0.3,
                response_format={"type": "json_object"},
            ),
            timeout=_PLAN_SYNTHESIS_TIMEOUT_S,
        )
    except Exception as exc:  # provider outage must never break the run
        logger.warning("Plan synthesis failed, using digest fallback: %s", exc)
        return fallback
    text, reasoning = strip_reasoning(raw)
    if not text or text.startswith("[LOCAL_ADAPTER]"):
        return fallback
    parsed = _parse_synthesis_json(text)
    summary = str(parsed.get("summary") or "").strip() if parsed else ""
    if not summary:
        if parsed:
            return fallback
        summary = trim_to_last_sentence(text)[0]
    result = {
        "summary": summary,
        "highlights": _string_list(parsed.get("highlights")) if parsed else [],
        "next_steps": _string_list(parsed.get("next_steps")) if parsed else [],
        "method": "llm",
    }
    if reasoning:
        result["reasoning_trace"] = reasoning
    return result


def _plan_run_summary(step_results: List[Dict[str, Any]]) -> str:
    for step in reversed(step_results):
        if step.get("id") == "team-synthesis" and step.get("status") == "completed":
            output = _plan_step_output(step)
            if isinstance(output, dict):
                return str(output.get("summary") or "")
    return ""


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
    prior: List[Dict[str, Any]] = []

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
        prior_context = _plan_prior_context(prior)
        step_prompt = step["prompt"]
        step_background = ""
        if prior_context and step.get("chain_context"):
            step_background = f"Results from earlier steps (build on these, do not repeat them):\n{prior_context}"

        if step.get("kind") == "synthesis":
            synthesis = await _synthesize_plan_results(objective, prior)
            ok = bool(synthesis.get("summary"))
            response = {
                "status": "ok" if ok else "error",
                "agent_id": step["agent_id"],
                "result": {
                    "status": "ok" if ok else "error",
                    "runtime_agent": "synthesis",
                    "output": {key: value for key, value in synthesis.items() if key != "reasoning_trace"},
                },
            }
            if synthesis.get("reasoning_trace"):
                response["reasoning_trace"] = synthesis["reasoning_trace"]
            result_obj = response["result"]
            inner_status = result_obj["status"]
            failure_reason = "" if ok else "No completed steps produced results to synthesize."
        else:
            run_body = {
                "intent": step["intent"],
                "payload": {
                    "prompt": step_prompt,
                    "background": step_background,
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
                        "objective": objective,
                        "prior_steps": prior_context,
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

        if step.get("kind") == "synthesis" and inner_status == "error":
            step_status = "skipped"
        elif response.get("status") != "ok" or inner_status == "error":
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
            "chained_context": bool(prior_context and step.get("chain_context")),
        }
        step_result["digest"] = _plan_step_digest(step_result)
        step_results.append(step_result)
        if step_result["digest"] and step.get("kind") != "synthesis":
            prior.append({"title": step["title"], "agent_id": step["agent_id"], "digest": step_result["digest"]})

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
    elif runtime_agent == "mammoth_guide":
        required = ["message", "guide_steps"]
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
            state["workspace_artifacts"] = _normalize_workspace_artifact_collection(state.get("workspace_artifacts"))
            state["agent_run_history"] = _normalize_agent_run_history_collection(state.get("agent_run_history"))
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
    "workspace_artifacts",
    "agent_run_history",
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


def _normalize_workspace_artifact_record(raw: Any, *, now: Optional[str] = None) -> Optional[Dict[str, Any]]:
    if not isinstance(raw, dict):
        return None
    created_at = str(raw.get("created_at") or now or datetime.now(timezone.utc).isoformat())
    artifact_id = str(raw.get("id") or "").strip() or f"artifact-{uuid.uuid4().hex[:12]}"
    title = str(raw.get("title") or "").strip() or "Saved artifact"
    summary = str(raw.get("summary") or "").strip() or "Saved from MammothOS workspace."
    body = str(raw.get("body") or "").strip()
    if not body:
        return None
    return {
        "id": artifact_id,
        "created_at": created_at,
        "title": title,
        "summary": summary,
        "body": body,
        "path": str(raw.get("path") or "").strip(),
        "source": str(raw.get("source") or "workspace").strip() or "workspace",
        "format": str(raw.get("format") or "txt").strip().lower() or "txt",
        "meta": raw.get("meta") if isinstance(raw.get("meta"), dict) else {},
    }


def _normalize_workspace_artifact_collection(raw_items: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw_items, list):
        return []
    normalized: List[Dict[str, Any]] = []
    seen_ids = set()
    for raw in raw_items:
        item = _normalize_workspace_artifact_record(raw)
        if not item:
            continue
        if item["id"] in seen_ids:
            continue
        seen_ids.add(item["id"])
        normalized.append(item)
    normalized.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
    return normalized[:120]


def _normalize_agent_run_history_entry(raw: Any, *, now: Optional[str] = None) -> Optional[Dict[str, Any]]:
    if not isinstance(raw, dict):
        return None
    created_at = str(raw.get("created_at") or now or datetime.now(timezone.utc).isoformat())
    run_id = str(raw.get("id") or "").strip() or f"run-{uuid.uuid4().hex[:12]}"
    prompt = str(raw.get("prompt") or "").strip()
    if not prompt:
        return None
    entry = dict(raw)
    entry["id"] = run_id
    entry["created_at"] = created_at
    entry["status"] = str(raw.get("status") or "unknown").strip().lower() or "unknown"
    entry["agent_id"] = str(raw.get("agent_id") or "agent").strip() or "agent"
    entry["intent"] = str(raw.get("intent") or "run").strip() or "run"
    entry["prompt"] = prompt
    return entry


def _normalize_agent_run_history_collection(raw_items: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw_items, list):
        return []
    normalized: List[Dict[str, Any]] = []
    seen_ids = set()
    for raw in raw_items:
        item = _normalize_agent_run_history_entry(raw)
        if not item:
            continue
        if item["id"] in seen_ids:
            continue
        seen_ids.add(item["id"])
        normalized.append(item)
    normalized.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
    return normalized[:160]


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
    state["lesson_telemetry"] = {}
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


def _append_study_aid(
    state: Dict[str, Any],
    aid_type: str,
    data: Any,
    *,
    lesson_id: Optional[str] = None,
    lesson_title: Optional[str] = None,
):
    aids = state.get("study_aids") or []
    if not isinstance(aids, list):
        aids = []
    lesson = state.get("current_lesson") or {}
    resolved_lesson_id = str(lesson_id or state.get("lesson_id") or lesson.get("lesson_id") or "").strip()
    resolved_lesson_title = str(
        lesson_title or lesson.get("title") or lesson.get("lesson_title") or ""
    ).strip()
    aids.append({
        "id": str(uuid.uuid4()),
        "type": str(aid_type or "unknown"),
        "lesson_id": resolved_lesson_id,
        "lesson_title": resolved_lesson_title,
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


def _normalize_flashcard_item(raw: Any) -> Optional[Dict[str, Any]]:
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return None
        return {
            "front": text,
            "back": "Recall the concept in your own words, then verify against lesson notes.",
            "source": None,
        }
    if not isinstance(raw, dict):
        return None
    front = str(raw.get("front") or raw.get("q") or raw.get("question") or "").strip()
    back = str(raw.get("back") or raw.get("a") or raw.get("answer") or "").strip()
    if not front or not back:
        return None
    source = raw.get("source")
    if isinstance(source, dict):
        normalized_source = {
            "title": str(source.get("title") or "").strip(),
            "url": str(source.get("url") or "").strip(),
        }
        if not normalized_source["title"] and not normalized_source["url"]:
            source = None
        else:
            source = normalized_source
    else:
        source = None
    return {"front": front, "back": back, "source": source}


def _normalize_flashcard_list(raw_cards: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw_cards, list):
        return []
    normalized: List[Dict[str, Any]] = []
    for card in raw_cards:
        item = _normalize_flashcard_item(card)
        if item:
            normalized.append(item)
    return normalized


def _latest_stored_flashcards(state: Dict[str, Any], *, limit: int = 12) -> List[Dict[str, Any]]:
    aids = state.get("study_aids") or []
    if not isinstance(aids, list):
        return []
    cards: List[Dict[str, Any]] = []
    for raw in reversed(aids):
        if not isinstance(raw, dict):
            continue
        aid_type = str(raw.get("type") or "").strip().lower()
        if aid_type != "flashcards":
            continue
        data = raw.get("data")
        if isinstance(data, dict) and isinstance(data.get("cards"), list):
            source_cards = data.get("cards")
        elif isinstance(data, list):
            source_cards = data
        else:
            source_cards = []
        for card in source_cards:
            item = _normalize_flashcard_item(card)
            if not item:
                continue
            cards.append(item)
            if len(cards) >= limit:
                return cards
    return cards


def _flashcards_to_ui_cards(cards: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    seen = set()
    for index, card in enumerate(cards, start=1):
        front = str(card.get("front") or "").strip()
        back = str(card.get("back") or "").strip()
        if not front or not back:
            continue
        dedupe_key = front.lower()
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        normalized.append(
            {
                "id": str(card.get("id") or f"card-{index}"),
                "q": front,
                "a": back,
                "front": front,
                "back": back,
                "source": card.get("source") if isinstance(card.get("source"), dict) else None,
            }
        )
    return normalized


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
    usage_snapshot = _current_usage_snapshot_from_state(state)
    warning_level = str(usage_snapshot.get("warning_level") or "normal")
    previous_level = str(state.get("last_usage_warning_level") or "normal")
    state["last_usage_warning_level"] = warning_level
    if warning_level in {"elevated", "critical", "blocked"} and warning_level != previous_level:
        user_id = _current_request_user_id()
        message = str(usage_snapshot.get("warning_message") or "Usage warning threshold reached.")
        requests = usage_snapshot.get("usage", {}).get("requests")
        request_limit = usage_snapshot.get("usage", {}).get("request_limit")
        plan = usage_snapshot.get("plan")
        _create_notification(
            title=f"Usage warning: {warning_level}",
            body=f"{message} ({requests}/{request_limit} requests on {plan})",
            kind="billing",
            user_id=user_id,
            action_url="/pricing",
            actor="system",
        )


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
            "chain_context": True,
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



























































def _collect_attached_atlas_material_context(user_id: str, material_ids: List[Any]) -> Dict[str, Any]:
    selected_ids = [str(item).strip() for item in material_ids if str(item).strip()][:6]
    if not selected_ids:
        return {"count": 0, "materials": []}
    index = _load_atlas_files_index(user_id)
    selected: List[Dict[str, Any]] = []
    for file_id in selected_ids:
        entry = next((f for f in index if f.get("file_id") == file_id), None)
        if not isinstance(entry, dict):
            continue
        selected.append(
            {
                "file_id": file_id,
                "name": str(entry.get("name") or "material"),
                "tag": str(entry.get("tag") or "other"),
                "excerpt": str(entry.get("text_preview") or "")[:2800],
            }
        )
    return {"count": len(selected), "materials": selected}






def _clean_web_text(raw: str, *, max_chars: int = 2200) -> str:
    text = str(raw or "")
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_chars:
        return text[:max_chars].rstrip() + "..."
    return text


def _repo_context_evidence_items(repo_context: Dict[str, Any], *, limit: int = 3) -> List[Dict[str, Any]]:
    evidence: List[Dict[str, Any]] = []
    if not isinstance(repo_context, dict):
        return evidence
    for snippet in (repo_context.get("snippets") or []):
        if len(evidence) >= limit:
            break
        if not isinstance(snippet, dict) or snippet.get("status") != "ok":
            continue
        evidence.append(
            {
                "agent_id": "repo-context",
                "source": "repo-snippet",
                "path": str(snippet.get("path") or ""),
                "summary": f"Loaded {snippet.get('path') or 'file'} ({snippet.get('line_count') or 0} lines).",
                "status": "ok",
            }
        )
    for hit in (repo_context.get("search_hits") or []):
        if len(evidence) >= limit:
            break
        if not isinstance(hit, dict):
            continue
        evidence.append(
            {
                "agent_id": "repo-context",
                "source": "repo-search",
                "path": str(hit.get("path") or ""),
                "summary": str(hit.get("preview") or "").strip()[:220],
                "status": "ok",
            }
        )
    warning = str(repo_context.get("root_warning") or "").strip()
    if warning and len(evidence) < limit:
        evidence.append(
            {
                "agent_id": "repo-context",
                "source": "repo-warning",
                "summary": warning,
                "status": "warning",
            }
        )
    return evidence


def _derive_chat_confidence(
    *,
    runtime_status: Dict[str, Any],
    evidence_items: List[Dict[str, Any]],
    reply: str,
    base: float = 0.74,
) -> float:
    confidence = float(base)
    state = str((runtime_status or {}).get("state") or "").lower()
    if state == "ready":
        confidence += 0.08
    elif state in {"degraded", "fallback"}:
        confidence -= 0.14
    elif state in {"error", "down"}:
        confidence -= 0.24
    if (runtime_status or {}).get("error_type"):
        confidence -= 0.08

    count = len([item for item in (evidence_items or []) if isinstance(item, dict)])
    if count >= 1:
        confidence += 0.04
    if count >= 3:
        confidence += 0.03
    if len(str(reply or "").strip()) < 40:
        confidence -= 0.06
    return round(max(0.2, min(0.96, confidence)), 2)


def _build_chat_trust_metadata(
    *,
    provider: str,
    confidence: float,
    evidence_items: List[Dict[str, Any]],
    content: str,
    response_type: str = "general",
) -> Dict[str, Any]:
    citations: List[str] = []
    for item in evidence_items or []:
        if not isinstance(item, dict):
            continue
        for key in ("url", "path", "source", "agent_id"):
            value = str(item.get(key) or "").strip()
            if value and value not in citations:
                citations.append(value)
    _, _, trust_metadata = enforce_on_release(
        {
            "provider": str(provider or "unknown"),
            "confidence": float(confidence),
            "citations": citations[:8],
            "contradictions": [],
            "content": str(content or ""),
        },
        response_type=response_type,
    )
    return trust_metadata


def _public_url_block_reason(url: str) -> str:
    """Return why ``url`` must not be fetched server-side (SSRF guard), or ''."""
    import ipaddress
    import socket

    parsed = urllib.parse.urlparse(str(url or ""))
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return "URL must be absolute and start with http:// or https://"
    host = parsed.hostname.strip("[]").lower()
    if host in {"localhost", "metadata.google.internal"} or host.endswith(".localhost") or host.endswith(".internal"):
        return "URL points at a private or local host."
    try:
        infos = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80), proto=socket.IPPROTO_TCP)
    except (socket.gaierror, UnicodeError, ValueError):
        return "URL host could not be resolved."
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0].split("%", 1)[0])
        except ValueError:
            return "URL host could not be resolved."
        if not ip.is_global or ip.is_multicast:
            return "URL points at a private or local host."
    return ""


class _PublicOnlyRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[override]
        if _public_url_block_reason(newurl):
            raise urllib.error.URLError("Redirect to a private or local host was blocked.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_PUBLIC_URL_OPENER = urllib.request.build_opener(_PublicOnlyRedirectHandler)


def _internet_fetch_url(url: str) -> Dict[str, Any]:
    cleaned = str(url or "").strip()
    parsed = urllib.parse.urlparse(cleaned)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return {"status": "error", "error": "URL must be absolute and start with http:// or https://"}
    blocked_reason = _public_url_block_reason(cleaned)
    if blocked_reason:
        return {"status": "error", "error": blocked_reason}
    req = urllib.request.Request(
        cleaned,
        headers={"User-Agent": "MammothOS/1.0 (+https://command.truexxiisupply.com)"},
    )
    try:
        with _PUBLIC_URL_OPENER.open(req, timeout=10) as resp:
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
    from mammoth_os.agents.research_agent import ResearchAgent

    result = ResearchAgent(router=None).run(
        {
            "prompt": q,
            "focus": "general",
            "max_sources": 5,
            "allow_web_lookup": True,
        }
    )
    sources = result.get("sources") if isinstance(result.get("sources"), list) else []
    highlights = []
    for item in sources:
        if not isinstance(item, dict) or str(item.get("source_type") or "").strip().lower() != "web":
            continue
        snippet = str(item.get("snippet") or "").strip()
        if not snippet:
            continue
        matched_tokens = item.get("matched_tokens") if isinstance(item.get("matched_tokens"), list) else []
        relevance_score = float(item.get("relevance_score") or 0.0)
        if relevance_score <= 0 and not matched_tokens:
            continue
        highlights.append(
            {
                "title": str(item.get("title") or "Primary finding").strip() or "Primary finding",
                "snippet": snippet,
                "url": str(item.get("url") or "").strip(),
                "publisher": str(item.get("publisher") or "").strip(),
            }
        )
        if len(highlights) >= 5:
            break

    retrieval_errors = result.get("retrieval_errors") if isinstance(result.get("retrieval_errors"), list) else []
    if not highlights:
        detail = f" Retrieval notes: {', '.join(str(err) for err in retrieval_errors[:2])}." if retrieval_errors else ""
        return {
            "status": "ok",
            "query": q,
            "highlights": [],
            "summary": f"No grounded internet highlights were found for this query.{detail}",
            "retrieval_errors": retrieval_errors,
        }

    summary_lines = [f"Internet research brief for: {q}"]
    for idx, item in enumerate(highlights, start=1):
        publisher = f" [{item['publisher']}]" if item.get("publisher") else ""
        url = f" ({item['url']})" if item.get("url") else ""
        summary_lines.append(f"{idx}. {item['snippet']}{publisher}{url}")
    return {
        "status": "ok",
        "query": q,
        "highlights": highlights,
        "summary": "\n".join(summary_lines),
        "retrieval_errors": retrieval_errors,
    }


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
    if command == "/guide":
        prompt = " ".join(tokens[1:]).strip()
        if not prompt:
            return {"kind": "error", "error": "Usage: /guide <question>"}
        return {"kind": "guide", "message": prompt}
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


def _path_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except (ValueError, OSError):
        return False


def _safe_repo_relative_path(raw_path: Any, *, repo_root: Any = None) -> str:
    candidate = str(raw_path or "").strip().replace("\\", "/")
    if not candidate:
        return ""
    path_obj = Path(candidate)
    if path_obj.is_absolute():
        if repo_root:
            try:
                path_obj = path_obj.relative_to(Path(str(repo_root)))
            except ValueError:
                return ""
        else:
            return ""
    if any(part in {"..", ""} for part in path_obj.parts):
        return ""
    return str(Path(*path_obj.parts)).replace("\\", "/")


def _repo_context_query_tokens(text: str, *, max_tokens: int = 8) -> List[str]:
    tokens = re.findall(r"[a-zA-Z0-9_]{3,}", str(text or "").lower())
    stop = {
        "the",
        "and",
        "for",
        "with",
        "that",
        "this",
        "from",
        "into",
        "your",
        "repo",
        "file",
        "path",
        "scan",
        "check",
    }
    ordered: List[str] = []
    for token in tokens:
        if token in stop:
            continue
        if token not in ordered:
            ordered.append(token)
        if len(ordered) >= max_tokens:
            break
    return ordered


def _extract_repo_file_hints(text: str, *, max_hints: int = 8) -> List[str]:
    query = str(text or "")
    hints: List[str] = []
    patterns = [
        r"(?:[A-Za-z]:[\\/]|/)(?:[A-Za-z0-9_.\-]+[\\/])*[A-Za-z0-9_.\-]+\.[A-Za-z0-9]{1,8}",
        r"(?:[A-Za-z0-9_.\-]+[\\/])+[A-Za-z0-9_.\-]+\.[A-Za-z0-9]{1,8}",
        r"\b[A-Za-z0-9_.\-]+\.(?:py|js|jsx|ts|tsx|md|json|toml|ya?ml|sql|sh|ps1)\b",
    ]
    for pattern in patterns:
        for match in re.findall(pattern, query):
            candidate = str(match).strip().strip(".,:;()[]{}<>\"'").replace("\\", "/")
            if not candidate:
                continue
            if candidate not in hints:
                hints.append(candidate)
            if len(hints) >= max_hints:
                return hints
    return hints


def _list_tracked_repo_files(git_ref: str, *, cwd: str) -> List[str]:
    for args in (["ls-tree", "-r", "--name-only", git_ref], ["ls-files"]):
        result = _run_git_command(args, timeout=60, cwd=cwd)
        if result.get("status") != "ok":
            continue
        files: List[str] = []
        for line in str(result.get("stdout") or "").splitlines():
            cleaned = _safe_repo_relative_path(line)
            if cleaned:
                files.append(cleaned)
        if files:
            return files
    return []


def _resolve_repo_file_hint_to_tracked_path(hint: str, *, tracked_files: List[str], repo_root: str) -> str:
    if not hint:
        return ""
    normalized = _safe_repo_relative_path(hint, repo_root=repo_root) or _safe_repo_relative_path(hint)
    if not normalized:
        normalized = str(hint).strip().replace("\\", "/").lstrip("./")
    if not normalized:
        return ""

    tracked_set = set(tracked_files)
    if normalized in tracked_set:
        return normalized

    lowered = normalized.lower()
    suffix_matches = [path for path in tracked_files if path.lower().endswith(lowered)]
    if suffix_matches:
        suffix_matches.sort(key=len)
        return suffix_matches[0]

    base = Path(normalized).name.lower()
    if base:
        base_matches = [path for path in tracked_files if Path(path).name.lower() == base]
        if base_matches:
            base_matches.sort(key=len)
            return base_matches[0]
    return ""


def _resolve_repo_context_root(raw_root: Any) -> Dict[str, str]:
    """Resolve a requested repo reference through the server-side access policy.

    Empty -> no repo context. The platform repo is owner/admin-only; everyone
    else can only reach repositories they connected (see /api/mammoth/repo-sources).
    """
    resolution = _REPO_POLICY.resolve(
        raw_root,
        user_id=_current_request_user_id(),
        is_admin=_request_is_admin(),
    )
    if resolution.scope == "denied":
        _append_audit_event(
            kind="repo_context_denied",
            message="Repository context request denied by access policy",
            details={"requested_root": resolution.requested_root[:200]},
            source="repo_access",
            actor=_current_request_user_id(),
        )
    return resolution.as_dict()


def _repo_context_denied_notice(raw_repo_context: Any) -> Dict[str, Any]:
    """Explain to the client why a repo request produced no context."""
    if not isinstance(raw_repo_context, dict) or not str(raw_repo_context.get("root") or "").strip():
        return {}
    resolution = _resolve_repo_context_root(raw_repo_context.get("root"))
    if resolution.get("scope") != "denied":
        return {}
    return {"scope": "denied", "requested_root": resolution.get("requested_root"), "root_warning": resolution.get("root_warning")}


def _normalize_repo_context_request(raw_repo_context: Any) -> Dict[str, Any]:
    if not isinstance(raw_repo_context, dict):
        return {}
    root_resolution = _resolve_repo_context_root(raw_repo_context.get("root"))
    if not root_resolution.get("root"):
        return {}
    files_raw = raw_repo_context.get("files") if isinstance(raw_repo_context.get("files"), list) else []
    files = []
    for value in files_raw:
        cleaned = _safe_repo_relative_path(value, repo_root=root_resolution["root"])
        if cleaned:
            files.append(cleaned)
        if len(files) >= 12:
            break
    symbols_raw = raw_repo_context.get("symbols") if isinstance(raw_repo_context.get("symbols"), list) else []
    symbols = [str(item).strip() for item in symbols_raw if str(item).strip()][:12]
    query = str(raw_repo_context.get("query") or "").strip()
    branch = str(raw_repo_context.get("branch") or "HEAD").strip() or "HEAD"
    # No leading '-' (git option injection) and no '..' (ref ranges).
    if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9._/\-]{0,120}", branch) or ".." in branch:
        branch = "HEAD"
    return {
        "query": query[:240],
        "files": files,
        "symbols": symbols,
        "branch": branch,
        "root": root_resolution["root"],
        "scope": root_resolution.get("scope", ""),
        "source_id": root_resolution.get("source_id", ""),
        "slug": root_resolution.get("slug", ""),
        "requested_root": root_resolution["requested_root"],
        "root_warning": root_resolution["root_warning"],
        "include_git_status": bool(raw_repo_context.get("include_git_status", True)),
        "max_results": max(1, min(12, int(raw_repo_context.get("max_results") or 4))),
        "max_snippets": max(1, min(8, int(raw_repo_context.get("max_snippets") or 3))),
    }


def _read_repo_file_excerpt(relative_path: str, *, repo_root: Any = None, max_lines: int = 120, max_chars: int = 3600) -> Dict[str, Any]:
    base = Path(str(repo_root or ROOT))
    target = base / relative_path
    if target.is_symlink() or not _path_within(target, base):
        return {"path": relative_path, "status": "error", "error": "path escapes repository root"}
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


def _read_repo_file_excerpt_from_ref(
    relative_path: str,
    git_ref: str,
    *,
    max_lines: int = 120,
    max_chars: int = 3600,
    cwd: str = "",
) -> Dict[str, Any]:
    result = _run_git_command(["show", f"{git_ref}:{relative_path}"], cwd=cwd)
    if result.get("status") != "ok":
        return {
            "path": relative_path,
            "status": "error",
            "ref": git_ref,
            "error": str(result.get("stderr") or "unable to read git ref content"),
        }
    raw = str(result.get("stdout") or "")
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
        "ref": git_ref,
    }


def _collect_repo_context_snapshot(repo_request: Dict[str, Any]) -> Dict[str, Any]:
    if not repo_request or not str(repo_request.get("root") or "").strip():
        return {}

    repo_cwd = str(repo_request.get("root")).strip()
    scope = str(repo_request.get("scope") or "")
    # Never echo server filesystem paths for tenant sandboxes back to clients.
    root_label = str(repo_request.get("slug") or "") if scope == "tenant" else repo_cwd

    snapshot: Dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "query": str(repo_request.get("query") or ""),
        "symbols": list(repo_request.get("symbols") or []),
        "files": list(repo_request.get("files") or []),
        "branch": str(repo_request.get("branch") or "main"),
        "root": root_label,
        "scope": scope,
        "source_id": str(repo_request.get("source_id") or ""),
        "requested_root": str(repo_request.get("requested_root") or ""),
        "snippets": [],
        "search_hits": [],
    }
    if repo_request.get("root_warning"):
        snapshot["root_warning"] = str(repo_request.get("root_warning"))

    if repo_request.get("include_git_status"):
        git_status = _run_git_command(["status", "--short", "--branch"], cwd=repo_cwd)
        snapshot["git_status"] = {
            "status": git_status.get("status"),
            "stdout": str(git_status.get("stdout") or "")[:2400],
            "stderr": str(git_status.get("stderr") or "")[:600],
        }

    git_ref = str(repo_request.get("branch") or "main")
    tracked_files: List[str] = []
    snippet_paths: List[str] = []
    for relative_path in (repo_request.get("files") or [])[: int(repo_request.get("max_snippets") or 3)]:
        snippet = _read_repo_file_excerpt_from_ref(relative_path, git_ref, cwd=repo_cwd)
        if snippet.get("status") != "ok":
            snippet = _read_repo_file_excerpt(relative_path, repo_root=repo_cwd)
            if snippet.get("status") == "ok":
                snippet["ref"] = "working-tree"
        snapshot["snippets"].append(snippet)
        if snippet.get("status") == "ok":
            snippet_paths.append(str(snippet.get("path") or ""))

    query = str(repo_request.get("query") or "").strip()
    if len(snapshot["snippets"]) < int(repo_request.get("max_snippets") or 3):
        hints = _extract_repo_file_hints(query)
        if hints:
            tracked_files = _list_tracked_repo_files(git_ref, cwd=repo_cwd)
        for hint in hints:
            if len(snapshot["snippets"]) >= int(repo_request.get("max_snippets") or 3):
                break
            resolved = _resolve_repo_file_hint_to_tracked_path(hint, tracked_files=tracked_files, repo_root=repo_cwd)
            if not resolved or resolved in snippet_paths:
                continue
            snippet = _read_repo_file_excerpt_from_ref(resolved, git_ref, cwd=repo_cwd)
            if snippet.get("status") != "ok":
                snippet = _read_repo_file_excerpt(resolved, repo_root=repo_cwd)
                if snippet.get("status") == "ok":
                    snippet["ref"] = "working-tree"
            snapshot["snippets"].append(snippet)
            if snippet.get("status") == "ok":
                snippet_paths.append(resolved)
        if hints:
            snapshot["resolved_file_hints"] = snippet_paths[:]

    query_lower = query.lower()
    if query:
        max_hits = int(repo_request.get("max_results") or 4)
        query_terms = [query]
        query_terms.extend(_repo_context_query_tokens(query))
        for term in query_terms:
            if len(snapshot["search_hits"]) >= max_hits:
                break
            # "-e" keeps user text from being parsed as a git option (e.g. --open-files-in-pager).
            grep_result = _run_git_command(["grep", "-n", "-I", "--no-color", "-F", "-i", "-e", term, git_ref, "--"], timeout=60, cwd=repo_cwd)
            if grep_result.get("status") != "ok":
                continue
            for line in str(grep_result.get("stdout") or "").splitlines():
                if len(snapshot["search_hits"]) >= max_hits:
                    break
                parts = line.split(":", 3)
                if len(parts) < 4:
                    continue
                _, hit_path, hit_line, hit_preview = parts
                normalized_path = str(hit_path).replace("/", "\\")
                if any(str(item.get("path") or "") == normalized_path and int(item.get("line") or 0) == int(hit_line) for item in snapshot["search_hits"]):
                    continue
                snapshot["search_hits"].append(
                    {
                        "path": normalized_path,
                        "line": int(hit_line) if str(hit_line).isdigit() else 0,
                        "preview": str(hit_preview).strip()[:280],
                        "ref": git_ref,
                    }
                )
            if snapshot["search_hits"]:
                break
        else:
            skipped_dirs = {".git", "node_modules", "dist", "__pycache__", ".venv", "venv", ".mammoth"}
            walk_root = Path(repo_cwd)
            for path in walk_root.rglob("*"):
                if len(snapshot["search_hits"]) >= max_hits:
                    break
                if not path.is_file() or path.is_symlink():
                    continue
                if any(part in skipped_dirs for part in path.parts):
                    continue
                if path.suffix.lower() not in {".py", ".ts", ".tsx", ".js", ".jsx", ".md", ".json", ".toml", ".yaml", ".yml"}:
                    continue
                try:
                    file_text = path.read_text(encoding="utf-8")
                except Exception:
                    continue
                lowered = file_text.lower()
                index = lowered.find(query_lower)
                if index < 0:
                    for token in _repo_context_query_tokens(query):
                        index = lowered.find(token)
                        if index >= 0:
                            break
                if index < 0:
                    continue
                start = max(0, index - 120)
                end = min(len(file_text), index + 220)
                try:
                    rel = str(path.relative_to(walk_root)).replace("/", "\\")
                except ValueError:
                    rel = str(path).replace("/", "\\")
                snapshot["search_hits"].append(
                    {
                        "path": rel,
                        "preview": file_text[start:end].replace("\n", " ").strip()[:280],
                        "ref": "working-tree",
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

























# ─────────────────────────────────────────────────────────────────────────────
# Chat Thread Storage paths
# ─────────────────────────────────────────────────────────────────────────────
CHAT_THREADS_DIR = MAMMOTH_DIR / "chat_threads"
CHAT_THREADS_DIR.mkdir(exist_ok=True)
USER_UPLOADS_DIR = MAMMOTH_DIR / "uploads"
USER_UPLOADS_DIR.mkdir(exist_ok=True)
ATLAS_FILES_DIR = MAMMOTH_DIR / "atlas_files"
ATLAS_FILES_DIR.mkdir(exist_ok=True)


def _thread_dir(user_id: str) -> Path:
    safe = re.sub(r"[^a-z0-9_-]", "-", str(user_id or "local").strip().lower()).strip("-") or "local"
    d = CHAT_THREADS_DIR / safe
    d.mkdir(exist_ok=True)
    return d


def _thread_index_path(user_id: str) -> Path:
    return _thread_dir(user_id) / "_index.json"


def _thread_msg_path(user_id: str, thread_id: str) -> Path:
    safe_tid = re.sub(r"[^a-z0-9_-]", "-", str(thread_id or "").strip().lower()).strip("-") or "unknown"
    return _thread_dir(user_id) / f"{safe_tid}.json"


def _load_thread_index(user_id: str) -> List[Dict[str, Any]]:
    p = _thread_index_path(user_id)
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_thread_index(user_id: str, index: List[Dict[str, Any]]) -> None:
    _thread_index_path(user_id).write_text(json.dumps(index, indent=2, default=str), encoding="utf-8")


def _load_thread_messages(user_id: str, thread_id: str) -> List[Dict[str, Any]]:
    p = _thread_msg_path(user_id, thread_id)
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_thread_messages(user_id: str, thread_id: str, messages: List[Dict[str, Any]]) -> None:
    _thread_msg_path(user_id, thread_id).write_text(json.dumps(messages, indent=2, default=str), encoding="utf-8")


def _find_rated_chat_exchange(
    user_id: str,
    account_id: str,
    *,
    run_id: str = "",
    created_at: str = "",
    thread_id: str = "",
) -> Optional[Tuple[Dict[str, Any], str]]:
    """Locate an assistant reply the requester owns, plus the user prompt before it.

    Only the requester's own scoped chat history and thread files are searched, so a
    rating can never attach to (or reveal) another user's conversation.
    """
    run_id = str(run_id or "").strip()
    created_at = str(created_at or "").strip()
    if not run_id and not created_at:
        return None

    def _matches(item: Dict[str, Any]) -> bool:
        if item.get("role") != "assistant":
            return False
        if run_id:
            return str(item.get("run_id") or "") == run_id
        return str(item.get("created_at") or "") == created_at

    candidates: List[List[Dict[str, Any]]] = []
    if thread_id:
        candidates.append([m for m in _load_thread_messages(user_id, thread_id) if isinstance(m, dict)])
    state = _load_atlas_state()
    history = state.get("mammoth_chat_history") if isinstance(state.get("mammoth_chat_history"), list) else []
    candidates.append([
        item for item in history
        if isinstance(item, dict)
        and str(item.get("user_id") or "") == user_id
        and _normalize_account_id(item.get("account_id") or "default") == account_id
    ])
    for messages in candidates:
        for index in range(len(messages) - 1, -1, -1):
            if not _matches(messages[index]):
                continue
            prompt = next(
                (str(messages[j].get("message") or "") for j in range(index - 1, -1, -1) if messages[j].get("role") == "user"),
                "",
            )
            return messages[index], prompt
    return None


def _load_message_feedback() -> List[Dict[str, Any]]:
    records = _read_json(MESSAGE_FEEDBACK_FILE, default=[])
    return [item for item in records if isinstance(item, dict)] if isinstance(records, list) else []


def _upsert_thread_index_entry(user_id: str, thread_id: str, *, title: str = "", agent_id: str = "assistant", message_count: int = 0) -> None:
    index = _load_thread_index(user_id)
    now_iso = datetime.now(timezone.utc).isoformat()
    entry = next((t for t in index if t.get("id") == thread_id), None)
    if entry:
        entry["updated_at"] = now_iso
        entry["message_count"] = message_count
        if title:
            entry["title"] = title
    else:
        index.append({
            "id": thread_id,
            "title": title or "New conversation",
            "agent_id": agent_id,
            "created_at": now_iso,
            "updated_at": now_iso,
            "message_count": message_count,
        })
    index.sort(key=lambda t: str(t.get("updated_at") or ""), reverse=True)
    _save_thread_index(user_id, index[:200])


# ─────────────────────────────────────────────────────────────────────────────
# /api/mammoth/chat/threads  — thread CRUD
# ─────────────────────────────────────────────────────────────────────────────











# ─────────────────────────────────────────────────────────────────────────────
# /api/mammoth/files — file uploads for chat context
# ─────────────────────────────────────────────────────────────────────────────

def _user_uploads_dir(user_id: str) -> Path:
    safe = re.sub(r"[^a-z0-9_-]", "-", str(user_id or "local").strip().lower()).strip("-") or "local"
    d = USER_UPLOADS_DIR / safe
    d.mkdir(exist_ok=True)
    return d


def _uploads_index_path(user_id: str) -> Path:
    return _user_uploads_dir(user_id) / "_index.json"


def _load_uploads_index(user_id: str) -> List[Dict[str, Any]]:
    p = _uploads_index_path(user_id)
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_uploads_index(user_id: str, index: List[Dict[str, Any]]) -> None:
    _uploads_index_path(user_id).write_text(json.dumps(index, indent=2, default=str), encoding="utf-8")


_ALLOWED_UPLOAD_EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".jsx", ".md", ".txt", ".json", ".toml", ".yaml", ".yml", ".csv", ".html", ".css", ".sh", ".sql", ".pdf"}
_MAX_UPLOAD_BYTES = 4 * 1024 * 1024  # 4MB


def _extract_text_preview(content_bytes: bytes, filename: str, max_chars: int = 8000) -> str:
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        try:
            import io
            import struct
            # Very basic PDF text extraction — just pull printable ASCII runs
            raw = content_bytes.decode("latin-1", errors="replace")
            import re as _re
            runs = _re.findall(r"[A-Za-z0-9 .,;:!?@/\\()-]{20,}", raw)
            return "\n".join(runs)[:max_chars]
        except Exception:
            return "[PDF content — text extraction failed]"
    try:
        return content_bytes.decode("utf-8", errors="replace")[:max_chars]
    except Exception:
        return "[Binary content]"


from fastapi import UploadFile, File, Form








# ─────────────────────────────────────────────────────────────────────────────
# /api/atlas/files — ATLAS lesson material uploads
# ─────────────────────────────────────────────────────────────────────────────

def _atlas_files_dir(user_id: str) -> Path:
    safe = re.sub(r"[^a-z0-9_-]", "-", str(user_id or "local").strip().lower()).strip("-") or "local"
    d = ATLAS_FILES_DIR / safe
    d.mkdir(exist_ok=True)
    return d


def _atlas_files_index_path(user_id: str) -> Path:
    return _atlas_files_dir(user_id) / "_index.json"


def _load_atlas_files_index(user_id: str) -> List[Dict[str, Any]]:
    p = _atlas_files_index_path(user_id)
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_atlas_files_index(user_id: str, index: List[Dict[str, Any]]) -> None:
    _atlas_files_index_path(user_id).write_text(json.dumps(index, indent=2, default=str), encoding="utf-8")


_ATLAS_ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md", ".docx", ".csv", ".py", ".js", ".ts", ".json", ".html"}
_ATLAS_TAGS = {"textbook", "homework", "notes", "worksheet", "practice", "other"}














# ── Repo sources (tenant-scoped, Phase 1) ────────────────────────────────────

def _repo_sources_payload(user_id: str) -> Dict[str, Any]:
    sources = [_REPO_POLICY.public_source(item) for item in _REPO_POLICY.list_sources(user_id)]
    options: List[Dict[str, Any]] = []
    if _request_is_admin():
        options.append({"id": "platform", "value": "platform", "label": "MammothOS platform (owner only)", "scope": "platform"})
    for item in sources:
        options.append({"id": item.get("id"), "value": item.get("id"), "label": item.get("slug"), "scope": "tenant", "status": item.get("status")})
    return {"status": "ok", "sources": sources, "options": options, "limit": 5, "write_mode": "proposal_only"}












_PUBLIC_GUIDE_DOCS = [
    "docs/public/mammoth_mind_user_guide.md",
    "docs/public/mammoth_paths_sdk_guide.md",
    "docs/atlas_fab_product_guide.md",
    "docs/mammoth_os_package_offering.md",
]


def _collect_public_docs_context(query: str, *, max_snippets: int = 3) -> Dict[str, Any]:
    """Curated, publishable docs for the MammothOS Guide. Never platform source code."""
    snippets: List[Dict[str, Any]] = []
    hits: List[Dict[str, Any]] = []
    tokens = _repo_context_query_tokens(query)
    for rel in _PUBLIC_GUIDE_DOCS:
        path = ROOT / rel
        if not path.is_file():
            continue
        if len(snippets) < max_snippets:
            excerpt = _read_repo_file_excerpt(rel, repo_root=ROOT, max_lines=80, max_chars=2400)
            if excerpt.get("status") == "ok":
                excerpt["ref"] = "public-docs"
                snippets.append(excerpt)
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except Exception:
            continue
        for idx, line in enumerate(lines, start=1):
            if len(hits) >= 4:
                break
            lowered = line.lower()
            if tokens and any(token in lowered for token in tokens):
                hits.append({"path": rel, "line": idx, "preview": line.strip()[:280], "ref": "public-docs"})
    if not snippets and not hits:
        return {}
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "public_docs",
        "root": "mammothos-docs",
        "branch": "published",
        "query": str(query or "")[:240],
        "snippets": snippets,
        "search_hits": hits,
    }




# ─────────────────────────────────────────────────────────────────────────────
# Mammoth Mind agent runs — typed run events, permissioned tools, MCP
# ─────────────────────────────────────────────────────────────────────────────

from mammoth_os.agent_loop import (  # noqa: E402
    AgentRun,
    AgentRunner,
    MCPBridge,
    RunStore,
    ToolContext,
    ToolRegistry,
    ToolSpec,
    TIER_NETWORK,
    TIER_READ,
    EVENT_CONTRACT_VERSION,
    register_query_tool,
    register_repo_tools,
)

_URL_ARG_SCHEMA = {
    "type": "object",
    "properties": {"url": {"type": "string", "minLength": 8, "maxLength": 2000}},
    "required": ["url"],
    "additionalProperties": False,
}


def _agent_tool_docs(query: str, ctx: ToolContext) -> Dict[str, Any]:
    docs = _collect_public_docs_context(query, max_snippets=2)
    if not docs:
        return {"status": "ok", "snippets": [], "note": "No published MammothOS docs matched."}
    return {"status": "ok", "snippets": docs.get("snippets") or [], "hits": docs.get("search_hits") or []}


async def _agent_tool_research(query: str, ctx: ToolContext) -> Dict[str, Any]:
    result = await asyncio.to_thread(_run_internet_command, {"kind": "research", "query": query})
    return {"status": result.get("status") or "error", "summary": str(result.get("reply") or "")[:6000], "evidence": result.get("evidence")}


async def _agent_tool_fetch(args: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
    result = await asyncio.to_thread(_internet_fetch_url, str(args.get("url") or ""))
    if result.get("status") != "ok":
        return {"status": "error", "error": result.get("error") or "Fetch failed."}
    return {"status": "ok", "url": result.get("url"), "title": result.get("title"), "content": str(result.get("summary") or "")[:8000]}


async def _agent_tool_web_search(query: str, ctx: ToolContext) -> Dict[str, Any]:
    from mammoth_os.web_search import web_search

    result = await asyncio.to_thread(web_search, query, 6)
    if result.get("status") != "ok":
        return {"status": "error", "code": result.get("code"), "error": result.get("error") or "Web search failed."}
    return {"status": "ok", "provider": result.get("provider"), "results": result.get("results") or []}


def _build_agent_tool_registry() -> "tuple[ToolRegistry, MCPBridge]":
    from mammoth_os.web_search import default_web_search

    registry = ToolRegistry()
    register_repo_tools(registry)
    # Registered only when a licensed provider key is configured (env change → restart).
    if default_web_search().configured():
        register_query_tool(
            registry,
            name="web_search",
            description="Search the public web. Returns titles, URLs, and snippets; use web_fetch to read a result.",
            tier=TIER_NETWORK,
            trace_kind="searched",
            handler=_agent_tool_web_search,
        )
    register_query_tool(
        registry,
        name="docs_search",
        description="Search the published MammothOS / ATLAS / SDK user documentation.",
        tier=TIER_READ,
        trace_kind="searched",
        handler=_agent_tool_docs,
    )
    register_query_tool(
        registry,
        name="web_research",
        description="Research a topic on the public internet and return a sourced summary.",
        tier=TIER_NETWORK,
        trace_kind="fetched",
        handler=_agent_tool_research,
    )
    registry.register(ToolSpec(
        name="web_fetch",
        description="Fetch a public web page (http/https, public hosts only) and return its readable text.",
        input_schema=_URL_ARG_SCHEMA,
        tier=TIER_NETWORK,
        handler=_agent_tool_fetch,
        trace_kind="fetched",
    ))
    bridge = MCPBridge(ROOT)
    bridge.register(registry)
    return registry, bridge


_AGENT_TOOLS, _AGENT_MCP = _build_agent_tool_registry()
_AGENT_RUNS = RunStore(MAMMOTH_DIR / "agent_runs")


def _agent_llm_factory():
    from mammoth_os.llm_client import get_llm_client

    return get_llm_client()


_AGENT_RUNNER = AgentRunner(_AGENT_TOOLS, _agent_llm_factory, _AGENT_RUNS)


def _agent_tool_context(raw_repo_context: Any) -> "tuple[ToolContext, Dict[str, Any]]":
    """Build a ToolContext for the current request. Repo access goes through the policy."""
    user_id = _current_request_user_id()
    is_admin = _request_is_admin()
    raw_root = raw_repo_context.get("root") if isinstance(raw_repo_context, dict) else raw_repo_context
    notice: Dict[str, Any] = {}
    resolution = _resolve_repo_context_root(raw_root) if str(raw_root or "").strip() else {"scope": "none"}
    root_text = str(resolution.get("root") or "")
    scope = str(resolution.get("scope") or "none")
    if scope == "denied":
        notice = {"code": "repo_access_denied", "message": resolution.get("root_warning") or "Repository access denied."}
    repo_root = Path(root_text) if root_text and scope in {"platform", "tenant", "local_path"} else None
    ctx = ToolContext(
        user_id=user_id,
        is_admin=is_admin,
        repo_root=repo_root if repo_root is not None and repo_root.is_dir() else None,
        repo_scope=scope if repo_root is not None else "none",
        repo_slug=str(resolution.get("slug") or ("platform" if scope == "platform" else "")),
        repo_source_id=str(resolution.get("source_id") or ""),
        policy=_REPO_POLICY,
    )
    return ctx, notice


def _agent_history_text(user_id: str, account_id: str, limit: int = 6) -> str:
    state = _load_atlas_state()
    items = [
        item for item in (state.get("mammoth_chat_history") or [])
        if isinstance(item, dict)
        and str(item.get("user_id") or "") == user_id
        and _normalize_account_id(item.get("account_id") or "default") == account_id
    ][-limit:]
    return "\n".join(f"{item.get('role', 'unknown')}: {str(item.get('message') or '')[:500]}" for item in items)


AGENT_RUN_SURFACES = {"mind", "agent_workspace"}

# Server-owned task briefs for the Agent page's Coding lane. Clients pick a key; they never
# supply instruction text, so a run cannot be re-prompted through this field.
_AGENT_TASK_BRIEFS: Dict[str, str] = {
    "generate_code": (
        "Task: write new code. If a repository is connected, read neighbouring files first so the code matches "
        "existing conventions, then propose new or changed files with repo_propose_patch."
    ),
    "patch_existing": (
        "Task: patch existing files. Find and read the relevant files with the repo tools before changing anything. "
        "Propose small exact edits with repo_propose_patch. Never guess file contents you have not read."
    ),
    "refactor_code": (
        "Task: refactor. Read the target code and its callers first, keep behaviour identical, and propose the "
        "change with repo_propose_patch. Call out anything that could change behaviour."
    ),
    "analyze_codebase": (
        "Task: review code. Read the relevant files and report concrete risks with file paths and line numbers. "
        "Do not propose patches unless the user asks for them."
    ),
    "run_tests": (
        "Task: write a validation plan. Read the changed area and the existing tests, then list the exact checks "
        "and test cases to run. Do not claim tests were executed."
    ),
    "write_docs": (
        "Task: write documentation. Read the code being documented so every statement is accurate; propose doc "
        "files with repo_propose_patch when a repository is connected."
    ),
}


def _agent_task_brief(task: Any) -> str:
    return _AGENT_TASK_BRIEFS.get(str(task or "").strip().lower(), "")


def _client_history_text(history: Any, *, turns: int = 8, chars: int = 800) -> str:
    """Conversation turns supplied by a client surface (the Agent page keeps its own threads)."""
    if not isinstance(history, list):
        return ""
    lines: List[str] = []
    for item in history[-turns:]:
        if not isinstance(item, dict):
            continue
        role = "user" if str(item.get("role") or "") == "user" else "assistant"
        text = str(item.get("text") or item.get("message") or "").strip()
        if text:
            lines.append(f"{role}: {text[:chars]}")
    return "\n".join(lines)


def _persist_agent_run_exchange(run: AgentRun, *, thread_id: str = "") -> None:
    state = _load_atlas_state()
    account_id = _active_account_id(state)
    all_history = state.get("mammoth_chat_history") if isinstance(state.get("mammoth_chat_history"), list) else []
    now_iso = datetime.now(timezone.utc).isoformat()
    exchange = [
        {"role": "user", "message": run.message, "created_at": run.created_at, "agent_id": run.agent_id, "mode": "agent",
         "user_id": run.user_id, "account_id": account_id},
        {"role": "assistant", "message": run.reply, "created_at": now_iso, "agent_id": run.agent_id, "mode": "agent",
         "adapter": run.provider, "model": run.model, "run_id": run.id, "user_id": run.user_id, "account_id": account_id},
    ]
    state["mammoth_chat_history"] = (all_history + exchange)[-400:]
    state["updated_at"] = now_iso
    _save_atlas_state(state)
    if thread_id:
        try:
            messages = _load_thread_messages(run.user_id, thread_id) + exchange
            _save_thread_messages(run.user_id, thread_id, messages[-120:])
            first_user = next((m.get("message", "") for m in messages if m.get("role") == "user"), "")
            title = (first_user.strip()[:60] + "…") if len(first_user.strip()) > 60 else first_user.strip()
            _upsert_thread_index_entry(run.user_id, thread_id, title=title or "Conversation", agent_id=run.agent_id, message_count=len(messages))
        except Exception:
            pass


def _agent_run_stream(run: AgentRun, events_iter, *, thread_id: str = "") -> StreamingResponse:
    async def event_stream():
        async for event in events_iter:
            yield event.to_sse()
            # Agent-page runs live in that page's own threads, not Mammoth Mind's chat history.
            if event.type == "run.completed" and run.request.get("surface") != "agent_workspace":
                try:
                    _persist_agent_run_exchange(run, thread_id=thread_id)
                except Exception:
                    pass

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "X-Mammoth-Run-Id": run.id},
    )



















# ─────────────────────────────────────────────────────────────────────────────
# /api/notes
# ─────────────────────────────────────────────────────────────────────────────













# ─────────────────────────────────────────────────────────────────────────────
# /api/buildlog
# ─────────────────────────────────────────────────────────────────────────────

def _buildlog_entry_visible(entry: Any, user_id: str, is_admin: bool) -> bool:
    if not isinstance(entry, dict):
        return False
    owner = str(entry.get("user_id") or "").strip()
    if not owner:
        # Entries written before tenant scoping belong to the operator.
        return is_admin
    return owner == user_id






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
    user_id = str(raw.get("user_id") or _current_request_user_id()).strip() or "local"
    account_id = _normalize_account_id(raw.get("account_id") or "default")

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
        "user_id": user_id,
        "account_id": account_id,
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

    score = 100
    findings: List[str] = []
    interface_mode = "async" if isinstance(run_node, ast.AsyncFunctionDef) else "sync" if run_node else "specialized"
    lowered = text.lower()
    placeholder_markers = [
        marker for marker in (
            "implement later",
            "deeper logic later",
            "stub response",
            "tbd implementation",
        )
        if marker in lowered
    ]
    is_base_agent_class = class_node.name == "BaseAgent"

    if not inherits_base_agent and not is_base_agent_class:
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
    {"id": "mammoth_guide", "name": "MammothGuideAgent", "version": "v1.0.0", "status": "active", "description": "Repo-aware onboarding and SDK/ATLAS usage guidance"},
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



async def _release_readiness_snapshot() -> Dict[str, Any]:
    modules = await get_modules()
    health = await get_health()
    entitlements = await get_entitlements()
    account = await get_account_profile()
    runtime = health.get("runtime") if isinstance(health.get("runtime"), dict) else _runtime_status_snapshot()
    eval_history = _load_eval_history()
    observability = _build_atlas_observability({"learner_model": {}, "plan_history": [], "fab_usage_events": []}, eval_history=eval_history)
    eval_gate = _eval_gate_snapshot(observability=observability)
    research_gate = _research_eval_gate_snapshot()

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

    research_score = 8.8 if research_gate.get("passed") else 5.8
    overall_score = round(((runtime_score * 0.35) + (module_score * 0.35) + (observability_score * 0.15) + (research_score * 0.15)), 1)

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
    if not eval_gate["passed"]:
        blockers.append({
            "title": "ATLAS eval moat is below release threshold",
            "severity": "high",
            "detail": eval_gate["blocker_detail"],
        })
    if not research_gate["passed"]:
        blockers.append({
            "title": "Research quality gate is below release threshold",
            "severity": "high",
            "detail": research_gate["blocker_detail"],
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
        "release_gate": _release_gate_snapshot(score=overall_score, blockers=blockers),
        "scores": {
            "runtime": runtime_score,
            "modules": module_score,
            "observability": observability_score,
            "research": research_score,
        },
        "summary": {
            "rated_modules": len(rated_modules),
            "healthy_services": int(health.get("summary", {}).get("healthy_services") or 0),
            "total_services": int(health.get("summary", {}).get("total_services") or 0),
            "cloud_providers_ready": cloud_ready,
            "non_local_providers_ready": non_local_ready,
            "eval_runs": eval_gate["eval_runs"],
            "eval_pass_rate": eval_gate["eval_pass_rate"],
            "research_gate_status": research_gate.get("status"),
        },
        "runtime": runtime,
        "eval_gate": eval_gate,
        "research_gate": research_gate,
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






# ─────────────────────────────────────────────────────────────────────────────
# /api/team/workflow-templates, /api/team/approval-policies, /api/team/runbooks
# ─────────────────────────────────────────────────────────────────────────────














































# ─────────────────────────────────────────────────────────────────────────────
# /api/terminal/exec  (HTTP fallback — returns full output at once)
# ─────────────────────────────────────────────────────────────────────────────



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
    "uname -a",
    "uname -r",
    "whoami",
    "hostname",
    "date",
    "uptime",
    "id",
    "env",
    "printenv",
    "python --version",
    "python3 --version",
    "pip --version",
    "pip list",
    "pip freeze",
    "df -h",
    "df -H",
    "free -m",
    "free -h",
    "ps aux",
    "ps -ef",
    "top -b -n 1",
    "htop",
    "systemctl status mammothos",
    "systemctl list-units --type=service",
    "journalctl -u mammothos -n 50 --no-pager",
    "journalctl -u mammothos -n 100 --no-pager",
}

ALLOW_PREFIXES = (
    "npm ",
    "uvicorn ",
    "cat ",
    "ls",
    "ls ",
    "dir",
    "dir ",
    "git ",
    "python -m cli.main",
    "python -m pytest",
    "python3 -m pytest",
    "py -m cli.main",
    "pytest",
    "python --version",
    "python3 --version",
    "python3 -m ",
    "python ",
    "pip list",
    "pip freeze",
    "pip show ",
    "pip install ",
    "systemctl status ",
    "systemctl restart ",
    "systemctl stop ",
    "systemctl start ",
    "journalctl -u ",
    "journalctl --unit",
    "tail ",
    "head ",
    "grep ",
    "find ",
    "echo ",
    "env",
    "printenv",
    "which ",
    "uname",
    "df ",
    "free ",
    "ps ",
    "top ",
    "whoami",
    "hostname",
    "date",
    "uptime",
    "id",
    "curl -s ",
    "curl --silent ",
    "wget -q ",
)


TERMINAL_BLOCKED_SEQUENCES = ("&&", "||", ";", "|", ">", "<", "`")
CLI_ROOTS = ("python -m cli.main", "python3 -m cli.main", "py -m cli.main")
CLI_TOP_LEVEL_COMMANDS = {"version", "engine-list", "agent-list", "health", "status", "diagnostics", "check", "schema-describe", "list", "run", "inspect"}
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

    if os.name == "nt":
        # Windows: translate Unix-isms to PowerShell equivalents
        if normalized == "pwd":
            normalized = "Get-Location | Select-Object -ExpandProperty Path"
        elif normalized in ("ls", "ls -la", "ls -l"):
            normalized = "Get-ChildItem | Format-Table Name,Length,LastWriteTime"
        elif normalized.startswith("cat "):
            normalized = "Get-Content " + normalized[4:]
    # Linux/Mac: pwd/ls/cat work natively — no translation needed

    # npm commands run from the UI directory
    if normalized.startswith("npm "):
        run_cwd = UI_DIR if UI_DIR.exists() else ROOT

    # Resolve venv python (python / python3 / py prefixes)
    if VENV_PYTHON.exists():
        for py_prefix in ("python3 -m cli.main", "python -m cli.main", "py -m cli.main"):
            if normalized.startswith(py_prefix):
                remainder = normalized[len(py_prefix):]
                if os.name == "nt":
                    normalized = f'& "{VENV_PYTHON}" -m cli.main{remainder}'
                else:
                    normalized = f'"{VENV_PYTHON}" -m cli.main{remainder}'
                break
        else:
            for py_prefix in ("python3 -m ", "python -m ", "py -m "):
                if normalized.startswith(py_prefix):
                    remainder = normalized[len(py_prefix):]
                    if os.name == "nt":
                        normalized = f'& "{VENV_PYTHON}" -m {remainder}'
                    else:
                        normalized = f'"{VENV_PYTHON}" -m {remainder}'
                    break

    # Resolve venv uvicorn
    if VENV_UVICORN.exists() and normalized.startswith("uvicorn "):
        remainder = normalized[len("uvicorn"):]
        if os.name == "nt":
            normalized = f'& "{VENV_UVICORN}"{remainder}'
        else:
            normalized = f'"{VENV_UVICORN}"{remainder}'

    return normalized, run_cwd


def _run_command_sync(resolved: str, run_cwd: Path, env: dict, timeout: int) -> Dict[str, Any]:
    """Run command synchronously via subprocess.run (cross-platform)."""
    try:
        if os.name == "nt":
            shell_cmd = ["powershell", "-NoProfile", "-NonInteractive", "-Command", resolved]
        else:
            shell_cmd = ["bash", "-c", resolved]
        result = subprocess.run(
            shell_cmd,
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
    if any(stripped.startswith(p) for p in (
        "python -m cli.main atlas code ", "py -m cli.main atlas code ",
        "python3 -m cli.main atlas code ",
    )):
        return 180
    if any(stripped.startswith(p) for p in (
        "python -m cli.main atlas ui ", "py -m cli.main atlas ui ",
        "python3 -m cli.main atlas ui ",
    )):
        return 120
    if stripped.startswith("npm run build"):
        return 300
    if stripped.startswith(("pip install ", "npm install")):
        return 180
    return 60


async def _execute_terminal_command(cmd: str, timeout: Optional[int] = None) -> Dict[str, Any]:
    resolved, run_cwd = _normalize_terminal_command(cmd)
    env = _make_env()
    resolved_timeout = timeout if timeout is not None else _terminal_timeout_for(cmd)
    result = await asyncio.to_thread(_run_command_sync, resolved, run_cwd, env, resolved_timeout)
    result["timeout_seconds"] = resolved_timeout
    return result




























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
    # "platform" resolves only for the owner/admin; everyone else gets no repo context.
    repo_request = _normalize_repo_context_request({
        "root": "platform",
        "files": existing,
        "query": "",
        "include_git_status": True,
        "max_results": 4,
        "max_snippets": 3,
    })
    return _collect_repo_context_snapshot(repo_request)





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












# ---------------------------------------------------------------------------
# RAG Context Store endpoints (Sweep 2)
# ---------------------------------------------------------------------------







# ---------------------------------------------------------------------------
# ATLAS Lesson Ingestion endpoint (Sweep 3)
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# Audit Engine endpoints (Sweep 4)
# ---------------------------------------------------------------------------







def _load_json_file(path) -> list:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []


ROUTE_FRAGMENT_DIR = ROOT / "server_routes"
_ROUTE_FRAGMENT_FILES = (
    "runtime_routes.py",
    "atlas_routes.py",
    "mammoth_routes.py",
    "team_routes.py",
    "workspace_routes.py",
    "governance_routes.py",
)
_ROUTE_FRAGMENTS_LOADED = False


def _exec_route_fragment(name: str) -> None:
    fragment = ROUTE_FRAGMENT_DIR / name
    code = compile(fragment.read_text(encoding="utf-8"), str(fragment), "exec")
    exec(code, globals(), globals())


def _load_route_fragments() -> None:
    global _ROUTE_FRAGMENTS_LOADED
    if _ROUTE_FRAGMENTS_LOADED:
        return
    for name in _ROUTE_FRAGMENT_FILES:
        _exec_route_fragment(name)
    _ROUTE_FRAGMENTS_LOADED = True


_load_route_fragments()
