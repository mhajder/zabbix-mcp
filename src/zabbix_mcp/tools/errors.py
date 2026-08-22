"""
Surfacing upstream Zabbix failures to the MCP client.

Returning ``{"error": ...}`` from a tool marks the call *successful*: the result
carries no ``isError``, so a client cannot tell a failure from an empty result,
and the dict collides with the success shape (a caller reading ``result["hosts"]``
gets a ``KeyError`` instead of a signalled error). Raising ``ToolError`` sets the
error flag, and FastMCP delivers its message to the client unmasked.
"""

from typing import NoReturn

from fastmcp import Context
from fastmcp.exceptions import ToolError


def describe(exc: Exception) -> str:
    """Render an exception, keeping the Zabbix JSON-RPC code when there is one.

    ``zabbix_utils`` raises ``APIRequestError`` with ``code``/``message``/``data``
    copied from the JSON-RPC error object. Flattening that to ``str(exc)`` drops
    the code, which is the part that distinguishes a bad parameter (-32602) from
    a server-side failure (-32500).

    Args:
        exc: The exception raised while talking to Zabbix.

    Returns:
        str: Human-readable description, prefixed with the API error code when
            the exception carries one.
    """
    code = getattr(exc, "code", None)
    if code is None:
        return f"{type(exc).__name__}: {exc}"

    detail = " ".join(
        part for part in (getattr(exc, "message", ""), getattr(exc, "data", "")) if part
    )
    return f"Zabbix API error {code}: {detail}".strip()


async def fail(ctx: Context, action: str, exc: Exception) -> NoReturn:
    """Log a failed tool call to the session and raise it as a tool error.

    Args:
        ctx: The MCP context of the running tool.
        action: What was being attempted, e.g. ``"Error retrieving hosts"``.
        exc: The exception that ended the call.

    Raises:
        ToolError: Always. This is how the failure reaches the client.
    """
    detail = f"{action}: {describe(exc)}"
    await ctx.error(detail)
    raise ToolError(detail) from exc
