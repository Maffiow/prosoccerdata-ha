"""Sensors for the ProSoccerData integration."""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import ProSoccerDataConfigEntry
from .const import (
    ATTR_ATTENDANCE,
    ATTR_COMPETITION,
    ATTR_EVENT_TYPE,
    ATTR_HOME_AWAY,
    ATTR_LOCATION,
    ATTR_MATCH_END,
    ATTR_MATCH_START,
    ATTR_MEETING_HOUR,
    ATTR_OPPONENT,
    ATTR_RECENT_MATCHES,
    ATTR_SCORE,
    ATTR_TEAM,
    ATTR_TITLE,
    DOMAIN,
    MATCH_ATTRIBUTE_LIMIT,
    MESSAGE_ATTRIBUTE_LIMIT,
)
from .coordinator import (
    ProSoccerDataCoordinator,
    as_local_datetime,
    player_name,
)

_LOGGER = logging.getLogger(__name__)

CURRENCY_EURO = "EUR"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ProSoccerDataConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the ProSoccerData sensors."""
    coordinator = entry.runtime_data

    entities: list[ProSoccerDataBaseSensor] = []
    for player in coordinator.players:
        entities.extend(
            sensor_class(coordinator, player)
            for sensor_class in (
                ProSoccerDataNextMatchSensor,
                ProSoccerDataNextTrainingSensor,
                ProSoccerDataLastMatchSensor,
                ProSoccerDataLastPaymentAmountSensor,
                ProSoccerDataLastPaymentStatusSensor,
                ProSoccerDataTotalPaidSensor,
                ProSoccerDataPaymentCountSensor,
                ProSoccerDataProfileSensor,
                ProSoccerDataTeamSensor,
                ProSoccerDataAccountSensor,
                ProSoccerDataMessageCountSensor,
                ProSoccerDataUnreadMessageCountSensor,
                ProSoccerDataLastMessageSensor,
                ProSoccerDataMessagesSensor,
            )
        )

    async_add_entities(entities)


class ProSoccerDataBaseSensor(CoordinatorEntity[ProSoccerDataCoordinator], SensorEntity):
    """Base sensor for ProSoccerData."""

    _attr_has_entity_name = True

    # Set by each subclass; also used for the unique_id suffix, so changing one
    # of these renames the entity.
    _key: str

    def __init__(
        self, coordinator: ProSoccerDataCoordinator, player: dict[str, Any]
    ) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator)
        self._player = player

        member_id = player["platformMemberId"]
        club = player.get("platform", "ProSoccerData")

        self._attr_unique_id = f"prosoccerdata_{member_id}_{self._key}"
        self._attr_translation_key = self._key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(member_id))},
            name=player_name(player),
            manufacturer="ProSoccerData",
            model=club,
            configuration_url=player.get("platformURL"),
        )

    @property
    def available(self) -> bool:
        """Only report available when this player actually has data."""
        return super().available and self._player_data is not None

    @property
    def _player_data(self) -> dict[str, Any] | None:
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(str(self._player["platformMemberId"]))

    def _section(self, key: str, default: Any) -> Any:
        """Return one block of this player's data, falling back to `default`."""
        data = self._player_data
        if not data:
            return default
        return data.get(key) or default

    @property
    def _teams(self) -> dict[str, Any]:
        return self._section("teams", {})


class ProSoccerDataNextEventSensor(ProSoccerDataBaseSensor):
    """Base for the sensors that point at the next scheduled event."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    # Set by each subclass to the coordinator key holding the event.
    _event_key: str

    @property
    def _event(self) -> dict[str, Any]:
        return self._section(self._event_key, {})

    @property
    def native_value(self) -> datetime | None:
        """Return when the event starts."""
        return as_local_datetime(self._event.get("start"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the details of the upcoming event."""
        event = self._event

        if not event:
            return {}

        return {
            ATTR_TITLE: event.get("full_title"),
            ATTR_EVENT_TYPE: event.get("type"),
            ATTR_MATCH_END: event.get("end"),
            ATTR_TEAM: event.get("team"),
            ATTR_COMPETITION: event.get("competition"),
            ATTR_LOCATION: event.get("location"),
            ATTR_MEETING_HOUR: event.get("meeting_hour"),
            "meeting_location": event.get("meeting_location"),
            ATTR_ATTENDANCE: event.get("attendance"),
        }


