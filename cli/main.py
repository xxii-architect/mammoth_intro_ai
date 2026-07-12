import argparse
import json
import sys
import asyncio

# Core registries
from mammoth_os.registry.agent_registry import agent_registry
from mammoth_os.engine_registry import EngineRegistry

# Maintenance tools
from mammoth_os.maintenance.diagnostics import run_system_check
from mammoth_os.maintenance.schema_agent import describe_schema

DEFAULT_TEST_USER = "d6c16bc9-fc2a-4efd-8d9e-a95fb6baa448"


# ---------------------------------------------------------
# COMMAND IMPLEMENTATIONS
# ---------------------------------------------------------

def cmd_version(args):
    print("🐘 Mammoth OS Version")
    print(json.dumps({
        "version": "0.4.0",
        "build": "local-dev",
        "python": sys.version,
    }, indent=2))


def cmd_engine_list(args):
    print("🐘 Mammoth OS Engines")
    engines = EngineRegistry.list_engines()
    print(json.dumps(engines, indent=2))


def cmd_agent_list(args):
    print("🐘 Mammoth OS Agents")
    agents = asyncio.run(agent_registry.list_agents())
    # Serialize AgentManifest objects
    agents_json = [a.__dict__ for a in agents]
    print(json.dumps(agents_json, indent=2))


def cmd_health(args):
    print("🐘 Mammoth OS Health Check")
    report = run_system_check(test_user=DEFAULT_TEST_USER)
    print(json.dumps(report, indent=2))


def cmd_status(args):
    print("🐘 Mammoth OS Status")

    engines = EngineRegistry.list_engines()
    agents = asyncio.run(agent_registry.list_agents())

    status = {
        "engines_loaded": len(engines),
        "agents_loaded": len(agents),
        "python_version": sys.version,
    }

    print(json.dumps(status, indent=2))


def cmd_diagnostics(args):
    print("🐘 Mammoth OS Full Diagnostics")

    # System check
    report = run_system_check(test_user=DEFAULT_TEST_USER)

    # Schema (safe fallback)
    schema = describe_schema(schema="atlas")

    # Engines
    engines = EngineRegistry.list_engines()

    # Agents (async)
    agents = asyncio.run(agent_registry.list_agents())
    agents_json = [a.__dict__ for a in agents]

    combined = {
        "system_check": report,
        "schema": schema,
        "engines": engines,
        "agents": agents_json,
    }

    print(json.dumps(combined, indent=2))


def cmd_start(args):
    print("🐘 Mammoth OS Start")
    print("Starting Mammoth OS runtime… (placeholder)")


def cmd_stop(args):
    print("🐘 Mammoth OS Stop")
    print("Stopping Mammoth OS runtime… (placeholder)")


def cmd_check(args):
    report = run_system_check(test_user=DEFAULT_TEST_USER)
    print("🐘 Mammoth OS System Check")
    print(json.dumps(report, indent=2))


def cmd_schema_describe(args):
    info = describe_schema(schema="atlas")
    print("🐘 Mammoth OS Schema (atlas)")
    print(json.dumps(info, indent=2))


# ---------------------------------------------------------
# ARGPARSE ROUTER
# ---------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(
        prog="mammoth",
        description="Mammoth OS Command Line Interface"
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # Version
    p_version = sub.add_parser("version", help="Show Mammoth OS version")
    p_version.set_defaults(func=cmd_version)

    # Engine commands
    p_eng_list = sub.add_parser("engine-list", help="List all engines")
    p_eng_list.set_defaults(func=cmd_engine_list)

    # Agent commands
    p_agent_list = sub.add_parser("agent-list", help="List all agents")
    p_agent_list.set_defaults(func=cmd_agent_list)

    # Health
    p_health = sub.add_parser("health", help="Run health check")
    p_health.set_defaults(func=cmd_health)

    # Status
    p_status = sub.add_parser("status", help="Show system status")
    p_status.set_defaults(func=cmd_status)

    # Diagnostics
    p_diag = sub.add_parser("diagnostics", help="Run full diagnostics")
    p_diag.set_defaults(func=cmd_diagnostics)

    # Start / Stop
    p_start = sub.add_parser("start", help="Start Mammoth OS runtime")
    p_start.set_defaults(func=cmd_start)

    p_stop = sub.add_parser("stop", help="Stop Mammoth OS runtime")
    p_stop.set_defaults(func=cmd_stop)

    # Existing maintenance commands
    p_check = sub.add_parser("check", help="Run system diagnostics")
    p_check.set_defaults(func=cmd_check)

    p_schema = sub.add_parser("schema-describe", help="Describe core schema")
    p_schema.set_defaults(func=cmd_schema_describe)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
