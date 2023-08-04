import logging

from datetime import timedelta
from functools import partial

from homeassistant.core import callback
from homeassistant.components.scene import Scene
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

import luxor_openapi_asyncio
from luxor_openapi_asyncio.api import themes_api

from .const import (
    DEFAULT_NAME,
    DOMAIN,
    SCENE,
    REQUEST_REFRESH_DELAY,
    CONF_THEME_INTERVAL,
    DEFAULT_THEME_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    controller = hass.data[DOMAIN][entry.entry_id]

    scene_coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="{}_{}".format(DOMAIN, SCENE),
        update_method=partial(async_fetch_scenes, controller),
        update_interval=timedelta(seconds=entry.data.get(CONF_THEME_INTERVAL, DEFAULT_THEME_INTERVAL)),
        request_refresh_debouncer=Debouncer(
            hass, _LOGGER, cooldown=REQUEST_REFRESH_DELAY, immediate=True
        ),
    )
    await scene_coordinator.async_refresh()

    if not scene_coordinator.last_update_success:
        raise PlatformNotReady

    scene_coordinator.async_add_listener(
        partial(
            async_update_scenes,
            hass,
            controller,
            {},
            async_add_entities,
            partial(LuxorScene, controller),
        )
    )
    await scene_coordinator.async_refresh()


async def async_fetch_scenes(controller):
    api_instance = themes_api.ThemesApi(controller.api)
    api_response = await api_instance.theme_list_get()
    if api_response.theme_list is not None:
        controller.scenes = {t.theme_index: t for t in api_response.theme_list}


@callback
def async_update_scenes(
    hass, controller, current_entities, async_add_entities, create_scene
):
    new_items = []
    for scene_id, data in controller.scenes.items():
        if scene_id in current_entities:
            continue
        scene = current_entities[scene_id] = create_scene(
            data.theme_index, data.name, data.on_off
        )
        new_items.append(scene)

    hass.async_create_task(async_remove_entities(controller, current_entities))

    # add new entities
    async_add_entities(new_items)


async def async_remove_entities(controller, current_entities):
    # clean up entities which are no longer present
    for scene_id, entity in list(current_entities.items()):
        if scene_id not in controller.scenes:
            await entity.async_remove(force_remove=True)
            del current_entities[scene_id]


class LuxorScene(Scene):
    def __init__(self, controller, theme_index, name, on_off):
        self.controller = controller
        self.theme_index = theme_index

        self._attr_name = name
        self._attr_unique_id = "{}{}".format(name, theme_index)
    async def async_activate(self, **kwargs):  # pylint: disable=unused-argument
        api_instance = themes_api.ThemesApi(self.controller.api)
        # TODO: handle non-0 status codes
        await api_instance.illuminate_theme(
            luxor_openapi_asyncio.IlluminateThemeRequest(self.theme_index, 1)
        )

    @property
    def device_info(self):
        return DeviceInfo(
            identifiers={(DOMAIN, self.controller.name)},
            name=self.controller.name,
        )