class ProSoccerDataNextMatchSensor(ProSoccerDataNextEventSensor):
    """When the player's next match starts."""

    _key = "next_match"
    _event_key = "next_match"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the details of the upcoming match."""
        attributes = super().extra_state_attributes

        if not attributes:
            return {}

        event = self._event

        return {
            **attributes,
            ATTR_OPPONENT: event.get("opponent"),
            ATTR_HOME_AWAY: event.get("home_away"),
        }


class ProSoccerDataNextTrainingSensor(ProSoccerDataNextEventSensor):
    """When the player's next training starts."""

    _key = "next_training"
    _event_key = "next_training"


class ProSoccerDataLastMatchSensor(ProSoccerDataBaseSensor):
    """Date of the player's most recent match."""

    _key = "last_match"
    _attr_device_class = SensorDeviceClass.DATE
    _unrecorded_attributes = frozenset({ATTR_RECENT_MATCHES})

    @property
    def native_value(self) -> date | None:
        """Return the match date."""
        last = self._section("last_match", {})
        raw = last.get("date")

        if not raw:
            return None

        try:
            return date.fromisoformat(raw)
        except (TypeError, ValueError):
            _LOGGER.debug("Unparseable match date %r", raw)
            return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return details of the last match plus a short history."""
        last = self._section("last_match", {})
        recent = self._section("matches", [])

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
            ATTR_RECENT_MATCHES: [
                {
                    "date": match.get("date"),
                    "opponent": match.get("opponent"),
                    "score": match.get("score"),
                    "home_away": match.get("home_away"),
                    "competition": match.get("competition"),
                    "cancelled": match.get("cancelled"),
                }
                for match in recent[:MATCH_ATTRIBUTE_LIMIT]
            ],
        }


class ProSoccerDataLastPaymentAmountSensor(ProSoccerDataBaseSensor):
    """Amount of the most recent payment request."""

    _key = "last_payment_amount"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = CURRENCY_EURO

    @property
    def native_value(self) -> float | None:
        """Return the requested amount."""
        payment = self._section("last_payment_request", {})
        return _as_float(payment.get("amount"))


class ProSoccerDataLastPaymentStatusSensor(ProSoccerDataBaseSensor):
    """Status of the most recent payment request."""

    _key = "last_payment_status"

    @property
    def native_value(self) -> str | None:
        """Return the payment status."""
        return self._section("last_payment_request", {}).get("status")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return details of the most recent payment request."""
        payment = self._section("last_payment_request", {})

        return {
            "id": payment.get("id"),
            "description": _payment_description(payment),
            "amount": payment.get("amount"),
            "sent_date": payment.get("sentDate"),
            "due_date": payment.get("dueDate"),
            "paid": payment.get("paid"),
        }


class ProSoccerDataTotalPaidSensor(ProSoccerDataBaseSensor):
    """Total of the fetched payment requests that are marked paid."""

    _key = "total_paid"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = CURRENCY_EURO

    @property
    def native_value(self) -> float:
        """Return the sum of the paid payment requests."""
        return round(
            sum(
                _as_float(payment.get("amount")) or 0.0
                for payment in self._section("payment_requests", [])
                if payment.get("status") == "paid"
            ),
            2,
        )


