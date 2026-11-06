"""Tests for the devices a ProSoccerData entry owns, and for removing them."""

from __future__ import annotations

from unittest.mock import AsyncMock

from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from custom_components.prosoccerdata import async_remove_config_entry_device
from custom_components.prosoccerdata.const import CONF_PLAYERS, DOMAIN

from .conftest import PLAYER, SECOND_PLAYER, setup_integration

MEMBER = str(PLAYER["platformMemberId"])
SECOND_MEMBER = str(SECOND_PLAYER["platformMemberId"])


def member_ids(registry: dr.DeviceRegistry, entry_id: str) -> set[str]:
    """Return the ProSoccerData member ids the entry still has devices for."""
    return {
        identifier
        for device in dr.async_entries_for_config_entry(registry, entry_id)
        for domain, identifier in device.identifiers
        if domain == DOMAIN
    }


async def test_dropping_a_player_removes_its_device(
    hass: HomeAssistant,
    mock_api: AsyncMock,
    mock_config_entry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """A player that is no longer selected loses its device on the reload."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_PLAYERS: [PLAYER, SECOND_PLAYER]}
    )
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert member_ids(device_registry, mock_config_entry.entry_id) == {
        MEMBER,
        SECOND_MEMBER,
    }

    # Options changes reload the entry, which is when the cleanup runs.
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_PLAYERS: [PLAYER]}
    )
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert member_ids(device_registry, mock_config_entry.entry_id) == {MEMBER}


async def test_a_tracked_device_cannot_be_deleted_by_hand(
    hass: HomeAssistant,
    mock_api: AsyncMock,
    mock_config_entry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Deleting a tracked player's device is refused; it would just come back."""
    await setup_integration(hass, mock_config_entry)

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, MEMBER), mock_config_entry.entry_id
    )
    assert device is not None

    assert not await async_remove_config_entry_device(
        hass, mock_config_entry, device
    )


async def test_an_untracked_device_can_be_deleted_by_hand(
    hass: HomeAssistant,
    mock_api: AsyncMock,
    mock_config_entry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """A device left over from a player that is gone may be deleted."""
    await setup_integration(hass, mock_config_entry)

    leftover = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "4242")},
        name="Someone who left",
    )

    assert await async_remove_config_entry_device(hass, mock_config_entry, leftover)


async def test_diagnostic_entities_are_categorised(
    hass: HomeAssistant,
    mock_api: AsyncMock,
    mock_config_entry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Profile and account describe the login, not the football."""
    await setup_integration(hass, mock_config_entry)

    for key in ("profile", "account"):
        entry = entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"prosoccerdata_{MEMBER}_{key}"
        )
        assert entry is not None
        assert (
            entity_registry.async_get(entry).entity_category
            is EntityCategory.DIAGNOSTIC
        )


async def test_the_account_sensor_starts_switched_off(
    hass: HomeAssistant,
    mock_api: AsyncMock,
    mock_config_entry,
    entity_registry: er.EntityRegistry,
) -> None:
    """The account sensor is the same for every player, so it is off by default."""
    await setup_integration(hass, mock_config_entry)

    account = entity_registry.async_get(
        entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"prosoccerdata_{MEMBER}_account"
        )
    )
    assert account.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert hass.states.get(account.entity_id) is None

    # Everything that is about the player itself stays on.
    last_match = entity_registry.async_get(
        entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"prosoccerdata_{MEMBER}_last_match"
        )
    )
    assert last_match.disabled_by is None
