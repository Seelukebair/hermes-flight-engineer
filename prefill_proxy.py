"""Loopback OpenAI-compatible adapter for profile-aware prompt injection."""

from __future__ import annotations

import argparse
import json
import logging
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from jailbreaks import JailbreakError, JailbreakStore


LOG = logging.getLogger("flight_engineer.prefill_proxy")
HOP_HEADERS = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailers", "transfer-encoding", "upgrade"}


def apply_injection(payload: dict[str, Any], prompts: dict[str, str]) -> bool:
    """Mutate only an initial chat request; tool-result continuations remain untouched."""
    messages = payload.get("messages")
    if not prompts or not isinstance(messages, list) or not messages:
        return False
    last = messages[-1]
    if not isinstance(last, dict) or last.get("role") != "user":
        return False
    system = prompts.get("system_framing")
    if system:
        target = next((m for m in messages if isinstance(m, dict) and m.get("role") == "system"), None)
        if target is None:
            messages.insert(0, {"role": "system", "content": system})
        elif isinstance(target.get("content"), str):
            target["content"] = target["content"].rstrip() + "\n\n" + system
        else:
            return False
    assistant, thinking = prompts.get("assistant_prefill"), prompts.get("thinking_prefill")
    if assistant or thinking:
        prefill: dict[str, Any] = {"role": "assistant", "content": assistant or ""}
        if thinking:
            prefill["reasoning_content"] = thinking
        messages.append(prefill)
    return True


class ProxyHandler(BaseHTTPRequestHandler):
    upstream = "http://127.0.0.1:8092"
    state_path: str | None = None
    active_profile = "/srv/gemma4-production/active-profile"

    def log_message(self, fmt: str, *args: Any) -> None:
        LOG.info("%s - %s", self.client_address[0], fmt % args)

    def _profile(self) -> str:
        return Path(self.active_profile).read_text(encoding="ascii").strip()

    def _forward(self) -> None:
        body = self.rfile.read(int(self.headers.get("Content-Length", "0") or 0))
        injected = False
        if self.command == "POST" and self.path.rstrip("/") == "/v1/chat/completions" and body:
            try:
                payload = json.loads(body)
                injected = apply_injection(payload, JailbreakStore(self.state_path).resolve(self._profile()))
                body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            except (json.JSONDecodeError, OSError, JailbreakError) as exc:
                # Fail closed for injection, fail open for inference availability.
                LOG.warning("injection skipped: %s", exc)
        target = self.upstream.rstrip("/") + self.path
        headers = {key: value for key, value in self.headers.items() if key.lower() not in HOP_HEADERS and key.lower() != "host"}
        headers["Content-Length"] = str(len(body))
        request = urllib.request.Request(target, data=body if self.command in {"POST", "PUT", "PATCH"} else None, headers=headers, method=self.command)
        try:
            response = urllib.request.urlopen(request, timeout=900)
        except urllib.error.HTTPError as exc:
            response = exc
        self.send_response(response.status)
        for key, value in response.headers.items():
            if key.lower() not in HOP_HEADERS and key.lower() != "content-length":
                self.send_header(key, value)
        self.send_header("X-Flight-Engineer-Injection", "applied" if injected else "none")
        self.end_headers()
        while True:
            chunk = response.read(64 * 1024)
            if not chunk:
                break
            self.wfile.write(chunk)
            self.wfile.flush()

    do_GET = _forward
    do_POST = _forward
    do_OPTIONS = _forward


def main() -> None:
    parser = argparse.ArgumentParser(description="Flight Engineer loopback prefill adapter")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8093)
    parser.add_argument("--upstream", default="http://127.0.0.1:8092")
    parser.add_argument("--state-path")
    parser.add_argument("--active-profile", default="/srv/gemma4-production/active-profile")
    args = parser.parse_args()
    ProxyHandler.upstream, ProxyHandler.state_path, ProxyHandler.active_profile = args.upstream, args.state_path, args.active_profile
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    ThreadingHTTPServer((args.host, args.port), ProxyHandler).serve_forever()


if __name__ == "__main__":
    main()

