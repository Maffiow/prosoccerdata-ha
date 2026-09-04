"""API client for ProSoccerData."""

from __future__ import annotations

import logging
import re
import time
from typing import Any

import aiohttp
import yarl

from .const import (
    APP_URL,
    CENTRAL_TOKEN_HEADER,
    DEFAULT_LANGUAGE,
    DEFAULT_TIME_ZONE,
    LOGIN_URL,
    MATCH_FETCH_COUNT,
    MESSAGE_FETCH_COUNT,
    PAYMENT_FETCH_COUNT,
    POSSIBLE_USERS_URL,
)

_LOGGER = logging.getLogger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"
)

_LOGIN_PAYLOAD_TEMPLATE = {
    "type": "login",
    "grant_type": "password",
    "mfa_clientdata": "",
    "mfa_ip": "",
    "mfa_origin": "",
    "mfa_code": "",
    "mfa_challenge": "",
    "mfa_sessionid": "",
}


class ProSoccerDataError(Exception):
    """Raised when ProSoccerData is unreachable or answers with something unusable."""


class AuthError(ProSoccerDataError):
    """Raised when ProSoccerData rejects the credentials or the session token."""


class ProSoccerDataAPI:
    """API client for ProSoccerData.

    Authentication is two-tiered: a central token identifies the account, and a
    per-platform token is exchanged for it to reach a specific club's API. Both
    expire, so every request refreshes them once on a 401 before giving up.
    """

    def __init__(
        self,
        session: aiohttp.ClientSession,
        email: str,
        password: str,
        *,
        language: str | None = None,
        time_zone: str | None = None,
    ) -> None:
        """Initialise the client."""
        self._session = session
        self._email = email
        self._password = password
        self._language = language or DEFAULT_LANGUAGE
        self._time_zone = time_zone or DEFAULT_TIME_ZONE
        self._central_token: str = ""
        self._platform_tokens: dict[int, dict[str, str]] = {}

    # ------------------------------------------------------------------
    # Headers
    # ------------------------------------------------------------------

    def _headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        """Headers for the central (account-level) API."""
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Origin": APP_URL,
            "Referer": f"{APP_URL}/",
            "Clienttimezone": self._time_zone,
            "Accept-Language": self._language,
            "User-Agent": _USER_AGENT,
            "X-Start-Timestamp": str(int(time.time() * 1000)),
        }
        if extra:
            headers.update(extra)
        return headers

    def _plat_headers(
        self, plat_url: str, extra: dict[str, str] | None = None
    ) -> dict[str, str]:
        """Headers for a club platform's API."""
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": self._language,
            "Referer": f"{plat_url}/dashboard",
            "Clienttimezone": self._time_zone,
            "User-Agent": _USER_AGENT,
            "X-Start-Timestamp": str(int(time.time() * 1000)),
        }
        if extra:
            headers.update(extra)
        return headers

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    async def _do_login(self, platform: str = "") -> dict[str, Any]:
        payload = {
            **_LOGIN_PAYLOAD_TEMPLATE,
            "login": self._email,
            "password": self._password,
        }

        try:
            resp = await self._session.post(
                LOGIN_URL,
                json=payload,
                params={"platform": platform},
                headers=self._headers(),
            )
        except aiohttp.ClientError as err:
            raise ProSoccerDataError(f"Cannot reach ProSoccerData: {err}") from err

        if resp.status in (400, 401, 403):
            raise AuthError(
                f"ProSoccerData rejected the credentials (HTTP {resp.status})"
            )

        if resp.status not in (200, 201):
            text = await resp.text()
            raise ProSoccerDataError(f"Login failed (HTTP {resp.status}): {text[:200]}")

        return await resp.json(content_type=None)

    async def login(self) -> None:
        """Obtain a central token, raising AuthError when the credentials fail."""
        data = await self._do_login()
        token = data.get("access_token")

        if not token:
            raise AuthError("Login succeeded but no access_token was returned")

        self._central_token = token
        # Platform tokens were minted against the previous session; drop them.
        self._platform_tokens.clear()
        _LOGGER.debug("Central login OK")

    async def _ensure_central_token(self) -> str:
        if not self._central_token:
            await self.login()
        return self._central_token

    def _invalidate(self, platform_id: int | None = None) -> None:
        """Force a fresh login on the next request."""
        self._central_token = ""
        if platform_id is None:
            self._platform_tokens.clear()
        else:
            self._platform_tokens.pop(platform_id, None)

    async def _ensure_platform_token(self, player: dict[str, Any]) -> str:
        """Exchange the central token for a token on the player's club platform."""
        platform_id: int = player["platformId"]

        if platform_id in self._platform_tokens:
            return self._platform_tokens[platform_id]["access_token"]

        await self._ensure_central_token()

        plat_url = player["platformURL"].rstrip("/")
        api_url = player.get("apiURL", "").rstrip("/")
        plat_key = plat_url.split("//")[1].split(".")[0]

        # A platform-scoped login is not always required, but when it is the
        # select call below fails without it, so a failure here is not fatal.
        try:
            await self._do_login(platform=plat_key)
        except ProSoccerDataError as err:
            _LOGGER.debug("Platform login failed for %s: %s", plat_key, err)

        try:
            resp = await self._session.post(
                f"{plat_url}/api/v2/central-users/select",
                json={
                    "userId": player["platformUserId"],
                    "platformId": platform_id,
                },
                headers=self._headers({CENTRAL_TOKEN_HEADER: self._central_token}),
            )
        except aiohttp.ClientError as err:
            raise ProSoccerDataError(f"Platform select failed: {err}") from err

        if resp.status in (401, 403):
            raise AuthError(f"Platform select was refused (HTTP {resp.status})")

        if resp.status not in (200, 201):
            text = await resp.text()
            raise ProSoccerDataError(
                f"Platform select failed (HTTP {resp.status}): {text[:200]}"
            )

        data = await resp.json(content_type=None)
        access_token = data.get("access_token", "")

        if not access_token:
            raise AuthError("Platform select returned no access_token")

        self._platform_tokens[platform_id] = {
            "access_token": access_token,
            "refresh_token": data.get("refresh_token", ""),
        }
        _LOGGER.debug("Platform select OK for platformId=%s", platform_id)

        await self._warm_up(api_url, plat_url, platform_id)

        return access_token

    async def _warm_up(self, api_url: str, plat_url: str, platform_id: int) -> None:
        """Hit the endpoints the web app calls right after login.

        The platform refuses data calls until the session has been established
        this way, so failures are logged and otherwise ignored.
        """
        cookie = self._build_platform_cookie(platform_id)

        for path in ("/modules", "/permissions", "/legal/termsofuse/accepted"):
            try:
                resp = await self._session.get(
                    f"{api_url}{path}",
                    headers=self._plat_headers(plat_url, {"Cookie": cookie}),
                )
                _LOGGER.debug("warmup %s -> HTTP %s", path, resp.status)
            except aiohttp.ClientError as err:
                _LOGGER.debug("warmup %s failed: %s", path, err)

    def _build_platform_cookie(self, platform_id: int) -> str:
        token_data = self._platform_tokens.get(platform_id, {})
        access_token = token_data.get("access_token", "")
        refresh_token = token_data.get("refresh_token", "")

        return (
            f"platform_access_token={access_token}; "
            f"platform_refresh_token={refresh_token}; "
            f"taal={self._language}; "
            f"central_access_token={self._central_token}"
        )

    # ------------------------------------------------------------------
    # Requests
    # ------------------------------------------------------------------

    async def _central_request(self, url: str, **kwargs: Any) -> Any:
        """GET against the central API, logging in again once on a 401."""
        for attempt in (1, 2):
            await self._ensure_central_token()

            try:
                resp = await self._session.get(
                    url,
                    headers=self._headers({CENTRAL_TOKEN_HEADER: self._central_token}),
                    **kwargs,
                )
            except aiohttp.ClientError as err:
                raise ProSoccerDataError(f"Request to {url} failed: {err}") from err

            if resp.status in (401, 403):
                self._invalidate()
                if attempt == 1:
                    continue
                raise AuthError(f"ProSoccerData refused {url} (HTTP {resp.status})")

            if resp.status != 200:
                text = await resp.text()
                raise ProSoccerDataError(
                    f"Request to {url} failed (HTTP {resp.status}): {text[:200]}"
                )

            return await resp.json(content_type=None)

        raise AuthError(f"ProSoccerData refused {url}")

    async def _platform_request(
        self,
        player: dict[str, Any],
        path: str,
        *,
        method: str = "GET",
        json_body: dict[str, Any] | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> Any:
        """Call a club platform endpoint, refreshing the tokens once on a 401.

        The retry is bounded to a single extra attempt; an endpoint that keeps
        answering 401 raises AuthError instead of recursing.
        """
        api_url = player.get("apiURL", "").rstrip("/")
        plat_url = player.get("platformURL", "").rstrip("/")
        platform_id = player["platformId"]

        # The API rejects re-encoded query strings, so build the URL verbatim.
        url = yarl.URL(f"{api_url}{path}", encoded=True)

        for attempt in (1, 2):
            await self._ensure_platform_token(player)

            headers = self._plat_headers(
                plat_url, {"Cookie": self._build_platform_cookie(platform_id)}
            )
            if extra_headers:
                headers.update(extra_headers)

            try:
                resp = await self._session.request(
                    method, url, headers=headers, json=json_body
                )
            except aiohttp.ClientError as err:
                raise ProSoccerDataError(f"Request to {path} failed: {err}") from err

            _LOGGER.debug("%s %s -> HTTP %s", method, path, resp.status)

            if resp.status in (401, 403):
                self._invalidate(platform_id)
                if attempt == 1:
                    continue
                raise AuthError(f"ProSoccerData refused {path} (HTTP {resp.status})")

            if resp.status not in (200, 201):
                text = await resp.text()
                raise ProSoccerDataError(
                    f"Request to {path} failed (HTTP {resp.status}): {text[:200]}"
                )

            return await resp.json(content_type=None)

        raise AuthError(f"ProSoccerData refused {path}")

    @staticmethod
    def _as_list(data: Any) -> list[dict[str, Any]]:
        if isinstance(data, dict):
            return data.get("content", [])
        return data if isinstance(data, list) else []

    @staticmethod
    def _as_dict(data: Any) -> dict[str, Any]:
        return data if isinstance(data, dict) else {}

    # ------------------------------------------------------------------
    # Endpoints
    # ------------------------------------------------------------------

    async def get_players(self) -> list[dict[str, Any]]:
        """Return the members this account can act on behalf of."""
        data = await self._central_request(POSSIBLE_USERS_URL, params={"platform": ""})
        return data if isinstance(data, list) else []

    async def get_previous_matches(
        self, player: dict[str, Any], count: int = MATCH_FETCH_COUNT
    ) -> list[dict[str, Any]]:
        """Return the player's most recent matches, newest first."""
        data = await self._platform_request(
            player,
            f"/schedule/dashboard/games/previous?size={count}&page=0&sort=date,desc",
        )
        return self._as_list(data)

    async def get_payment_requests(
        self, player: dict[str, Any], count: int = PAYMENT_FETCH_COUNT
    ) -> list[dict[str, Any]]:
        """Return the player's most recent payment requests, newest first."""
        member_id = player["platformMemberId"]
        data = await self._platform_request(
            player,
            f"/finances/members/{member_id}/paymentrequests"
            f"?size={count}&page=0&sort=sentDate,desc",
            extra_headers={"Content-Type": "text/plain"},
        )
        return self._as_list(data)

    async def get_teams(self, player: dict[str, Any]) -> dict[str, Any]:
        """Return the player's profile, team and account block.

        This is the calendar module's filter endpoint; it is the only place the
        API exposes the member and user records in a single response.
        """
        plat_url = player.get("platformURL", "").rstrip("/")
        data = await self._platform_request(
            player,
            "/filters/module/kalender/name/teams",
            method="POST",
            json_body={"module": "kalender", "name": "teams", "value": "{}"},
            extra_headers={
                "Content-Type": "application/json",
                "Referer": f"{plat_url}/planning/calendar",
            },
        )
        return self._as_dict(data)

    async def get_messages(
        self, player: dict[str, Any], count: int = MESSAGE_FETCH_COUNT
    ) -> dict[str, Any]:
        """Return a page of the player's mailbox inbox, newest first."""
        plat_url = player.get("platformURL", "").rstrip("/")
        data = await self._platform_request(
            player,
            f"/mailbox/status/INBOX?size={count}&page=0&sort=creation_date,desc",
            extra_headers={
                "Content-Type": "text/plain",
                "Referer": f"{plat_url}/mail?page=list",
            },
        )
        return self._as_dict(data)

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    @staticmethod
    def parse_match(event: dict[str, Any]) -> dict[str, Any]:
        """Flatten a calendar event into the shape the sensors expect."""
        subtype = event.get("subtype", "")
        home_away = "Away" if subtype == "away" else "Home"

        full_title = event.get("fullTitle", "")
        if " - " in full_title:
            parts = full_title.split(" - ", 1)
            opponent = parts[0].strip() if home_away == "Away" else parts[1].strip()
        else:
            opponent = full_title

        description = event.get("fullDescription") or event.get("description", "")

        return {
            "id": event.get("id"),
            "start": event.get("start", ""),
            "end": event.get("end", ""),
            "date": (event.get("start") or "")[:10],
            "team": event.get("teamNames", ""),
            "opponent": opponent,
            "full_title": full_title,
            "home_away": home_away,
            "score": event.get("scoreFinal") or _extract_score(description),
            "competition": (
                event.get("competitionType") or _extract_competition(description)
            ),
            "attendance": event.get("attendanceStatus", ""),
            "location": (event.get("location") or {}).get("fullAddress", ""),
            "meeting_hour": event.get("meetingHour", ""),
            "meeting_location": (event.get("meetingLocation") or {}).get(
                "fullAddress", ""
            ),
            "cancelled": event.get("cancelled", False),
        }


def _extract_competition(description: str) -> str:
    """Pull the competition name out of the HTML blob the API returns."""
    match = re.search(r"<strong[^>]*>([^<]+)</strong>", description)
    return match.group(1).strip() if match else ""


def _extract_score(description: str) -> str | None:
    """Pull a `2-1` style score out of the HTML blob the API returns."""
    match = re.search(r"\b(\d+)\s*[-–]\s*(\d+)\b", description)
    return f"{match.group(1)}-{match.group(2)}" if match else None
