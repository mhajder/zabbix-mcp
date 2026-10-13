import os

TRUTHY_VALUES = ("true", "1", "yes", "on")
FALSY_VALUES = ("false", "0", "no", "off")
# "true/false, 1/0, yes/no, on/off", for error messages.
BOOL_HELP = ", ".join(
    f"{t}/{f}" for t, f in zip(TRUTHY_VALUES, FALSY_VALUES, strict=True)
)

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
    silently flip a setting off. Any other value must be a recognized spelling:
    a typo such as ``READ_ONLY_MODE=enable`` raises instead of reading as False,
    which would expose the write tools or disable TLS verification.

    Args:
        val: The value to convert.
        default (bool, optional): The default value to return if val is None or blank. Defaults to True.

    Returns:
        bool: True for "true", "1", "yes", "on"; False for "false", "0", "no",
        "off" (case-insensitive).

    Raises:
        ValueError: If val is set to anything else.
    """
    if val is None:
        return default
    normalized = str(val).strip().casefold()
    if not normalized:
        return default
    if normalized in TRUTHY_VALUES:
        return True
    if normalized in FALSY_VALUES:
        return False
    raise ValueError(f"Expected a boolean ({BOOL_HELP}), got {val!r}")


def env_bool(name: str, default: bool) -> bool:
    """
    Read a boolean environment variable, treating a blank value as unset.

    Raises:
        ValueError: If the variable is set to an unrecognized value.
    """
    try:
        return parse_bool(os.getenv(name), default)
    except ValueError:
        raise ValueError(
            f"{name} must be one of {BOOL_HELP}, got {os.getenv(name)!r}"
        ) from None
