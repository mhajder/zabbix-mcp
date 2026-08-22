import asyncio
import logging
import os
from typing import Any

import aiohttp
from zabbix_utils import AsyncZabbixAPI
from zabbix_utils.common import ModuleUtils
from zabbix_utils.types import APIVersion

from zabbix_mcp.models import TransportConfig
from zabbix_mcp.models import ZabbixConfig
from zabbix_mcp.retry import build_session
from zabbix_mcp.utils import parse_bool

logger = logging.getLogger(__name__)

# Name-mangled cache slot for AsyncZabbixAPI.__version. Populating it keeps the
# library's constructor from resolving the version itself - see _seed_api_version.
_VERSION_CACHE_ATTR = "_AsyncZabbixAPI__version"


class ZabbixClient:
    """Async client wrapper for Zabbix API using zabbix_utils AsyncZabbixAPI."""

    _instance: "ZabbixClient | None" = None
    _initialized: bool = False
    _task_apis: dict

    def __new__(cls, config: ZabbixConfig | None = None):  # noqa: ARG004
        """Create a new instance of ZabbixClient (singleton)."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, config: ZabbixConfig | None = None):
        """Initialize the ZabbixClient."""
        if self._initialized:
            return
        if config is None:
            raise ValueError("Config must be provided for first initialization")
        self.config = config
        self._task_apis = {}
        self._initialized = True

    async def __aenter__(self) -> Any:
        """Create a fresh, authenticated API instance for the current task."""
        api, session = await self._create_fresh_api()
        task = asyncio.current_task()
        key = id(task) if task is not None else 0
        self._task_apis[key] = (api, session)
        return api

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Log out and discard the API instance belonging to the current task."""
        task = asyncio.current_task()
        key = id(task) if task is not None else 0
        entry = self._task_apis.pop(key, None)
        if entry is not None:
            await self._discard(*entry)
        return False

    @staticmethod
    async def _discard(api: Any, session: Any) -> None:
        """Log out and close the session backing an API instance.

        Args:
            api: The API instance to log out.
            session: Its HTTP session, which we own and must close ourselves.
        """
        try:
            await api.logout()
        except Exception:
            logger.debug("Ignoring exception while closing Zabbix API session")
        finally:
            await session.close()

    async def _seed_api_version(self) -> None:
        """Resolve the Zabbix API version once, without blocking the event loop.

        ``AsyncZabbixAPI.__init__`` resolves the version through a *synchronous*
        ``urllib.urlopen`` call, and since a fresh instance is built per request
        that stalls the whole loop on every tool call. That call also ignores the
        configured timeout (``urlopen`` does not read ``Request.timeout``), so an
        unresponsive server hangs every session indefinitely.

        Caching the value on the class means the constructor finds it already
        resolved and issues no request at all. If the library stops keeping the
        cache there, this quietly does nothing and the old behaviour returns.
        """
        if not hasattr(AsyncZabbixAPI, _VERSION_CACHE_ATTR):
            logger.debug("zabbix_utils no longer caches the API version; skipping seed")
            return
        if getattr(AsyncZabbixAPI, _VERSION_CACHE_ATTR) is not None:
            return

        url = ModuleUtils.check_url(self.config.zabbix_url)
        payload = {"jsonrpc": "2.0", "method": "apiinfo.version", "params": {}, "id": 1}
        connector = aiohttp.TCPConnector(ssl=self.config.verify_ssl)
        async with aiohttp.ClientSession(
            connector=connector,
            timeout=aiohttp.ClientTimeout(total=self.config.timeout),
        ) as session:
            # apiinfo.version is rejected if an Authorization header is present.
            response = await session.post(
                url, json=payload, headers={"Content-Type": "application/json-rpc"}
            )
            response.raise_for_status()
            body = await response.json()

        if "error" in body:
            raise RuntimeError(f"Could not read Zabbix API version: {body['error']}")

        setattr(AsyncZabbixAPI, _VERSION_CACHE_ATTR, APIVersion(body["result"]))
        logger.info("Connected to Zabbix API version %s", body["result"])

    async def _create_fresh_api(self) -> Any:
        """Create and return a new, authenticated AsyncZabbixAPI instance.

        Returns:
            AsyncZabbixAPI: Authenticated API instance ready for requests.
        """
        logger.debug(
            "Creating fresh Zabbix API connection to %s", self.config.zabbix_url
        )
        await self._seed_api_version()
        # Supplying the session makes retries possible and hands us its
        # lifecycle: zabbix_utils only closes sessions it created itself.
        session = build_session(self.config.verify_ssl)
        try:
            api: Any = AsyncZabbixAPI(
                url=self.config.zabbix_url,
                token=self.config.token,
                user=self.config.user,
                password=self.config.password,
                validate_certs=self.config.verify_ssl,
                timeout=self.config.timeout,
                skip_version_check=self.config.skip_version_check,
                client_session=session,
            )
            await api.login()
        except BaseException:
            await session.close()
            raise
        return api, session

    async def close(self):
        """Close any lingering task-keyed API sessions."""
        for api, session in list(self._task_apis.values()):
            await self._discard(api, session)
        self._task_apis.clear()

    @property
    def api(self) -> AsyncZabbixAPI | None:
        """Return the task-local API instance, or None outside a context manager."""
        task = asyncio.current_task()
        key = id(task) if task is not None else 0
        entry = self._task_apis.get(key)
        return entry[0] if entry else None


