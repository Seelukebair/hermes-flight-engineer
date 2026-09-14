"""Reusable prompt-injection recipes with write-only Hermes secret storage."""

from __future__ import annotations

import json
import os
import re
import tempfile
import base64
from pathlib import Path
from typing import Any


RECIPE_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
SECRET_TYPES = ("system_framing", "thinking_prefill", "assistant_prefill")
DEFAULT_STATE_PATH = Path.home() / ".hermes" / "flight-engineer" / "jailbreaks.json"
DEFAULT_ENV_PATH = Path.home() / ".hermes" / ".env"


class JailbreakError(RuntimeError):
    """A recipe or protected-value operation failed validation."""


def _id(value: str) -> str:
    result = str(value or "").strip().lower()
    if not RECIPE_ID.fullmatch(result):
        raise JailbreakError("invalid recipe id")
    return result


def _secret_ref(recipe_id: str, technique: str) -> str:
    suffix = {"system_framing": "SYSTEM", "thinking_prefill": "THINKING", "assistant_prefill": "ASSISTANT"}[technique]
    return f"FLIGHT_ENGINEER_JAILBREAK_{recipe_id.upper().replace('-', '_')}_{suffix}"


class HermesSecretStore:
    """Use Hermes's profile-scoped .env writer; reads never cross the API boundary."""

    def __init__(self, env_path: str | Path | None = None) -> None:
        self.env_path = Path(env_path or os.getenv("FLIGHT_ENGINEER_ENV_PATH", DEFAULT_ENV_PATH))

    def set(self, name: str, value: str) -> None:
        try:
            from hermes_cli.config import save_env_value
        except ImportError as exc:  # pragma: no cover - only absent outside Hermes
            raise JailbreakError("Hermes secret writer is unavailable") from exc
        encoded = "b64v1:" + base64.b64encode(value.encode("utf-8")).decode("ascii")
        save_env_value(name, encoded)
        try:
            self.env_path.chmod(0o600)
        except OSError:
            pass

    def get(self, name: str) -> str:
        try:
            from dotenv import dotenv_values
        except ImportError as exc:
            raise JailbreakError("python-dotenv is unavailable") from exc
        if not self.env_path.exists():
            return ""
        value = str(dotenv_values(self.env_path).get(name) or "")
        if not value.startswith("b64v1:"):
            return ""
        try:
            return base64.b64decode(value[6:], validate=True).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            return ""

    def delete(self, name: str) -> None:
        try:
            from hermes_cli.config import remove_env_value
        except ImportError as exc:  # pragma: no cover - only absent outside Hermes
            raise JailbreakError("Hermes secret writer is unavailable") from exc
        remove_env_value(name)


