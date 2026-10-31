"""The ProSoccerData integration."""

from __future__ import annotations

import logging
import re
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
SERVICE_GET_ATTENDANCE = "get_attendance"

ATTR_MESSAGE_ID = "message_id"
ATTR_MEMBER_ID = "member_id"
ATTR_READ = "read"
ATTR_EVENT = "event"
ATTR_STATUS = "status"

ATTENDANCE_STATUSES = ["ALL", "PRESENT", "ABSENT"]

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
GET_ATTENDANCE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_EVENT): cv.string,
        vol.Optional(ATTR_MEMBER_ID): vol.Coerce(int),
        vol.Optional(ATTR_STATUS, default="ALL"): vol.In(ATTENDANCE_STATUSES),
    }
)


def event_id_from(value: str) -> int:
    """Accept either a calendar uid such as `game-6963` or a bare event id."""
    digits = re.sub(r"\D", "", str(value))

    if not digits:
        raise ServiceValidationError(f"{value!r} holds no ProSoccerData event id")

    return int(digits)


def event_type_from(value: str) -> str:
    """Read the event type out of a calendar uid such as `training-18161`."""
    head = str(value).split("-", 1)[0].strip().lower()
    return head if head in ("game", "training", "other") else "game"


def presence_summary(item: dict) -> dict:
    """Pick the readable fields out of a presence record.

    ProSoccerData has not documented this response, so every field is looked
    for in the nested player and member records as well as the record itself.
    """
    member = item.get("player") or item.get("member") or item.get("platformMember") or {}
    first = member.get("firstName") or item.get("firstName")
    last = member.get("lastName") or item.get("lastName")
    name = f"{first or ''} {last or ''}".strip()

    return {
        "name": name or member.get("fullName") or item.get("name"),
        "status": item.get("attendanceStatus") or item.get("status"),
        "shirt_number": member.get("shirtNumber") or item.get("number"),
        "keeper": member.get("keeper"),
    }


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

    async def get_attendance(call: ServiceCall) -> ServiceResponse:
        coordinator, player = _resolve(call)
        event_id = event_id_from(call.data[ATTR_EVENT])

        try:
            path, items = await coordinator.api.get_event_presences(
                player,
                event_id,
                event_type=event_type_from(call.data[ATTR_EVENT]),
                status=call.data[ATTR_STATUS],
            )
        except AuthError as err:
            raise HomeAssistantError(
                "ProSoccerData will not let this account read attendance lists"
                f" ({err}). The club's staff screen is the only place that"
                " shows them."
            ) from err
        except ProSoccerDataError as err:
            raise HomeAssistantError(
                f"Could not read the attendance list: {err}"
            ) from err

        return {
            "event_id": event_id,
            "path": path,
            "count": len(items),
            # The shape of a record is undocumented; report the keys so an
            # unexpected response can be read without guessing.
            "fields": sorted(items[0]) if items else [],
            "players": [presence_summary(item) for item in items],
        }

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_ATTENDANCE,
        get_attendance,
        schema=GET_ATTENDANCE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
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
