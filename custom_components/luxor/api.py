"""Luxor API client that uses Home Assistant's shared aiohttp session."""

import asyncio
import logging
import time
from typing import Any

import aiohttp
import luxor_openapi_asyncio
from luxor_openapi_asyncio import rest

_LOGGER = logging.getLogger(__name__)


class SharedSessionRESTClient(rest.RESTClientObject):
    """REST client that sends requests through an existing aiohttp session.

    The library's own client builds an SSL context, which loads certificates
    from disk and blocks the event loop, and opens a session it never closes.
    The controller only speaks plain HTTP, so neither is needed.
    """

    def __init__(
        self,
        configuration: luxor_openapi_asyncio.Configuration,
        session: aiohttp.ClientSession,
    ) -> None:
        # Skip RESTClientObject.__init__, which builds the SSL context.
        self.proxy = configuration.proxy
        self.proxy_headers = configuration.proxy_headers
        self.pool_manager = session
        # The library limited its connector to this many parallel requests.
        self._request_limit = asyncio.Semaphore(configuration.connection_pool_maxsize)

    async def request(
        self, method: str, url: str, *args: Any, **kwargs: Any
    ) -> rest.RESTResponse:
        async with self._request_limit:
            try:
                return await self._send(method, url, *args, **kwargs)
            except aiohttp.ServerDisconnectedError:
                # The controller now and then accepts a connection and closes
                # it without answering. Every API call is a POST, which aiohttp
                # won't resend on its own, so try once more.
                _LOGGER.debug("%s %s: retrying", method, url)
                return await self._send(method, url, *args, **kwargs)

    async def _send(
        self, method: str, url: str, *args: Any, **kwargs: Any
    ) -> rest.RESTResponse:
        """Send one request, logging how it went and how long it took."""
        start = time.monotonic()
        try:
            response = await super().request(method, url, *args, **kwargs)
        except Exception as err:
            _LOGGER.debug(
                "%s %s: failed after %.2fs: %r",
                method,
                url,
                time.monotonic() - start,
                err,
            )
            raise
        _LOGGER.debug(
            "%s %s: %s in %.2fs", method, url, response.status, time.monotonic() - start
        )
        return response

    async def close(self) -> None:
        """Leave the shared session open; its owner closes it."""


class LuxorApiClient(luxor_openapi_asyncio.ApiClient):
    """ApiClient whose requests go through a shared aiohttp session."""

    def __init__(
        self,
        configuration: luxor_openapi_asyncio.Configuration,
        session: aiohttp.ClientSession,
    ) -> None:
        # Skip ApiClient.__init__, which builds the library's own REST client.
        self.configuration = configuration
        self.pool_threads = 1
        self.rest_client = SharedSessionRESTClient(configuration, session)
        self.default_headers: dict[str, str] = {}
        self.cookie = None
        self.user_agent = "OpenAPI-Generator/1.0.0/python"
        self.client_side_validation = configuration.client_side_validation


def create_api_client(
    host: str,
    session: aiohttp.ClientSession,
    max_parallel_requests: int = 1,
) -> LuxorApiClient:
    """Return a client for the Luxor controller at host."""
    configuration = luxor_openapi_asyncio.Configuration(host="http://{}".format(host))
    configuration.connection_pool_maxsize = max_parallel_requests
    return LuxorApiClient(configuration, session)
