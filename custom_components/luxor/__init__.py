import asyncio
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Config, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

import luxor_openapi_asyncio
from luxor_openapi_asyncio.api import controller_api

from .const import CONF_HOST, DOMAIN, PLATFORMS

_LOGGER: logging.Logger = logging.getLogger(__package__)


async def async_setup(hass: HomeAssistant, config: Config):
    """Set up this integration using YAML is not supported."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up this integration using UI."""
    if hass.data.get(DOMAIN) is None:
        hass.data.setdefault(DOMAIN, {})

    host = entry.data.get(CONF_HOST)
    api_client_config = luxor_openapi_asyncio.Configuration(host="http://{}".format(host))
    api_client_config.connection_pool_maxsize = 1
    api_client = luxor_openapi_asyncio.ApiClient(api_client_config)

    api_instance = controller_api.ControllerApi(api_client)

    try:
        api_response = await api_instance.controller_name()
    except luxor_openapi_asyncio.ApiException as e:
        raise ConfigEntryNotReady from e

    controller = LuxorController(api_client=api_client, name=api_response.controller)
    hass.data[DOMAIN][entry.entry_id] = controller

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        identifiers={(DOMAIN, controller.name)},
        config_entry_id=entry.entry_id,
        manufacturer="FXLuminaire",
        name=controller.name,
    )

    for platform in PLATFORMS:
        hass.async_add_job(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    entry.add_update_listener(async_reload_entry)
    return True


class LuxorController(object):
    def __init__(
        self,
        api_client: luxor_openapi_asyncio.ApiClient,
        name: str,
    ) -> None:
        """Initialize."""
        self.api = api_client
        self.name = name

        self.lights = {}
        self.scenes = {}


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle removal of an entry."""
    unloaded = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
            ]
        )
    )
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unloaded


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
