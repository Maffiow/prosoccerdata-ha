"""Tests for the ProSoccerData API client."""

from __future__ import annotations

from datetime import datetime

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
    mock_aiohttp_client,
)

from custom_components.prosoccerdata.api import (
    AuthError,
    ProSoccerDataAPI,
    ProSoccerDataError,
)
from custom_components.prosoccerdata.const import LOGIN_URL, POSSIBLE_USERS_URL

from .conftest import EMAIL, PASSWORD, PLAYER

PLAT = PLAYER["platformURL"]
API = PLAYER["apiURL"]
SELECT_URL = f"{PLAT}/api/v2/central-users/select"


@pytest.fixture
def mocker():
    """An aiohttp mocker whose session the client can use."""
    with mock_aiohttp_client() as mock:
        yield mock


@pytest.fixture
async def api(hass: HomeAssistant, mocker: AiohttpClientMocker):
    """A client bound to the mocked session, closed again afterwards."""
    session = mocker.create_session(hass.loop)
    yield ProSoccerDataAPI(
        session, EMAIL, PASSWORD, language="nl", time_zone="Europe/Brussels"
    )
    await session.close()


def allow_platform_login(mocker: AiohttpClientMocker) -> None:
    """Register the calls the client makes before it can reach a club."""
    mocker.post(LOGIN_URL, json={"access_token": "central-token"})
    mocker.post(SELECT_URL, json={"access_token": "plat", "refresh_token": "refresh"})
    for path in ("/modules", "/permissions", "/legal/termsofuse/accepted"):
        mocker.get(f"{API}{path}", json={})


async def test_login(
    hass: HomeAssistant, mocker: AiohttpClientMocker, api: ProSoccerDataAPI
) -> None:
    """A good login keeps the central token."""
    mocker.post(LOGIN_URL, json={"access_token": "central-token"})

    await api.login()

    assert mocker.mock_calls[0][0] == "POST"


@pytest.mark.parametrize("status", [400, 401, 403])
async def test_login_rejected(
    hass: HomeAssistant,
    mocker: AiohttpClientMocker,
    api: ProSoccerDataAPI,
    status: int,
) -> None:
    """Bad credentials raise AuthError, not a generic failure."""
    mocker.post(LOGIN_URL, status=status, text="nope")

    with pytest.raises(AuthError):
        await api.login()


async def test_login_server_error(
    hass: HomeAssistant, mocker: AiohttpClientMocker, api: ProSoccerDataAPI
) -> None:
    """A broken service is not mistaken for bad credentials."""
    mocker.post(LOGIN_URL, status=500, text="boom")

    with pytest.raises(ProSoccerDataError) as err:
        await api.login()
    assert not isinstance(err.value, AuthError)


async def test_login_without_a_token(
    hass: HomeAssistant, mocker: AiohttpClientMocker, api: ProSoccerDataAPI
) -> None:
    """A 200 that carries no token is still a failed login."""
    mocker.post(LOGIN_URL, json={})

    with pytest.raises(AuthError):
        await api.login()


async def test_get_players(
    hass: HomeAssistant, mocker: AiohttpClientMocker, api: ProSoccerDataAPI
) -> None:
    """The client logs in on demand before the first central call."""
    mocker.post(LOGIN_URL, json={"access_token": "central-token"})
    mocker.get(POSSIBLE_USERS_URL, json=[PLAYER])

    assert await api.get_players() == [PLAYER]


async def test_get_players_handles_a_bad_payload(
    hass: HomeAssistant, mocker: AiohttpClientMocker, api: ProSoccerDataAPI
) -> None:
    """An answer that is not a list yields no players."""
    mocker.post(LOGIN_URL, json={"access_token": "central-token"})
    mocker.get(POSSIBLE_USERS_URL, json={"unexpected": True})

    assert await api.get_players() == []


async def test_previous_matches(
    hass: HomeAssistant, mocker: AiohttpClientMocker, api: ProSoccerDataAPI
) -> None:
    """A paged answer is unwrapped to its content."""
    allow_platform_login(mocker)
    mocker.get(
        f"{API}/schedule/dashboard/games/previous",
        json={"content": [{"id": 1, "fullTitle": "A - B"}]},
    )

    matches = await api.get_previous_matches(PLAYER)
    assert [match["id"] for match in matches] == [1]


async def test_schedule_formats_its_window(
    hass: HomeAssistant, mocker: AiohttpClientMocker, api: ProSoccerDataAPI
) -> None:
    """The schedule window is sent in the format the API expects."""
    allow_platform_login(mocker)
    mocker.get(f"{API}/schedule/dashboard", json=[{"id": 2}])

    await api.get_schedule(
        PLAYER, datetime(2026, 11, 1, 8, 30), datetime(2026, 12, 1, 8, 30)
    )

    url = str(mocker.mock_calls[-1][1])
    assert "from=2026-11-01-083000" in url
    assert "to=2026-12-01-083000" in url


