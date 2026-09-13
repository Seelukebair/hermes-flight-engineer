"""Stable, shell-free boundary to the host's validated profile manager."""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any


PROFILE_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
DEFAULT_MANAGER = "/usr/local/bin/jarvis-model-profile"
DEFAULT_CONTROL = "/usr/local/libexec/flight-engineer-control"
DEFAULT_PROFILE_DIR = "/srv/gemma4-production/profiles"
STABLE_PROVIDER = "gemma4-thinker-local"
STABLE_MODEL = "gemma4-thinker"


class FlightEngineerError(RuntimeError):
    """A bounded profile operation failed."""


class FlightEngineer:
    def __init__(
        self,
        *,
        manager: str | None = None,
        control: str | None = None,
        profile_dir: str | Path | None = None,
    ) -> None:
        self.manager = manager or os.getenv("FLIGHT_ENGINEER_MANAGER", DEFAULT_MANAGER)
        self.control = control or os.getenv("FLIGHT_ENGINEER_CONTROL", DEFAULT_CONTROL)
        self.profile_dir = Path(profile_dir or os.getenv("FLIGHT_ENGINEER_PROFILE_DIR", DEFAULT_PROFILE_DIR))

    @staticmethod
    def _validate_profile_id(profile_id: str) -> str:
        value = str(profile_id or "").strip()
        if not PROFILE_ID.fullmatch(value):
            raise FlightEngineerError("invalid profile id")
        return value

    @staticmethod
    def _run(argv: list[str], *, timeout: int = 900) -> str:
        try:
            result = subprocess.run(
                argv,
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise FlightEngineerError(str(exc)) from exc
        output = (result.stdout or "").strip()
        error = (result.stderr or "").strip()
        if result.returncode:
            raise FlightEngineerError((error or output or f"command exited {result.returncode}")[:1000])
        return output

    def status(self) -> dict[str, Any]:
        raw = self._run([self.manager, "status"], timeout=15)
        try:
            status = json.loads(raw)
        except (TypeError, json.JSONDecodeError) as exc:
            raise FlightEngineerError("profile manager returned invalid status JSON") from exc
        if not isinstance(status, dict):
            raise FlightEngineerError("profile manager returned an invalid status object")
        status["stable_route"] = {"provider": STABLE_PROVIDER, "model": STABLE_MODEL}
        return status

    def profiles(self) -> list[dict[str, Any]]:
        active = self.status().get("active_profile")
        profiles: list[dict[str, Any]] = []
        for path in sorted(self.profile_dir.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(data, dict) or data.get("id") != path.stem:
                continue
            runtime = data.get("runtime") if isinstance(data.get("runtime"), dict) else {}
            profiles.append({
                "id": data["id"],
                "label": str(data.get("label") or data["id"]),
                "status": str(data.get("status") or "unknown"),
                "description": str(data.get("description") or ""),
                "active": data["id"] == active,
                "context_length": runtime.get("context_length"),
                "parallel_slots": runtime.get("parallel_slots"),
                "gpu_layers": runtime.get("gpu_layers"),
                "kv_cache": runtime.get("kv_cache"),
            })
        return profiles

    def use(self, profile_id: str, *, confirm_interrupt: bool = False) -> dict[str, Any]:
        profile = self._validate_profile_id(profile_id)
        if not confirm_interrupt:
            raise FlightEngineerError("profile changes interrupt local inference; confirmation is required")
        self._run(["sudo", "-n", self.control, "use", profile], timeout=900)
        return self.status()

    def rollback(self, *, confirm_interrupt: bool = False) -> dict[str, Any]:
        if not confirm_interrupt:
            raise FlightEngineerError("rollback interrupts local inference; confirmation is required")
        self._run(["sudo", "-n", self.control, "rollback"], timeout=900)
        return self.status()