class ProSoccerDataPaymentCountSensor(ProSoccerDataBaseSensor):
    """Number of fetched payment requests."""

    _key = "payment_count"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _unrecorded_attributes = frozenset({"payment_requests"})

    @property
    def native_value(self) -> int:
        """Return how many payment requests were fetched."""
        return len(self._section("payment_requests", []))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return a summary of the fetched payment requests."""
        payments = self._section("payment_requests", [])

        return {
            "payment_requests": [
                {
                    "id": payment.get("id"),
                    "description": _payment_description(payment),
                    "amount": payment.get("amount"),
                    "status": payment.get("status"),
                    "sent_date": payment.get("sentDate"),
                    "due_date": payment.get("dueDate"),
                    "paid": payment.get("paid"),
                }
                for payment in payments[:MATCH_ATTRIBUTE_LIMIT]
            ]
        }


class ProSoccerDataProfileSensor(ProSoccerDataBaseSensor):
    """Member profile information."""

    _key = "profile"

    @property
    def native_value(self) -> str | None:
        """Return the member's full name."""
        member = self._teams.get("member") or {}
        name = f"{member.get('firstName') or ''} {member.get('lastName') or ''}".strip()
        return name or None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the member's profile fields."""
        member = self._teams.get("member") or {}

        return {
            "member_id": member.get("id"),
            "first_name": member.get("firstName"),
            "last_name": member.get("lastName"),
            "nickname": member.get("nickname"),
            "local_name": member.get("localName"),
            "birth_date": member.get("birthDate"),
            "age": member.get("age"),
            "status": member.get("status"),
            "active": member.get("active"),
            "gender": member.get("gender"),
            "keeper": member.get("keeper"),
            "foot": member.get("foot"),
            "shirt_number": member.get("shirtNumber"),
            "language": member.get("languagePSD"),
            "uuid": member.get("uuid"),
            "central_psd_id": member.get("centralPsdId"),
            "profile_picture_url": member.get("profilePictureURL"),
        }


