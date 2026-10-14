"""Settings are read from the environment strictly: a typo stops the server."""

import pytest

from zabbix_mcp.zabbix_client import get_transport_config_from_env
from zabbix_mcp.zabbix_client import get_zabbix_config_from_env

# Every variable get_zabbix_config_from_env reads, cleared so the developer's
# own environment cannot leak into these tests.
CONFIG_VARS = (
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
    "MCP_TRANSPORT",
    "MCP_HTTP_HOST",
    "MCP_HTTP_PORT",
    "MCP_HTTP_BEARER_TOKEN",
)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in CONFIG_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("ZABBIX_URL", "https://zabbix.invalid/api_jsonrpc.php")
    monkeypatch.setenv("ZABBIX_TOKEN", "t")


@pytest.mark.parametrize(
    "name",
    [
        "ZABBIX_VERIFY_SSL",
        "ZABBIX_SKIP_VERSION_CHECK",
        "READ_ONLY_MODE",
        "RATE_LIMIT_ENABLED",
        "TOOL_SEARCH_ENABLED",
    ],
)
def test_unknown_bool_setting_stops_startup(monkeypatch, name):
    """A typo must not turn read-only mode or TLS verification off."""
    monkeypatch.setenv(name, "enabled")
    with pytest.raises(ValueError, match=f"{name} must be one of"):
        get_zabbix_config_from_env()


def test_blank_settings_fall_back_to_defaults(monkeypatch):
    """A variable declared without a value means "unset", not a crash."""
    for name in ("ZABBIX_TIMEOUT", "ZABBIX_VERIFY_SSL", "READ_ONLY_MODE"):
        monkeypatch.setenv(name, "")
    config = get_zabbix_config_from_env()
    assert config.timeout == 30
    assert config.verify_ssl is True
    assert config.read_only_mode is False


def test_bad_integer_setting_names_the_variable(monkeypatch):
    monkeypatch.setenv("ZABBIX_TIMEOUT", "30s")
    with pytest.raises(ValueError, match="ZABBIX_TIMEOUT must be an integer"):
        get_zabbix_config_from_env()


def test_whitespace_only_credentials_count_as_missing(monkeypatch):
    monkeypatch.setenv("ZABBIX_URL", "   ")
    monkeypatch.setenv("ZABBIX_TOKEN", "  ")
    monkeypatch.setenv("ZABBIX_USER", " ")
    monkeypatch.setenv("ZABBIX_PASSWORD", "  ")
    config = get_zabbix_config_from_env()
    assert config.zabbix_url == ""
    assert config.token is None
    assert config.user is None
    assert config.password is None


def test_password_keeps_its_spaces(monkeypatch):
    monkeypatch.delenv("ZABBIX_TOKEN")
    monkeypatch.setenv("ZABBIX_USER", "admin")
    monkeypatch.setenv("ZABBIX_PASSWORD", " pass word ")
    assert get_zabbix_config_from_env().password == " pass word "  # noqa: S105


@pytest.mark.parametrize("raw", ["", "   "])
def test_whitespace_bearer_token_is_no_token(monkeypatch, raw):
    """A blank token must not become the one accepted credential."""
    monkeypatch.setenv("MCP_HTTP_BEARER_TOKEN", raw)
    assert get_transport_config_from_env().http_bearer_token is None


def test_bearer_token_is_stripped(monkeypatch):
    monkeypatch.setenv("MCP_HTTP_BEARER_TOKEN", " secret ")
    assert get_transport_config_from_env().http_bearer_token == "secret"  # noqa: S105


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("RATE_LIMIT_MAX_REQUESTS", "0"),
        ("RATE_LIMIT_WINDOW_MINUTES", "abc"),
        ("TOOL_SEARCH_MAX_RESULTS", "-1"),
        ("TOOL_SEARCH_STRATEGY", "regx"),
    ],
)
def test_disabled_feature_ignores_its_settings(monkeypatch, name, value):
    """A leftover value for a feature that is off must not stop the server."""
    monkeypatch.setenv(name, value)
    config = get_zabbix_config_from_env()
    assert config.rate_limit_max_requests == 60
    assert config.rate_limit_window_minutes == 1
    assert config.tool_search_max_results == 5
    assert config.tool_search_strategy == "bm25"


@pytest.mark.parametrize(
    ("enable", "name"),
    [
        ("RATE_LIMIT_ENABLED", "RATE_LIMIT_MAX_REQUESTS"),
        ("RATE_LIMIT_ENABLED", "RATE_LIMIT_WINDOW_MINUTES"),
        ("TOOL_SEARCH_ENABLED", "TOOL_SEARCH_MAX_RESULTS"),
    ],
)
def test_enabled_feature_rejects_zero(monkeypatch, enable, name):
    monkeypatch.setenv(enable, "true")
    monkeypatch.setenv(name, "0")
    with pytest.raises(ValueError, match=f"must be at least 1: {name}=0"):
        get_zabbix_config_from_env()


def test_enabled_feature_reads_its_settings(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("RATE_LIMIT_MAX_REQUESTS", "120")
    monkeypatch.setenv("TOOL_SEARCH_ENABLED", "true")
    monkeypatch.setenv("TOOL_SEARCH_STRATEGY", " Regex ")
    monkeypatch.setenv("TOOL_SEARCH_MAX_RESULTS", "8")
    config = get_zabbix_config_from_env()
    assert config.rate_limit_max_requests == 120
    assert config.tool_search_strategy == "regex"
    assert config.tool_search_max_results == 8


def test_strategy_typo_is_rejected_when_tool_search_is_on(monkeypatch):
    monkeypatch.setenv("TOOL_SEARCH_ENABLED", "true")
    monkeypatch.setenv("TOOL_SEARCH_STRATEGY", "regx")
    with pytest.raises(ValueError, match="TOOL_SEARCH_STRATEGY must be 'bm25' or"):
        get_zabbix_config_from_env()


@pytest.mark.parametrize("timeout", ["0", "-5"])
def test_timeout_must_be_positive(monkeypatch, timeout):
    monkeypatch.setenv("ZABBIX_TIMEOUT", timeout)
    with pytest.raises(ValueError, match="timeout"):
        get_zabbix_config_from_env()


@pytest.mark.parametrize("transport", [None, "stdio"])
def test_port_is_ignored_under_stdio(monkeypatch, transport):
    """`fastmcp run` imports the server; a leftover bad port must not stop it."""
    if transport is not None:
        monkeypatch.setenv("MCP_TRANSPORT", transport)
    monkeypatch.setenv("MCP_HTTP_PORT", "not-a-port")
    assert get_transport_config_from_env().http_port == 8000


@pytest.mark.parametrize("transport", ["http", "sse"])
def test_port_is_checked_for_http_transports(monkeypatch, transport):
    monkeypatch.setenv("MCP_TRANSPORT", transport)
    monkeypatch.setenv("MCP_HTTP_PORT", "not-a-port")
    with pytest.raises(ValueError, match="MCP_HTTP_PORT must be an integer"):
        get_transport_config_from_env()


@pytest.mark.parametrize("name", ["ZABBIX_USER", "ZABBIX_PASSWORD"])
def test_token_with_user_or_password_stops_startup(monkeypatch, name):
    """zabbix_utils rejects the mix at login, failing every call otherwise."""
    monkeypatch.setenv(name, "x")
    with pytest.raises(ValueError, match="Provide only one authentication method"):
        get_zabbix_config_from_env()
