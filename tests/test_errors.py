"""Upstream failures reach the client as tool errors that say what went wrong."""

import aiohttp
import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError
from multidict import CIMultiDict
from multidict import CIMultiDictProxy
from yarl import URL
from zabbix_utils.exceptions import APIRequestError
from zabbix_utils.exceptions import ProcessingError

from zabbix_mcp.tools.errors import describe


def api_error(code=-32602, message="Invalid params.", data="No permissions."):
    return APIRequestError(
        {"code": code, "message": message, "data": data, "body": {"id": "1"}}
    )


ZABBIX_URL = URL("https://zabbix.invalid/api_jsonrpc.php")


def http_error(status, message="Bad Gateway"):
    request = aiohttp.RequestInfo(
        ZABBIX_URL, "POST", CIMultiDictProxy(CIMultiDict()), ZABBIX_URL
    )
    return aiohttp.ClientResponseError(
        request_info=request,
        history=(),
        status=status,
        message=message,
    )


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (api_error(), "Zabbix API error -32602: Invalid params. No permissions."),
        (api_error(data=""), "Zabbix API error -32602: Invalid params."),
        (http_error(502), "HTTP 502 from the Zabbix server: Bad Gateway"),
        # aiohttp's .code aliases .status: a 500 is not a JSON-RPC code.
        (http_error(500, "Internal Server Error"), "HTTP 500 from the Zabbix server"),
        # str(asyncio.TimeoutError()) is "", which used to leave the message blank.
        (TimeoutError(), "TimeoutError"),
        (aiohttp.ServerTimeoutError(), "ServerTimeoutError"),
        (ValueError("bad id"), "ValueError: bad id"),
        (
            ProcessingError("Unable to connect to", "https://zabbix.invalid"),
            "ProcessingError: Unable to connect to https://zabbix.invalid",
        ),
    ],
)
def test_describe(exc, expected):
    assert describe(exc).startswith(expected)


def test_http_error_without_a_message_falls_back_to_the_exception():
    assert describe(http_error(503, message="")) == (
        "HTTP 503 from the Zabbix server: 503, message='', "
        "url='https://zabbix.invalid/api_jsonrpc.php'"
    )


@pytest.mark.asyncio
async def test_failure_is_a_tool_error_and_a_session_log(mcp_server, zabbix):
    """A dict carrying 'error' would read as a successful, empty result."""
    zabbix.on("host.get", api_error(-32500, "Application error.", "DB down"))
    logs = []

    async def log_handler(message):
        logs.append((message.level, message.data["msg"]))

    async with Client(mcp_server, log_handler=log_handler) as client:
        with pytest.raises(ToolError) as excinfo:
            await client.call_tool("host_get", {})

    expected = (
        "Error retrieving hosts: Zabbix API error -32500: Application error. DB down"
    )
    assert str(excinfo.value) == expected
    assert ("error", expected) in logs
