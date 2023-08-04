"""Adds config flow for Luxor."""
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_create_clientsession
import voluptuous as vol

import luxor_openapi_asyncio
from luxor_openapi_asyncio.api import controller_api

from pprint import pprint

from .const import (
    CONF_HOST,
    CONF_GROUP_INTERVAL,
    CONF_THEME_INTERVAL,
    DOMAIN,
    PLATFORMS,
    DEFAULT_GROUP_INTERVAL,
    DEFAULT_THEME_INTERVAL,
)


class LuxorFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Luxor."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize."""
        self._errors = {}

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        self._errors = {}

        if user_input is not None:
            info = await self._get_controller_details(user_input[CONF_HOST])
            if info:
                return self.async_create_entry(title=info.controller, data=user_input)
            else:
                self._errors["base"] = "host"

            return await self._show_config_form(user_input)

        user_input = {}
        # Provide defaults for form
        user_input[CONF_HOST] = ""
        user_input[CONF_GROUP_INTERVAL] = DEFAULT_GROUP_INTERVAL
        user_input[CONF_THEME_INTERVAL] = DEFAULT_THEME_INTERVAL

        return await self._show_config_form(user_input)

    async def _show_config_form(self, user_input):  # pylint: disable=unused-argument
        """Show the configuration form to edit location data."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=user_input[CONF_HOST]): str,
                    vol.Required(CONF_GROUP_INTERVAL, default=user_input[CONF_GROUP_INTERVAL]): vol.All(vol.Coerce(int), vol.Range(min=5)),
                    vol.Required(CONF_THEME_INTERVAL, default=user_input[CONF_THEME_INTERVAL]): vol.All(vol.Coerce(int), vol.Range(min=60))
                }
            ),
            errors=self._errors,
        )

    async def _get_controller_details(self, host):
        """Return true if credentials is valid."""
        try:
            api_client = luxor_openapi_asyncio.ApiClient(
                luxor_openapi_asyncio.Configuration(host="http://{}".format(host))
            )
            api_instance = controller_api.ControllerApi(api_client)

            try:
                api_response = await api_instance.controller_name()
            except luxor_openapi_asyncio.ApiException as e:
                return None
            if api_response.status == 0:
                return api_response
            return None
        except Exception:  # pylint: disable=broad-except
            pass
        return None
