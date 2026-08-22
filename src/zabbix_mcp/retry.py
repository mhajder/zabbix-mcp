"""
Retrying transport for the Zabbix API.

``zabbix_utils`` calls ``raise_for_status()`` on every response and offers no
retry, so a rate limit or a momentary 502 from a reverse proxy fails the whole
tool call. Retries live in the HTTP layer rather than in each tool: it is the
one place every request already passes through, and it keeps ``Retry-After``
next to the response that carries it.

Only responses that can plausibly succeed on a second attempt are retried - 429
and 5xx. Zabbix reports its own application errors as HTTP 200 with a JSON-RPC
``error`` member, so a bad parameter is never retried.
"""

import asyncio
import logging

import aiohttp
from aiohttp import ClientHandlerType
from aiohttp import ClientRequest
from aiohttp import ClientResponse

logger = logging.getLogger(__name__)

RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})

MAX_ATTEMPTS = 3
BASE_BACKOFF = 0.5
MAX_DELAY = 10.0


def _retry_after_seconds(response: ClientResponse) -> float | None:
    """Read a Retry-After header, in seconds, if the server sent a usable one.

    Args:
        response: The response to inspect.

    Returns:
        float | None: Delay in seconds, or None if absent, unparsable, or longer
            than a tool call should reasonably block for.
    """
    raw = response.headers.get("Retry-After")
    if not raw:
        return None
    try:
        # Only the delta-seconds form is handled; the HTTP-date form is rare
        # here and not worth the parsing risk.
        delay = float(raw.strip())
    except ValueError:
        return None
    if delay < 0 or delay > MAX_DELAY:
        return None
    return delay


async def retry_middleware(
    request: ClientRequest, handler: ClientHandlerType
) -> ClientResponse:
    """Retry a Zabbix API request when the server reports a transient failure.

    Args:
        request: The outgoing request, replayed unchanged on each attempt.
        handler: Next handler in the aiohttp client middleware chain.

    Returns:
        ClientResponse: The first non-retryable response, or the last attempt.
    """
    for attempt in range(1, MAX_ATTEMPTS + 1):
        response = await handler(request)
        if response.status not in RETRY_STATUSES or attempt == MAX_ATTEMPTS:
            return response

        delay = _retry_after_seconds(response)
        if delay is None:
            delay = min(BASE_BACKOFF * 2 ** (attempt - 1), MAX_DELAY)
        response.release()

        logger.warning(
            "Zabbix API returned HTTP %d (attempt %d/%d), retrying in %.1fs",
            response.status,
            attempt,
            MAX_ATTEMPTS,
            delay,
        )
        await asyncio.sleep(delay)

    raise RuntimeError("unreachable: retry loop always returns")


def build_session(verify_ssl: bool) -> aiohttp.ClientSession:
    """Create the HTTP session used for one Zabbix API connection.

    Passing our own session to ``AsyncZabbixAPI`` is what allows retries to be
    installed, and it makes the session ours to close - ``zabbix_utils`` only
    closes sessions it created itself.

    Args:
        verify_ssl: Whether to validate the server's TLS certificate.

    Returns:
        aiohttp.ClientSession: Session with the retry middleware installed.
    """
    return aiohttp.ClientSession(
        connector=aiohttp.TCPConnector(ssl=verify_ssl),
        middlewares=(retry_middleware,),
    )
