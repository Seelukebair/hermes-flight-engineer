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


def _http_error(exc: FlightEngineerError) -> HTTPException:
    message = str(exc)
    status = 409 if "active request" in message or "confirmation" in message else 500
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
