import argparse
import json
from mammoth_os.maintenance.diagnostics import run_system_check
from mammoth_os.maintenance.schema_agent import describe_schema

DEFAULT_TEST_USER = "d6c16bc9-fc2a-4efd-8d9e-a95fb6baa448"


def cmd_check(args: argparse.Namespace) -> None:
    report = run_system_check(test_user=DEFAULT_TEST_USER)
    print("🐘 Mammoth OS System Check")
    print(json.dumps(report, indent=2))


def cmd_schema_describe(args: argparse.Namespace) -> None:
    info = describe_schema(schema="atlas")
    print("🐘 Mammoth OS Schema (atlas)")
    print(json.dumps(info, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mammoth", description="Mammoth OS Maintenance Console")
    sub = parser.add_subparsers(dest="command", required=True)

    # mammoth maintenance check
    p_check = sub.add_parser("check", help="Run system diagnostics")
    p_check.set_defaults(func=cmd_check)

    # mammoth maintenance schema-describe
    p_schema = sub.add_parser("schema-describe", help="Describe core schema")
    p_schema.set_defaults(func=cmd_schema_describe)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
