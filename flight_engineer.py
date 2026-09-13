"""Stable, shell-free boundary to the host's validated profile manager."""

from __future__ import annotations

import json
import os
import re
import subprocess
import urllib.request
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
    def _run(argv: list[str], *, timeout: int = 900, input_text: str | None = None) -> str:
        try:
            result = subprocess.run(
                argv,
                check=False,
                capture_output=True,
                text=True,
                input=input_text,
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
        status = self.status()
        active = status.get("active_profile")
        default = status.get("default_profile")
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
                "default": data["id"] == default,
                "context_length": runtime.get("context_length"),
                "parallel_slots": runtime.get("parallel_slots"),
                "gpu_layers": runtime.get("gpu_layers"),
                "kv_cache": runtime.get("kv_cache"),
                "mmproj_offload": runtime.get("mmproj_offload"),
                "batch_size": runtime.get("batch_size"),
                "ubatch_size": runtime.get("ubatch_size"),
                "image_min_tokens": runtime.get("image_min_tokens"),
                "image_max_tokens": runtime.get("image_max_tokens"),
                "model_file": ((data.get("artifacts") or {}).get("model") or {}).get("file"),
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

    def update(self, profile_id: str, *, label: str | None = None,
               runtime: dict[str, Any] | None = None) -> dict[str, Any]:
        profile = self._validate_profile_id(profile_id)
        payload: dict[str, Any] = {}
        if label is not None:
            payload["label"] = label
        if runtime is not None:
            payload["runtime"] = runtime
        self._run(
            ["sudo", "-n", self.control, "update", profile],
            timeout=30,
            input_text=json.dumps(payload),
        )
        return next(item for item in self.profiles() if item["id"] == profile)

    def clone(self, source_id: str, target_id: str, *, label: str) -> dict[str, Any]:
        source = self._validate_profile_id(source_id)
        target = self._validate_profile_id(target_id)
        self._run(
            ["sudo", "-n", self.control, "clone", source, target],
            timeout=30,
            input_text=json.dumps({"label": label}),
        )
        return next(item for item in self.profiles() if item["id"] == target)

    def apply(self, profile_id: str, *, confirm_interrupt: bool = False) -> dict[str, Any]:
        profile = self._validate_profile_id(profile_id)
        if not confirm_interrupt:
            raise FlightEngineerError("applying a profile interrupts local inference; confirmation is required")
        self._run(["sudo", "-n", self.control, "apply", profile], timeout=900)
        return self.status()

    def set_default(self, profile_id: str) -> dict[str, Any]:
        profile = self._validate_profile_id(profile_id)
        self._run(["sudo", "-n", self.control, "set-default", profile], timeout=30)
        return self.status()

    @staticmethod
    def _url_json(url: str, *, timeout: int = 3) -> Any:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return json.loads(response.read())

    @staticmethod
    def _metrics() -> dict[str, float]:
        with urllib.request.urlopen("http://127.0.0.1:8092/metrics", timeout=3) as response:
            content = response.read().decode("utf-8", errors="replace")
        wanted = {
            "llamacpp:requests_processing", "llamacpp:requests_deferred",
            "llamacpp:prompt_tokens_total", "llamacpp:prompt_tokens_cached_total",
            "llamacpp:tokens_predicted_total", "llamacpp:tokens_predicted_seconds_total",
        }
        metrics: dict[str, float] = {}
        for line in content.splitlines():
            if line.startswith("#") or " " not in line:
                continue
            name, value = line.rsplit(" ", 1)
            if name in wanted:
                try:
                    metrics[name.removeprefix("llamacpp:")] = float(value)
                except ValueError:
                    continue
        return metrics

    def telemetry(self) -> dict[str, Any]:
        """Return only aggregate host/runtime telemetry; slot prompt data stays private."""
        try:
            metrics = self._metrics()
            slots = self._url_json("http://127.0.0.1:8092/slots")
            slot_rows = slots if isinstance(slots, list) else []
            total_slots = len(slot_rows)
            active_slots = sum(1 for slot in slot_rows if isinstance(slot, dict) and slot.get("is_processing"))
            contexts = [int(slot.get("n_ctx") or 0) for slot in slot_rows if isinstance(slot, dict)]
            gpu_raw = self._run([
                "nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw,power.limit",
                "--format=csv,noheader,nounits",
            ], timeout=5).splitlines()[0].split(",")
            gpu = [float(value.strip()) for value in gpu_raw]
            meminfo: dict[str, int] = {}
            for line in Path("/proc/meminfo").read_text(encoding="ascii").splitlines():
                if line.startswith(("MemTotal:", "MemAvailable:")):
                    key, value, *_ = line.split()
                    meminfo[key.rstrip(":")] = int(value)
            load_1m = float(Path("/proc/loadavg").read_text(encoding="ascii").split()[0])
            cpu_count = os.cpu_count() or 1
            predicted_seconds = metrics.get("tokens_predicted_seconds_total", 0)
            return {
            "inference": {
                "active": int(metrics.get("requests_processing", active_slots)),
                "queued": int(metrics.get("requests_deferred", 0)),
                "slots": total_slots,
                "context_per_slot": max(contexts, default=0),
                "tokens_predicted_total": int(metrics.get("tokens_predicted_total", 0)),
                "prompt_tokens_total": int(metrics.get("prompt_tokens_total", 0)),
                "prompt_tokens_cached_total": int(metrics.get("prompt_tokens_cached_total", 0)),
                "lifetime_tokens_per_second": round(metrics.get("tokens_predicted_total", 0) / predicted_seconds, 2) if predicted_seconds else 0,
            },
            "system": {
                "gpu_percent": gpu[0], "vram_used_mb": gpu[1], "vram_total_mb": gpu[2],
                "gpu_temperature_c": gpu[3], "gpu_power_w": gpu[4], "gpu_power_limit_w": gpu[5],
                "ram_used_mb": round((meminfo.get("MemTotal", 0) - meminfo.get("MemAvailable", 0)) / 1024),
                "ram_total_mb": round(meminfo.get("MemTotal", 0) / 1024),
                "cpu_load_percent": round(min(100, load_1m / cpu_count * 100), 1),
            },
            }
        except FlightEngineerError:
            raise
        except (OSError, ValueError, IndexError, KeyError, json.JSONDecodeError) as exc:
            raise FlightEngineerError(f"telemetry unavailable: {exc}") from exc