async def test_platform_select_refusal_is_an_auth_error(
    hass: HomeAssistant, mocker: AiohttpClientMocker, api: ProSoccerDataAPI
) -> None:
    """Being refused a club token is a rights problem."""
    mocker.post(LOGIN_URL, json={"access_token": "central-token"})
    mocker.post(SELECT_URL, status=403, text="no")

    with pytest.raises(AuthError):
        await api.get_previous_matches(PLAYER)


async def test_expired_session_is_refreshed_once(
    hass: HomeAssistant, mocker: AiohttpClientMocker, api: ProSoccerDataAPI
) -> None:
    """A 401 throws the tokens away and fetches a new club token, once."""
    allow_platform_login(mocker)
    mocker.get(f"{API}/schedule/dashboard/games/previous", status=401, text="no")

    with pytest.raises(AuthError):
        await api.get_previous_matches(PLAYER)

    selects = [call for call in mocker.mock_calls if str(call[1]) == SELECT_URL]
    # Once for the first attempt, once after the 401 invalidated the tokens,
    # and no more than that: the retry is bounded.
    assert len(selects) == 2


async def test_repeated_refusal_gives_up(
    hass: HomeAssistant, mocker: AiohttpClientMocker, api: ProSoccerDataAPI
) -> None:
    """An endpoint that keeps answering 401 raises instead of looping."""
    allow_platform_login(mocker)
    mocker.get(f"{API}/schedule/dashboard/games/previous", status=401, text="no")

    with pytest.raises(AuthError):
        await api.get_previous_matches(PLAYER)


async def test_server_error_is_reported(
    hass: HomeAssistant, mocker: AiohttpClientMocker, api: ProSoccerDataAPI
) -> None:
    """A 500 is a plain failure, not an auth problem."""
    allow_platform_login(mocker)
    mocker.get(f"{API}/schedule/dashboard/games/previous", status=500, text="boom")

    with pytest.raises(ProSoccerDataError) as err:
        await api.get_previous_matches(PLAYER)
    assert not isinstance(err.value, AuthError)


async def test_presences_falls_back_to_the_second_route(
    hass: HomeAssistant, mocker: AiohttpClientMocker, api: ProSoccerDataAPI
) -> None:
    """When /agenda rejects the request, the /schedule route is tried."""
    allow_platform_login(mocker)
    mocker.get(f"{API}/agenda/6786/presences/ALL", status=400, text="bad")
    mocker.get(
        f"{API}/schedule/game/6786/presences/ALL",
        json={"content": [{"playerId": 1}]},
    )

    path, items = await api.get_event_presences(PLAYER, 6786)

    assert "/schedule/game/6786/presences/ALL" in path
    assert items == [{"playerId": 1}]


async def test_presences_gives_up_when_both_routes_fail(
    hass: HomeAssistant, mocker: AiohttpClientMocker, api: ProSoccerDataAPI
) -> None:
    """Both routes failing is reported, not silently empty."""
    allow_platform_login(mocker)
    mocker.get(f"{API}/agenda/6786/presences/ALL", status=400, text="bad")
    mocker.get(f"{API}/schedule/game/6786/presences/ALL", status=400, text="bad")

    with pytest.raises(ProSoccerDataError):
        await api.get_event_presences(PLAYER, 6786)


def test_parse_match_reads_an_away_game() -> None:
    """The opponent, score and side come out of the event."""
    parsed = ProSoccerDataAPI.parse_match(
        {
            "id": 1,
            "subtype": "away",
            "start": "2026-10-25 10:00",
            "end": "2026-10-25 11:15",
            "fullTitle": "Eendracht Termien U10 - KFC Testclub",
            "fullDescription": "<strong>Competitie</strong> eindstand 1 - 15",
            "teamNames": "U10",
            "attendanceStatus": "PRESENT",
        }
    )

    assert parsed["home_away"] == "Away"
    assert parsed["opponent"] == "Eendracht Termien U10"
    assert parsed["date"] == "2026-10-25"
    assert parsed["score"] == "1-15"
    assert parsed["competition"] == "Competitie"


