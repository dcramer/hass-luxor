"""Test setting up Luxor against a local HTTP server standing in for a controller."""

import asyncio
from collections.abc import AsyncIterator
import logging
import re
from dataclasses import dataclass, field
from typing import Any

import aiohttp
from aiohttp import web
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.luxor.api import create_api_client
from custom_components.luxor.const import CONF_HOST, DOMAIN

from luxor_openapi_asyncio.api import controller_api

CONTROLLER_NAME = "lxtwo-test"


@dataclass
class FakeController:
    """Serves the Luxor endpoints the integration calls."""

    host: str = ""
    in_flight: int = 0
    max_in_flight: int = 0
    response_delay: float = 0.0
    drop_requests: int = 0
    paths: list[str] = field(default_factory=list)

    async def handle(self, request: web.Request) -> web.Response:
        self.paths.append(request.path)
        if self.drop_requests:
            # The real controller occasionally accepts a connection and closes
            # it without answering.
            self.drop_requests -= 1
            assert request.transport is not None
            request.transport.close()
            return web.Response()
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        try:
            await asyncio.sleep(self.response_delay)
            return web.json_response(RESPONSES[request.path])
        finally:
            self.in_flight -= 1


RESPONSES: dict[str, dict[str, Any]] = {
    "/ControllerName.json": {"Status": 0, "Controller": CONTROLLER_NAME},
    "/GroupListGet.json": {
        "Status": 0,
        "GroupList": [{"Grp": 1, "Name": "Path Lights", "Inten": 50, "Colr": 0}],
    },
    "/ThemeListGet.json": {
        "Status": 0,
        "Restricted": 0,
        "ThemeList": [{"ThemeIndex": 0, "Name": "Evening", "OnOff": 0}],
    },
}


@pytest.fixture
async def controller(socket_enabled: None) -> AsyncIterator[FakeController]:
    fake = FakeController()
    app = web.Application()
    for path in RESPONSES:
        app.router.add_post(path, fake.handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = runner.addresses[0][1]
    fake.host = "127.0.0.1:{}".format(port)
    yield fake
    await runner.cleanup()


async def test_setup_entry(hass: HomeAssistant, controller: FakeController) -> None:
    """Setup talks to the controller through Home Assistant's shared session.

    The library's own session builds an SSL context, which blocks the event loop.
    """
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: controller.host})
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get("light.path_lights") is not None
    assert "/ControllerName.json" in controller.paths
    api_client = hass.data[DOMAIN][entry.entry_id].api
    assert api_client.rest_client.pool_manager is async_get_clientsession(hass)


async def test_client_sends_one_request_at_a_time(
    hass: HomeAssistant, controller: FakeController
) -> None:
    """The client keeps the library's limit of one request in flight."""
    controller.response_delay = 0.05
    api = controller_api.ControllerApi(
        create_api_client(controller.host, async_get_clientsession(hass))
    )

    responses = await asyncio.gather(*(api.controller_name() for _ in range(3)))

    assert [r.controller for r in responses] == [CONTROLLER_NAME] * 3
    assert controller.max_in_flight == 1


async def test_client_retries_dropped_request_once(
    hass: HomeAssistant, controller: FakeController, caplog: pytest.LogCaptureFixture
) -> None:
    """A request the controller drops unanswered is sent again."""
    controller.drop_requests = 1
    api = controller_api.ControllerApi(
        create_api_client(controller.host, async_get_clientsession(hass))
    )

    with caplog.at_level(logging.DEBUG, logger="custom_components.luxor.api"):
        response = await api.controller_name()

    assert response.controller == CONTROLLER_NAME
    assert controller.paths == ["/ControllerName.json"] * 2
    url = re.escape("POST http://{}/ControllerName.json".format(controller.host))
    patterns = [
        url + r": failed after \d+\.\d\ds: ServerDisconnectedError\(",
        url + r": retrying$",
        url + r": 200 in \d+\.\d\ds$",
    ]
    messages = [
        r.getMessage()
        for r in caplog.records
        if r.name == "custom_components.luxor.api"
    ]
    assert len(messages) == len(patterns)
    for pattern, message in zip(patterns, messages):
        assert re.match(pattern, message), message


async def test_client_gives_up_after_second_drop(
    hass: HomeAssistant, controller: FakeController
) -> None:
    """A controller that keeps dropping requests still raises."""
    controller.drop_requests = 2
    api = controller_api.ControllerApi(
        create_api_client(controller.host, async_get_clientsession(hass))
    )

    with pytest.raises(aiohttp.ServerDisconnectedError):
        await api.controller_name()

    assert controller.paths == ["/ControllerName.json"] * 2


async def test_close_leaves_shared_session_open(
    hass: HomeAssistant, controller: FakeController
) -> None:
    """Closing the client does not close Home Assistant's shared session."""
    session = async_get_clientsession(hass)
    api_client = create_api_client(controller.host, session)

    await api_client.close()

    assert not session.closed
    response = await controller_api.ControllerApi(api_client).controller_name()
    assert response.controller == CONTROLLER_NAME
