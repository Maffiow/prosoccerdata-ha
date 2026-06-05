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
    coordinator: ProSoccerDataCoordinator = entry.runtime_data

    entities = []
    for player in coordinator.players:
        entities.extend(
            [
                ProSoccerDataLastMatchSensor(coordinator, player),
                ProSoccerDataLastPaymentAmountSensor(coordinator, player),
                ProSoccerDataLastPaymentStatusSensor(coordinator, player),
                ProSoccerDataTotalPaidSensor(coordinator, player),
                ProSoccerDataPaymentCountSensor(coordinator, player),
                ProSoccerDataProfileSensor(coordinator, player),
                ProSoccerDataTeamSensor(coordinator, player),
                ProSoccerDataAccountSensor(coordinator, player),
                ProSoccerDataMessageCountSensor(coordinator, player),
                ProSoccerDataUnreadMessageCountSensor(coordinator, player),
                ProSoccerDataLastMessageSensor(coordinator, player),
                ProSoccerDataMessagesSensor(coordinator, player),
                ProSoccerDataUnreadMessagesSensor(coordinator, player),
            ]
        )

    async_add_entities(entities)


class ProSoccerDataBaseSensor(CoordinatorEntity, SensorEntity):
    """Base sensor for ProSoccerData."""

    def __init__(
        self,
        coordinator: ProSoccerDataCoordinator,
        player: dict,
        key: str,
        name_suffix: str,
        icon: str,
    ) -> None:
        super().__init__(coordinator)
        self._player = player

        member_id = player["platformMemberId"]
        first = player.get("platformUserFirstName") or player.get("platformMemberFirstName", "?")
        last = player.get("platformUserLastName") or player.get("platformMemberLastName", "?")
        club = player.get("platform", "ProSoccerData")

        self._attr_unique_id = f"prosoccerdata_{member_id}_{key}"
        self._attr_has_entity_name = True
        self._attr_name = name_suffix
        self._attr_icon = icon
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


class ProSoccerDataLastMatchSensor(ProSoccerDataBaseSensor):
    """Sensor showing last match date."""

    def __init__(self, coordinator: ProSoccerDataCoordinator, player: dict) -> None:
        super().__init__(
            coordinator,
            player,
            key="last_match",
            name_suffix="Last Match",
            icon="mdi:soccer",
        )

    @property
    def native_value(self) -> str | None:
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
        }


class ProSoccerDataLastPaymentAmountSensor(ProSoccerDataBaseSensor):
    """Sensor showing latest payment amount."""

    _attr_native_unit_of_measurement = "EUR"

    def __init__(self, coordinator: ProSoccerDataCoordinator, player: dict) -> None:
        super().__init__(
            coordinator,
            player,
            key="last_payment_amount",
            name_suffix="Last Payment Amount",
            icon="mdi:cash",
        )

    @property
    def native_value(self) -> float | None:
        data = self._player_data
        payment = (data or {}).get("last_payment_request") or {}
        amount = payment.get("amount")

        try:
            return float(amount) if amount is not None else None
        except (TypeError, ValueError):
            return None


class ProSoccerDataLastPaymentStatusSensor(ProSoccerDataBaseSensor):
    """Sensor showing latest payment status."""

    def __init__(self, coordinator: ProSoccerDataCoordinator, player: dict) -> None:
        super().__init__(
            coordinator,
            player,
            key="last_payment_status",
            name_suffix="Last Payment Status",
            icon="mdi:cash-check",
        )

    @property
    def native_value(self) -> str | None:
        data = self._player_data
        payment = (data or {}).get("last_payment_request") or {}
        return payment.get("status")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self._player_data
        payment = (data or {}).get("last_payment_request") or {}

        return {
            "id": payment.get("id"),
            "description": (
                payment.get("description")
                or payment.get("name")
                or payment.get("title")
            ),
            "amount": payment.get("amount"),
            "sent_date": payment.get("sentDate"),
            "due_date": payment.get("dueDate"),
            "paid": payment.get("paid"),
        }


