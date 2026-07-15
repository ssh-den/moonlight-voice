"""Text-to-speech entity backed by the Moonlight Voice add-on."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

from aiohttp import ClientError
from homeassistant.components.tts import TextToSpeechEntity, TtsAudioType
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.event import async_track_time_interval

from .const import CONF_URL, DOMAIN

LOGGER = logging.getLogger(__name__)
SUPPORTED_LANGUAGES = ["ru", "en"]
CACHE_KEY_OPTION = "moonlight_cache_key"
CACHE_KEY_REFRESH_INTERVAL = timedelta(seconds=5)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
) -> None:
    """Set up the Moonlight Voice TTS entity."""
    entity = MoonlightVoiceTTSEntity(entry)
    async_add_entities([entity])


class MoonlightVoiceTTSEntity(TextToSpeechEntity):
    """Send Home Assistant TTS messages to Moonlight Voice response matching."""

    _attr_has_entity_name = True
    _attr_name = "Response audio"
    _attr_default_language = "ru"
    _attr_supported_languages = SUPPORTED_LANGUAGES
    _attr_supported_options = [CACHE_KEY_OPTION]

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the entity from the configured endpoint."""
        self._endpoint = entry.data[CONF_URL]
        self._attr_unique_id = entry.entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id or entry.entry_id)},
            name="Moonlight Voice",
            manufacturer="Moonlight Voice",
            model="Local audio response service",
            entry_type=DeviceEntryType.SERVICE,
        )
        self._cache_key = "unknown"
        self._cancel_cache_key_refresh = None

    @property
    def default_options(self) -> dict[str, str]:
        """Return an in-memory cache key that changes with the clip library."""
        return {CACHE_KEY_OPTION: self._cache_key}

    async def async_added_to_hass(self) -> None:
        """Refresh the cache fingerprint while the entity is active."""
        await super().async_added_to_hass()
        await self.async_refresh_cache_key()
        self._cancel_cache_key_refresh = async_track_time_interval(
            self.hass,
            self._async_refresh_cache_key,
            CACHE_KEY_REFRESH_INTERVAL,
        )

    async def async_will_remove_from_hass(self) -> None:
        """Stop refreshing after the entity is removed."""
        if self._cancel_cache_key_refresh:
            self._cancel_cache_key_refresh()
            self._cancel_cache_key_refresh = None
        await super().async_will_remove_from_hass()

    async def async_refresh_cache_key(self) -> None:
        """Fetch the current clip-library fingerprint without doing I/O in properties."""
        try:
            session = async_get_clientsession(self.hass)
            async with session.get(f"{self._endpoint}/config") as response:
                response.raise_for_status()
                payload = await response.json()
        except (asyncio.TimeoutError, ClientError, ValueError) as err:
            LOGGER.debug("Could not refresh Moonlight Voice TTS cache key: %s", err)
            return

        cache_key = payload.get("tts_cache_key")
        if isinstance(cache_key, str) and cache_key and cache_key != self._cache_key:
            self._cache_key = cache_key
            self.async_write_ha_state()

    async def _async_refresh_cache_key(self, _now) -> None:
        """Refresh the cache fingerprint on the scheduled interval."""
        await self.async_refresh_cache_key()

    async def async_get_tts_audio(
        self, message: str, language: str, options: dict[str, Any]
    ) -> TtsAudioType:
        """Return the response clip whose code matches the requested message."""
        requested_format = str(options.get("preferred_format", "mp3")).lower()
        if requested_format not in {"mp3", "wav"}:
            requested_format = "mp3"

        try:
            session = async_get_clientsession(self.hass)
            async with session.post(
                f"{self._endpoint}/tts",
                json={"message": message, "format": requested_format},
            ) as response:
                response.raise_for_status()
                data = await response.read()
                content_type = response.headers.get("Content-Type", "")
        except (asyncio.TimeoutError, ClientError) as err:
            LOGGER.error("Moonlight Voice request failed: %s", err)
            return None, None

        extension = "wav" if "audio/wav" in content_type else "mp3"
        return extension, data
