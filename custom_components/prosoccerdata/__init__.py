import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .api import ProSoccerDataAPI
from .const import CONF_PLAYERS, DOMAIN
from .coordinator import ProSoccerDataCoordinator

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    session = async_create_clientsession(hass)
    api = ProSoccerDataAPI(session, entry.data["email"], entry.data["password"])

    if not await api.login():
        _LOGGER.error("ProSoccerData login failed for %s", entry.data["email"])
        return False

    players = entry.data.get(CONF_PLAYERS, [])
    coordinator = ProSoccerDataCoordinator(hass, api, players)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unloaded
