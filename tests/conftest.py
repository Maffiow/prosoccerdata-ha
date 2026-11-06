"""Fixtures for the ProSoccerData tests."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.prosoccerdata.const import (
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_PLAYERS,
    DOMAIN,
)

EMAIL = "parent@example.test"
PASSWORD = "hunter2"

PLAYER: dict[str, Any] = {
    "platformMemberId": 7486,
    "platformId": 7,
    "platformUserId": 99,
    "platformURL": "https://club.prosoccerdata.com",
    "apiURL": "https://club-api.prosoccerdata.com",
    "platform": "KFC Testclub",
    "platformUserFirstName": "Sam",
    "platformUserLastName": "Peeters",
}

SECOND_PLAYER: dict[str, Any] = {
    **PLAYER,
    "platformMemberId": 7487,
    "platformUserFirstName": "Nore",
}

RAW_MATCH = {
    "id": 6786,
    "start": "2026-10-31 12:45",
    "end": "2026-10-31 14:00",
    "subtype": "home",
    "fullTitle": "KFC Testclub - FC Elders",
    "fullDescription": "<strong>Competitie</strong>",
    "teamNames": "U10",
    "attendanceStatus": "PRESENT",
    "competitionType": "Competitie",
    "location": {"fullAddress": "Oude baan 374"},
    "meetingHour": "12:00",
    "cancelled": False,
    "scoreFinal": "13-0",
}

RAW_EVENT = {
    "id": 6787,
    "type": "game",
    "start": "2099-01-10 10:00",
    "end": "2099-01-10 11:15",
    "subtype": "away",
    "fullTitle": "FC Elders - KFC Testclub",
    "teamNames": "U10",
    "attendanceStatus": "PRESENT",
    "competitionType": "Competitie",
    "cancelled": False,
}

RAW_TRAINING = {
    "id": 18161,
    "type": "training",
    "start": "2099-01-08 16:15",
    "end": "2099-01-08 17:30",
    "fullTitle": "Training Mottekamp",
    "teamNames": "U10",
    "attendanceStatus": "PRESENT",
    "cancelled": False,
}

PAYMENT = {
    "id": 5,
    "amount": "45.50",
    "status": "paid",
    "description": "Lidgeld",
    "sentDate": "2026-07-01",
    "dueDate": "2026-07-31",
}

MESSAGE = {
    "id": 11,
    "subject": "Training verplaatst",
    "sender": {"firstName": "Jan", "lastName": "Coach"},
    "date": "2026-09-01 10:00",
    "firstSentence": "Beste ouders",
    "attachments": [],
    "receivers": [{"id": 3, "read": False, "type": "MEMBER"}],
}

TEAMS = {
    "member": {
        "id": 7486,
        "firstName": "Sam",
        "lastName": "Peeters",
        "teamId": 3,
        "age": 8,
    },
    "user": {
        "username": "parent@example.test",
        "member": {"myTeamName": "U10", "teamIds": [3]},
    },
}

TEAM_MEMBERS = [
    {"name": "Sam Peeters", "keeper": False, "shirt_number": 7, "position": None},
]


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(
    enable_custom_integrations: None,
) -> None:
    """Let Home Assistant load the integration from custom_components."""
    return


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """A config entry for one tracked player."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=f"ProSoccerData ({EMAIL})",
        unique_id=f"prosoccerdata_{EMAIL}",
        data={
            CONF_EMAIL: EMAIL,
            CONF_PASSWORD: PASSWORD,
            CONF_PLAYERS: [PLAYER],
        },
    )


def build_api_mock() -> AsyncMock:
    """An API client that answers every call with usable data."""
    api = AsyncMock()
    api.login.return_value = None
    api.get_players.return_value = [PLAYER]
    api.get_previous_matches.return_value = [RAW_MATCH]
    api.get_payment_requests.return_value = [PAYMENT]
    api.get_teams.return_value = TEAMS
    api.get_messages.return_value = {"content": [MESSAGE], "totalElements": 55}
    api.get_schedule.return_value = [RAW_EVENT, RAW_TRAINING]
    api.get_team_members.return_value = TEAM_MEMBERS
    api.get_unread_messages.return_value = [MESSAGE]
    api.get_message_detail.return_value = {
        "id": 11,
        "subject": "Training verplaatst",
        "date": "2026-09-01 10:00",
        "message": "<p>Beste ouders</p>",
    }
    api.set_messages_read.return_value = None
    api.get_event_presences.return_value = (
        "/schedule/game/6786/presences/ALL",
        [{"player": {"firstName": "Sam", "lastName": "Peeters"}, "present": True}],
    )

    # These are plain functions on the real client, not coroutines.
    from custom_components.prosoccerdata.api import ProSoccerDataAPI

    api.parse_match = ProSoccerDataAPI.parse_match
    api.parse_event = ProSoccerDataAPI.parse_event
    return api


@pytest.fixture
def mock_api() -> Generator[AsyncMock]:
    """Patch the API client everywhere the integration builds one."""
    api = build_api_mock()

    with (
        patch(
            "custom_components.prosoccerdata.ProSoccerDataAPI",
            return_value=api,
        ),
        patch(
            "custom_components.prosoccerdata.config_flow.build_api",
            return_value=api,
        ),
    ):
        yield api


async def setup_integration(
    hass: HomeAssistant, entry: MockConfigEntry
) -> MockConfigEntry:
    """Add the entry and run setup to completion."""
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry
