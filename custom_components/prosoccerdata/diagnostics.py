"""Diagnostics support for the ProSoccerData integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import ProSoccerDataConfigEntry
from .const import CONF_EMAIL, CONF_PASSWORD

# Credentials and anything that identifies a real child stay out of the dump.
TO_REDACT = {
    CONF_EMAIL,
    CONF_PASSWORD,
    "email",
    "username",
    "firstName",
    "lastName",
    "platformUserFirstName",
    "platformUserLastName",
    "platformMemberFirstName",
    "platformMemberLastName",
    "nickname",
    "localName",
    "birthDate",
    "uuid",
    "uid",
    "profilePictureURL",
    "sender",
    "receivers",
    "subject",
    "firstSentence",
    "attachments",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ProSoccerDataConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data

    return {
        "entry": {
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": async_redact_data(dict(entry.options), TO_REDACT),
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "update_interval": str(coordinator.update_interval),
            "player_count": len(coordinator.players),
        },
        "data": async_redact_data(coordinator.data or {}, TO_REDACT),
    }
