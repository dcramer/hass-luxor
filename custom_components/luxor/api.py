"""API client that reuses Home Assistant's pre-built SSL context.

The generated client calls ``ssl.create_default_context()`` in its constructor,
which loads CA certificates from disk and blocks the event loop.
"""

import aiohttp

from homeassistant.util.ssl import get_default_context

from luxor_openapi_asyncio import ApiClient, Configuration
from luxor_openapi_asyncio.rest import RESTClientObject


class _RESTClient(RESTClientObject):
    def __init__(self, configuration, pools_size=4, maxsize=None):
        if maxsize is None:
            maxsize = configuration.connection_pool_maxsize

        self.proxy = configuration.proxy
        self.proxy_headers = configuration.proxy_headers
        self.pool_manager = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(limit=maxsize, ssl=get_default_context())
        )


class LuxorApiClient(ApiClient):
    # Mirrors ApiClient.__init__ (luxor-openapi-asyncio==0.1.0), minus the
    # blocking REST client construction.
    def __init__(self, configuration: Configuration) -> None:
        self.configuration = configuration
        self.pool_threads = 1
        self.rest_client = _RESTClient(configuration)
        self.default_headers = {}
        self.cookie = None
        self.user_agent = "OpenAPI-Generator/1.0.0/python"
        self.client_side_validation = configuration.client_side_validation