class ProSoccerDataTeamSensor(ProSoccerDataBaseSensor):
    """Team information for the member."""

    _key = "team"

    @property
    def _user_member(self) -> dict[str, Any]:
        return (self._teams.get("user") or {}).get("member") or {}

    @property
    def native_value(self) -> str | None:
        """Return the team name."""
        user_member = self._user_member
        member = self._teams.get("member") or {}

        return (
            user_member.get("myTeamName")
            or user_member.get("teamName")
            or member.get("teamId")
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the member's team and club fields."""
        user_member = self._user_member
        member = self._teams.get("member") or {}

        return {
            "team_id": member.get("teamId") or user_member.get("team"),
            "team_ids": user_member.get("teamIds"),
            "team_name": user_member.get("myTeamName") or user_member.get("teamName"),
            "team_subcategory": user_member.get("teamSubcategory"),
            "team_international": member.get("teamInternational"),
            "team_international_subcategory": user_member.get(
                "teamInternationalSubcategory"
            ),
            "club_id": member.get("clubId") or user_member.get("clubId"),
            "club_international": member.get("clubInternational"),
            "role_name": user_member.get("roleName"),
            "function_title": member.get("functionTitle")
            or user_member.get("functionTitle"),
            "main_sportive_role": user_member.get("mainSportiveRole"),
            "main_sportive_role_id": member.get("mainSportiveRoleId"),
        }


class ProSoccerDataAccountSensor(ProSoccerDataBaseSensor):
    """ProSoccerData account information."""

    _key = "account"

    @property
    def native_value(self) -> str | None:
        """Return the account username."""
        return (self._teams.get("user") or {}).get("username")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the account fields."""
        user = self._teams.get("user") or {}
        user_member = user.get("member") or {}

        return {
            "user_id": user.get("id"),
            "username": user.get("username"),
            "email": user.get("email"),
            "central_user_id": user.get("centralUserId"),
            "is_active": user.get("isActive"),
            "first_login_date": user.get("firstLoginDate"),
            "last_login_date": user.get("lastLoginDate"),
            "notifications_view": user.get("notificationsView"),
            "accepted_terms_of_use": user_member.get("acceptedTermsOfUse"),
            "has_profile_picture": user_member.get("hasProfilePicture"),
            "profile_picture_version": user_member.get("profilePictureVersion"),
            "creation_date": user_member.get("creationDate"),
            "last_modified_date": user_member.get("lastModifiedDate"),
            "link_status": user_member.get("linkStatus"),
            "external": user_member.get("external"),
            "uid": user_member.get("uid"),
        }


class ProSoccerDataMessageCountSensor(ProSoccerDataBaseSensor):
    """Total number of inbox messages reported by ProSoccerData."""

    _key = "message_count"
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> int:
        """Return the inbox total."""
        messages_data = self._section("messages_data", {})
        return messages_data.get("totalElements", len(self._section("messages", [])))


class ProSoccerDataUnreadMessageCountSensor(ProSoccerDataBaseSensor):
    """Number of unread messages in the fetched inbox page."""

    _key = "unread_message_count"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _unrecorded_attributes = frozenset({"messages", "messages_text"})

    @property
    def _unread(self) -> list[dict[str, Any]]:
        return [
            message
            for message in self._section("messages", [])
            if _message_is_unread(message)
        ]

    @property
    def native_value(self) -> int:
        """Return how many fetched messages are unread."""
        return len(self._unread)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the unread messages, both structured and as a ready-made list."""
        unread = self._unread

        return {
            "latest_subject": unread[0].get("subject") if unread else None,
            "messages": [
                _message_summary(message)
                for message in unread[:MESSAGE_ATTRIBUTE_LIMIT]
            ],
            "messages_text": "\n".join(
                f"• {message.get('date')} | {_sender_name(message)}"
                f" | {message.get('subject')}"
                for message in unread[:MESSAGE_ATTRIBUTE_LIMIT]
            ),
        }


class ProSoccerDataLastMessageSensor(ProSoccerDataBaseSensor):
    """Subject of the most recent inbox message."""

    _key = "last_message"
    _unrecorded_attributes = frozenset({"attachments", "receivers"})

    @property
    def native_value(self) -> str | None:
        """Return the subject of the newest message."""
        return self._section("last_message", {}).get("subject")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the full detail of the newest message."""
        message = self._section("last_message", {})

        if not message:
            return {}

        return _message_summary(message, full=True)


class ProSoccerDataMessagesSensor(ProSoccerDataBaseSensor):
    """Number of fetched inbox messages, with a summary of each."""

    _key = "messages"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _unrecorded_attributes = frozenset({"messages"})

    @property
    def native_value(self) -> int:
        """Return how many messages were fetched."""
        return len(self._section("messages", []))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return a summary of the fetched messages."""
        messages_data = self._section("messages_data", {})
        messages = self._section("messages", [])

        return {
            "total_elements": messages_data.get("totalElements"),
            "number_of_elements": messages_data.get("numberOfElements"),
            "total_pages": messages_data.get("totalPages"),
            "messages": [
                _message_summary(message)
                for message in messages[:MESSAGE_ATTRIBUTE_LIMIT]
            ],
        }


def _as_float(value: Any) -> float | None:
    """Return `value` as a float, or None when it is not numeric."""
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _payment_description(payment: dict[str, Any]) -> str | None:
    return payment.get("description") or payment.get("name") or payment.get("title")


def _sender_name(message: dict[str, Any]) -> str | None:
    sender = message.get("sender") or {}
    name = f"{sender.get('firstName') or ''} {sender.get('lastName') or ''}".strip()
    return name or None


def _message_is_unread(message: dict[str, Any]) -> bool:
    return any(
        receiver.get("read") is False for receiver in message.get("receivers") or []
    )


def _message_summary(message: dict[str, Any], *, full: bool = False) -> dict[str, Any]:
    """Summarise a message.

    The compact form is used for list attributes, which are written to the
    recorder on every update; only the single newest message carries the full
    attachment and receiver detail.
    """
    attachments = message.get("attachments") or []
    receivers = message.get("receivers") or []

    summary: dict[str, Any] = {
        "id": message.get("id"),
        "subject": message.get("subject"),
        "sender": _sender_name(message),
        "date": message.get("date"),
        "first_sentence": message.get("firstSentence"),
        "unread": _message_is_unread(message),
        "attachment_count": len(attachments),
        "receiver_count": len(receivers),
    }

    if not full:
        return summary

    return {
        **summary,
        "deleted": message.get("deleted"),
        "draft": message.get("draft"),
        "attachments": [
            {
                "file_name": attachment.get("fileName"),
                "url": attachment.get("attachmentUrl"),
            }
            for attachment in attachments
        ],
        "receivers": [
            {
                "id": receiver.get("id"),
                "type": receiver.get("type"),
                "status": receiver.get("status"),
                "read": receiver.get("read"),
                "marked": receiver.get("marked"),
                "external_sent_date": receiver.get("externalSentDate"),
            }
            for receiver in receivers
        ],
    }
