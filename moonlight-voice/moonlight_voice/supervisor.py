"""Publish the live add-on endpoint to Home Assistant Supervisor."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .config import DEFAULT_AUDIO_DIR

LOGGER = logging.getLogger("moonlight_voice.supervisor")
DISCOVERY_SERVICE = "moonlight_voice"
DISCOVERY_STATE_PATH = DEFAULT_AUDIO_DIR / "supervisor-discovery.json"
SUPERVISOR_URL = "http://supervisor"


def _request_json(token: str, path: str, method: str = "GET", payload: dict | None = None) -> dict:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(
        f"{SUPERVISOR_URL}{path}",
        data=body,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    with urlopen(request, timeout=5) as response:  # noqa: S310 - fixed Supervisor URL
        raw_response = response.read()
    if not raw_response:
        return {}
    decoded = json.loads(raw_response.decode("utf-8"))
    if not isinstance(decoded, dict):
        raise ValueError("Supervisor returned a non-object response")
    data = decoded.get("data", decoded)
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError("Supervisor response data is not an object")
    return data


def _read_previous_discovery_id(state_path: Path) -> str | None:
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except OSError, ValueError, json.JSONDecodeError:
        return None
    discovery_id = payload.get("uuid") if isinstance(payload, dict) else None
    return discovery_id if isinstance(discovery_id, str) and discovery_id else None


def _delete_previous_discovery(token: str, state_path: Path) -> None:
    discovery_id = _read_previous_discovery_id(state_path)
    if not discovery_id:
        return

    try:
        _request_json(token, f"/discovery/{discovery_id}", method="DELETE")
    except HTTPError as err:
        if err.code != 404:
            raise
        LOGGER.debug("Previous discovery %s was already removed", discovery_id)
    state_path.unlink(missing_ok=True)


def _write_discovery_id(state_path: Path, discovery_id: str) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = state_path.with_name(f".{state_path.name}.tmp")
    temporary_path.write_text(json.dumps({"uuid": discovery_id}) + "\n", encoding="utf-8")
    temporary_path.replace(state_path)


def publish_discovery(port: int, state_path: Path = DISCOVERY_STATE_PATH) -> str | None:
    """Publish this running add-on's private endpoint for the custom integration."""
    token = os.getenv("SUPERVISOR_TOKEN")
    if not token:
        LOGGER.debug("Supervisor API is unavailable; skipping endpoint discovery")
        return None

    try:
        addon = _request_json(token, "/addons/self/info")
        host = addon.get("ip_address")
        if not isinstance(host, str) or not host:
            raise ValueError("Supervisor did not provide an add-on IP address")

        _delete_previous_discovery(token, state_path)

        discovery = _request_json(
            token,
            "/discovery",
            method="POST",
            payload={
                "service": DISCOVERY_SERVICE,
                "config": {"host": host, "port": port},
            },
        )
        discovery_id = discovery.get("uuid")
        if not isinstance(discovery_id, str) or not discovery_id:
            raise ValueError("Supervisor did not return a discovery UUID")

        _write_discovery_id(state_path, discovery_id)
        endpoint = f"http://{host}:{port}"
        LOGGER.info("Published Moonlight Voice discovery endpoint %s", endpoint)
        return endpoint
    except (HTTPError, URLError, OSError, ValueError, json.JSONDecodeError) as err:
        LOGGER.warning("Could not publish Moonlight Voice discovery: %s", err)
        return None
