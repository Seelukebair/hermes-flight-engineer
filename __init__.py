"""Hermes Flight Engineer plugin surfaces."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .flight_engineer import FlightEngineer, FlightEngineerError


def _dispatch(args: dict[str, Any], **_: Any) -> str:
    engineer = FlightEngineer()
    action = str(args.get("action") or "status").strip().lower()
    try:
        if action == "status":
            result: Any = engineer.status()
        elif action == "list":
            result = {"profiles": engineer.profiles()}
        elif action == "use":
            result = engineer.use(
                str(args.get("profile_id") or ""),
                confirm_interrupt=args.get("confirm_interrupt") is True,
            )
        elif action == "rollback":
            result = engineer.rollback(confirm_interrupt=args.get("confirm_interrupt") is True)
        else:
            raise FlightEngineerError(f"unsupported action: {action}")
        return json.dumps({"ok": True, "result": result}, sort_keys=True)
    except FlightEngineerError as exc:
        return json.dumps({"ok": False, "error": str(exc)}, sort_keys=True)


def _cli_handler(args: Any) -> None:
    engineer = FlightEngineer()
    command = getattr(args, "flight_engineer_command", "status") or "status"
    try:
        if command == "status":
            result: Any = engineer.status()
        elif command == "list":
            result = engineer.profiles()
        elif command == "use":
            result = engineer.use(args.profile, confirm_interrupt=args.confirm_interrupt)
        elif command == "rollback":
            result = engineer.rollback(confirm_interrupt=args.confirm_interrupt)
        else:
            raise FlightEngineerError(f"unsupported command: {command}")
        print(json.dumps(result, indent=2, sort_keys=True))
    except FlightEngineerError as exc:
        raise SystemExit(f"flight-engineer: {exc}") from exc


def _setup_cli(parser: Any) -> None:
    commands = parser.add_subparsers(dest="flight_engineer_command")
    commands.add_parser("status", help="Show the active backend profile and service state")
    commands.add_parser("list", help="List validated backend profiles")
    use = commands.add_parser("use", help="Activate a validated backend profile")
    use.add_argument("profile")
    use.add_argument("--confirm-interrupt", action="store_true")
    rollback = commands.add_parser("rollback", help="Return to the preceding accepted profile")
    rollback.add_argument("--confirm-interrupt", action="store_true")
    parser.set_defaults(func=_cli_handler)


def register(ctx: Any) -> None:
    ctx.register_tool(
        name="flight_engineer",
        toolset="flight-engineer",
        description="Inspect or change validated local inference backend profiles.",
        emoji="",
        schema={
            "name": "flight_engineer",
            "description": "Inspect tested backend profiles or perform a confirmed, guarded profile change.",
            "parameters": {
                "type": "object",
                "required": ["action"],
                "properties": {
                    "action": {"type": "string", "enum": ["status", "list", "use", "rollback"]},
                    "profile_id": {"type": "string", "description": "Profile id returned by list."},
                    "confirm_interrupt": {
                        "type": "boolean",
                        "description": "True only after the user explicitly requests a disruptive switch.",
                    },
                },
            },
        },
        handler=_dispatch,
    )
    skill = Path(__file__).parent / "skills" / "flight-engineer" / "SKILL.md"
    ctx.register_skill("flight-engineer", skill)
    ctx.register_cli_command(
        name="flight-engineer",
        help="Manage validated inference backend profiles",
        description="Inspect, activate, or roll back tested local inference configurations.",
        setup_fn=_setup_cli,
        handler_fn=_cli_handler,
    )

