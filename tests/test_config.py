"""Settings are read from the environment strictly: a typo stops the server."""

import pytest

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
