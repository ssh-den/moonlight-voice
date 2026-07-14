"""Config flow for Moonlight Voice."""

from __future__ import annotations

import asyncio
from typing import Any
from urllib.parse import urlsplit

import voluptuous as vol
from aiohttp import ClientError
from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.hassio import HassioServiceInfo

from .const import CONF_URL, DEFAULT_URL, DOMAIN, HOME_ASSISTANT_MODE


class CannotConnectError(Exception):
    """Raised when Moonlight Voice cannot be reached."""


class TtsModeError(Exception):
    """Raised when the add-on has not enabled Home Assistant TTS mode."""


def _default_endpoint(hass) -> str:
    """Suggest the direct add-on URL from Home Assistant's internal URL."""
    internal_url = getattr(hass.config, "internal_url", None)
    if not isinstance(internal_url, str):
        return DEFAULT_URL

    hostname = urlsplit(internal_url).hostname
    if not hostname:
        return DEFAULT_URL

    if ":" in hostname:
        hostname = f"[{hostname}]"
    return f"http://{hostname}:8031"


async def _async_validate_endpoint(hass, endpoint: str) -> None:
    """Validate the endpoint and selected add-on mode."""
    session = async_get_clientsession(hass)
    try:
        async with session.get(f"{endpoint}/config") as response:
            response.raise_for_status()
            config = await response.json()
    except (asyncio.TimeoutError, ClientError, ValueError) as err:
        raise CannotConnectError from err

    if config.get("tts_mode") != HOME_ASSISTANT_MODE:
        raise TtsModeError


class MoonlightVoiceConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure the Moonlight Voice TTS entity."""

    VERSION = 1
    _discovered_endpoint: str | None = None

    async def async_step_hassio(
        self, discovery_info: HassioServiceInfo
    ) -> config_entries.ConfigFlowResult:
        """Handle discovery from a Moonlight Voice add-on."""
        try:
            host = discovery_info.config["host"]
            port = int(discovery_info.config["port"])
            if not isinstance(host, str) or not host or not 1 <= port <= 65535:
                raise ValueError
        except KeyError:
            return self.async_abort(reason="cannot_connect")
        except TypeError, ValueError:
            return self.async_abort(reason="cannot_connect")

        endpoint = f"http://{host}:{port}"
        try:
            await _async_validate_endpoint(self.hass, endpoint)
        except CannotConnectError:
            return self.async_abort(reason="cannot_connect")
        except TtsModeError:
            return self.async_abort(reason="home_assistant_mode_required")

        existing_entries = self._async_current_entries()
        if existing_entries:
            entry = existing_entries[0]
            unique_id = f"hassio:{discovery_info.slug}"
            endpoint_changed = entry.data.get(CONF_URL) != endpoint
            if endpoint_changed or entry.unique_id != unique_id:
                self.hass.config_entries.async_update_entry(
                    entry,
                    data={CONF_URL: endpoint},
                    unique_id=unique_id,
                )
            if endpoint_changed:
                await self.hass.config_entries.async_reload(entry.entry_id)
            return self.async_abort(reason="already_configured")

        await self.async_set_unique_id(f"hassio:{discovery_info.slug}")
        self._abort_if_unique_id_configured()
        self._discovered_endpoint = endpoint
        return await self.async_step_user()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial configuration step."""
        errors: dict[str, str] = {}
        default_endpoint = self._discovered_endpoint or _default_endpoint(self.hass)
        if user_input is not None:
            endpoint = user_input[CONF_URL].strip().rstrip("/")
            default_endpoint = endpoint
            if not endpoint.startswith(("http://", "https://")):
                errors["base"] = "invalid_url"
            else:
                try:
                    await _async_validate_endpoint(self.hass, endpoint)
                except CannotConnectError:
                    errors["base"] = "cannot_connect"
                except TtsModeError:
                    errors["base"] = "home_assistant_mode_required"
                else:
                    await self.async_set_unique_id(endpoint)
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title="Moonlight Voice", data={CONF_URL: endpoint}
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_URL, default=default_endpoint): str}),
            errors=errors,
        )
