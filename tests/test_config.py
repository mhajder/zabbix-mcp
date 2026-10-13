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
