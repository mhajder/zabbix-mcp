import os

TRUTHY_VALUES = ("1", "true", "yes", "on")

# MCP_TRANSPORT values that serve HTTP. Anything else runs the stdio transport.
HTTP_TRANSPORTS = frozenset({"sse", "http"})
# FastMCP calls the streamable HTTP transport "streamable-http"; accept that
# spelling for the "http" transport this server documents.
TRANSPORT_ALIASES = {"streamable-http": "http"}

# Liveness endpoint served on the HTTP transports and probed by the container
# healthcheck.
HEALTH_PATH = "/health"


def transport_from_env() -> str:
    """
    Return MCP_TRANSPORT lowercased, defaulting to stdio when unset.

    The server and the container healthcheck both read the transport here, so
    they always agree on it. Values outside HTTP_TRANSPORTS select stdio.

    'streamable-http' is read as 'http', FastMCP's name for that transport.
    """
    transport = os.getenv("MCP_TRANSPORT", "stdio").lower()
    return TRANSPORT_ALIASES.get(transport, transport)


def http_host_from_env() -> str:
    """
    Return MCP_HTTP_HOST without IPv6 brackets, defaulting to loopback when unset.

    The server and the container healthcheck both read the bind address here,
    so they always agree on it.
    """
    host = os.getenv("MCP_HTTP_HOST", "127.0.0.1")
    # Accept the URL form of an IPv6 literal ('[::]'); uvicorn needs it bare.
    if host.startswith("[") and host.endswith("]"):
        host = host[1:-1]
    return host


def http_port_from_env() -> int:
    """
    Return MCP_HTTP_PORT as an integer, defaulting to 8000 when unset.

    Raises:
        ValueError: If the variable is set to something that is not an integer.
    """
    return int(os.getenv("MCP_HTTP_PORT", "8000"))


def parse_bool(val, default=True):
    """
    Convert a value to boolean.

    A blank or whitespace-only value counts as unset and yields the default,
    so an env var declared without a value (``ZABBIX_VERIFY_SSL=``) cannot
    silently flip a setting off.

    Args:
        val: The value to convert.
        default (bool, optional): The default value to return if val is None or blank. Defaults to True.

    Returns:
        bool: True if val represents a truthy value ("1", "true", "yes", "on"), case-insensitive; otherwise False.
    """
    if val is None:
        return default
    normalized = str(val).strip().casefold()
    if not normalized:
        return default
    return normalized in TRUTHY_VALUES
