import pytest

from zabbix_mcp.utils import env_bool
from zabbix_mcp.utils import env_float
from zabbix_mcp.utils import env_int
from zabbix_mcp.utils import env_str
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


@pytest.mark.parametrize("val", ["random", "enabled", "enable", "y", "2"])
@pytest.mark.parametrize("default", [True, False])
def test_parse_bool_rejects_unknown_values(val, default):
    """A typo must not read as False: READ_ONLY_MODE=enable would expose writes."""
    with pytest.raises(ValueError, match=f"got {val!r}"):
        parse_bool(val, default)


def test_env_bool_names_the_variable(monkeypatch):
    monkeypatch.setenv("ZABBIX_TEST_BOOL", "nope")
    with pytest.raises(ValueError, match="ZABBIX_TEST_BOOL must be one of"):
        env_bool("ZABBIX_TEST_BOOL", default=True)


@pytest.mark.parametrize(
    ("raw", "expected"), [(None, True), ("", True), ("off", False)]
)
def test_env_bool(monkeypatch, raw, expected):
    if raw is None:
        monkeypatch.delenv("ZABBIX_TEST_BOOL", raising=False)
    else:
        monkeypatch.setenv("ZABBIX_TEST_BOOL", raw)
    assert env_bool("ZABBIX_TEST_BOOL", default=True) is expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, "stdio"),
        ("http", "http"),
        ("SSE", "sse"),
        # FastMCP's name for the streamable HTTP transport.
        ("streamable-http", "http"),
        (" http ", "http"),
        ("", "stdio"),
        ("   ", "stdio"),
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
        (" 0.0.0.0 ", "0.0.0.0"),  # noqa: S104
        # Blank counts as unset: it must not bind every interface.
        ("", "127.0.0.1"),
        ("   ", "127.0.0.1"),
    ],
)
def test_http_host_from_env(monkeypatch, raw, expected):
    """The server and the healthcheck share this; uvicorn needs bare IPv6."""
    if raw is None:
        monkeypatch.delenv("MCP_HTTP_HOST", raising=False)
    else:
        monkeypatch.setenv("MCP_HTTP_HOST", raw)
    assert http_host_from_env() == expected


@pytest.mark.parametrize(
    ("raw", "expected"), [(None, 8000), ("9000", 9000), ("", 8000), (" 9000 ", 9000)]
)
def test_http_port_from_env(monkeypatch, raw, expected):
    if raw is None:
        monkeypatch.delenv("MCP_HTTP_PORT", raising=False)
    else:
        monkeypatch.setenv("MCP_HTTP_PORT", raw)
    assert http_port_from_env() == expected


def test_http_port_from_env_rejects_non_integer(monkeypatch):
    monkeypatch.setenv("MCP_HTTP_PORT", "abc")
    with pytest.raises(ValueError, match="MCP_HTTP_PORT must be an integer, got 'abc'"):
        http_port_from_env()


@pytest.mark.parametrize(
    ("raw", "expected"), [(None, 30), ("", 30), ("  ", 30), ("45", 45), (" 45 ", 45)]
)
def test_env_int_treats_blank_as_unset(monkeypatch, raw, expected):
    if raw is None:
        monkeypatch.delenv("ZABBIX_TEST_INT", raising=False)
    else:
        monkeypatch.setenv("ZABBIX_TEST_INT", raw)
    assert env_int("ZABBIX_TEST_INT", 30) == expected


@pytest.mark.parametrize("raw", ["abc", "1.5"])
def test_env_int_error_names_the_variable(monkeypatch, raw):
    monkeypatch.setenv("ZABBIX_TEST_INT", raw)
    with pytest.raises(
        ValueError, match=f"ZABBIX_TEST_INT must be an integer, got {raw!r}"
    ):
        env_int("ZABBIX_TEST_INT", 30)


@pytest.mark.parametrize(("raw", "expected"), [(None, 1.0), ("", 1.0), ("0.25", 0.25)])
def test_env_float_treats_blank_as_unset(monkeypatch, raw, expected):
    if raw is None:
        monkeypatch.delenv("ZABBIX_TEST_FLOAT", raising=False)
    else:
        monkeypatch.setenv("ZABBIX_TEST_FLOAT", raw)
    assert env_float("ZABBIX_TEST_FLOAT", 1.0) == expected


def test_env_float_error_names_the_variable(monkeypatch):
    monkeypatch.setenv("ZABBIX_TEST_FLOAT", "half")
    with pytest.raises(ValueError, match="ZABBIX_TEST_FLOAT must be a number"):
        env_float("ZABBIX_TEST_FLOAT", 1.0)


@pytest.mark.parametrize(
    ("raw", "expected"), [(None, None), ("", None), ("   ", None), (" tok ", "tok")]
)
def test_env_str_strips_and_treats_blank_as_unset(monkeypatch, raw, expected):
    if raw is None:
        monkeypatch.delenv("ZABBIX_TEST_STR", raising=False)
    else:
        monkeypatch.setenv("ZABBIX_TEST_STR", raw)
    assert env_str("ZABBIX_TEST_STR") == expected
