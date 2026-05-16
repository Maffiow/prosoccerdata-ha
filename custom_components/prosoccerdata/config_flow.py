import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import AuthError, ProSoccerDataAPI
from .const import CONF_PLAYERS, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_CREDENTIALS_SCHEMA = vol.Schema(
    {
        vol.Required("email"): TextSelector(
            TextSelectorConfig(type=TextSelectorType.EMAIL)
        ),
        vol.Required("password"): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
    }
)


async def _validate_credentials(hass: HomeAssistant, email: str, password: str) -> list[dict]:
    """Return list of players or raise if login fails."""
    session = async_create_clientsession(hass, cookie_jar=aiohttp.DummyCookieJar())
    api = ProSoccerDataAPI(session, email, password)
    ok = await api.login()
    if not ok:
        raise AuthError("invalid_auth")
    players = await api.get_players()
    if not players:
        raise AuthError("no_players")
    return players


class ProSoccerDataConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the multi-step config flow."""

    VERSION = 1

    def __init__(self) -> None:
        self._email: str = ""
        self._password: str = ""
        self._players: list[dict] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 1 – ask for credentials."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                self._email = user_input.get("email", "")
                self._password = user_input.get("password", "")
                _LOGGER.debug("ProSoccerData login attempt for %s", self._email)
                self._players = await _validate_credentials(
                    self.hass, self._email, self._password
                )
                _LOGGER.debug("ProSoccerData got %d players", len(self._players))
            except AuthError as err:
                errors["base"] = str(err)
            except Exception:
                _LOGGER.exception("Unexpected error during ProSoccerData login")
                errors["base"] = "unknown"
            else:
                return await self.async_step_select_players()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_CREDENTIALS_SCHEMA,
            errors=errors,
            description_placeholders={"url": "app.prosoccerdata.com"},
        )

    async def async_step_select_players(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 2 – pick which kids to track."""
        errors: dict[str, str] = {}

        select_options = [
            {
                "value": str(p["platformMemberId"]),
                "label": (
                    f"{p.get('platformUserFirstName', p.get('platformMemberFirstName', '?'))}"
                    f" {p.get('platformUserLastName', p.get('platformMemberLastName', '?'))}"
                    f" – {p.get('platform', '')}"
                ),
            }
            for p in self._players
        ]

        _LOGGER.debug("ProSoccerData select_players options: %s", select_options)

        if user_input is not None:
            selected_ids = user_input.get("player_ids", [])
            if not selected_ids:
                errors["base"] = "no_players_selected"
            else:
                selected_players = [
                    p for p in self._players
                    if str(p["platformMemberId"]) in selected_ids
                ]
                await self.async_set_unique_id(f"prosoccerdata_{self._email}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"ProSoccerData ({self._email})",
                    data={
                        "email": self._email,
                        "password": self._password,
                        CONF_PLAYERS: selected_players,
                    },
                )

        schema = vol.Schema(
            {
                vol.Required("player_ids"): SelectSelector(
                    SelectSelectorConfig(
                        options=select_options,
                        multiple=True,
                        mode=SelectSelectorMode.LIST,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="select_players",
            data_schema=schema,
            errors=errors,
        )
