"""Tests for the ProSoccerData actions and the diagnostics dump."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from pytest_homeassistant_custom_component.components.diagnostics import (
    get_diagnostics_for_config_entry,
)

from custom_components.prosoccerdata.api import AuthError, ProSoccerDataError
from custom_components.prosoccerdata.const import CONF_PASSWORD, DOMAIN

from .conftest import PASSWORD, PLAYER, setup_integration

MEMBER = PLAYER["platformMemberId"]


async def test_actions_are_registered_without_an_entry(hass: HomeAssistant) -> None:
    """The actions exist as soon as the integration is set up."""
    from custom_components.prosoccerdata import async_setup

    await async_setup(hass, {})

    for action in ("open_message", "mark_message_read", "get_attendance"):
        assert hass.services.has_service(DOMAIN, action)


async def test_actions_refuse_to_run_without_a_loaded_entry(
    hass: HomeAssistant,
) -> None:
    """With no account loaded there is no mailbox to act on."""
    from custom_components.prosoccerdata import async_setup

    await async_setup(hass, {})

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "open_message",
            {"message_id": 11},
            blocking=True,
            return_response=True,
        )


async def test_open_message_returns_the_body(
    hass: HomeAssistant, mock_api: AsyncMock, mock_config_entry
) -> None:
    """Opening a message hands back its text and remembers it."""
    await setup_integration(hass, mock_config_entry)

    response = await hass.services.async_call(
        DOMAIN,
        "open_message",
        {"message_id": 11},
        blocking=True,
        return_response=True,
    )

    assert response["subject"] == "Training verplaatst"
    assert "Beste ouders" in response["body_html"]

    selected = hass.states.get("sensor.sam_peeters_selected_message")
    assert selected is not None
    assert selected.state == "Training verplaatst"


async def test_open_message_reports_a_refusal(
    hass: HomeAssistant, mock_api: AsyncMock, mock_config_entry
) -> None:
    """A failed fetch surfaces as an error, not as an empty answer."""
    await setup_integration(hass, mock_config_entry)
    mock_api.get_message_detail.side_effect = ProSoccerDataError("HTTP 500")

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            "open_message",
            {"message_id": 11},
            blocking=True,
            return_response=True,
        )


async def test_mark_message_read_needs_a_message(
    hass: HomeAssistant, mock_api: AsyncMock, mock_config_entry
) -> None:
    """Without an id and without a previously opened message, it refuses."""
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, "mark_message_read", {}, blocking=True
        )


async def test_mark_message_read(
    hass: HomeAssistant, mock_api: AsyncMock, mock_config_entry
) -> None:
    """Marking a message read passes the id on to ProSoccerData."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        DOMAIN, "mark_message_read", {"message_id": 11}, blocking=True
    )

    mock_api.set_messages_read.assert_awaited()
    args = mock_api.set_messages_read.await_args.args
    assert args[1] == [11]
    assert args[2] is True


async def test_unknown_member_is_rejected(
    hass: HomeAssistant, mock_api: AsyncMock, mock_config_entry
) -> None:
    """A member id that matches no configured player is a validation error."""
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "open_message",
            {"message_id": 11, "member_id": 1},
            blocking=True,
            return_response=True,
        )


@pytest.mark.parametrize("event", ["game-6786", "6786"])
async def test_get_attendance(
    hass: HomeAssistant, mock_api: AsyncMock, mock_config_entry, event: str
) -> None:
    """The attendance action accepts a uid or a bare id."""
    await setup_integration(hass, mock_config_entry)

    response = await hass.services.async_call(
        DOMAIN,
        "get_attendance",
        {"event": event},
        blocking=True,
        return_response=True,
    )

    assert response["event_id"] == 6786
    assert response["count"] == 1
    assert response["players"][0]["name"] == "Sam Peeters"


async def test_get_attendance_rejects_a_bad_event(
    hass: HomeAssistant, mock_api: AsyncMock, mock_config_entry
) -> None:
    """An event reference without digits cannot name an event."""
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "get_attendance",
            {"event": "nonsense"},
            blocking=True,
            return_response=True,
        )


async def test_get_attendance_reports_a_refusal(
    hass: HomeAssistant, mock_api: AsyncMock, mock_config_entry
) -> None:
    """Being denied the list is reported as such."""
    await setup_integration(hass, mock_config_entry)
    mock_api.get_event_presences.side_effect = AuthError("not allowed")

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            "get_attendance",
            {"event": "game-6786"},
            blocking=True,
            return_response=True,
        )


async def test_diagnostics_redacts_credentials(
    hass: HomeAssistant, hass_client, mock_api: AsyncMock, mock_config_entry
) -> None:
    """The dump carries the state but never the password."""
    await setup_integration(hass, mock_config_entry)

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert diagnostics["entry"]["data"][CONF_PASSWORD] != PASSWORD
    assert diagnostics["coordinator"]["player_count"] == 1
    assert PASSWORD not in str(diagnostics)
