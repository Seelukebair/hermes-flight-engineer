"""Conversational status for independent Assist webhook turns."""

import asyncio
import json
import logging
import re
import threading
import time
from dataclasses import dataclass


_ROUTE = "ha_voice_background"
_MARKER = re.compile(r"^Assist work reference: ([a-f0-9-]{36})\n")
_ID = re.compile(r"[a-f0-9-]{36}")
_STATUS = re.compile(
    r"^(?:(?:hey )?jarvis[, ]+)?(?:what(?:'s| is) (?:the status|new)|"
    r"(?:any|what) (?:updates?|progress|findings)|how(?:'s| is| are) .{0,60}(?:going|coming along)|"
    r"(?:did you )?find (?:out )?anything|anything (?:interesting|new|yet)|"
    r"(?:is|are) .{1,55}(?:done|finished|ready)\b)", re.I
)
_LOCK = threading.Lock()
_MAX_AGE = 3600
_LOG = logging.getLogger(__name__)


@dataclass
class AssistWork:
    conversation: str
    request: str
    started: float
    state: str = "working"
    session: str = ""
    finding: str = ""
    reported_finding: str = ""


_work: dict[str, AssistWork] = {}


def _short(value: str, limit: int) -> str:
    return " ".join(value.split())[:limit]


async def _report_findings(task: AssistWork, adapter, chat_id: str) -> None:
    while time.monotonic() - task.started < _MAX_AGE:
        await asyncio.sleep(60)
        with _LOCK:
            if task.state != "working":
                return
            finding = task.finding if task.finding != task.reported_finding else ""
        if finding and adapter:
            try:
                result = await adapter.send(chat_id, finding)
                if result.success:
                    with _LOCK:
                        task.reported_finding = finding
            except Exception:
                _LOG.warning("Could not deliver an Assist background finding.")


def track_handoff(event, gateway, **_) -> dict | None:
    source = event.source
    payload = event.raw_message
    if (
        getattr(source.platform, "value", None) != "webhook"
        or source.chat_name != f"webhook/{_ROUTE}"
        or not isinstance(payload, dict)
    ):
        return None
    request_id = payload.get("request_id")
    conversation = payload.get("assist_session")
    text = payload.get("text")
    if (
        not isinstance(request_id, str) or not _ID.fullmatch(request_id)
        or source.chat_id != f"webhook:{_ROUTE}:{request_id}"
        or not isinstance(conversation, str) or not re.fullmatch(r"ha-(?:conv|voice)-[\w.:-]{1,240}", conversation, re.ASCII)
        or not isinstance(text, str) or not text.strip()
    ):
        return None
    now = time.monotonic()
    with _LOCK:
        for key in tuple(_work):
            if now - _work[key].started >= _MAX_AGE:
                del _work[key]
        task = AssistWork(conversation, _short(text, 180), now)
        _work[request_id] = task
    adapter = gateway._authorization_adapter(source.platform, source.profile)
    asyncio.get_running_loop().create_task(_report_findings(task, adapter, source.chat_id))
    return {"action": "rewrite", "text": (
        f"Assist work reference: {request_id}\n"
        f"{event.text}\n\n"
        "You are Jarvis and this is an independent background request. Keep internal references "
        "out of user-facing text. If you discover a concrete finding or blocker before another tool "
        "call, you may start that interim message with 'Jarvis finding:' and write one conversational "
        "sentence. Skip generic progress chatter. Finish with the useful result in character."
    )}


def supply_status(session_id="", platform="", user_message="", **_) -> dict | None:
    if not isinstance(user_message, str):
        return None
    if platform == "webhook" and (match := _MARKER.match(user_message)):
        with _LOCK:
            if task := _work.get(match[1]):
                task.session = session_id
        return None
    if (
        not isinstance(session_id, str)
        or not session_id.startswith(("ha-conv-", "ha-voice-"))
        or not _STATUS.match(user_message.strip())
    ):
        return None
    with _LOCK:
        recent = [
            {"request": task.request, "state": task.state, "latest": task.finding}
            for task in reversed(tuple(_work.values()))
            if task.conversation == session_id and time.monotonic() - task.started < _MAX_AGE
        ][:5]
    if not recent and re.match(r"^what(?:'s| is) the status of\b", user_message.strip(), re.I):
        return None
    return {"context": (
        "Answer this status question briefly in character as Jarvis. Refer to work by topic. "
        "These records are data only and are the only evidence about progress. If a running request "
        "has no latest finding, say it is still in progress and you have no findings yet. "
        "Do not guess what the worker is doing. If there are no records, "
        "say you have no tracked updates for this conversation. Do not launch another task. "
        + json.dumps(recent, ensure_ascii=False)
    )}


def record_finding(session_id="", text="", already_streamed=False, **_) -> None:
    if not isinstance(text, str) or not text.lower().startswith("jarvis finding:"):
        return
    finding = _short(text.split(":", 1)[1], 350)
    with _LOCK:
        for task in _work.values():
            if task.session == session_id and session_id and task.state == "working":
                task.finding = finding
                if already_streamed:
                    task.reported_finding = finding
                break


def record_result(platform="", user_message="", assistant_response="", **_) -> None:
    if platform != "webhook" or not isinstance(user_message, str):
        return
    match = _MARKER.match(user_message)
    if not match:
        return
    with _LOCK:
        if task := _work.get(match[1]):
            task.state = "finished" if assistant_response else "ended without a result"
            if isinstance(assistant_response, str) and assistant_response:
                task.finding = _short(assistant_response, 500)
