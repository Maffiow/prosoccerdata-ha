"""Tests for the sensor and calendar entities."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from custom_components.prosoccerdata.api import ProSoccerDataError
from custom_components.prosoccerdata.const import DOMAIN

from .conftest import PLAYER, setup_integration

MEMBER = str(PLAYER["platformMemberId"])


async def test_entities_are_created_on_one_device(
    hass: HomeAssistant,
    mock_api: AsyncMock,
    mock_config_entry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Every entity carries a unique id and hangs off the player's device."""
    await setup_integration(hass, mock_config_entry)

    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert entities

    device = device_registry.async_get_device(identifiers={(DOMAIN, MEMBER)})
    assert device is not None
    assert device.name == "Sam Peeters"
    assert device.manufacturer == "ProSoccerData"

    for entry in entities:
        assert entry.unique_id.startswith(f"prosoccerdata_{MEMBER}_")
        assert entry.device_id == device.id

    # Both platforms are represented.
    assert {entry.domain for entry in entities} == {"sensor", "calendar"}


async def test_sensor_states(
    hass: HomeAssistant, mock_api: AsyncMock, mock_config_entry
) -> None:
    """The headline sensors read the values the coordinator collected."""
    await setup_integration(hass, mock_config_entry)

    last_match = hass.states.get("sensor.sam_peeters_last_match")
    assert last_match is not None
    assert last_match.state == "2026-10-31"
    assert last_match.attributes["opponent"] == "FC Elders"
    assert last_match.attributes["score"] == "13-0"

    total_paid = hass.states.get("sensor.sam_peeters_total_paid")
    assert total_paid.state == "45.5"

    message_count = hass.states.get("sensor.sam_peeters_message_count")
    assert message_count.state == "55"


async def test_next_match_is_a_timestamp(
    hass: HomeAssistant, mock_api: AsyncMock, mock_config_entry
) -> None:
    """The next-event sensors expose a real timestamp, not a string."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.sam_peeters_next_match")
    assert state is not None
    assert state.attributes["device_class"] == "timestamp"
    assert dt_util.parse_datetime(state.state) is not None
    assert state.attributes["opponent"] == "FC Elders"


async def test_calendar_lists_the_schedule(
    hass: HomeAssistant, mock_api: AsyncMock, mock_config_entry
) -> None:
    """The calendar answers a range query from the API."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("calendar.sam_peeters_schedule")
    assert state is not None

    events = await hass.services.async_call(
        "calendar",
        "get_events",
        {
            "entity_id": "calendar.sam_peeters_schedule",
            "start_date_time": "2099-01-01 00:00:00",
            "end_date_time": "2099-02-01 00:00:00",
        },
        blocking=True,
        return_response=True,
    )

    summaries = [
        event["summary"]
        for event in events["calendar.sam_peeters_schedule"]["events"]
    ]
    assert "Training Mottekamp" in summaries
    assert "FC Elders - KFC Testclub" in summaries


async def test_calendar_survives_a_failed_range_query(
    hass: HomeAssistant, mock_api: AsyncMock, mock_config_entry
) -> None:
    """A refused range query yields no events rather than an error."""
    await setup_integration(hass, mock_config_entry)
    mock_api.get_schedule.side_effect = ProSoccerDataError("HTTP 500")

    events = await hass.services.async_call(
        "calendar",
        "get_events",
        {
            "entity_id": "calendar.sam_peeters_schedule",
            "start_date_time": "2099-01-01 00:00:00",
            "end_date_time": "2099-02-01 00:00:00",
        },
        blocking=True,
        return_response=True,
    )

    assert events["calendar.sam_peeters_schedule"]["events"] == []


async def test_entities_go_unavailable_without_data(
    hass: HomeAssistant, mock_api: AsyncMock, mock_config_entry, freezer
) -> None:
    """When a refresh stops returning the player, its entities say so."""
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get("sensor.sam_peeters_last_match").state != STATE_UNAVAILABLE

    mock_api.get_previous_matches.side_effect = ProSoccerDataError("HTTP 500")
    coordinator = mock_config_entry.runtime_data
    # Drop what was kept from the last good refresh, so nothing is served.
    coordinator.data = None

    freezer.tick(coordinator.update_interval + timedelta(minutes=1))
    async_fire = __import__(
        "pytest_homeassistant_custom_component.common",
        fromlist=["async_fire_time_changed"],
    ).async_fire_time_changed
    async_fire(hass, dt_util.utcnow() + coordinator.update_interval)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.sam_peeters_last_match").state == STATE_UNAVAILABLE
    assert hass.states.get("calendar.sam_peeters_schedule").state == STATE_UNAVAILABLE
