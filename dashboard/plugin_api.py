"""Authenticated dashboard routes for Flight Engineer."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel


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

