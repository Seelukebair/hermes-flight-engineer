"""Authenticated dashboard routes for Flight Engineer."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from flight_engineer import FlightEngineer, FlightEngineerError  # noqa: E402
from jailbreaks import JailbreakError, JailbreakStore, SECRET_TYPES  # noqa: E402


router = APIRouter()


class SwitchRequest(BaseModel):
    profile_id: str
    confirm_interrupt: bool = False


class RollbackRequest(BaseModel):
    confirm_interrupt: bool = False


class RuntimePatch(BaseModel):
    context_length: int | None = Field(default=None, ge=8192, le=1048576)
    parallel_slots: int | None = Field(default=None, ge=1, le=8)
    gpu_layers: int | None = Field(default=None, ge=1, le=999)
    kv_cache: str | None = None
    mmproj_offload: bool | None = None
    batch_size: int | None = Field(default=None, ge=32, le=2048)
    ubatch_size: int | None = Field(default=None, ge=32, le=2048)
    image_min_tokens: int | None = Field(default=None, ge=64, le=4096)
    image_max_tokens: int | None = Field(default=None, ge=64, le=4096)


class UpdateRequest(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=80)
    runtime: RuntimePatch | None = None


class CloneRequest(BaseModel):
    source_id: str
    target_id: str
    label: str = Field(min_length=1, max_length=80)


class JailbreakCreateRequest(BaseModel):
    recipe_id: str
    name: str = Field(min_length=1, max_length=80)
    recipe_type: str
    description: str = Field(default="", max_length=240)
    value: str = Field(min_length=1, max_length=16000)


class JailbreakUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=240)
    enabled: bool | None = None
    profile_ids: list[str] | None = None


class JailbreakSecretRequest(BaseModel):
    value: str = Field(max_length=16000)


class JailbreakConfigRequest(BaseModel):
    enabled: bool | None = None
    profile_id: str | None = None
    recipe_id: str | None = None
    technique: str | None = None


class JailbreakCloneRequest(BaseModel):
    source_id: str
    target_id: str
    name: str = Field(min_length=1, max_length=80)


def _http_error(exc: FlightEngineerError) -> HTTPException:
    message = str(exc)
    status = 409 if "active request" in message or "confirmation" in message else 500
    return HTTPException(status_code=status, detail=message)


def _jailbreak_error(exc: JailbreakError) -> HTTPException:
    message = str(exc)
    status = 404 if "not found" in message else 409 if "already exists" in message else 400
    return HTTPException(status_code=status, detail=message)


@router.get("/status")
def status():
    try:
        return FlightEngineer().status()
    except FlightEngineerError as exc:
        raise _http_error(exc) from exc


@router.get("/profiles")
def profiles():
    try:
        return {"profiles": FlightEngineer().profiles()}
    except FlightEngineerError as exc:
        raise _http_error(exc) from exc


@router.get("/telemetry")
def telemetry():
    try:
        return FlightEngineer().telemetry()
    except FlightEngineerError as exc:
        raise _http_error(exc) from exc


@router.patch("/profiles/{profile_id}")
def update_profile(profile_id: str, request: UpdateRequest):
    try:
        payload = request.runtime.model_dump(exclude_none=True) if request.runtime else None
        return FlightEngineer().update(profile_id, label=request.label, runtime=payload)
    except FlightEngineerError as exc:
        raise _http_error(exc) from exc


@router.post("/profiles/clone")
def clone_profile(request: CloneRequest):
    try:
        return FlightEngineer().clone(request.source_id, request.target_id, label=request.label)
    except FlightEngineerError as exc:
        raise _http_error(exc) from exc


@router.post("/profiles/{profile_id}/apply")
def apply_profile(profile_id: str, request: SwitchRequest):
    try:
        return FlightEngineer().apply(profile_id, confirm_interrupt=request.confirm_interrupt)
    except FlightEngineerError as exc:
        raise _http_error(exc) from exc


@router.post("/profiles/{profile_id}/default")
def set_default_profile(profile_id: str):
    try:
        return FlightEngineer().set_default(profile_id)
    except FlightEngineerError as exc:
        raise _http_error(exc) from exc


@router.post("/switch")
def switch(request: SwitchRequest):
    try:
        return FlightEngineer().use(
            request.profile_id,
            confirm_interrupt=request.confirm_interrupt,
        )
    except FlightEngineerError as exc:
        raise _http_error(exc) from exc


@router.post("/rollback")
def rollback(request: RollbackRequest):
    try:
        return FlightEngineer().rollback(confirm_interrupt=request.confirm_interrupt)
    except FlightEngineerError as exc:
        raise _http_error(exc) from exc


@router.get("/jailbreaks")
def jailbreaks():
    try:
        return JailbreakStore().list()
    except JailbreakError as exc:
        raise _jailbreak_error(exc) from exc


@router.post("/jailbreaks")
def create_jailbreak(request: JailbreakCreateRequest):
    store = JailbreakStore()
    created = False
    try:
        entry = store.create(request.recipe_id, request.name, request.recipe_type, request.description)
        created = True
        return store.set_secret(entry["id"], request.recipe_type, request.value)
    except JailbreakError as exc:
        if created:
            try:
                store.delete(entry["id"])
            except JailbreakError:
                pass
        raise _jailbreak_error(exc) from exc


@router.patch("/jailbreaks/{recipe_id}")
def update_jailbreak(recipe_id: str, request: JailbreakUpdateRequest):
    try:
        return JailbreakStore().update(recipe_id, **request.model_dump(exclude_none=True))
    except JailbreakError as exc:
        raise _jailbreak_error(exc) from exc


@router.delete("/jailbreaks/{recipe_id}")
def delete_jailbreak(recipe_id: str):
    try:
        return JailbreakStore().delete(recipe_id)
    except JailbreakError as exc:
        raise _jailbreak_error(exc) from exc


@router.post("/jailbreaks/clone")
def clone_jailbreak(request: JailbreakCloneRequest):
    try:
        return JailbreakStore().clone(request.source_id, request.target_id, request.name)
    except JailbreakError as exc:
        raise _jailbreak_error(exc) from exc


@router.put("/jailbreaks/{recipe_id}/secrets/{technique}")
def set_jailbreak_secret(recipe_id: str, technique: str, request: JailbreakSecretRequest):
    if technique not in SECRET_TYPES:
        raise HTTPException(status_code=400, detail="invalid injection type")
    try:
        return JailbreakStore().set_secret(recipe_id, technique, request.value)
    except JailbreakError as exc:
        raise _jailbreak_error(exc) from exc


@router.patch("/jailbreaks")
def configure_jailbreaks(request: JailbreakConfigRequest):
    try:
        return JailbreakStore().configure(**request.model_dump(exclude_none=True))
    except JailbreakError as exc:
        raise _jailbreak_error(exc) from exc