def get_zabbix_config_from_env() -> ZabbixConfig:
    """Get Zabbix configuration from environment variables."""
    # Parse disabled tags from comma-separated string
    disabled_tags_str = os.getenv("DISABLED_TAGS", "")
    disabled_tags = set()
    if disabled_tags_str.strip():
        disabled_tags = {
            tag.strip() for tag in disabled_tags_str.split(",") if tag.strip()
        }

    return ZabbixConfig(
        zabbix_url=os.getenv("ZABBIX_URL", ""),
        token=os.getenv("ZABBIX_TOKEN"),
        user=os.getenv("ZABBIX_USER"),
        password=os.getenv("ZABBIX_PASSWORD"),
        verify_ssl=parse_bool(os.getenv("ZABBIX_VERIFY_SSL"), default=True),
        timeout=int(os.getenv("ZABBIX_TIMEOUT", "30")),
        skip_version_check=parse_bool(
            os.getenv("ZABBIX_SKIP_VERSION_CHECK"), default=False
        ),
        read_only_mode=parse_bool(os.getenv("READ_ONLY_MODE"), default=False),
        disabled_tags=disabled_tags,
        rate_limit_enabled=parse_bool(os.getenv("RATE_LIMIT_ENABLED"), default=False),
        rate_limit_max_requests=int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "60")),
        rate_limit_window_minutes=int(os.getenv("RATE_LIMIT_WINDOW_MINUTES", "1")),
        tool_search_enabled=parse_bool(os.getenv("TOOL_SEARCH_ENABLED"), default=False),
        tool_search_strategy=(
            "regex"
            if os.getenv("TOOL_SEARCH_STRATEGY", "bm25").lower() == "regex"
            else "bm25"
        ),
        tool_search_max_results=int(os.getenv("TOOL_SEARCH_MAX_RESULTS", "5")),
    )


def get_transport_config_from_env() -> TransportConfig:
    """Get transport configuration from environment variables."""
    http_bearer_token = os.getenv("MCP_HTTP_BEARER_TOKEN")
    if http_bearer_token is not None:
        http_bearer_token = http_bearer_token.strip() or None

    return TransportConfig(
        transport_type=os.getenv("MCP_TRANSPORT", "stdio").lower(),
        http_host=os.getenv("MCP_HTTP_HOST", "127.0.0.1"),
        http_port=int(os.getenv("MCP_HTTP_PORT", "8000")),
        http_bearer_token=http_bearer_token,
    )


_zabbix_client_singleton: ZabbixClient | None = None


def get_zabbix_client(config: ZabbixConfig | None = None) -> ZabbixClient:
    """Get the singleton Zabbix client instance."""
    global _zabbix_client_singleton
    if _zabbix_client_singleton is None:
        if config is None:
            raise ValueError("Zabbix config must be provided for first initialization")
        _zabbix_client_singleton = ZabbixClient(config)
    return _zabbix_client_singleton
