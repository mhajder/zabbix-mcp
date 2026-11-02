"""In-process tests for server.py's module-level setup and main().

server.py configures everything at import time, so each test imports a fresh
copy under a controlled environment. The subprocess tests in
test_healthcheck.py cover the same module end to end, but coverage does not
see them.
"""

import importlib
import importlib.metadata
import logging
import sys
from unittest.mock import MagicMock

import dotenv
import pytest
from fastmcp.server.middleware.rate_limiting import SlidingWindowRateLimitingMiddleware
from fastmcp.server.transforms.search import BM25SearchTransform
from fastmcp.server.transforms.search import RegexSearchTransform

from zabbix_mcp.zabbix_client import ZabbixClient

MODULE = "zabbix_mcp.server"

SERVER_ENV_VARS = (
    "ZABBIX_URL",
    "ZABBIX_TOKEN",
    "ZABBIX_USER",
    "ZABBIX_PASSWORD",
    "ZABBIX_VERIFY_SSL",
    "ZABBIX_TIMEOUT",
    "ZABBIX_SKIP_VERSION_CHECK",
    "READ_ONLY_MODE",
    "DISABLED_TAGS",
    "RATE_LIMIT_ENABLED",
    "RATE_LIMIT_MAX_REQUESTS",
    "RATE_LIMIT_WINDOW_MINUTES",
    "TOOL_SEARCH_ENABLED",
    "TOOL_SEARCH_STRATEGY",
    "TOOL_SEARCH_MAX_RESULTS",
    "LOG_LEVEL",
    "MCP_TRANSPORT",
    "MCP_HTTP_HOST",
    "MCP_HTTP_PORT",
    "MCP_HTTP_BEARER_TOKEN",
    "SENTRY_DSN",
)


@pytest.fixture
def load_server(monkeypatch):
    """Import a fresh server module with only the given environment."""
    for name in SERVER_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    # A developer's .env must not leak into the tests.
    monkeypatch.setattr(dotenv, "load_dotenv", lambda *_args, **_kwargs: False)
    original = sys.modules.get(MODULE)

    def factory(**env: str):
        env.setdefault("ZABBIX_URL", "https://zabbix.invalid/api_jsonrpc.php")
        if "ZABBIX_USER" not in env and "ZABBIX_PASSWORD" not in env:
            env.setdefault("ZABBIX_TOKEN", "static-token")
        for name, value in env.items():
            monkeypatch.setenv(name, value)
        sys.modules.pop(MODULE, None)
        module = importlib.import_module(MODULE)
        monkeypatch.setattr(module.mcp, "run", MagicMock())
        return module

    yield factory
    if original is None:
        sys.modules.pop(MODULE, None)
    else:
        sys.modules[MODULE] = original


async def tool_names(module) -> set[str]:
    return {tool.name for tool in await module.mcp.list_tools()}


@pytest.mark.asyncio
async def test_health_route_answers_ok(load_server):
    server = load_server()

    response = await server.health(MagicMock())

    assert response.status_code == 200
    assert response.body == b"ok"


@pytest.mark.asyncio
async def test_all_tools_are_exposed_by_default(load_server):
    names = await tool_names(load_server())

    assert {"host_get", "host_create", "script_execute", "api_version"} <= names
    assert "search_tools" not in names


@pytest.mark.asyncio
async def test_read_only_mode_hides_write_tools(load_server, caplog):
    caplog.set_level(logging.INFO)
    server = load_server(READ_ONLY_MODE="true")
    names = await tool_names(server)

    assert {"host_get", "configuration_export", "history_get"} <= names
    for write in ("host_create", "event_acknowledge", "script_execute"):
        assert write not in names
    assert all(
        name.endswith("_get")
        for name in names - {"configuration_export"} - {"api_version"}
    )
    assert "Read-only mode is enabled" in caplog.text


@pytest.mark.asyncio
async def test_disabled_tags_hide_matching_tools(load_server, caplog):
    caplog.set_level(logging.INFO)
    names = await tool_names(load_server(DISABLED_TAGS="host, script"))

    assert not {"host_get", "host_delete", "script_get", "script_execute"} & names
    # Host groups carry their own tag.
    assert {"hostgroup_get", "item_get"} <= names
    assert "Disabled tags configured" in caplog.text


@pytest.mark.parametrize(
    ("strategy", "transform"),
    [("bm25", BM25SearchTransform), ("regex", RegexSearchTransform)],
)
@pytest.mark.asyncio
async def test_tool_search_replaces_the_tool_list(
    load_server, caplog, strategy, transform
):
    caplog.set_level(logging.INFO)
    server = load_server(
        TOOL_SEARCH_ENABLED="true",
        TOOL_SEARCH_STRATEGY=strategy,
        TOOL_SEARCH_MAX_RESULTS="8",
    )

    added = [t for t in server.mcp.transforms if isinstance(t, transform)]
    assert len(added) == 1
    assert added[0]._max_results == 8
    assert await tool_names(server) == {"search_tools", "call_tool"}
    assert f"strategy={strategy}, max_results=8" in caplog.text


def test_rate_limiting_adds_middleware(load_server):
    server = load_server(
        RATE_LIMIT_ENABLED="true",
        RATE_LIMIT_MAX_REQUESTS="10",
        RATE_LIMIT_WINDOW_MINUTES="2",
    )

    (limiter,) = [
        m
        for m in server.mcp.middleware
        if isinstance(m, SlidingWindowRateLimitingMiddleware)
    ]
    assert limiter.max_requests == 10
    assert limiter.window_seconds == 120


def test_rate_limiting_is_off_by_default(load_server):
    server = load_server()

    assert not any(
        isinstance(m, SlidingWindowRateLimitingMiddleware)
        for m in server.mcp.middleware
    )