class ProSoccerDataTotalPaidSensor(ProSoccerDataBaseSensor):
    """Sensor showing total paid amount from fetched payment requests."""

    _attr_native_unit_of_measurement = "EUR"

    def __init__(self, coordinator: ProSoccerDataCoordinator, player: dict) -> None:
        super().__init__(
            coordinator,
            player,
            key="total_paid",
            name_suffix="Total Paid",
            icon="mdi:cash-multiple",
        )

    @property
    def native_value(self) -> float:
        data = self._player_data
        payments = (data or {}).get("payment_requests", [])

        total = 0.0
        for payment in payments:
            if payment.get("status") == "paid":
                amount = payment.get("amount")
                try:
                    if amount is not None:
                        total += float(amount)
                except (TypeError, ValueError):
                    pass

        return total


class ProSoccerDataPaymentCountSensor(ProSoccerDataBaseSensor):
    """Sensor showing number of fetched payment requests."""

    def __init__(self, coordinator: ProSoccerDataCoordinator, player: dict) -> None:
        super().__init__(
            coordinator,
            player,
            key="payment_count",
            name_suffix="Payment Count",
            icon="mdi:counter",
        )

    @property
    def native_value(self) -> int:
        data = self._player_data
        payments = (data or {}).get("payment_requests", [])
        return len(payments)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self._player_data
        payments = (data or {}).get("payment_requests", [])

        return {
            "payment_requests": [
                {
                    "id": p.get("id"),
                    "description": (
                        p.get("description")
                        or p.get("name")
                        or p.get("title")
                    ),
                    "amount": p.get("amount"),
                    "status": p.get("status"),
                    "sent_date": p.get("sentDate"),
                    "due_date": p.get("dueDate"),
                    "paid": p.get("paid"),
                }
                for p in payments[:10]
            ]
        }


