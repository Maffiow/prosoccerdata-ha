"""Data coordinator for the ProSoccerData integration."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import AuthError, ProSoccerDataAPI, ProSoccerDataError
from .const import (
    DOMAIN,
    EVENT_TYPE_GAME,
    EVENT_TYPE_TRAINING,
    SCHEDULE_FUTURE_DAYS,
    SCHEDULE_PAST_DAYS,
)

_LOGGER = logging.getLogger(__name__)

# ProSoccerData sends local wall-clock times without an offset.
_TIME_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M")


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


def as_local_datetime(value: str | None) -> datetime | None:
    """Parse one of ProSoccerData's naive timestamps into an aware datetime.

    The API has no offset in its timestamps: they are wall-clock times in the
    club's time zone, which is the one we send in the Clienttimezone header.
    """
    if not value:
        return None

    text = value.strip()
    if "." in text:
        text = text.split(".", 1)[0]
    if text.endswith("Z"):
        text = text[:-1]

    for fmt in _TIME_FORMATS:
        try:
            naive = datetime.strptime(text, fmt)
        except ValueError:
            continue
        return naive.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE)

    _LOGGER.debug("Unparseable ProSoccerData timestamp %r", value)
    return None


class ProSoccerDataCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetch schedule, match, payment, profile and mailbox data per player."""

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
        # The message each player last opened through the open_message action,
        # keyed like the player data. Lives outside `data` so a refresh does
        # not wipe what the dashboard is showing.
        self.selected_messages: dict[str, dict[str, Any]] = {}

    async def async_open_message(
        self, player: dict[str, Any], message_id: int
    ) -> dict[str, Any]:
        """Fetch a message's full body and expose it as the selected message."""
        mail = await self.api.get_message_detail(player, message_id)
        if not mail:
            raise ProSoccerDataError(f"Message {message_id} was not found")

        key = str(player["platformMemberId"])
        unread_ids = {
            message.get("id")
            for message in unread_messages((self.data or {}).get(key) or {})
        }
        mail["unread"] = mail.get("id") in unread_ids

        self.selected_messages[key] = mail
        self.async_update_listeners()
        return mail

    async def async_set_message_read(
        self, player: dict[str, Any], message_id: int, read: bool
    ) -> None:
        """Change a message's read flag and reflect it without waiting for a poll."""
        await self.api.set_messages_read(player, [message_id], read)

        key = str(player["platformMemberId"])
        selected = self.selected_messages.get(key)
        if selected and selected.get("id") == message_id:
            selected["unread"] = not read

        await self.async_request_refresh()

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
            raise UpdateFailed(f"No data could be fetched for: {', '.join(failures)}")

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
        unread_messages = await self._fetch_unread(player)
        team_members = await self._fetch_team_members(player, teams)

        upcoming = await self._fetch_upcoming(player)

        _LOGGER.debug(
            "Fetched %d matches, %d payment requests, %d messages and"
            " %d upcoming events for %s",
            len(matches),
            len(payment_requests),
            len(messages),
            len(upcoming),
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
            "unread_messages": unread_messages,
            "team_members": team_members,
            "upcoming": upcoming,
            "next_match": _first_of_type(upcoming, EVENT_TYPE_GAME),
            "next_training": _first_of_type(upcoming, EVENT_TYPE_TRAINING),
        }

    async def _fetch_team_members(
        self, player: dict[str, Any], teams: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Return the player's teammates; an empty list when unavailable."""
        team_id = (teams.get("member") or {}).get("teamId") or (
            (teams.get("user") or {}).get("member") or {}
        ).get("team")
        if not team_id:
            return []

        try:
            return await self.api.get_team_members(player, team_id)
        except AuthError:
            raise
        except (ProSoccerDataError, AttributeError, KeyError, TypeError, ValueError) as err:
            _LOGGER.debug(
                "Could not fetch the team members for %s: %s", player_name(player), err
            )
            return []

    async def _fetch_unread(
        self, player: dict[str, Any]
    ) -> list[dict[str, Any]] | None:
        """Return the unread messages, or None when the endpoint is unavailable.

        The inbox page only covers the newest messages, so an old unread one
        would be missed there; this endpoint lists them all. A failure falls
        back to deriving unread messages from the inbox page.
        """
        try:
            return await self.api.get_unread_messages(player)
        except AuthError:
            raise
        except (ProSoccerDataError, AttributeError, KeyError, TypeError, ValueError) as err:
            _LOGGER.debug(
                "Could not fetch unread messages for %s: %s", player_name(player), err
            )
            return None

    async def _fetch_upcoming(self, player: dict[str, Any]) -> list[dict[str, Any]]:
        """Return the player's schedule for the rolling window, soonest first.

        A failure here is deliberately not fatal: the schedule endpoint is the
        newest thing this integration talks to, and losing it should not take
        the match, payment and mailbox sensors down with it.
        """
        now = dt_util.now()

        try:
            raw_events = await self.api.get_schedule(
                player,
                now - timedelta(days=SCHEDULE_PAST_DAYS),
                now + timedelta(days=SCHEDULE_FUTURE_DAYS),
            )
            events = [self.api.parse_event(event) for event in raw_events]
        except AuthError:
            raise
        except (ProSoccerDataError, AttributeError, KeyError, TypeError, ValueError) as err:
            _LOGGER.warning(
                "Could not fetch the schedule for %s: %s", player_name(player), err
            )
            return []

        return sorted(
            (event for event in events if not event.get("cancelled")),
            key=lambda event: as_local_datetime(event.get("start")) or dt_util.utcnow(),
        )


def message_is_unread(message: dict[str, Any]) -> bool:
    """Return whether the account has not read this message yet."""
    return any(
        receiver.get("read") is False for receiver in message.get("receivers") or []
    )


def unread_messages(player_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Return a player's unread messages, newest first.

    Prefers the dedicated unread listing; when that could not be fetched, falls
    back to the unread messages on the fetched inbox page.
    """
    unread = player_data.get("unread_messages")
    if unread is not None:
        return unread
    return [
        message
        for message in player_data.get("messages") or []
        if message_is_unread(message)
    ]


def _first_of_type(
    events: list[dict[str, Any]], event_type: str
) -> dict[str, Any] | None:
    """Return the soonest event of a type that has not started yet."""
    now = dt_util.now()

    for event in events:
        if event.get("type") != event_type:
            continue
        start = as_local_datetime(event.get("start"))
        if start and start >= now:
            return event

    return None