def test_unknown_log_level_falls_back_to_info(load_server, caplog):
    load_server(LOG_LEVEL="chatty")

    assert "Unknown LOG_LEVEL 'CHATTY'" in caplog.text


@pytest.mark.parametrize("value", ["", "   "])
def test_blank_log_level_means_info_without_a_warning(load_server, caplog, value):
    """LOG_LEVEL= in a .env or compose file is "unset", not an unknown level."""
    server = load_server(LOG_LEVEL=value)

    assert "Unknown LOG_LEVEL" not in caplog.text
    assert server._resolved_log_level == logging.INFO


def test_lowercase_log_level_is_accepted(load_server, caplog):
    server = load_server(LOG_LEVEL="debug")

    assert server._resolved_log_level == logging.DEBUG
    assert "Unknown LOG_LEVEL" not in caplog.text


def test_version_comes_from_the_installed_package(load_server):
    assert load_server().__version__ == importlib.metadata.version("zabbix-mcp")


def test_version_falls_back_when_package_is_not_installed(load_server, monkeypatch):
    def missing(_name):
        raise importlib.metadata.PackageNotFoundError

    monkeypatch.setattr(importlib.metadata, "version", missing)

    assert load_server().__version__ == "0.0.1"


def test_invalid_configuration_is_logged_and_raised(load_server, caplog):
    with pytest.raises(ValueError, match="TOOL_SEARCH_STRATEGY"):
        load_server(TOOL_SEARCH_ENABLED="true", TOOL_SEARCH_STRATEGY="regx")

    assert "Invalid configuration" in caplog.text


def test_bearer_token_enables_auth(load_server):
    assert load_server().mcp.auth is None
    assert load_server(MCP_HTTP_BEARER_TOKEN="secret").mcp.auth is not None


@pytest.mark.asyncio
async def test_bearer_token_is_the_one_accepted_credential(load_server):
    auth = load_server(MCP_HTTP_BEARER_TOKEN="secret").mcp.auth

    assert (await auth.verify_token("secret")).client_id == "authenticated-client"
    assert await auth.verify_token("guess") is None


@pytest.mark.asyncio
async def test_lifespan_closes_the_zabbix_connection(load_server, monkeypatch):
    server = load_server()
    monkeypatch.setattr(ZabbixClient, "_instance", None)
    closed = []

    async def fake_close(self):
        closed.append(self.config)

    monkeypatch.setattr(ZabbixClient, "close", fake_close)
    async with server.zabbix_lifespan(server.mcp) as state:
        assert state == {}
        assert closed == []
    assert closed == [server.ZABBIX_CONFIG]


def test_main_runs_stdio_by_default(load_server, caplog):
    caplog.set_level(logging.INFO)
    server = load_server()

    server.main()

    server.mcp.run.assert_called_once_with()
    assert "(auth: token)" in caplog.text
    assert "Using STDIO transport" in caplog.text


@pytest.mark.parametrize("transport", ["http", "sse", "streamable-http"])
def test_main_runs_http_transports_on_the_configured_address(
    load_server, caplog, transport
):
    caplog.set_level(logging.INFO)
    server = load_server(
        MCP_TRANSPORT=transport,
        MCP_HTTP_HOST="192.0.2.10",
        MCP_HTTP_PORT="9001",
        MCP_HTTP_BEARER_TOKEN="secret",
    )

    server.main()

    server.mcp.run.assert_called_once_with(
        transport="sse" if transport == "sse" else "http",
        host="192.0.2.10",
        port=9001,
    )
    assert "Bearer token authentication enabled" in caplog.text
    assert "WITHOUT authentication" not in caplog.text


@pytest.mark.parametrize("transport", ["http", "sse"])
def test_main_warns_when_http_runs_without_a_token(load_server, caplog, transport):
    caplog.set_level(logging.INFO)
    server = load_server(MCP_TRANSPORT=transport)

    server.main()

    assert "WITHOUT authentication" in caplog.text
    assert "Bearer token authentication enabled" not in caplog.text
    server.mcp.run.assert_called_once()


def test_main_accepts_user_and_password(load_server, caplog):
    caplog.set_level(logging.INFO)
    server = load_server(ZABBIX_USER="Admin", ZABBIX_PASSWORD="zabbix")

    server.main()

    assert "(auth: user/password)" in caplog.text
    server.mcp.run.assert_called_once_with()


def test_main_warns_about_plaintext_http(load_server, caplog):
    server = load_server(ZABBIX_URL="http://zabbix.invalid/api_jsonrpc.php")

    server.main()

    assert "ZABBIX_URL uses plaintext http://" in caplog.text
    server.mcp.run.assert_called_once()


@pytest.mark.parametrize(
    ("env", "message"),
    [
        ({"MCP_TRANSPORT": "websocket"}, "Unknown MCP_TRANSPORT 'websocket'"),
        ({"ZABBIX_URL": ""}, "Missing required Zabbix URL"),
        # zabbix_utils would prepend http:// and send the token in the clear.
        (
            {"ZABBIX_URL": "zabbix.invalid/api_jsonrpc.php"},
            "ZABBIX_URL must start with https:// or http://",
        ),
        ({"ZABBIX_URL": "ftp://zabbix.invalid"}, "ZABBIX_URL must start with"),
        ({"ZABBIX_USER": "Admin"}, "Missing Zabbix authentication"),
        ({"ZABBIX_PASSWORD": "zabbix"}, "Missing Zabbix authentication"),
    ],
)
def test_main_stops_on_bad_settings(load_server, caplog, env, message):
    server = load_server(**env)

    with pytest.raises(SystemExit) as exc:
        server.main()

    assert exc.value.code == 1
    assert message in caplog.text
    server.mcp.run.assert_not_called()
