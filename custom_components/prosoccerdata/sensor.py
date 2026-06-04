import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    ATTR_TEAM,
    ATTR_OPPONENT,
    ATTR_SCORE,
    ATTR_HOME_AWAY,
    ATTR_COMPETITION,
    ATTR_LOCATION,
    ATTR_MEETING_HOUR,
    ATTR_RECENT_MATCHES,
    ATTR_MATCH_START,
    ATTR_MATCH_END,
    ATTR_ATTENDANCE,
)
from .coordinator import ProSoccerDataCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: ProSoccerDataCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        ProSoccerDataSensor(coordinator, player)
        for player in coordinator.players
    ]
    async_add_entities(entities)


class ProSoccerDataSensor(CoordinatorEntity, SensorEntity):
    """One sensor per tracked player showing their last played match date."""

    _attr_icon = "mdi:soccer"

    def __init__(
        self,
        coordinator: ProSoccerDataCoordinator,
        player: dict,
    ) -> None:
        super().__init__(coordinator)
        self._player = player
        member_id = player["platformMemberId"]
        first = player.get("platformUserFirstName") or player.get("platformMemberFirstName", "?")
        last = player.get("platformUserLastName") or player.get("platformMemberLastName", "?")
        club = player.get("platform", "ProSoccerData")

        self._attr_unique_id = f"prosoccerdata_{member_id}_last_match"
        self._attr_name = f"{first} {last} – Last Match"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(member_id))},
            name=f"{first} {last}",
            manufacturer="ProSoccerData",
            model=club,
            configuration_url=player.get("platformURL"),
        )

    @property
    def _player_data(self) -> dict | None:
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(str(self._player["platformMemberId"]))

    @property
    def native_value(self) -> str | None:
        """State is the date of the last played match (YYYY-MM-DD)."""
        data = self._player_data
        if data and data.get("last_match"):
            return data["last_match"].get("date")
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self._player_data
        if not data:
            return {}

        last = data.get("last_match") or {}
        recent = data.get("matches", [])

        # Summarised list for the attribute (keep last 10)
        recent_summary = [
            {
                "date": m.get("date"),
                "opponent": m.get("opponent"),
                "score": m.get("score"),
                "home_away": m.get("home_away"),
                "competition": m.get("competition"),
                "cancelled": m.get("cancelled"),
            }
            for m in recent[:10]
        ]

        payments = data.get("payment_requests", [])
        last_payment = data.get("last_payment_request") or {}

        payment_summary = [
            {
                "id": p.get("id"),
                "description": p.get("description") or p.get("name") or p.get("title"),
                "amount": p.get("amount"),
                "status": p.get("status"),
                "sent_date": p.get("sentDate"),
                "due_date": p.get("dueDate"),
                "paid": p.get("paid"),
            }
            for p in payments[:10]
        ]

        return {
            ATTR_MATCH_START: last.get("start"),
            ATTR_MATCH_END: last.get("end"),
            ATTR_TEAM: last.get("team"),
            ATTR_OPPONENT: last.get("opponent"),
            ATTR_SCORE: last.get("score"),
            ATTR_HOME_AWAY: last.get("home_away"),
            ATTR_COMPETITION: last.get("competition"),
            ATTR_LOCATION: last.get("location"),
            ATTR_MEETING_HOUR: last.get("meeting_hour"),
            ATTR_ATTENDANCE: last.get("attendance"),
            "full_title": last.get("full_title"),
            ATTR_RECENT_MATCHES: recent_summary,

            # Finance/payment attributes
            "last_payment_request": {
                "id": last_payment.get("id"),
                "description": (
                    last_payment.get("description")
                    or last_payment.get("name")
                    or last_payment.get("title")
                ),
                "amount": last_payment.get("amount"),
                "status": last_payment.get("status"),
                "sent_date": last_payment.get("sentDate"),
                "due_date": last_payment.get("dueDate"),
                "paid": last_payment.get("paid"),
            },
            "payment_requests": payment_summary,
        }
