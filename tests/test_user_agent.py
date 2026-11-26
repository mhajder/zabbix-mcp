"""Tests for outbound User-Agent configuration and aiohttp header injection."""

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from zabbix_mcp.models import ZabbixConfig
from zabbix_mcp.retry import build_session
from zabbix_mcp.zabbix_client import DEFAULT_USER_AGENT
from zabbix_mcp.zabbix_client import ZabbixClient
from zabbix_mcp.zabbix_client import get_zabbix_config_from_env


def test_env_user_agent_defaults_and_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ZABBIX_URL", "https://zabbix.invalid/api_jsonrpc.php")
    monkeypatch.setenv("ZABBIX_TOKEN", "t")
    monkeypatch.delenv("ZABBIX_USER_AGENT", raising=False)

    assert get_zabbix_config_from_env().user_agent is None

    monkeypatch.setenv("ZABBIX_USER_AGENT", "  custom-zabbix/1.0  ")
    assert get_zabbix_config_from_env().user_agent == "custom-zabbix/1.0"

    monkeypatch.setenv("ZABBIX_USER_AGENT", "   ")
    assert get_zabbix_config_from_env().user_agent is None


@pytest.mark.asyncio
async def test_build_session_sets_user_agent() -> None:
    seen: list[str | None] = []

    async def handle(request: web.Request) -> web.Response:
        seen.append(request.headers.get("User-Agent"))
        return web.json_response({"jsonrpc": "2.0", "result": "7.0.0", "id": 1})

    app = web.Application()
    app.router.add_post("/api_jsonrpc.php", handle)
    async with TestServer(app) as server:
        url = str(server.make_url("/api_jsonrpc.php"))
        async with (
            build_session(verify_ssl=True, user_agent="custom-zabbix/1.0") as sess,
            sess.post(
                url, json={"jsonrpc": "2.0", "method": "apiinfo.version", "id": 1}
            ),
        ):
            pass

    assert seen == ["custom-zabbix/1.0"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("configured", "expected"),
    [
        (None, DEFAULT_USER_AGENT),
        ("custom-zabbix/1.0", "custom-zabbix/1.0"),
    ],
)
async def test_zabbix_client_sends_user_agent(
    configured: str | None, expected: str
) -> None:
    seen: list[str | None] = []

    async def handle(request: web.Request) -> web.Response:
        seen.append(request.headers.get("User-Agent"))
        payload = await request.json()
        if payload.get("method") == "apiinfo.version":
            return web.json_response({"jsonrpc": "2.0", "result": "7.0.0", "id": 1})
        return web.json_response({"jsonrpc": "2.0", "result": [], "id": 1})

    app = web.Application()
    app.router.add_post("/api_jsonrpc.php", handle)
    ZabbixClient._instance = None
    ZabbixClient._initialized = False
    try:
        async with TestServer(app) as server:
            config = ZabbixConfig(
                zabbix_url=str(server.make_url("/api_jsonrpc.php")),
                token="t",
                user_agent=configured,
            )
            client = ZabbixClient(config)
            async with client as zapi:
                await zapi.host.get()
            await client.close()
    finally:
        ZabbixClient._instance = None
        ZabbixClient._initialized = False

    assert seen
    assert all(ua == expected for ua in seen)
