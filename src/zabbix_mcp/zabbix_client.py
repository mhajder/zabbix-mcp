import asyncio
import logging
import os

from zabbix_utils import AsyncZabbixAPI

from zabbix_mcp.models import TransportConfig
from zabbix_mcp.models import ZabbixConfig
from zabbix_mcp.utils import parse_bool

logger = logging.getLogger(__name__)


class ZabbixClient:
    """Async client wrapper for Zabbix API using zabbix_utils AsyncZabbixAPI."""

    _instance: "ZabbixClient | None" = None
    _initialized: bool = False
    _api: AsyncZabbixAPI | None = None
    _task_apis: dict

    def __new__(cls, config: ZabbixConfig | None = None):
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

    async def __aenter__(self) -> AsyncZabbixAPI:
        """Create a fresh, authenticated API instance for the current task."""
        api = await self._create_fresh_api()
        task = asyncio.current_task()
        key = id(task) if task is not None else 0
        self._task_apis[key] = api
        return api

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Log out and discard the API instance belonging to the current task."""
        task = asyncio.current_task()
        key = id(task) if task is not None else 0
        api = self._task_apis.pop(key, None)
        if api is not None:
            try:
                await api.logout()
            except Exception:
                logger.debug("Ignoring exception while closing Zabbix API session")
        return False

    async def _create_fresh_api(self) -> AsyncZabbixAPI:
        """Create and return a new, authenticated AsyncZabbixAPI instance.

        Returns:
            AsyncZabbixAPI: Authenticated API instance ready for requests.
        """
        logger.debug(
            f"Creating fresh Zabbix API connection to {self.config.zabbix_url}"
        )
        api = AsyncZabbixAPI(
            url=self.config.zabbix_url,
            token=self.config.token,
            user=self.config.user,
            password=self.config.password,
            validate_certs=self.config.verify_ssl,
            timeout=self.config.timeout,
            skip_version_check=self.config.skip_version_check,
        )
        await api.login()
        logger.debug(f"Connected to Zabbix API version {api.version}")
        return api

    async def get_api(self) -> AsyncZabbixAPI:
        """Return a fresh authenticated API instance (convenience for direct callers).

        Returns:
            AsyncZabbixAPI: Authenticated API instance ready for requests.
        """
        return await self._create_fresh_api()

    async def close(self):
        """Close any lingering task-keyed API sessions."""
        for api in list(self._task_apis.values()):
            try:
                await api.logout()
            except Exception:
                logger.debug("Ignoring exception while closing Zabbix API session")
        self._task_apis.clear()
        self._api = None

    @property
    def api(self) -> AsyncZabbixAPI | None:
        """Return the task-local API instance, or None outside a context manager."""
        task = asyncio.current_task()
        key = id(task) if task is not None else 0
        return self._task_apis.get(key, self._api)


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
        zabbix_url=os.getenv("ZABBIX_URL"),
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
    )


def get_transport_config_from_env() -> TransportConfig:
    """Get transport configuration from environment variables."""
    return TransportConfig(
        transport_type=os.getenv("MCP_TRANSPORT", "stdio").lower(),
        http_host=os.getenv("MCP_HTTP_HOST", "0.0.0.0"),
        http_port=int(os.getenv("MCP_HTTP_PORT", "8000")),
        http_bearer_token=os.getenv("MCP_HTTP_BEARER_TOKEN"),
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
