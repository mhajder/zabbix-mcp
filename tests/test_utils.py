import pytest

from zabbix_mcp.utils import http_host_from_env
from zabbix_mcp.utils import http_port_from_env
from zabbix_mcp.utils import parse_bool
from zabbix_mcp.utils import transport_from_env


@pytest.mark.parametrize(
    ("val", "default", "expected"),
    [
        (None, True, True),
        (None, False, False),
        ("1", False, True),
        ("true", False, True),
        ("yes", False, True),
        ("on", False, True),
        ("TrUe", False, True),
        ("YES", False, True),
        ("ON", False, True),
        ("1 ", False, True),
        ("0", True, False),
        ("false", True, False),
        ("no", True, False),
        ("random", True, False),
        ("False", True, False),
        # Blank means "unset", so the default wins rather than False.
        ("", True, True),
        ("", False, False),
        ("  ", True, True),
        ("  ", False, False),
    ],
)
def test_parse_bool(val, default, expected):
    assert parse_bool(val, default) is expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, "stdio"),
        ("http", "http"),
        ("SSE", "sse"),
        # Only lowercased: anything else selects stdio in the server.
        (" http ", " http "),
        ("", ""),
    ],
)
def test_transport_from_env(monkeypatch, raw, expected):
    if raw is None:
        monkeypatch.delenv("MCP_TRANSPORT", raising=False)
    else:
        monkeypatch.setenv("MCP_TRANSPORT", raw)
    assert transport_from_env() == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, "127.0.0.1"),
        ("0.0.0.0", "0.0.0.0"),  # noqa: S104
        ("::", "::"),
        # The URL form of an IPv6 literal; uvicorn needs it bare.
        ("[::]", "::"),
        ("[fd00::5]", "fd00::5"),
        ("", ""),
    ],
)
def test_http_host_from_env(monkeypatch, raw, expected):
    """The server and the healthcheck share this; uvicorn needs bare IPv6."""
    if raw is None:
        monkeypatch.delenv("MCP_HTTP_HOST", raising=False)
    else:
        monkeypatch.setenv("MCP_HTTP_HOST", raw)
    assert http_host_from_env() == expected


@pytest.mark.parametrize(("raw", "expected"), [(None, 8000), ("9000", 9000)])
def test_http_port_from_env(monkeypatch, raw, expected):
    if raw is None:
        monkeypatch.delenv("MCP_HTTP_PORT", raising=False)
    else:
        monkeypatch.setenv("MCP_HTTP_PORT", raw)
    assert http_port_from_env() == expected


def test_http_port_from_env_rejects_non_integer(monkeypatch):
    monkeypatch.setenv("MCP_HTTP_PORT", "abc")
    with pytest.raises(ValueError, match="invalid literal for int"):
        http_port_from_env()