def test_parse_match_prefers_the_reported_score() -> None:
    """A final score on the event beats one scraped from the description."""
    parsed = ProSoccerDataAPI.parse_match(
        {"scoreFinal": "13-0", "fullDescription": "irrelevant 2 - 1", "subtype": "home"}
    )
    assert parsed["score"] == "13-0"
    assert parsed["home_away"] == "Home"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ({"type": "game"}, "game"),
        ({"type": "match"}, "game"),
        ({"type": "training"}, "training"),
        ({"eventType": "trainingSession"}, "training"),
        ({"type": "party"}, "other"),
        ({}, "other"),
    ],
)
def test_event_type(raw: dict, expected: str) -> None:
    """Every event is classified, whichever key carries the type."""
    assert ProSoccerDataAPI.event_type(raw) == expected


def test_parse_event_strips_match_only_fields() -> None:
    """A training carries no opponent or score."""
    parsed = ProSoccerDataAPI.parse_event(
        {"type": "training", "fullTitle": "Training Mottekamp", "subtype": "home"}
    )

    assert parsed["type"] == "training"
    assert parsed["opponent"] == ""
    assert parsed["home_away"] == ""
    assert parsed["score"] is None


async def test_payment_requests(
    hass: HomeAssistant, mocker: AiohttpClientMocker, api: ProSoccerDataAPI
) -> None:
    """Payment requests come back as a plain list."""
    allow_platform_login(mocker)
    mocker.get(
        f"{API}/finances/members/{PLAYER['platformMemberId']}/paymentrequests",
        json={"content": [{"id": 5, "amount": "45.50"}]},
    )

    assert await api.get_payment_requests(PLAYER) == [{"id": 5, "amount": "45.50"}]


async def test_get_teams_posts_the_filter(
    hass: HomeAssistant, mocker: AiohttpClientMocker, api: ProSoccerDataAPI
) -> None:
    """The profile block is fetched through the calendar filter endpoint."""
    allow_platform_login(mocker)
    mocker.post(
        f"{API}/filters/module/kalender/name/teams",
        json={"member": {"id": 1}, "user": {"username": "x"}},
    )

    teams = await api.get_teams(PLAYER)

    assert teams["member"]["id"] == 1
    assert mocker.mock_calls[-1][0] == "POST"


async def test_get_messages(
    hass: HomeAssistant, mocker: AiohttpClientMocker, api: ProSoccerDataAPI
) -> None:
    """The inbox page keeps its envelope, which carries the total."""
    allow_platform_login(mocker)
    mocker.get(
        f"{API}/mailbox/status/INBOX",
        json={"content": [{"id": 11}], "totalElements": 55},
    )

    page = await api.get_messages(PLAYER)

    assert page["totalElements"] == 55


async def test_get_team_members(
    hass: HomeAssistant, mocker: AiohttpClientMocker, api: ProSoccerDataAPI
) -> None:
    """A team's squad is fetched by team id."""
    allow_platform_login(mocker)
    mocker.get(f"{API}/teams/3/members", json=[{"id": 1}])

    assert await api.get_team_members(PLAYER, 3) == [{"id": 1}]


async def test_get_unread_messages(
    hass: HomeAssistant, mocker: AiohttpClientMocker, api: ProSoccerDataAPI
) -> None:
    """Unread messages come back as a list, not a page."""
    allow_platform_login(mocker)
    mocker.get(f"{API}/mailbox/unread", json=[{"id": 11}])

    assert await api.get_unread_messages(PLAYER) == [{"id": 11}]


async def test_message_detail_unwraps_the_mail(
    hass: HomeAssistant, mocker: AiohttpClientMocker, api: ProSoccerDataAPI
) -> None:
    """The body sits one level down, under `mail`."""
    allow_platform_login(mocker)
    mocker.get(
        f"{API}/mailbox/11/detail",
        json={"mail": {"id": 11, "message": "<p>Hallo</p>"}},
    )

    mail = await api.get_message_detail(PLAYER, 11)

    assert mail["message"] == "<p>Hallo</p>"


async def test_message_detail_without_a_mail_key(
    hass: HomeAssistant, mocker: AiohttpClientMocker, api: ProSoccerDataAPI
) -> None:
    """An answer without the expected key yields nothing rather than raising."""
    allow_platform_login(mocker)
    mocker.get(f"{API}/mailbox/11/detail", json={})

    assert await api.get_message_detail(PLAYER, 11) == {}


@pytest.mark.parametrize(("read", "expected"), [(True, "true"), (False, "false")])
async def test_set_messages_read(
    hass: HomeAssistant,
    mocker: AiohttpClientMocker,
    api: ProSoccerDataAPI,
    read: bool,
    expected: str,
) -> None:
    """Both marking read and marking unread hit the matching path."""
    allow_platform_login(mocker)
    mocker.post(f"{API}/mailbox/read/{expected}", json={})

    await api.set_messages_read(PLAYER, [11, 12], read)

    url = str(mocker.mock_calls[-1][1])
    assert f"/mailbox/read/{expected}" in url
    assert "mailIds=11,12" in url
