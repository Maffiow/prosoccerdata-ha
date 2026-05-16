import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .api import AuthError, ProSoccerDataAPI
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from .const import CONF_PLAYERS, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_CREDENTIALS_SCHEMA = vol.Schema(
    {
        vol.Required("email"): str,
        vol.Required("password"): str,
    }
)


async def _validate_credentials(hass: HomeAssistant, email: str, password: str) -> list[dict]:
    """Return list of players or raise if login fails."""
    session = async_create_clientsession(hass)
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
            self._email = user_input["email"]
            self._password = user_input["password"]
            try:
                self._players = await _validate_credentials(
                    self.hass, self._email, self._password
                )
            except AuthError as err:
                errors["base"] = str(err)
            except Exception:
                _LOGGER.exception("Unexpected error during login")
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

        # Build options: "FirstName LastName (Club)" -> str(platformMemberId)
        options = {
            str(p["platformMemberId"]): (
                f"{p.get('platformUserFirstName', p.get('platformMemberFirstName', '?'))}"
                f" {p.get('platformUserLastName', p.get('platformMemberLastName', '?'))}"
                f" – {p.get('platform', '')}"
            )
            for p in self._players
        }

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
                vol.Required("player_ids"): vol.All(
                    cv_multi_select(options), vol.Length(min=1)
                )
            }
        )

        return self.async_show_form(
            step_id="select_players",
            data_schema=schema,
            errors=errors,
        )


def cv_multi_select(options: dict) -> Any:
    """Return a voluptuous validator that accepts a list of keys from options."""
    import homeassistant.helpers.config_validation as cv

    def _validate(value: Any) -> list[str]:
        if isinstance(value, str):
            value = [value]
        invalid = [v for v in value if v not in options]
        if invalid:
            raise vol.Invalid(f"Invalid selection: {invalid}")
        return value

    return _validate
