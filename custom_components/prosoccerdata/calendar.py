"""Calendar platform for the ProSoccerData integration."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import ProSoccerDataConfigEntry
from .api import ProSoccerDataError
from .const import EVENT_TYPE_GAME
from .coordinator import ProSoccerDataCoordinator, as_local_datetime, player_name
from .entity import ProSoccerDataEntity

_LOGGER = logging.getLogger(__name__)

# The coordinator drives every refresh; async_get_events fetches on demand.
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ProSoccerDataConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a calendar per tracked player."""
    coordinator = entry.runtime_data

    async_add_entities(
        ProSoccerDataCalendar(coordinator, player) for player in coordinator.players
    )


class ProSoccerDataCalendar(ProSoccerDataEntity, CalendarEntity):
    """The player's ProSoccerData schedule: matches, trainings and other events."""

    def __init__(
        self, coordinator: ProSoccerDataCoordinator, player: dict[str, Any]
    ) -> None:
        """Initialise the calendar."""
        super().__init__(coordinator, player, "schedule")

    @property
    def _upcoming(self) -> list[dict[str, Any]]:
        return self._section("upcoming", [])

    @property
    def event(self) -> CalendarEvent | None:
        """Return the event that is running now, else the next one."""
        now = dt_util.now()
        upcoming: CalendarEvent | None = None

        for raw in self._upcoming:
            event = _to_calendar_event(raw)
            if event is None:
                continue

            if event.start <= now < event.end:
                return event
            if event.start >= now and (upcoming is None or event.start < upcoming.start):
                upcoming = event

        return upcoming

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Return the events in a window, asked for directly by the calendar panel.

        The coordinator only keeps a rolling window, so anything outside it is
        fetched on demand rather than cached.
        """
        try:
            raw_events = await self.coordinator.api.get_schedule(
                self._player, dt_util.as_local(start_date), dt_util.as_local(end_date)
            )
        except ProSoccerDataError as err:
            _LOGGER.warning(
                "Could not fetch the schedule for %s: %s",
                player_name(self._player),
                err,
            )
            return []

        events = []
        for raw in raw_events:
            parsed = self.coordinator.api.parse_event(raw)
            if parsed.get("cancelled"):
                continue
            if (event := _to_calendar_event(parsed)) is not None:
                events.append(event)

        return sorted(events, key=lambda event: event.start)


def _to_calendar_event(parsed: dict[str, Any]) -> CalendarEvent | None:
    """Turn a parsed ProSoccerData event into a Home Assistant calendar event."""
    start = as_local_datetime(parsed.get("start"))

    if start is None:
        return None

    # A missing end would make the event invalid; assume it runs an hour.
    end = as_local_datetime(parsed.get("end"))
    if end is None or end <= start:
        end = start + timedelta(hours=1)

    return CalendarEvent(
        summary=parsed.get("full_title") or parsed.get("team") or "ProSoccerData",
        start=start,
        end=end,
        location=parsed.get("location") or parsed.get("meeting_location") or None,
        description=_describe(parsed) or None,
        uid=f"{parsed.get('type', 'event')}-{parsed.get('id')}",
    )


def _describe(parsed: dict[str, Any]) -> str:
    """Build a readable description out of the fields worth surfacing."""
    parts: list[str] = []

    if parsed.get("type") == EVENT_TYPE_GAME:
        if opponent := parsed.get("opponent"):
            parts.append(f"Opponent: {opponent}")
        if home_away := parsed.get("home_away"):
            parts.append(home_away)

    for label, key in (
        ("Team", "team"),
        ("Competition", "competition"),
        ("Meeting time", "meeting_hour"),
        ("Meeting point", "meeting_location"),
        ("Attendance", "attendance"),
    ):
        if value := parsed.get(key):
            parts.append(f"{label}: {value}")

    return "\n".join(parts)
