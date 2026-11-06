"""Tests for the ProSoccerData config, reauth and options flows."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from homeassistant.config_entries import SOURCE_RECONFIGURE, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.prosoccerdata.api import AuthError, ProSoccerDataError
from custom_components.prosoccerdata.const import (
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_PLAYER_IDS,
    CONF_PLAYERS,
    CONF_SCAN_INTERVAL_MINUTES,
    DOMAIN,
)

from .conftest import EMAIL, PASSWORD, PLAYER, SECOND_PLAYER, setup_integration

CREDENTIALS = {CONF_EMAIL: EMAIL, CONF_PASSWORD: PASSWORD}


async def start_user_flow(hass: HomeAssistant) -> dict:
    """Open the user step."""
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )


async def test_user_flow_creates_entry(hass: HomeAssistant, mock_api: AsyncMock) -> None:
    """The happy path asks for credentials, then for players."""
    result = await start_user_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], CREDENTIALS
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "select_players"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PLAYER_IDS: [str(PLAYER["platformMemberId"])]}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"ProSoccerData ({EMAIL})"
    assert result["data"][CONF_EMAIL] == EMAIL
    assert result["data"][CONF_PASSWORD] == PASSWORD
    assert result["data"][CONF_PLAYERS] == [PLAYER]
    assert result["result"].unique_id == f"prosoccerdata_{EMAIL}"
    # The credentials are checked before the entry is created.
    assert mock_api.login.called


@pytest.mark.parametrize(
    ("side_effect", "expected"),
    [
        (AuthError("invalid"), "invalid_auth"),
        (ProSoccerDataError("boom"), "cannot_connect"),
        (RuntimeError("surprise"), "unknown"),
    ],
)
async def test_user_flow_login_errors(
    hass: HomeAssistant,
    mock_api: AsyncMock,
    side_effect: Exception,
    expected: str,
) -> None:
    """A failed login keeps the form open and names the problem."""
    mock_api.login.side_effect = side_effect

    result = await start_user_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], CREDENTIALS
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected}

    # Recovering from the error completes the flow.
    mock_api.login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], CREDENTIALS
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "select_players"


async def test_user_flow_without_players(
    hass: HomeAssistant, mock_api: AsyncMock
) -> None:
    """An account with no players cannot be configured."""
    mock_api.get_players.return_value = []

    result = await start_user_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], CREDENTIALS
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_players"}


async def test_user_flow_requires_a_selection(
    hass: HomeAssistant, mock_api: AsyncMock
) -> None:
    """Submitting the player step empty re-shows it with an error."""
    result = await start_user_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], CREDENTIALS
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PLAYER_IDS: []}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "select_players"
    assert result["errors"] == {"base": "no_players_selected"}


async def test_user_flow_aborts_on_duplicate(
    hass: HomeAssistant, mock_api: AsyncMock, mock_config_entry
) -> None:
    """The same account cannot be added twice."""
    mock_config_entry.add_to_hass(hass)

    result = await start_user_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], CREDENTIALS
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PLAYER_IDS: [str(PLAYER["platformMemberId"])]}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_stores_the_new_password(
    hass: HomeAssistant, mock_api: AsyncMock, mock_config_entry
) -> None:
    """Reauth verifies the password before saving it."""
    await setup_integration(hass, mock_config_entry)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "new-secret"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_PASSWORD] == "new-secret"
    # Everything else is left alone.
    assert mock_config_entry.data[CONF_EMAIL] == EMAIL


@pytest.mark.parametrize(
    ("side_effect", "expected"),
    [
        (AuthError("invalid"), "invalid_auth"),
        (ProSoccerDataError("boom"), "cannot_connect"),
        (RuntimeError("surprise"), "unknown"),
    ],
)
async def test_reauth_errors(
    hass: HomeAssistant,
    mock_api: AsyncMock,
    mock_config_entry,
    side_effect: Exception,
    expected: str,
) -> None:
    """A password that still fails keeps the reauth form open."""
    await setup_integration(hass, mock_config_entry)
    mock_api.login.side_effect = side_effect

    result = await mock_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "still-wrong"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected}
    assert mock_config_entry.data[CONF_PASSWORD] == PASSWORD


async def test_options_flow(
    hass: HomeAssistant, mock_api: AsyncMock, mock_config_entry
) -> None:
    """The options flow changes the players and the poll interval."""
    mock_api.get_players.return_value = [PLAYER, SECOND_PLAYER]
    await setup_integration(hass, mock_config_entry)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_PLAYER_IDS: [str(SECOND_PLAYER["platformMemberId"])],
            CONF_SCAN_INTERVAL_MINUTES: 60,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options[CONF_SCAN_INTERVAL_MINUTES] == 60
    assert mock_config_entry.options[CONF_PLAYERS] == [SECOND_PLAYER]


async def test_options_flow_requires_a_selection(
    hass: HomeAssistant, mock_api: AsyncMock, mock_config_entry
) -> None:
    """Clearing every player is refused."""
    await setup_integration(hass, mock_config_entry)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_PLAYER_IDS: [], CONF_SCAN_INTERVAL_MINUTES: 30},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_players_selected"}


@pytest.mark.parametrize(
    ("side_effect", "expected"),
    [
        (AuthError("invalid"), "invalid_auth"),
        (ProSoccerDataError("boom"), "cannot_connect"),
    ],
)
async def test_options_flow_aborts_when_unreachable(
    hass: HomeAssistant,
    mock_api: AsyncMock,
    mock_config_entry,
    side_effect: Exception,
    expected: str,
) -> None:
    """The options flow needs the player list, so it aborts without one."""
    await setup_integration(hass, mock_config_entry)
    mock_api.login.side_effect = side_effect

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == expected


async def start_reconfigure_flow(hass: HomeAssistant, entry) -> dict:
    """Open the reconfigure step for an existing entry."""
    return await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
    )


async def test_reconfigure_changes_password_and_players(
    hass: HomeAssistant, mock_api: AsyncMock, mock_config_entry
) -> None:
    """Reconfiguring re-enters the credentials and the selection in one pass."""
    mock_api.get_players.return_value = [PLAYER, SECOND_PLAYER]
    await setup_integration(hass, mock_config_entry)

    result = await start_reconfigure_flow(hass, mock_config_entry)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_EMAIL: EMAIL, CONF_PASSWORD: "new-secret"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure_players"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PLAYER_IDS: [str(SECOND_PLAYER["platformMemberId"])]},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_PASSWORD] == "new-secret"
    assert mock_config_entry.data[CONF_PLAYERS] == [SECOND_PLAYER]


async def test_reconfigure_moves_the_options_selection_too(
    hass: HomeAssistant, mock_api: AsyncMock, mock_config_entry
) -> None:
    """An entry whose players live in its options has those replaced as well."""
    mock_api.get_players.return_value = [PLAYER, SECOND_PLAYER]
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={CONF_PLAYERS: [PLAYER], CONF_SCAN_INTERVAL_MINUTES: 45},
    )
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await start_reconfigure_flow(hass, mock_config_entry)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], CREDENTIALS
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PLAYER_IDS: [str(SECOND_PLAYER["platformMemberId"])]},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert mock_config_entry.options[CONF_PLAYERS] == [SECOND_PLAYER]
    # The interval is left where it was.
    assert mock_config_entry.options[CONF_SCAN_INTERVAL_MINUTES] == 45


async def test_reconfigure_refuses_another_account(
    hass: HomeAssistant, mock_api: AsyncMock, mock_config_entry
) -> None:
    """The email is the entry's unique id, so it cannot be swapped here."""
    await setup_integration(hass, mock_config_entry)

    result = await start_reconfigure_flow(hass, mock_config_entry)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_EMAIL: "someone.else@example.test", CONF_PASSWORD: PASSWORD},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "account_mismatch"
    assert mock_config_entry.data[CONF_EMAIL] == EMAIL


@pytest.mark.parametrize(
    ("side_effect", "expected"),
    [
        (AuthError("invalid"), "invalid_auth"),
        (AuthError("no_players"), "no_players"),
        (ProSoccerDataError("boom"), "cannot_connect"),
        (RuntimeError("surprise"), "unknown"),
    ],
)
async def test_reconfigure_errors(
    hass: HomeAssistant,
    mock_api: AsyncMock,
    mock_config_entry,
    side_effect: Exception,
    expected: str,
) -> None:
    """A login that fails keeps the reconfigure form open."""
    await setup_integration(hass, mock_config_entry)
    mock_api.login.side_effect = side_effect

    result = await start_reconfigure_flow(hass, mock_config_entry)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], CREDENTIALS
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected}


async def test_reconfigure_requires_a_selection(
    hass: HomeAssistant, mock_api: AsyncMock, mock_config_entry
) -> None:
    """Clearing every player in the reconfigure flow is refused."""
    await setup_integration(hass, mock_config_entry)

    result = await start_reconfigure_flow(hass, mock_config_entry)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], CREDENTIALS
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PLAYER_IDS: []}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure_players"
    assert result["errors"] == {"base": "no_players_selected"}

