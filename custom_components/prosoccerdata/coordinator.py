"""Data coordinator for the ProSoccerData integration."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import AuthError, ProSoccerDataAPI, ProSoccerDataError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def player_name(player: dict[str, Any]) -> str:
    """Return a display name for a player record."""
    first = (
        player.get("platformUserFirstName")
        or player.get("platformMemberFirstName")
        or "?"
    )
    last = (
        player.get("platformUserLastName")
        or player.get("platformMemberLastName")
        or "?"
    )
    return f"{first} {last}"


class ProSoccerDataCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetch match, payment, profile and mailbox data for the selected players."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: ProSoccerDataAPI,
        players: list[dict[str, Any]],
        update_interval: timedelta,
    ) -> None:
        """Initialise the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=update_interval,
        )
        self.api = api
        self.players = players

    async def _async_update_data(self) -> dict[str, Any]:
        """Refresh every player, keeping the last good data for those that fail."""
        previous: dict[str, Any] = self.data or {}
        result: dict[str, Any] = {}
        failures: list[str] = []

        for player in self.players:
            key = str(player["platformMemberId"])
            name = player_name(player)

            try:
                result[key] = await self._fetch_player(player)
            except AuthError:
                # Credentials or session are no longer valid for the whole
                # account, so stop here and let Home Assistant ask again.
                raise ConfigEntryAuthFailed(
                    "ProSoccerData rejected the stored credentials"
                ) from None
            except (ProSoccerDataError, KeyError, TypeError, ValueError) as err:
                _LOGGER.warning("Error fetching data for %s: %s", name, err)
                failures.append(name)
                # Keep serving the previous values rather than blanking the
                # sensors on a single bad refresh.
                if key in previous:
                    result[key] = previous[key]

        if failures and len(failures) == len(self.players):
            raise UpdateFailed(
                f"No data could be fetched for: {', '.join(failures)}"
            )

        if not result:
            raise UpdateFailed("No players are configured")

        return result

    async def _fetch_player(self, player: dict[str, Any]) -> dict[str, Any]:
        """Fetch everything the sensors need for one player."""
        raw_matches = await self.api.get_previous_matches(player)
        matches = [self.api.parse_match(match) for match in raw_matches]

        payment_requests = await self.api.get_payment_requests(player)
        teams = await self.api.get_teams(player)

        messages_data = await self.api.get_messages(player)
        messages = messages_data.get("content", [])

        _LOGGER.debug(
            "Fetched %d matches, %d payment requests and %d messages for %s",
            len(matches),
            len(payment_requests),
            len(messages),
            player_name(player),
        )

        return {
            "player": player,
            "matches": matches,
            "last_match": matches[0] if matches else None,
            "payment_requests": payment_requests,
            "last_payment_request": payment_requests[0] if payment_requests else None,
            "teams": teams,
            "messages_data": messages_data,
            "messages": messages,
            "last_message": messages[0] if messages else None,
        }
