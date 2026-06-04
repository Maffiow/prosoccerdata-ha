import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ProSoccerDataAPI
from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class ProSoccerDataCoordinator(DataUpdateCoordinator):
    """Fetch match, payment and profile data for all selected players."""

    def __init__(self, hass: HomeAssistant, api: ProSoccerDataAPI, players: list[dict]) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)
        self.api = api
        self.players = players

    async def _async_update_data(self) -> dict[str, Any]:
        result: dict[str, Any] = {}

        for player in self.players:
            member_id = player["platformMemberId"]
            name = (
                f"{player.get('platformUserFirstName') or player.get('platformMemberFirstName', '?')}"
                f" {player.get('platformUserLastName') or player.get('platformMemberLastName', '?')}"
            )

            try:
                raw_matches = await self.api.get_previous_matches(player)
                parsed_matches = [self.api.parse_match(m) for m in raw_matches]

                payment_requests = await self.api.get_payment_requests(player)
                teams = await self.api.get_teams(player)

                result[str(member_id)] = {
                    "player": player,
                    "matches": parsed_matches,
                    "last_match": parsed_matches[0] if parsed_matches else None,
                    "payment_requests": payment_requests,
                    "last_payment_request": payment_requests[0] if payment_requests else None,
                    "teams": teams,
                }

                _LOGGER.debug(
                    "Fetched %d matches, %d payment requests and profile/team data for %s",
                    len(parsed_matches),
                    len(payment_requests),
                    name,
                )

            except Exception as err:
                _LOGGER.error("Error fetching data for %s: %s", name, err)

                result[str(member_id)] = {
                    "player": player,
                    "matches": [],
                    "last_match": None,
                    "payment_requests": [],
                    "last_payment_request": None,
                    "teams": {},
                }

        if not result:
            raise UpdateFailed("No data returned for any player")

        return result
