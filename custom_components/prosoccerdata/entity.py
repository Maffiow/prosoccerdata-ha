"""Base entity for the ProSoccerData integration."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ProSoccerDataCoordinator, player_name


class ProSoccerDataEntity(CoordinatorEntity[ProSoccerDataCoordinator]):
    """An entity belonging to one tracked player.

    Every platform hangs its entities off the player's device and reads the
    same slice of the coordinator's data, so that lives here rather than being
    repeated per platform.
    """

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ProSoccerDataCoordinator,
        player: dict[str, Any],
        key: str,
    ) -> None:
        """Initialise the entity for one player."""
        super().__init__(coordinator)
        self._player = player

        member_id = player["platformMemberId"]

        self._attr_unique_id = f"prosoccerdata_{member_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(member_id))},
            name=player_name(player),
            manufacturer="ProSoccerData",
            model=player.get("platform", "ProSoccerData"),
            configuration_url=player.get("platformURL"),
        )

    @property
    def available(self) -> bool:
        """Only report available while this player actually has data."""
        return super().available and self._player_data is not None

    @property
    def _player_data(self) -> dict[str, Any] | None:
        """Return this player's slice of the coordinator's data."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(str(self._player["platformMemberId"]))

    def _section(self, key: str, default: Any) -> Any:
        """Return one block of this player's data, falling back to `default`."""
        data = self._player_data
        if not data:
            return default
        return data.get(key) or default
