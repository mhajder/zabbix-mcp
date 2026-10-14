"""
Retrying transport for the Zabbix API.

``zabbix_utils`` calls ``raise_for_status()`` on every response and offers no
retry, so a rate limit or a momentary 502 from a reverse proxy fails the whole
tool call. Retries live in the HTTP layer rather than in each tool: it is the
one place every request already passes through, and it keeps ``Retry-After``
next to the response that carries it.

Only responses that can plausibly succeed on a second attempt are retried - 429
and some 5xx. Zabbix reports its own application errors as HTTP 200 with a JSON-RPC
``error`` member, so a bad parameter is never retried.

A 5xx does not prove the request was not carried out: a reverse proxy times
out while Zabbix is still running ``script.execute`` or ``host.create``, and
Envoy-style proxies answer 503 after the upstream has already read the body.
5xx is therefore retried only for read methods; writes are retried only on
429, which means the request was turned away before it ran.
"""

import asyncio
import json
import logging
import math
import re

import aiohttp
from aiohttp import ClientHandlerType
from aiohttp import ClientRequest
from aiohttp import ClientResponse

logger = logging.getLogger(__name__)

# Statuses that mean the server turned the request away, so it is safe to
# resend any method.
REJECTED_STATUSES = frozenset({429})
# Statuses after which the request may or may not have been applied.
RETRY_STATUSES = REJECTED_STATUSES | {500, 502, 503, 504}

# The start of every body zabbix_utils sends: it builds the request dict with
# "jsonrpc" then "method" first, and aiohttp serializes keys in that order.
_METHOD_PREFIX = re.compile(r'\{"jsonrpc":\s*"2\.0",\s*"method":\s*"([^"\\]+)"')

# JSON-RPC methods that change nothing, so a duplicate is harmless.
_SAFE_METHODS = frozenset(
    {
        "apiinfo.version",
        "configuration.export",
        "user.login",
        "user.checkAuthentication",
    }
)

MAX_ATTEMPTS = 3
BASE_BACKOFF = 0.5
MAX_DELAY = 10.0


def _is_safe_to_replay(request: ClientRequest) -> bool:
    """Tell whether resending the request cannot apply a change twice.

    Args:
        request: The outgoing JSON-RPC request.

    Returns:
        bool: True for read methods; False for writes or an unreadable body.
    """
    try:
        text = request.body.decode()
        # Reading the method off the start avoids parsing the whole body, which
        # is megabytes for a configuration.import. Any other layout falls back
        # to a full parse rather than guessing.
        match = _METHOD_PREFIX.match(text)
        method = match.group(1) if match else json.loads(text).get("method", "")
    except Exception:
        return False
    return isinstance(method, str) and (
        method.endswith(".get") or method in _SAFE_METHODS
    )


def _retry_after_seconds(response: ClientResponse) -> float | None:
    """Read a Retry-After header, in seconds, if the server sent a usable one.

    Args:
        response: The response to inspect.

    Returns:
        float | None: Delay in seconds, or None if absent or unparsable. The
            value may exceed MAX_DELAY; the caller decides what to do then.
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
    # "nan" and "inf" parse as floats; nan would reach asyncio.sleep.
    if not math.isfinite(delay) or delay < 0:
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
    retryable = RETRY_STATUSES if _is_safe_to_replay(request) else REJECTED_STATUSES
    for attempt in range(1, MAX_ATTEMPTS + 1):
        response = await handler(request)
        if response.status not in retryable or attempt == MAX_ATTEMPTS:
            return response

        delay = _retry_after_seconds(response)
        if delay is None:
            delay = min(BASE_BACKOFF * 2 ** (attempt - 1), MAX_DELAY)
        elif delay > MAX_DELAY:
            # Retrying sooner than the server asked would only be refused again.
            return response
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
