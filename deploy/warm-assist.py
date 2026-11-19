"""Prime the local Assist prompt once without requesting speech playback."""

import ipaddress
import json
import os
import time
import urllib.request
from urllib.error import HTTPError
from pathlib import Path
from uuid import uuid4
from urllib.parse import urlsplit

import yaml
from dotenv import dotenv_values


def local_default(config: dict) -> tuple[str, str] | None:
    model = config.get("model", {})
    if not isinstance(model, dict):
        return None
    provider = config.get("providers", {}).get(model.get("provider"), {})
    default = model.get("default") or provider.get("default_model")
    endpoint = model.get("base_url") or provider.get("api") or provider.get("base_url")
    if not isinstance(default, str) or not isinstance(endpoint, str):
        return None
    url = urlsplit(endpoint)
    if url.scheme not in {"http", "https"} or not url.hostname or url.username or url.query or url.fragment:
        return None
    if url.hostname != "localhost":
        try:
            ip = ipaddress.ip_address(url.hostname)
        except ValueError:
            return None
        if not (ip.is_loopback or ip.is_private):
            return None
    return default, endpoint.rstrip("/") + "/models"


def backend_busy(models_url: str) -> bool:
    endpoint = models_url.removesuffix("/models").removesuffix("/v1")
    try:
        with urllib.request.urlopen(endpoint + "/metrics", timeout=2) as response:
            for line in response.read().decode().splitlines():
                if line.startswith(("llamacpp:requests_processing ", "vllm:num_requests_running ")):
                    return float(line.split()[1]) > 0
    except (OSError, ValueError):
        pass
    return False


def delete_warmup_session(conversation_id: str, api_key: str) -> None:
    request = urllib.request.Request(
        f"http://127.0.0.1:8642/api/sessions/ha-conv-{conversation_id}",
        headers={"Authorization": "Bearer " + api_key},
        method="DELETE",
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            if json.load(response).get("deleted") is not True:
                raise RuntimeError("Assist warmup session cleanup failed.")
        print("Deleted the disposable Assist warmup session.")
    except HTTPError as error:
        if error.code != 404:
            raise RuntimeError("Assist warmup session cleanup failed.") from None
        print("The disposable Assist warmup session was not stored.")


def main() -> None:
    home = Path.home() / ".hermes"
    config = yaml.safe_load((home / "config.yaml").read_text(encoding="utf-8"))
    target = local_default(config)
    if target is None:
        print("Assist warmup skipped because no supported local default endpoint is configured.")
        return
    model_id, models_url = target
    gateway_health = os.getenv(
        "FLIGHT_ENGINEER_GATEWAY_HEALTH_URL", "http://127.0.0.1:8642/health"
    )

    for attempt in range(30):
        try:
            with urllib.request.urlopen(gateway_health, timeout=2) as gateway:
                if gateway.status == 200:
                    with urllib.request.urlopen(models_url, timeout=2) as response:
                        if any(item.get("id") == model_id for item in json.load(response).get("data", [])):
                            break
        except (OSError, ValueError):
            pass
        if attempt == 29:
            raise RuntimeError("Hermes Gateway or the local default model did not become ready.")
        time.sleep(2)

    if backend_busy(models_url):
        print("Assist warmup skipped because the local model is busy.")
        return

    env = dotenv_values(home / ".env")
    api_key = env["API_SERVER_KEY"]
    conversation_id = str(uuid4())
    request = urllib.request.Request(
        env["HASS_URL"].rstrip("/") + "/api/conversation/process",
        headers={"Authorization": "Bearer " + env["HASS_TOKEN"], "Content-Type": "application/json"},
        data=json.dumps({
            "agent_id": "conversation.hermes_proxy_agent",
            "conversation_id": conversation_id,
            "text": "Quick diagnostic. Reply exactly: The voice route is working. Do not use tools.",
        }).encode(),
    )
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            speech = json.load(response)["response"]["speech"]["plain"]["speech"]
    except (OSError, ValueError, KeyError):
        raise RuntimeError("Assist warmup request failed.") from None
    finally:
        delete_warmup_session(conversation_id, api_key)
    if speech.strip().lower().rstrip(".") != "the voice route is working":
        raise RuntimeError("Assist warmup did not return the expected diagnostic reply.")
    print(f"Assist prompt warmup for {model_id} completed in {time.monotonic() - started:.2f} seconds.")


if __name__ == "__main__":
    main()
