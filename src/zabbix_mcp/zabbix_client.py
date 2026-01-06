import logging
import os

from zabbix_utils import AsyncZabbixAPI

from zabbix_mcp.models import TransportConfig
from zabbix_mcp.models import ZabbixConfig
from zabbix_mcp.utils import parse_bool

logger = logging.getLogger(__name__)


class ZabbixClient:
    """Async client wrapper for Zabbix API using zabbix_utils AsyncZabbixAPI.

    This class provides a singleton pattern for managing the Zabbix API connection
    and exposes the underlying AsyncZabbixAPI for making API calls.
    """

    _instance: "ZabbixClient | None" = None
    _initialized: bool = False
    _api: AsyncZabbixAPI | None = None

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
        self._initialized = True

    async def __aenter__(self) -> AsyncZabbixAPI:
        """Enter the async context manager and return authenticated API.

        Kept for backward compatibility: it returns the persistent API instance
        but does not logout on exit (to allow reuse across tool calls).
        """
        return await self.get_api()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Do not logout on context exit to allow session reuse."""
        return False

    async def get_api(self) -> AsyncZabbixAPI:
        """Get authenticated API instance, creating and logging in if necessary.

        Returns:
            AsyncZabbixAPI: Authenticated API instance ready for requests.
        """
        # If we don't yet have an API instance, create and login.
        if self._api is None:
            logger.debug(f"Connecting to Zabbix API at {self.config.zabbix_url}")
            self._api = AsyncZabbixAPI(
                url=self.config.zabbix_url,
                token=self.config.token,
                user=self.config.user,
                password=self.config.password,
                validate_certs=self.config.verify_ssl,
                timeout=self.config.timeout,
                skip_version_check=self.config.skip_version_check,
            )

            await self._api.login()
            logger.debug(f"Connected to Zabbix API version {self._api.version}")

            return self._api

        # If we already have an API instance, verify the session is still valid.
        try:
            valid = await self._api.check_auth()
        except Exception:
            logger.exception(
                "Error while checking Zabbix API authentication; marking session as invalid"
            )
            valid = False

        if not valid:
            logger.info("Zabbix API session invalid or closed; reconnecting...")
            try:
                await self._api.logout()
            except Exception:
                logger.debug("Ignoring exception during logout while reconnecting")

            self._api = AsyncZabbixAPI(
                url=self.config.zabbix_url,
                token=self.config.token,
                user=self.config.user,
                password=self.config.password,
                validate_certs=self.config.verify_ssl,
                timeout=self.config.timeout,
                skip_version_check=self.config.skip_version_check,
            )

            await self._api.login()
            logger.debug(f"Reconnected to Zabbix API version {self._api.version}")

        return self._api

    async def close(self):
        """Close the Zabbix API session."""
        if self._api is not None:
            await self._api.logout()
            self._api = None

    @property
    def api(self) -> AsyncZabbixAPI | None:
        """Get the underlying AsyncZabbixAPI instance."""
        return self._api


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
