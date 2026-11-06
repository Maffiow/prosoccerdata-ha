"""Tests for setting up and tearing down the ProSoccerData entry."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from custom_components.prosoccerdata.api import AuthError, ProSoccerDataError
from custom_components.prosoccerdata.const import (
    CONF_PLAYERS,
    CONF_SCAN_INTERVAL_MINUTES,
)

from .conftest import SECOND_PLAYER, setup_integration


async def test_setup_and_unload(
    hass: HomeAssistant, mock_api: AsyncMock, mock_config_entry
) -> None:
    """A good entry loads its platforms and unloads cleanly."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data is not None

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_starts_reauth_on_bad_credentials(
    hass: HomeAssistant, mock_api: AsyncMock, mock_config_entry
) -> None:
    """A rejected password asks the user to sign in again."""
    mock_api.login.side_effect = AuthError("nope")

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert [flow["context"]["source"] for flow in flows] == ["reauth"]


async def test_setup_retries_when_unreachable(
    hass: HomeAssistant, mock_api: AsyncMock, mock_config_entry
) -> None:
    """An unreachable service leaves the entry to be retried."""
    mock_api.login.side_effect = ProSoccerDataError("down")

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_options_drive_players_and_interval(
    hass: HomeAssistant, mock_api: AsyncMock, mock_config_entry
) -> None:
    """Options win over the values captured during the config flow."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={CONF_PLAYERS: [SECOND_PLAYER], CONF_SCAN_INTERVAL_MINUTES: 90},
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    assert coordinator.players == [SECOND_PLAYER]
    assert coordinator.update_interval.total_seconds() == 90 * 60


@pytest.mark.parametrize("platform", ["sensor", "calendar"])
async def test_platforms_declare_no_parallel_updates(platform: str) -> None:
    """Coordinator-driven platforms must not serialise their updates."""
    module = __import__(
        f"custom_components.prosoccerdata.{platform}", fromlist=["PARALLEL_UPDATES"]
    )
    assert module.PARALLEL_UPDATES == 0
