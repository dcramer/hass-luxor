import logging

from datetime import timedelta
from functools import partial

from homeassistant.core import callback
from homeassistant.components.light import (
    LightEntity,
    COLOR_MODE_BRIGHTNESS,
)
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

import luxor_openapi_asyncio
from luxor_openapi_asyncio.api import groups_api

from .const import (
    DEFAULT_NAME,
    DOMAIN,
    LIGHT,
    REQUEST_REFRESH_DELAY,
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=60)


async def async_setup_entry(hass, entry, async_add_entities):
    controller = hass.data[DOMAIN][entry.entry_id]

    light_coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="{}_{}".format(DOMAIN, LIGHT),
        update_method=partial(async_fetch_lights, controller),
        update_interval=SCAN_INTERVAL,
        request_refresh_debouncer=Debouncer(
            hass, _LOGGER, cooldown=REQUEST_REFRESH_DELAY, immediate=True
        ),
    )
    await light_coordinator.async_refresh()

    if not light_coordinator.last_update_success:
        raise PlatformNotReady

    light_coordinator.async_add_listener(
        partial(
            async_update_lights,
            hass,
            controller,
            {},
            async_add_entities,
            partial(LuxorLight, light_coordinator, controller),
        )
    )
    await light_coordinator.async_refresh()


async def async_fetch_lights(controller):
    api_instance = groups_api.GroupsApi(controller.api)
    api_response = await api_instance.group_list_get()
    if api_response.group_list is not None:
        controller.lights = {g.grp: g for g in api_response.group_list}


@callback
def async_update_lights(
    hass, controller, current_entities, async_add_entities, create_light
):
    new_items = []
    for grp_id, data in controller.lights.items():
        if grp_id in current_entities:
            continue
        light = current_entities[grp_id] = create_light(
            data.grp, data.name, data.inten, data.colr
        )
        new_items.append(light)

    hass.async_create_task(async_remove_entities(controller, current_entities))

    # add new entities
    async_add_entities(new_items)


async def async_remove_entities(controller, current_entities):
    # clean up entities which are no longer present
    for grp_id, entity in list(current_entities.items()):
        if grp_id not in controller.lights:
            await entity.async_remove(force_remove=True)
            del current_entities[grp_id]


def intensity_to_brightness(intensity: int):
    return round(255 * (intensity / 100))


def brightness_to_intensity(brightness: int):
    return round(100 * (1 - (255 - brightness) / 255))


class LuxorLight(CoordinatorEntity, LightEntity):
    supported_color_modes = {COLOR_MODE_BRIGHTNESS}

    def __init__(self, coordinator, controller, group_id, name, intensity, color):
        super().__init__(coordinator)
        self.controller = controller
        self.group_id = group_id
        self.intensity = intensity
        self.color = color

        self._attr_name = name

    async def async_turn_on(
        self, brightness=255, **kwargs
    ):  # pylint: disable=unused-argument
        intensity = brightness_to_intensity(brightness)

        api_instance = groups_api.GroupsApi(self.controller.api)
        api_response = await api_instance.illuminate_group(
            luxor_openapi_asyncio.IlluminateGroupRequest(self.group_id, intensity)
        )

        if api_response.status == 0:
            self.intensity = intensity
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):  # pylint: disable=unused-argument
        api_instance = groups_api.GroupsApi(self.controller.api)
        api_response = await api_instance.illuminate_group(
            luxor_openapi_asyncio.IlluminateGroupRequest(self.group_id, 0)
        )

        if api_response.status == 0:
            self.intensity = 0

        await self.coordinator.async_request_refresh()

    @property
    def brightness(self):
        return intensity_to_brightness(self.intensity)

    @property
    def is_on(self):
        return self.intensity > 0

    @property
    def device_info(self):
        return {
            "identifiers": ("{}_{}".format(DOMAIN, LIGHT), self.group_id),
            "name": self.name,
            "via_device": (DOMAIN, self.controller.name),
        }
