"""Tests for how the coordinator copes with partial and total failures."""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.prosoccerdata.api import AuthError, ProSoccerDataError
from custom_components.prosoccerdata.const import CONF_PLAYERS

from .conftest import PLAYER, SECOND_PLAYER, setup_integration


async def test_refresh_collects_every_block(
    hass: HomeAssistant, mock_api: AsyncMock, mock_config_entry
) -> None:
    """One refresh fills matches, payments, messages and the schedule."""
    await setup_integration(hass, mock_config_entry)
    data = mock_config_entry.runtime_data.data[str(PLAYER["platformMemberId"])]

    assert data["last_match"]["opponent"] == "FC Elders"
    assert data["last_payment_request"]["status"] == "paid"
    assert data["last_message"]["subject"] == "Training verplaatst"
    # The cancelled flag is respected and the events come back sorted.
    assert [event["type"] for event in data["upcoming"]] == ["training", "game"]
    assert data["next_match"]["opponent"] == "FC Elders"
    assert data["next_training"]["full_title"] == "Training Mottekamp"


async def test_one_failing_player_keeps_the_other(
    hass: HomeAssistant, mock_api: AsyncMock, mock_config_entry
) -> None:
    """A player that fails does not take the whole entry down."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_PLAYERS: [PLAYER, SECOND_PLAYER]}
    )

    async def fail_for_second(player, *args, **kwargs):
        if player["platformMemberId"] == SECOND_PLAYER["platformMemberId"]:
            raise ProSoccerDataError("HTTP 500")
        return []

    mock_api.get_previous_matches.side_effect = fail_for_second

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    data = mock_config_entry.runtime_data.data
    assert str(PLAYER["platformMemberId"]) in data
    # The failing player has no previous data to fall back on, so it is absent.
    assert str(SECOND_PLAYER["platformMemberId"]) not in data


async def test_every_player_failing_raises(
    hass: HomeAssistant, mock_api: AsyncMock, mock_config_entry
) -> None:
    """When nothing can be fetched the refresh fails as a whole."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data

    mock_api.get_previous_matches.side_effect = ProSoccerDataError("HTTP 500")

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_auth_error_during_refresh_triggers_reauth(
    hass: HomeAssistant, mock_api: AsyncMock, mock_config_entry
) -> None:
    """A rejected session asks for the password rather than retrying forever."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data

    mock_api.get_previous_matches.side_effect = AuthError("expired")

    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()


async def test_failure_is_logged_once_and_recovery_is_reported(
    hass: HomeAssistant,
    mock_api: AsyncMock,
    mock_config_entry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A player that keeps failing warns once, not on every refresh."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data

    mock_api.get_previous_matches.side_effect = ProSoccerDataError("HTTP 500")

    with caplog.at_level(logging.DEBUG):
        caplog.clear()
        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()
        first = [r for r in caplog.records if r.levelno == logging.WARNING]

        caplog.clear()
        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()
        second = [r for r in caplog.records if r.levelno == logging.WARNING]

    assert len(first) == 1
    assert second == []

    # Recovering says so, once.
    mock_api.get_previous_matches.side_effect = None
    with caplog.at_level(logging.INFO):
        caplog.clear()
        await coordinator._async_update_data()

    recovered = [r for r in caplog.records if r.levelno == logging.INFO]
    assert any("works again" in r.message for r in recovered)


async def test_schedule_failure_is_not_fatal(
    hass: HomeAssistant, mock_api: AsyncMock, mock_config_entry
) -> None:
    """Losing the schedule leaves the other sensors working."""
    mock_api.get_schedule.side_effect = ProSoccerDataError("HTTP 404")

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    data = mock_config_entry.runtime_data.data[str(PLAYER["platformMemberId"])]
    assert data["upcoming"] == []
    assert data["next_match"] is None
    assert data["last_match"] is not None


async def test_team_members_without_a_team(
    hass: HomeAssistant, mock_api: AsyncMock, mock_config_entry
) -> None:
    """Without a team id there is nobody to look up."""
    mock_api.get_teams.return_value = {"member": {}, "user": {}}

    await setup_integration(hass, mock_config_entry)

    data = mock_config_entry.runtime_data.data[str(PLAYER["platformMemberId"])]
    assert data["team_members"] == []
    mock_api.get_team_members.assert_not_awaited()


async def test_team_members_failure_is_not_fatal(
    hass: HomeAssistant, mock_api: AsyncMock, mock_config_entry
) -> None:
    """Losing the squad list leaves the rest of the player's data intact."""
    mock_api.get_team_members.side_effect = ProSoccerDataError("HTTP 403")

    await setup_integration(hass, mock_config_entry)

    data = mock_config_entry.runtime_data.data[str(PLAYER["platformMemberId"])]
    assert data["team_members"] == []
    assert data["last_match"] is not None


async def test_unread_falls_back_to_the_inbox_page(
    hass: HomeAssistant, mock_api: AsyncMock, mock_config_entry
) -> None:
    """When the unread endpoint fails, unread is derived from the inbox."""
    mock_api.get_unread_messages.side_effect = ProSoccerDataError("HTTP 404")

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.sam_peeters_unread_message_count")
    # The single fixture message is unread, so the fallback still finds it.
    assert state.state == "1"


async def test_auth_error_on_a_side_fetch_still_asks_for_the_password(
    hass: HomeAssistant, mock_api: AsyncMock, mock_config_entry
) -> None:
    """A rejected session anywhere in a refresh triggers reauth."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data

    mock_api.get_team_members.side_effect = AuthError("expired")

    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()


@pytest.mark.parametrize(
    ("raw", "parses"),
    [
        ("2026-08-29 10:00", True),
        ("2026-08-29 10:00:00", True),
        ("2026-08-29T10:00:00", True),
        ("2026-08-29T10:00:00.000Z", True),
        ("", False),
        (None, False),
        ("nonsense", False),
    ],
)
def test_timestamp_parsing(raw: str | None, parses: bool) -> None:
    """ProSoccerData's naive timestamps are read in every shape it sends."""
    from custom_components.prosoccerdata.coordinator import as_local_datetime

    parsed = as_local_datetime(raw)

    assert (parsed is not None) is parses
    if parses:
        assert parsed.tzinfo is not None
