"""Shared fixtures: an in-memory MCP server whose tools talk to a fake Zabbix API.

The fake goes through zabbix_utils' real ``APIObject``, so ``api.host.get(...)``
and ``api.host.delete(*ids)`` turn into the same JSON-RPC method name and params
the library would send. Nothing leaves the process.
"""

from collections import defaultdict
from collections.abc import Callable
from typing import Any
from typing import cast

import pytest
from fastmcp import Client
from fastmcp import FastMCP
from zabbix_utils.aioapi import APIObject
from zabbix_utils.types import APIVersion

from zabbix_mcp.models import ZabbixConfig
from zabbix_mcp.tools import register_tools
from zabbix_mcp.zabbix_client import ZabbixClient

TEST_CONFIG = ZabbixConfig(
    zabbix_url="https://zabbix.invalid/api_jsonrpc.php", token="test-token"
)


class FakeZabbixAPI:
    """Records every JSON-RPC call and answers from per-method handlers.

    A handler is a value (returned as the result), an exception (raised), or a
    callable taking the request params. ``queue`` answers successive calls of
    one method in order, for the count-then-rows queries of paging.
    """

    def __init__(self, version: str = "7.0.0") -> None:
        self.version = APIVersion(version)
        self.calls: list[tuple[str, Any]] = []
        self._handlers: dict[str, Any] = {}
        self._queues: dict[str, list[Any]] = defaultdict(list)

    def __getattr__(self, name: str) -> APIObject:
        return APIObject(name, cast(Any, self))

    def on(self, method: str, handler: Any) -> None:
        self._handlers[method] = handler

    def queue(self, method: str, *results: Any) -> None:
        self._queues[method].extend(results)

    def params(self, method: str) -> list[Any]:
        """Params of every call to ``method``, in order."""
        return [params for name, params in self.calls if name == method]

    async def send_async_request(
        self, method: str, params: Any = None, need_auth: bool = True
    ) -> dict:
        del need_auth
        self.calls.append((method, params))
        if self._queues[method]:
            handler = self._queues[method].pop(0)
        elif method in self._handlers:
            handler = self._handlers[method]
        else:
            raise AssertionError(f"unexpected Zabbix call {method} {params!r}")
        if isinstance(handler, BaseException):
            raise handler
        if callable(handler):
            handler = handler(params)
        return {"jsonrpc": "2.0", "result": handler, "id": "1"}


@pytest.fixture(scope="session")
def mcp_server() -> FastMCP:
    """Every tool, registered once; ZabbixClient is patched per test."""
    server = FastMCP("zabbix-test")
    register_tools(server, TEST_CONFIG)
    return server


@pytest.fixture
def zabbix(monkeypatch) -> FakeZabbixAPI:
    """The fake API every tool gets from ``async with ZabbixClient(config)``."""
    fake = FakeZabbixAPI()

    async def enter(_self: ZabbixClient) -> FakeZabbixAPI:
        return fake

    monkeypatch.setattr(ZabbixClient, "__aenter__", enter)
    return fake


@pytest.fixture
def call_tool(mcp_server, zabbix) -> Callable[..., Any]:
    """Call a tool over an in-memory MCP session and return its structured result.

    Failures raise fastmcp's ToolError, as a client would see them.
    """
    del zabbix  # requested so the tool never reaches a real ZabbixClient

    async def call(name: str, arguments: dict[str, Any] | None = None) -> Any:
        async with Client(mcp_server) as client:
            result = await client.call_tool(name, arguments or {})
        return result.structured_content

    return call
