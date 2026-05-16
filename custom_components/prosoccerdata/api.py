import logging
import re
import time

import aiohttp

from .const import APP_URL, CENTRAL_TOKEN_HEADER, LOGIN_URL, POSSIBLE_USERS_URL

_LOGGER = logging.getLogger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"
)

_BASE_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "Origin": APP_URL,
    "Referer": f"{APP_URL}/",
    "Clienttimezone": "Europe/Brussels",
    "Accept-Language": "nl",
    "User-Agent": _USER_AGENT,
}

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


class AuthError(Exception):
    pass


class ProSoccerDataAPI:
    """API client for ProSoccerData.

    Auth flow:
      1. POST psd.../api/v2/login/oauth/token?platform=  → central JWT
      2. GET  psd.../api/v2/central-users/current/possible-users
             header: central-token: <JWT>   → list of players
      3. POST kskmeeuwen.../api/v2/central-users/select
             header: central-token: <JWT>
             body:   {userId: platformUserId, platformId: platformId}
             → {access_token: "<UUID>", refresh_token: "<UUID>", expires_in: 86399}
      4. GET  kskmeeuwen.../api/v2/schedule/dashboard/games/previous
             cookie: platform_access_token=<UUID>
             → {content: [...matches...], totalElements: N, ...}
    """

    def __init__(self, session: aiohttp.ClientSession, email: str, password: str) -> None:
        self._session = session
        self._email = email
        self._password = password
        self._central_token: str = ""
        # platformId -> {access_token, refresh_token}
        self._platform_tokens: dict[int, dict] = {}

    def _headers(self, extra: dict | None = None) -> dict:
        h = {**_BASE_HEADERS, "X-Start-Timestamp": str(int(time.time() * 1000))}
        if extra:
            h.update(extra)
        return h

    def _plat_headers(self, plat_url: str, extra: dict | None = None) -> dict:
        """Headers for platform-domain calls (same-origin, no global Origin)."""
        h = {
            "Accept": "application/json, text/plain, */*",
            "Referer": f"{plat_url}/dashboard",
            "Clienttimezone": "Europe/Brussels",
            "User-Agent": _USER_AGENT,
            "X-Start-Timestamp": str(int(time.time() * 1000)),
        }
        if extra:
            h.update(extra)
        return h

    async def _do_login(self, platform: str = "") -> dict:
        payload = {
            **_LOGIN_PAYLOAD_TEMPLATE,
            "login": self._email,
            "password": self._password,
        }
        resp = await self._session.post(
            LOGIN_URL,
            json=payload,
            params={"platform": platform},
            headers=self._headers(),
        )
        if resp.status not in (200, 201):
            text = await resp.text()
            raise AuthError(f"Login failed (HTTP {resp.status}): {text[:200]}")
        return await resp.json(content_type=None)

    async def login(self) -> bool:
        """Central login — stores the central token used for possible-users and select."""
        try:
            data = await self._do_login(platform="")
            token = data.get("access_token")
            if not token:
                _LOGGER.error("Login succeeded but no access_token in response")
                return False
            self._central_token = token
            _LOGGER.debug("Central login OK")
            return True
        except AuthError as err:
            _LOGGER.error("Login error: %s", err)
            return False
        except aiohttp.ClientError as err:
            raise AuthError(str(err)) from err

    async def get_players(self) -> list[dict]:
        """Return list of available players/platforms."""
        try:
            resp = await self._session.get(
                POSSIBLE_USERS_URL,
                params={"platform": ""},
                headers=self._headers({CENTRAL_TOKEN_HEADER: self._central_token}),
            )
            if resp.status == 200:
                return await resp.json(content_type=None)
            _LOGGER.warning("get_players HTTP %s", resp.status)
            return []
        except aiohttp.ClientError as err:
            _LOGGER.error("get_players error: %s", err)
            return []

    async def _ensure_platform_token(self, player: dict) -> str:
        """Return (and cache) the UUID platform_access_token via the select endpoint."""
        platform_id: int = player["platformId"]
        if platform_id not in self._platform_tokens:
            plat_url = player["platformURL"].rstrip("/")
            select_url = f"{plat_url}/api/v2/central-users/select"
            try:
                resp = await self._session.post(
                    select_url,
                    json={
                        "userId": player["platformUserId"],
                        "platformId": platform_id,
                    },
                    headers=self._headers({CENTRAL_TOKEN_HEADER: self._central_token}),
                )
                if resp.status not in (200, 201):
                    text = await resp.text()
                    _LOGGER.error("Platform select HTTP %s: %s", resp.status, text[:200])
                    return ""
                data = await resp.json(content_type=None)
                pat = data.get("access_token", "")
                prt = data.get("refresh_token", "")
                if pat:
                    self._platform_tokens[platform_id] = {
                        "access_token": pat,
                        "refresh_token": prt,
                    }
                    _LOGGER.debug("Platform select OK for platformId=%s", platform_id)
                else:
                    _LOGGER.error("Platform select returned no access_token")
            except aiohttp.ClientError as err:
                _LOGGER.error("Platform select error: %s", err)
        return self._platform_tokens.get(platform_id, {}).get("access_token", "")

    async def get_previous_matches(self, player: dict, count: int = 20) -> list[dict]:
        """Fetch previous matches for a player."""
        api_url = player.get("apiURL", "").rstrip("/")
        plat_url = player.get("platformURL", "").rstrip("/")

        pat = await self._ensure_platform_token(player)
        if not pat:
            return []

        prt = self._platform_tokens.get(player["platformId"], {}).get("refresh_token", "")
        cookie = f"platform_access_token={pat}; platform_refresh_token={prt}; taal=nl; central_access_token={self._central_token}"
        # Must build URL manually — aiohttp percent-encodes commas in params dicts,
        # but the server requires a literal comma in sort=date,desc (returns 400 otherwise).
        url = f"{api_url}/schedule/dashboard/games/previous?size={count}&page=0&sort=date,desc"

        try:
            resp = await self._session.get(
                url,
                headers=self._plat_headers(plat_url, {"Cookie": cookie}),
            )
            _LOGGER.debug("get_previous_matches → HTTP %s", resp.status)
            if resp.status == 200:
                data = await resp.json(content_type=None)
                if isinstance(data, dict):
                    return data.get("content", [])
                return data if isinstance(data, list) else []
            if resp.status == 401:
                # Token expired — clear and retry once
                platform_id = player["platformId"]
                self._platform_tokens.pop(platform_id, None)
                pat = await self._ensure_platform_token(player)
                if pat:
                    prt = self._platform_tokens.get(platform_id, {}).get("refresh_token", "")
                    cookie2 = f"platform_access_token={pat}; platform_refresh_token={prt}; taal=nl; central_access_token={self._central_token}"
                    resp2 = await self._session.get(
                        url,
                        headers=self._plat_headers(plat_url, {"Cookie": cookie2}),
                    )
                    if resp2.status == 200:
                        data = await resp2.json(content_type=None)
                        if isinstance(data, dict):
                            return data.get("content", [])
                        return data if isinstance(data, list) else []
            _LOGGER.warning("get_previous_matches HTTP %s", resp.status)
            return []
        except aiohttp.ClientError as err:
            _LOGGER.error("get_previous_matches error: %s", err)
            return []

    @staticmethod
    def parse_match(event: dict) -> dict:
        """Normalise a raw event dict into a clean match dict."""
        subtype = event.get("subtype", "")
        home_away = "Away" if subtype == "away" else "Home"

        full_title = event.get("fullTitle", "")
        if " - " in full_title:
            parts = full_title.split(" - ", 1)
            # fullTitle = "HomeTeam - AwayTeam"; player is home or away
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
            "competition": event.get("competitionType") or _extract_competition(description),
            "attendance": event.get("attendanceStatus", ""),
            "location": (event.get("location") or {}).get("fullAddress", ""),
            "meeting_hour": event.get("meetingHour", ""),
            "meeting_location": (event.get("meetingLocation") or {}).get("fullAddress", ""),
            "cancelled": event.get("cancelled", False),
        }


def _extract_competition(description: str) -> str:
    m = re.search(r"<strong[^>]*>([^<]+)</strong>", description)
    return m.group(1).strip() if m else ""


def _extract_score(description: str) -> str | None:
    m = re.search(r"\b(\d+)\s*[-–]\s*(\d+)\b", description)
    return f"{m.group(1)}-{m.group(2)}" if m else None