class ProSoccerDataProfileSensor(ProSoccerDataBaseSensor):
    """Sensor showing member profile information."""

    def __init__(self, coordinator: ProSoccerDataCoordinator, player: dict) -> None:
        super().__init__(
            coordinator,
            player,
            key="profile",
            name_suffix="Profile",
            icon="mdi:account",
        )

    @property
    def native_value(self) -> str | None:
        data = self._player_data
        member = ((data or {}).get("teams") or {}).get("member", {})
        first = member.get("firstName")
        last = member.get("lastName")

        if first or last:
            return f"{first or ''} {last or ''}".strip()

        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self._player_data
        member = ((data or {}).get("teams") or {}).get("member", {})

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
    """Sensor showing member team information."""

    def __init__(self, coordinator: ProSoccerDataCoordinator, player: dict) -> None:
        super().__init__(
            coordinator,
            player,
            key="team",
            name_suffix="Team",
            icon="mdi:account-group",
        )

    @property
    def native_value(self) -> str | None:
        data = self._player_data
        teams_data = (data or {}).get("teams") or {}
        user_member = ((teams_data.get("user") or {}).get("member") or {})
        member = teams_data.get("member") or {}

        return (
            user_member.get("myTeamName")
            or user_member.get("teamName")
            or member.get("teamId")
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self._player_data
        teams_data = (data or {}).get("teams") or {}
        user_member = ((teams_data.get("user") or {}).get("member") or {})
        member = teams_data.get("member") or {}

        return {
            "team_id": member.get("teamId") or user_member.get("team"),
            "team_ids": user_member.get("teamIds"),
            "team_name": user_member.get("myTeamName") or user_member.get("teamName"),
            "team_subcategory": user_member.get("teamSubcategory"),
            "team_international": member.get("teamInternational"),
            "team_international_subcategory": user_member.get("teamInternationalSubcategory"),
            "club_id": member.get("clubId") or user_member.get("clubId"),
            "club_international": member.get("clubInternational"),
            "role_name": user_member.get("roleName"),
            "function_title": member.get("functionTitle") or user_member.get("functionTitle"),
            "main_sportive_role": user_member.get("mainSportiveRole"),
            "main_sportive_role_id": member.get("mainSportiveRoleId"),
        }

def _sender_name(message: dict) -> str | None:
    sender = message.get("sender") or {}
    first = sender.get("firstName")
    last = sender.get("lastName")

    if first or last:
        return f"{first or ''} {last or ''}".strip()

    return None


def _message_is_unread(message: dict) -> bool:
    receivers = message.get("receivers") or []

    return any(
        receiver.get("read") is False
        for receiver in receivers
    )


def _message_summary(message: dict) -> dict:
    attachments = message.get("attachments") or []
    receivers = message.get("receivers") or []

    return {
        "id": message.get("id"),
        "subject": message.get("subject"),
        "sender": _sender_name(message),
        "date": message.get("date"),
        "first_sentence": message.get("firstSentence"),
        "deleted": message.get("deleted"),
        "draft": message.get("draft"),
        "unread": _message_is_unread(message),
        "has_attachments": len(attachments) > 0,
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

class ProSoccerDataMessageCountSensor(ProSoccerDataBaseSensor):
    """Sensor showing total PSD inbox message count."""

    def __init__(self, coordinator: ProSoccerDataCoordinator, player: dict) -> None:
        super().__init__(
            coordinator,
            player,
            key="message_count",
            name_suffix="Message Count",
            icon="mdi:email",
        )

    @property
    def native_value(self) -> int:
        data = self._player_data
        messages_data = (data or {}).get("messages_data") or {}
        messages = (data or {}).get("messages", [])

        return messages_data.get("totalElements", len(messages))

class ProSoccerDataUnreadMessageCountSensor(ProSoccerDataBaseSensor):
    """Sensor showing unread PSD inbox message count."""

    def __init__(self, coordinator: ProSoccerDataCoordinator, player: dict) -> None:
        super().__init__(
            coordinator,
            player,
            key="unread_message_count",
            name_suffix="Unread Message Count",
            icon="mdi:email-alert",
        )

    @property
    def native_value(self) -> int:
        data = self._player_data
        messages = (data or {}).get("messages", [])

        return sum(
            1
            for message in messages
            if _message_is_unread(message)
        )

class ProSoccerDataLastMessageSensor(ProSoccerDataBaseSensor):
    """Sensor showing latest PSD inbox message."""

    def __init__(self, coordinator: ProSoccerDataCoordinator, player: dict) -> None:
        super().__init__(
            coordinator,
            player,
            key="last_message",
            name_suffix="Last Message",
            icon="mdi:email-open-outline",
        )

    @property
    def native_value(self) -> str | None:
        data = self._player_data
        message = (data or {}).get("last_message") or {}

        return message.get("subject")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self._player_data
        message = (data or {}).get("last_message") or {}

        if not message:
            return {}

        return _message_summary(message)

class ProSoccerDataMessagesSensor(ProSoccerDataBaseSensor):
    """Sensor showing all fetched PSD inbox messages."""

    def __init__(self, coordinator: ProSoccerDataCoordinator, player: dict) -> None:
        super().__init__(
            coordinator,
            player,
            key="messages",
            name_suffix="Messages",
            icon="mdi:email-multiple-outline",
        )

    @property
    def native_value(self) -> int:
        data = self._player_data
        messages = (data or {}).get("messages", [])

        return len(messages)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self._player_data
        messages_data = (data or {}).get("messages_data") or {}
        messages = (data or {}).get("messages", [])

        return {
            "total_elements": messages_data.get("totalElements"),
            "number_of_elements": messages_data.get("numberOfElements"),
            "total_pages": messages_data.get("totalPages"),
            "messages": [
                _message_summary(message)
                for message in messages[:30]
            ],
        }

class ProSoccerDataUnreadMessagesSensor(ProSoccerDataBaseSensor):
    """Sensor showing all unread PSD inbox messages."""

    def __init__(self, coordinator: ProSoccerDataCoordinator, player: dict) -> None:
        super().__init__(
            coordinator,
            player,
            key="unread_messages",
            name_suffix="Unread Messages",
            icon="mdi:email-alert-outline",
        )

    @property
    def native_value(self) -> int:
        data = self._player_data
        messages = (data or {}).get("messages", [])

        return sum(
            1
            for message in messages
            if _message_is_unread(message)
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self._player_data
        messages = (data or {}).get("messages", [])

        unread_messages = [
            message
            for message in messages
            if _message_is_unread(message)
        ]

        return {
            "messages": [
                _message_summary(message)
                for message in unread_messages[:30]
            ]
        }

class ProSoccerDataAccountSensor(ProSoccerDataBaseSensor):
    """Sensor showing account information."""

    def __init__(self, coordinator: ProSoccerDataCoordinator, player: dict) -> None:
        super().__init__(
            coordinator,
            player,
            key="account",
            name_suffix="Account",
            icon="mdi:account-key",
        )

    @property
    def native_value(self) -> str | None:
        data = self._player_data
        user = ((data or {}).get("teams") or {}).get("user", {})
        return user.get("username")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self._player_data
        teams_data = (data or {}).get("teams") or {}
        user = teams_data.get("user") or {}
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
