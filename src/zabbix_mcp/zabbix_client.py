import asyncio
import logging
import os
import time
from typing import Any

import aiohttp
from zabbix_utils.aioapi import AsyncZabbixAPI
from zabbix_utils.common import ModuleUtils
from zabbix_utils.exceptions import APIRequestError
from zabbix_utils.types import APIVersion

from zabbix_mcp.models import TransportConfig
from zabbix_mcp.models import ZabbixConfig
from zabbix_mcp.retry import build_session
from zabbix_mcp.utils import HTTP_TRANSPORTS
from zabbix_mcp.utils import env_bool
from zabbix_mcp.utils import env_int
from zabbix_mcp.utils import env_str
from zabbix_mcp.utils import http_host_from_env
from zabbix_mcp.utils import http_port_from_env
from zabbix_mcp.utils import transport_from_env

logger = logging.getLogger(__name__)

# Name-mangled cache slot for AsyncZabbixAPI.__version. Populating it keeps the
# library's constructor from resolving the version itself - see _seed_api_version.
_VERSION_CACHE_ATTR = "_AsyncZabbixAPI__version"

# The error 'data' Zabbix returns for a session that expired or was removed.
# Matched exactly: other errors echo caller input (a host named "re-login"),
# and a substring match would take those for an expired session.
_SESSION_LOST_ERRORS = frozenset(
    {"session terminated, re-login, please.", "not authorised.", "not authorized."}
)


# Credentials zabbix_utils reads straight from the environment whenever the
# value it was given is None - see _drop_blank_credentials.
_CREDENTIAL_VARS = ("ZABBIX_TOKEN", "ZABBIX_USER", "ZABBIX_PASSWORD")


# After a failed re-login, how long to return the session error instead of
# trying again. Zabbix blocks an account after 5 failed logins in a row, so a
# rotated password must not get one attempt per tool call.
RELOGIN_COOLDOWN = 300.0


def _drop_blank_credentials() -> None:
    """Remove whitespace-only credential variables from the environment.

    The config treats them as unset and passes None, but ``login()`` then falls
    back to the raw variable, so ZABBIX_USER=" " next to a token would fail
    every call with "Token cannot be used with username and password".
    """
    for name in _CREDENTIAL_VARS:
        value = os.environ.get(name)
        if value is not None and not value.strip():
            del os.environ[name]


def _is_session_lost(error: APIRequestError) -> bool:
    """Tell whether a Zabbix API error means the login session is gone."""
    data = getattr(error, "data", None)
    return isinstance(data, str) and data.strip().lower() in _SESSION_LOST_ERRORS


