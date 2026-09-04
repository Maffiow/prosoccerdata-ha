"""The ProSoccerData integration."""

from __future__ import annotations

import logging
from datetime import timedelta

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .api import AuthError, ProSoccerDataAPI, ProSoccerDataError
from .const import (
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_PLAYERS,
    CONF_SCAN_INTERVAL_MINUTES,
    DEFAULT_SCAN_INTERVAL_MINUTES,
)
from .coordinator import ProSoccerDataCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]

type ProSoccerDataConfigEntry = ConfigEntry[ProSoccerDataCoordinator]


def build_api(hass: HomeAssistant, email: str, password: str) -> ProSoccerDataAPI:
    """Create an API client that speaks Home Assistant's language and time zone."""
    session = async_create_clientsession(hass, cookie_jar=aiohttp.DummyCookieJar())

    return ProSoccerDataAPI(
        session,
        email,
        password,
        language=(hass.config.language or "").split("-")[0] or None,
        time_zone=hass.config.time_zone,
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: ProSoccerDataConfigEntry
) -> bool:
    """Set up ProSoccerData from a config entry."""
    api = build_api(hass, entry.data[CONF_EMAIL], entry.data[CONF_PASSWORD])

    try:
        await api.login()
    except AuthError as err:
        raise ConfigEntryAuthFailed(
            f"ProSoccerData rejected the stored credentials: {err}"
        ) from err
    except ProSoccerDataError as err:
        raise ConfigEntryNotReady(f"Cannot reach ProSoccerData: {err}") from err

    # Options win over the values captured during the initial config flow.
    players = entry.options.get(CONF_PLAYERS, entry.data.get(CONF_PLAYERS, []))
    minutes = entry.options.get(
        CONF_SCAN_INTERVAL_MINUTES, DEFAULT_SCAN_INTERVAL_MINUTES
    )

    coordinator = ProSoccerDataCoordinator(
        hass, entry, api, players, timedelta(minutes=minutes)
    )
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: ProSoccerDataConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
