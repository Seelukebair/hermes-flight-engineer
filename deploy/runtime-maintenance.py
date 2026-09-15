#!/usr/bin/env python3
"""Stage, smoke-test, and promote pinned llama.cpp runtime images."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROFILE_DIR = Path(os.environ.get("FLIGHT_ENGINEER_PROFILE_DIR", "/srv/gemma4-production/profiles"))
STATE_FILE = Path(os.environ.get("FLIGHT_ENGINEER_UPDATE_STATE", "/srv/gemma4-production/runtime-update.json"))
BACKUP_DIR = Path(os.environ.get("FLIGHT_ENGINEER_PROFILE_BACKUPS", "/srv/gemma4-production/profile-backups"))
MANAGER = os.environ.get("FLIGHT_ENGINEER_MANAGER", "/usr/local/bin/jarvis-model-profile")
PROFILE_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
PINNED_IMAGE = re.compile(r"^(?P<repo>[a-z0-9._/-]+)@sha256:[0-9a-f]{64}$")
CHANNEL = re.compile(r"^(?P<repo>[a-z0-9._/-]+):(?P<tag>[A-Za-z0-9._-]+)$")
TEST_PROFILE = "flight-engineer-runtime-test"
REQUIRED_FLAGS = (
    "--cache-type-k", "--cache-type-v", "--image-min-tokens", "--image-max-tokens",
    "--jinja", "--metrics", "--mmproj", "--parallel",
)


class MaintenanceError(RuntimeError):
    pass


def _run(argv: list[str], *, timeout: int = 900, check: bool = True) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise MaintenanceError(str(exc)) from exc
    if check and result.returncode:
        message = (result.stderr or result.stdout or f"command exited {result.returncode}").strip()
        raise MaintenanceError(message[-2000:])
    return result


def _profile_path(profile_id: str) -> Path:
    if not PROFILE_ID.fullmatch(profile_id):
        raise MaintenanceError("invalid profile id")
    return PROFILE_DIR / f"{profile_id}.json"


def _load_profile(profile_id: str) -> dict[str, Any]:
    path = _profile_path(profile_id)
    try:
        profile = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MaintenanceError(f"cannot read profile {profile_id}: {exc}") from exc
    if not isinstance(profile, dict) or profile.get("id") != profile_id:
        raise MaintenanceError("profile id does not match its filename")
    image = profile.get("image")
    channel = profile.get("runtime_update_channel")
    pinned_match = PINNED_IMAGE.fullmatch(str(image or ""))
    channel_match = CHANNEL.fullmatch(str(channel or ""))
    if not pinned_match or not channel_match or pinned_match.group("repo") != channel_match.group("repo"):
        raise MaintenanceError("profile needs a pinned image and matching runtime_update_channel")
    return profile


def _atomic_json(path: Path, value: dict[str, Any], *, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp_name, mode)
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def _fingerprint(profile: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(profile, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _state() -> dict[str, Any]:
    try:
        value = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _image_metadata(image: str) -> dict[str, Any]:
    result = _run(["docker", "image", "inspect", image, "--format", "{{json .}}"], timeout=30)
    data = json.loads(result.stdout)
    labels = ((data.get("Config") or {}).get("Labels") or {})
    return {
        "image": image,
        "version": labels.get("org.opencontainers.image.version") or "unknown",
        "revision": labels.get("org.opencontainers.image.revision") or "unknown",
        "created": labels.get("org.opencontainers.image.created") or data.get("Created") or "unknown",
    }


def status(profile_id: str) -> dict[str, Any]:
    profile = _load_profile(profile_id)
    state = _state()
    current = _image_metadata(profile["image"])
    relevant = state if state.get("profile_id") == profile_id else {}
    return {
        "profile_id": profile_id,
        "channel": profile["runtime_update_channel"],
        "current": current,
        "candidate": relevant.get("candidate"),
        "stage": relevant.get("stage", "not_checked"),
        "tested": bool(relevant.get("tested")),
        "tested_at": relevant.get("tested_at"),
        "promoted_at": relevant.get("promoted_at"),
        "message": relevant.get("message", "Check the configured channel for a newer pinned runtime."),
    }


def stage(profile_id: str) -> dict[str, Any]:
    profile = _load_profile(profile_id)
    channel = profile["runtime_update_channel"]
    _run(["docker", "pull", channel], timeout=1800)
    inspect = json.loads(_run(["docker", "image", "inspect", channel, "--format", "{{json .}}"], timeout=30).stdout)
    repo = CHANNEL.fullmatch(channel).group("repo")  # type: ignore[union-attr]
    candidates = [item for item in inspect.get("RepoDigests") or [] if item.startswith(repo + "@sha256:")]
    if not candidates:
        raise MaintenanceError("pulled image did not expose an immutable repository digest")
    candidate = sorted(candidates)[0]
    help_result = _run(["docker", "run", "--rm", candidate, "--help"], timeout=120)
    help_text = (help_result.stdout or "") + (help_result.stderr or "")
    missing = [flag for flag in REQUIRED_FLAGS if flag not in help_text]
    if missing:
        raise MaintenanceError("candidate lacks required llama.cpp flags: " + ", ".join(missing))
    metadata = _image_metadata(candidate)
    same = candidate == profile["image"]
    state_data = {
        "schema_version": 1,
        "profile_id": profile_id,
        "profile_fingerprint": _fingerprint(profile),
        "original_image": profile["image"],
        "channel": channel,
        "candidate": metadata,
        "stage": "current" if same else "staged",
        "tested": same,
        "tested_at": datetime.now(timezone.utc).isoformat() if same else None,
        "message": "Runtime is already current." if same else "Candidate downloaded and capability checks passed. Live smoke test is required.",
    }
    _atomic_json(STATE_FILE, state_data)
    return status(profile_id)


def test(profile_id: str) -> dict[str, Any]:
    profile = _load_profile(profile_id)
    state_data = _state()
    candidate = (state_data.get("candidate") or {}).get("image")
    if state_data.get("profile_id") != profile_id or state_data.get("stage") != "staged" or not candidate:
        raise MaintenanceError("stage a newer candidate for this profile first")
    if state_data.get("profile_fingerprint") != _fingerprint(profile):
        raise MaintenanceError("profile changed after staging; check for updates again")

    test_path = _profile_path(TEST_PROFILE)
    if test_path.exists():
        raise MaintenanceError(f"reserved test profile already exists: {test_path}")
    test_profile = copy.deepcopy(profile)
    test_profile.update({"id": TEST_PROFILE, "label": "Flight Engineer runtime smoke test", "status": "experimental", "image": candidate})
    _atomic_json(test_path, test_profile, mode=0o644)
    restored = False
    try:
        _run([MANAGER, "use", TEST_PROFILE], timeout=1800)
        _run([MANAGER, "use", profile_id], timeout=1800)
        restored = True
    finally:
        if not restored:
            _run([MANAGER, "use", profile_id, "--force"], timeout=1800, check=False)
        test_path.unlink(missing_ok=True)
    if not restored:
        raise MaintenanceError("candidate test failed; the original profile restoration was attempted")
    state_data.update({
        "tested": True,
        "tested_at": datetime.now(timezone.utc).isoformat(),
        "message": "Live inference smoke test passed and the original runtime was restored. Candidate is ready to promote.",
    })
    _atomic_json(STATE_FILE, state_data)
    return status(profile_id)


def promote(profile_id: str) -> dict[str, Any]:
    profile = _load_profile(profile_id)
    state_data = _state()
    candidate = (state_data.get("candidate") or {}).get("image")
    if state_data.get("profile_id") != profile_id or not state_data.get("tested") or not candidate:
        raise MaintenanceError("only a tested candidate can be promoted")
    if state_data.get("profile_fingerprint") != _fingerprint(profile):
        raise MaintenanceError("profile changed after testing; check and test again")
    path = _profile_path(profile_id)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    backup = BACKUP_DIR / f"{profile_id}-runtime-{stamp}.json"
    backup.write_bytes(path.read_bytes())
    os.chmod(backup, 0o600)
    profile["image"] = candidate
    _atomic_json(path, profile, mode=0o644)
    state_data.update({
        "stage": "promoted",
        "promoted_at": datetime.now(timezone.utc).isoformat(),
        "backup": str(backup),
        "profile_fingerprint": _fingerprint(profile),
        "message": "Tested runtime pin promoted. Reload this profile when you are ready to run it.",
    })
    _atomic_json(STATE_FILE, state_data)
    return status(profile_id)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("status", "stage", "test", "promote"))
    parser.add_argument("profile")
    args = parser.parse_args()
    try:
        result = {"status": status, "stage": stage, "test": test, "promote": promote}[args.action](args.profile)
        print(json.dumps(result, sort_keys=True))
    except (MaintenanceError, OSError, json.JSONDecodeError) as exc:
        print(f"flight-engineer-runtime: {exc}", file=os.sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
