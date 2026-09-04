"""Config, reauth and options flows for the ProSoccerData integration."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from . import build_api
from .api import AuthError, ProSoccerDataError
from .const import (
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_PLAYER_IDS,
    CONF_PLAYERS,
    CONF_SCAN_INTERVAL_MINUTES,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DOMAIN,
    MAX_SCAN_INTERVAL_MINUTES,
    MIN_SCAN_INTERVAL_MINUTES,
)

_LOGGER = logging.getLogger(__name__)

STEP_CREDENTIALS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): TextSelector(
            TextSelectorConfig(type=TextSelectorType.EMAIL)
        ),
        vol.Required(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
    }
)

STEP_PASSWORD_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
    }
)


async def _fetch_players(
    hass: HomeAssistant, email: str, password: str
) -> list[dict[str, Any]]:
    """Log in and return the selectable players, or raise AuthError."""
    api = build_api(hass, email, password)
    await api.login()

    players = await api.get_players()
    if not players:
        raise AuthError("no_players")

    return players


def _player_label(player: dict[str, Any]) -> str:
    first = player.get("platformUserFirstName") or player.get(
        "platformMemberFirstName", "?"
    )
    last = player.get("platformUserLastName") or player.get(
        "platformMemberLastName", "?"
    )
    return f"{first} {last} – {player.get('platform', '')}"


def _player_options(players: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [
        {"value": str(player["platformMemberId"]), "label": _player_label(player)}
        for player in players
    ]


def _scan_interval_selector() -> NumberSelector:
    return NumberSelector(
        NumberSelectorConfig(
            min=MIN_SCAN_INTERVAL_MINUTES,
            max=MAX_SCAN_INTERVAL_MINUTES,
            step=5,
            mode=NumberSelectorMode.BOX,
            unit_of_measurement="min",
        )
    )


class ProSoccerDataConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the multi-step config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialise the flow."""
        self._email: str = ""
        self._password: str = ""
        self._players: list[dict[str, Any]] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 1 - ask for credentials."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._email = user_input[CONF_EMAIL]
            self._password = user_input[CONF_PASSWORD]

            try:
                self._players = await _fetch_players(
                    self.hass, self._email, self._password
                )
            except AuthError as err:
                errors["base"] = "no_players" if str(err) == "no_players" else "invalid_auth"
            except ProSoccerDataError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001 - surfaced to the user as "unknown"
                _LOGGER.exception("Unexpected error during ProSoccerData login")
                errors["base"] = "unknown"
            else:
                return await self.async_step_select_players()

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_CREDENTIALS_SCHEMA, user_input
            ),
            errors=errors,
            description_placeholders={"url": "app.prosoccerdata.com"},
        )

    async def async_step_select_players(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 2 - pick which players to track."""
        errors: dict[str, str] = {}

        if user_input is not None:
            selected_ids = user_input.get(CONF_PLAYER_IDS, [])

            if not selected_ids:
                errors["base"] = "no_players_selected"
            else:
                await self.async_set_unique_id(f"prosoccerdata_{self._email}")
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"ProSoccerData ({self._email})",
                    data={
                        CONF_EMAIL: self._email,
                        CONF_PASSWORD: self._password,
                        CONF_PLAYERS: [
                            player
                            for player in self._players
                            if str(player["platformMemberId"]) in selected_ids
                        ],
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_PLAYER_IDS): SelectSelector(
                    SelectSelectorConfig(
                        options=_player_options(self._players),
                        multiple=True,
                        mode=SelectSelectorMode.LIST,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="select_players", data_schema=schema, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start reauth after the stored password stopped working."""
        self._email = entry_data[CONF_EMAIL]
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for a new password and verify it before storing it."""
        errors: dict[str, str] = {}

        if user_input is not None:
            password = user_input[CONF_PASSWORD]

            try:
                await _fetch_players(self.hass, self._email, password)
            except AuthError:
                errors["base"] = "invalid_auth"
            except ProSoccerDataError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001 - surfaced to the user as "unknown"
                _LOGGER.exception("Unexpected error during ProSoccerData reauth")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(),
                    data_updates={CONF_PASSWORD: password},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_PASSWORD_SCHEMA,
            errors=errors,
            description_placeholders={"email": self._email},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: Any) -> ProSoccerDataOptionsFlow:
        """Return the options flow handler."""
        return ProSoccerDataOptionsFlow()


class ProSoccerDataOptionsFlow(OptionsFlowWithReload):
    """Change the tracked players and the polling interval."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the options form."""
        entry = self.config_entry
        errors: dict[str, str] = {}

        current_players: list[dict[str, Any]] = entry.options.get(
            CONF_PLAYERS, entry.data.get(CONF_PLAYERS, [])
        )
        current_ids = [str(player["platformMemberId"]) for player in current_players]
        current_interval = entry.options.get(
            CONF_SCAN_INTERVAL_MINUTES, DEFAULT_SCAN_INTERVAL_MINUTES
        )

        try:
            available = await _fetch_players(
                self.hass, entry.data[CONF_EMAIL], entry.data[CONF_PASSWORD]
            )
        except AuthError:
            return self.async_abort(reason="invalid_auth")
        except ProSoccerDataError:
            return self.async_abort(reason="cannot_connect")

        if user_input is not None:
            selected_ids = user_input.get(CONF_PLAYER_IDS, [])

            if not selected_ids:
                errors["base"] = "no_players_selected"
            else:
                return self.async_create_entry(
                    data={
                        CONF_PLAYERS: [
                            player
                            for player in available
                            if str(player["platformMemberId"]) in selected_ids
                        ],
                        CONF_SCAN_INTERVAL_MINUTES: int(
                            user_input[CONF_SCAN_INTERVAL_MINUTES]
                        ),
                    }
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_PLAYER_IDS, default=current_ids): SelectSelector(
                    SelectSelectorConfig(
                        options=_player_options(available),
                        multiple=True,
                        mode=SelectSelectorMode.LIST,
                    )
                ),
                vol.Required(
                    CONF_SCAN_INTERVAL_MINUTES, default=current_interval
                ): _scan_interval_selector(),
            }
        )

        return self.async_show_form(
            step_id="init", data_schema=schema, errors=errors
        )
