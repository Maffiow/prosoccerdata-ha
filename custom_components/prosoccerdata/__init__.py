"""The ProSoccerData integration."""

from __future__ import annotations

import logging
from datetime import timedelta

import aiohttp
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    HomeAssistantError,
    ServiceValidationError,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import AuthError, ProSoccerDataAPI, ProSoccerDataError
from .const import (
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_PLAYERS,
    CONF_SCAN_INTERVAL_MINUTES,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DOMAIN,
)
from .coordinator import ProSoccerDataCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.CALENDAR, Platform.SENSOR]

type ProSoccerDataConfigEntry = ConfigEntry[ProSoccerDataCoordinator]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

SERVICE_OPEN_MESSAGE = "open_message"
SERVICE_MARK_MESSAGE_READ = "mark_message_read"

ATTR_MESSAGE_ID = "message_id"
ATTR_MEMBER_ID = "member_id"
ATTR_READ = "read"

OPEN_MESSAGE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_MESSAGE_ID): vol.Coerce(int),
        vol.Optional(ATTR_MEMBER_ID): vol.Coerce(int),
    }
)
MARK_MESSAGE_READ_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_MESSAGE_ID): vol.Coerce(int),
        vol.Optional(ATTR_MEMBER_ID): vol.Coerce(int),
        vol.Optional(ATTR_READ, default=True): cv.boolean,
    }
)


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


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the mailbox actions."""

    def _resolve(call: ServiceCall) -> tuple[ProSoccerDataCoordinator, dict]:
        """Find the coordinator and player an action call is about."""
        member_id = call.data.get(ATTR_MEMBER_ID)
        coordinators = [
            entry.runtime_data
            for entry in hass.config_entries.async_loaded_entries(DOMAIN)
        ]
        players = [
            (coordinator, player)
            for coordinator in coordinators
            for player in coordinator.players
            if member_id is None or str(player["platformMemberId"]) == str(member_id)
        ]

        if not players:
            raise ServiceValidationError(f"No ProSoccerData player matches {member_id}")
        if len(players) > 1:
            raise ServiceValidationError(
                "More than one ProSoccerData player is configured; pass member_id"
            )
        return players[0]

    async def open_message(call: ServiceCall) -> ServiceResponse:
        coordinator, player = _resolve(call)
        try:
            mail = await coordinator.async_open_message(
                player, call.data[ATTR_MESSAGE_ID]
            )
        except ProSoccerDataError as err:
            raise HomeAssistantError(f"Could not open the message: {err}") from err

        return {
            "id": mail.get("id"),
            "subject": mail.get("subject"),
            "date": mail.get("date"),
            "body_html": mail.get("message"),
        }

    async def mark_message_read(call: ServiceCall) -> None:
        coordinator, player = _resolve(call)
        message_id = call.data.get(ATTR_MESSAGE_ID)

        if message_id is None:
            selected = coordinator.selected_messages.get(
                str(player["platformMemberId"])
            )
            if not selected:
                raise ServiceValidationError(
                    "No message_id given and no message has been opened"
                )
            message_id = selected["id"]

        try:
            await coordinator.async_set_message_read(
                player, message_id, call.data[ATTR_READ]
            )
        except ProSoccerDataError as err:
            raise HomeAssistantError(
                f"Could not update the message's read status: {err}"
            ) from err

    hass.services.async_register(
        DOMAIN,
        SERVICE_OPEN_MESSAGE,
        open_message,
        schema=OPEN_MESSAGE_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_MARK_MESSAGE_READ,
        mark_message_read,
        schema=MARK_MESSAGE_READ_SCHEMA,
    )
    return True


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