class JailbreakStore:
    """Own non-secret recipe metadata and resolve secrets only for inference."""

    def __init__(self, state_path: str | Path | None = None, secrets: HermesSecretStore | None = None) -> None:
        self.path = Path(state_path or os.getenv("FLIGHT_ENGINEER_JAILBREAK_STATE", DEFAULT_STATE_PATH))
        self.secrets = secrets or HermesSecretStore()

    @staticmethod
    def _empty() -> dict[str, Any]:
        return {"version": 1, "enabled": False, "assignments": {}, "recipes": []}

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return self._empty()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise JailbreakError("jailbreak metadata is unreadable") from exc
        if not isinstance(data, dict) or data.get("version") != 1:
            raise JailbreakError("unsupported jailbreak metadata version")
        data.setdefault("enabled", False)
        data.setdefault("assignments", {})
        data.setdefault("recipes", [])
        return data

    def _save(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path.parent.chmod(0o700)
        fd, temporary = tempfile.mkstemp(prefix=".jailbreaks-", dir=self.path.parent, text=True)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(data, handle, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary, 0o600)
            os.replace(temporary, self.path)
        finally:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass

    @staticmethod
    def _public(data: dict[str, Any]) -> dict[str, Any]:
        # Secret references are implementation details. Only configuration state leaves this layer.
        return {
            "version": 1,
            "enabled": bool(data.get("enabled")),
            "assignments": dict(data.get("assignments") or {}),
            "recipes": [{
                "id": recipe["id"],
                "name": recipe["name"],
                "description": recipe.get("description", ""),
                "enabled": bool(recipe.get("enabled", True)),
                "profile_ids": list(recipe.get("profile_ids") or []),
                "techniques": {
                    kind: bool((recipe.get("techniques") or {}).get(kind, {}).get("configured"))
                    for kind in SECRET_TYPES
                },
            } for recipe in data.get("recipes", []) if isinstance(recipe, dict)],
        }

    def list(self) -> dict[str, Any]:
        return self._public(self._load())

    def create(self, recipe_id: str, name: str, description: str = "") -> dict[str, Any]:
        rid = _id(recipe_id)
        clean_name = str(name or "").strip()
        if not clean_name or len(clean_name) > 80:
            raise JailbreakError("recipe name must be 1-80 characters")
        data = self._load()
        if any(item.get("id") == rid for item in data["recipes"]):
            raise JailbreakError("recipe id already exists")
        data["recipes"].append({
            "id": rid, "name": clean_name, "description": str(description or "").strip()[:240],
            "enabled": True, "profile_ids": [], "techniques": {
                kind: {"configured": False, "secret_ref": _secret_ref(rid, kind)} for kind in SECRET_TYPES
            },
        })
        self._save(data)
        return next(item for item in self.list()["recipes"] if item["id"] == rid)

    def update(self, recipe_id: str, *, name: str | None = None, description: str | None = None,
               enabled: bool | None = None, profile_ids: list[str] | None = None) -> dict[str, Any]:
        rid, data = _id(recipe_id), self._load()
        recipe = next((item for item in data["recipes"] if item.get("id") == rid), None)
        if recipe is None:
            raise JailbreakError("recipe not found")
        if name is not None:
            clean = str(name).strip()
            if not clean or len(clean) > 80:
                raise JailbreakError("recipe name must be 1-80 characters")
            recipe["name"] = clean
        if description is not None:
            recipe["description"] = str(description).strip()[:240]
        if enabled is not None:
            recipe["enabled"] = bool(enabled)
        if profile_ids is not None:
            recipe["profile_ids"] = sorted({_id(value) for value in profile_ids})
        self._save(data)
        return next(item for item in self.list()["recipes"] if item["id"] == rid)

    def set_secret(self, recipe_id: str, technique: str, value: str) -> dict[str, Any]:
        rid = _id(recipe_id)
        if technique not in SECRET_TYPES:
            raise JailbreakError("invalid injection type")
        data = self._load()
        recipe = next((item for item in data["recipes"] if item.get("id") == rid), None)
        if recipe is None:
            raise JailbreakError("recipe not found")
        clean = str(value or "").strip()
        if len(clean) > 16000:
            raise JailbreakError("injection text exceeds 16000 characters")
        ref = recipe["techniques"][technique]["secret_ref"]
        if clean:
            self.secrets.set(ref, clean)
        else:
            self.secrets.delete(ref)
        recipe["techniques"][technique]["configured"] = bool(clean)
        self._save(data)
        return next(item for item in self.list()["recipes"] if item["id"] == rid)

    def delete(self, recipe_id: str) -> dict[str, Any]:
        rid, data = _id(recipe_id), self._load()
        recipe = next((item for item in data["recipes"] if item.get("id") == rid), None)
        if recipe is None:
            raise JailbreakError("recipe not found")
        for entry in (recipe.get("techniques") or {}).values():
            if isinstance(entry, dict) and entry.get("secret_ref"):
                self.secrets.delete(entry["secret_ref"])
        data["recipes"] = [item for item in data["recipes"] if item.get("id") != rid]
        data["assignments"] = {
            profile: assigned for profile, assigned in data["assignments"].items() if assigned != rid
        }
        self._save(data)
        return self.list()

    def configure(self, *, enabled: bool | None = None, profile_id: str | None = None,
                  recipe_id: str | None = None) -> dict[str, Any]:
        data = self._load()
        if enabled is not None:
            data["enabled"] = bool(enabled)
        if profile_id is not None:
            pid = _id(profile_id)
            if recipe_id:
                rid = _id(recipe_id)
                recipe = next((item for item in data["recipes"] if item.get("id") == rid), None)
                if recipe is None:
                    raise JailbreakError("recipe not found")
                if pid not in (recipe.get("profile_ids") or []):
                    raise JailbreakError("recipe is not marked compatible with this profile")
                data["assignments"][pid] = rid
            else:
                data["assignments"].pop(pid, None)
        self._save(data)
        return self.list()

    def resolve(self, profile_id: str) -> dict[str, str]:
        """Resolve a profile's active prompt bodies without exposing them to dashboard callers."""
        pid, data = _id(profile_id), self._load()
        if not data.get("enabled"):
            return {}
        rid = (data.get("assignments") or {}).get(pid)
        recipe = next((item for item in data["recipes"] if item.get("id") == rid), None)
        if not recipe or not recipe.get("enabled", True) or pid not in (recipe.get("profile_ids") or []):
            return {}
        result: dict[str, str] = {}
        for kind in SECRET_TYPES:
            entry = (recipe.get("techniques") or {}).get(kind) or {}
            if entry.get("configured") and entry.get("secret_ref"):
                value = self.secrets.get(entry["secret_ref"])
                if value:
                    result[kind] = value
        return result