class _ReloggingZabbixAPI(AsyncZabbixAPI):
    """AsyncZabbixAPI that logs in again, once, when its session has expired.

    The connection is shared for the life of the server, so a user/password
    session can outlive Zabbix's auto-logout. Zabbix rejects such a request
    before running it, which makes resending it safe even for writes. Token
    auth never expires this way, so it is not retried. A failed re-login is
    not repeated for RELOGIN_COOLDOWN seconds.
    """

    def __init__(self, *args: Any, relogin: bool, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self._relogin = relogin
        self._login_lock = asyncio.Lock()
        self._login_generation = 0
        self._login_failed_at: float | None = None

    async def send_async_request(
        self, method: str, params: dict | None = None, need_auth: bool = True
    ) -> dict:
        generation = self._login_generation
        try:
            return await super().send_async_request(method, params, need_auth)
        except APIRequestError as err:
            if not (
                self._relogin
                and need_auth
                and method != "user.logout"
                and _is_session_lost(err)
            ):
                raise
            session_error = err

        async with self._login_lock:
            # Concurrent calls can all hit the expired session; only the first
            # logs in, the rest reuse its new session.
            if self._login_generation == generation:
                failed_at = self._login_failed_at
                if (
                    failed_at is not None
                    and time.monotonic() - failed_at < RELOGIN_COOLDOWN
                ):
                    raise session_error
                logger.info("Zabbix session expired - logging in again")
                try:
                    await self.login()
                except BaseException:
                    self._login_failed_at = time.monotonic()
                    logger.warning(
                        "Logging in to Zabbix again failed; not retrying for %.0fs",
                        RELOGIN_COOLDOWN,
                    )
                    raise
                finally:
                    # Bumped even on failure, so callers queued behind a failed
                    # login do not each repeat it.
                    self._login_generation += 1
                self._login_failed_at = None
        return await super().send_async_request(method, params, need_auth)


class ZabbixClient:
    """Shared, authenticated connection to the Zabbix API.

    Tools use it as ``async with ZabbixClient(config) as api``. The connection
    is made on first use and kept until close(): building one per tool call
    opened a new HTTP session each time and, with user/password auth, added a
    login and a logout request to every call.
    """

    _instance: "ZabbixClient | None" = None
    _initialized: bool = False

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
        self._api: Any = None
        self._session: aiohttp.ClientSession | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._connect_lock = asyncio.Lock()
        self._initialized = True

    async def __aenter__(self) -> Any:
        """Return the shared API instance, connecting on first use."""
        loop = asyncio.get_running_loop()
        if self._loop is not loop:
            # A session and a lock belong to the loop that created them, so a
            # new loop (a restarted server, a test) starts from scratch.
            self._api = self._session = None
            self._connect_lock = asyncio.Lock()
            self._loop = loop
        if self._api is None:
            async with self._connect_lock:
                if self._api is None:
                    self._api, self._session = await self._create_api()
        return self._api

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Keep the connection open for the next tool call."""
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
        ``urllib.urlopen`` call, which stalls the whole event loop while it waits. That call also ignores the
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

    async def _create_api(self) -> tuple[Any, aiohttp.ClientSession]:
        """Create and log in the API instance shared by all tool calls.

        Returns:
            tuple: The authenticated API instance and its HTTP session.
        """
        logger.debug("Connecting to Zabbix API at %s", self.config.zabbix_url)
        await self._seed_api_version()
        _drop_blank_credentials()
        # Supplying the session makes retries possible and hands us its
        # lifecycle: zabbix_utils only closes sessions it created itself.
        session = build_session(self.config.verify_ssl)
        try:
            api = _ReloggingZabbixAPI(
                url=self.config.zabbix_url,
                token=self.config.token,
                user=self.config.user,
                password=self.config.password,
                validate_certs=self.config.verify_ssl,
                timeout=self.config.timeout,
                skip_version_check=self.config.skip_version_check,
                client_session=session,
                relogin=not self.config.token,
            )
            await api.login()
        except BaseException:
            await session.close()
            raise
        return api, session

    async def close(self) -> None:
        """Log out and close the shared connection, if one was made."""
        api, session = self._api, self._session
        self._api = self._session = None
        if api is not None:
            await self._discard(api, session)


def _password_from_env() -> str | None:
    """Return ZABBIX_PASSWORD unstripped, as spaces may be part of it; blank is unset."""
    password = os.getenv("ZABBIX_PASSWORD")
    return password if password and password.strip() else None


def _env_setting(name: str, field: str) -> int:
    """Read an integer setting, defaulting to ZabbixConfig's own default."""
    return env_int(name, ZabbixConfig.model_fields[field].default)


def get_zabbix_config_from_env() -> ZabbixConfig:
    """Get Zabbix configuration from environment variables."""
    # Parse disabled tags from comma-separated string
    disabled_tags_str = os.getenv("DISABLED_TAGS", "")
    disabled_tags = set()
    if disabled_tags_str.strip():
        disabled_tags = {
            tag.strip() for tag in disabled_tags_str.split(",") if tag.strip()
        }

    # Unknown values used to fall back to bm25 silently, hiding a typo such as
    # "regx" or a stray space; trim, then refuse anything else - but only when
    # tool search is on, so a leftover value cannot stop a server that never
    # uses it.
    tool_search_enabled = env_bool("TOOL_SEARCH_ENABLED", default=False)
    tool_search_strategy = (env_str("TOOL_SEARCH_STRATEGY") or "bm25").lower()
    if tool_search_enabled and tool_search_strategy not in ("bm25", "regex"):
        raise ValueError(
            "TOOL_SEARCH_STRATEGY must be 'bm25' or 'regex', "
            f"got {os.getenv('TOOL_SEARCH_STRATEGY')!r}"
        )
    rate_limit_enabled = env_bool("RATE_LIMIT_ENABLED", default=False)

    # Numeric settings of a disabled feature are not read at all: a leftover
    # value must not stop a server that never uses it, and ZabbixConfig's own
    # defaults then apply. Read ones fall back to those same defaults.
    numbers: dict[str, int] = {}
    if rate_limit_enabled:
        numbers["rate_limit_max_requests"] = _env_setting(
            "RATE_LIMIT_MAX_REQUESTS", "rate_limit_max_requests"
        )
        numbers["rate_limit_window_minutes"] = _env_setting(
            "RATE_LIMIT_WINDOW_MINUTES", "rate_limit_window_minutes"
        )
    if tool_search_enabled:
        numbers["tool_search_max_results"] = _env_setting(
            "TOOL_SEARCH_MAX_RESULTS", "tool_search_max_results"
        )

    return ZabbixConfig(
        # Whitespace-only counts as missing: it would otherwise start the server
        # and fail every call with a confusing connection or auth error.
        zabbix_url=env_str("ZABBIX_URL") or "",
        token=env_str("ZABBIX_TOKEN"),
        user=env_str("ZABBIX_USER"),
        password=_password_from_env(),
        verify_ssl=env_bool("ZABBIX_VERIFY_SSL", default=True),
        timeout=_env_setting("ZABBIX_TIMEOUT", "timeout"),
        skip_version_check=env_bool("ZABBIX_SKIP_VERSION_CHECK", default=False),
        read_only_mode=env_bool("READ_ONLY_MODE", default=False),
        disabled_tags=disabled_tags,
        rate_limit_enabled=rate_limit_enabled,
        tool_search_enabled=tool_search_enabled,
        tool_search_strategy=("regex" if tool_search_strategy == "regex" else "bm25"),
        **numbers,
    )


def get_transport_config_from_env() -> TransportConfig:
    """Get transport configuration from environment variables."""
    transport_type = transport_from_env()
    # The port is only parsed when an HTTP transport will bind it: a leftover
    # non-numeric MCP_HTTP_PORT must not stop stdio or `fastmcp run`.
    http_port = (
        http_port_from_env()
        if transport_type in HTTP_TRANSPORTS
        else TransportConfig.model_fields["http_port"].default
    )

    return TransportConfig(
        transport_type=transport_type,
        http_host=http_host_from_env(),
        http_port=http_port,
        http_bearer_token=env_str("MCP_HTTP_BEARER_TOKEN"),
    )
