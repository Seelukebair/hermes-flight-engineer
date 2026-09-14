"""Hermes Flight Engineer plugin surfaces."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .flight_engineer import FlightEngineer, FlightEngineerError
from .jailbreaks import JailbreakError, JailbreakStore


_PROFILE_INTENT = re.compile(
    r"\b(?:flight engineer|backend profile|model profile|daily driver|smart(?:er)? model|jailbreak|prefill|injection recipe)\b"
    r"|\b(?:switch|change|load|activate|use|rollback|revert)\b.{0,48}"
    r"\b(?:backend|inference|local model|model configuration|profile)\b",
    re.IGNORECASE | re.DOTALL,
)


def _profile_intent_context(user_message: str = "", **_: Any) -> dict[str, str] | None:
    """Expose the operating contract only when a turn concerns backend profiles."""
    if not _PROFILE_INTENT.search(str(user_message or "")):
        return None
    return {"context": (
        "Flight Engineer backend-profile intent detected. Use the `flight_engineer` tool to call status and list "
        "before proposing a change. The stable Hermes route is gemma4-thinker-local/gemma4-thinker and may be "
        "used by native Mixture of Agents. Profiles are mutually exclusive configurations behind that route, not "
        "simultaneously loaded MoA models. Set confirm_interrupt=true only when the user explicitly requested the "
        "disruptive switch. Jailbreak recipes are profile-specific and their protected text is never readable through "
        "the tool; list metadata before changing an assignment or global state. Report returned state; never infer success."
    )}


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
        elif action == "set_default":
            result = engineer.set_default(str(args.get("profile_id") or ""))
        elif action == "list_jailbreaks":
            result = JailbreakStore().list()
        elif action == "set_jailbreak_enabled":
            result = JailbreakStore().configure(enabled=args.get("enabled") is True)
        elif action == "assign_jailbreak":
            result = JailbreakStore().configure(
                profile_id=str(args.get("profile_id") or ""),
                recipe_id=str(args.get("recipe_id") or "") or None,
            )
        else:
            raise FlightEngineerError(f"unsupported action: {action}")
        return json.dumps({"ok": True, "result": result}, sort_keys=True)
    except (FlightEngineerError, JailbreakError) as exc:
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
        elif command == "set-default":
            result = engineer.set_default(args.profile)
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
    set_default = commands.add_parser("set-default", help="Select the profile loaded on the next host boot")
    set_default.add_argument("profile")
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
                    "action": {"type": "string", "enum": ["status", "list", "use", "rollback", "set_default", "list_jailbreaks", "set_jailbreak_enabled", "assign_jailbreak"]},
                    "profile_id": {"type": "string", "description": "Profile id returned by list."},
                    "recipe_id": {"type": "string", "description": "Recipe id returned by list_jailbreaks; omit to clear an assignment."},
                    "enabled": {"type": "boolean", "description": "Global jailbreak-library state for set_jailbreak_enabled."},
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
    ctx.register_hook("pre_llm_call", _profile_intent_context)
    ctx.register_cli_command(
        name="flight-engineer",
        help="Manage validated inference backend profiles",
        description="Inspect, activate, or roll back tested local inference configurations.",
        setup_fn=_setup_cli,
        handler_fn=_cli_handler,
    )
