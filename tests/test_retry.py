"""Transient HTTP failures are retried, but never in a way that repeats a write."""

import asyncio
import json
from types import SimpleNamespace
from typing import Any

import aiohttp
import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from zabbix_mcp import retry
from zabbix_mcp.retry import build_session
from zabbix_mcp.retry import retry_middleware

pytestmark = pytest.mark.asyncio


@pytest.fixture
def sleeps(monkeypatch):
    """Record backoff delays instead of waiting them out."""
    delays: list[float] = []
    real_sleep = asyncio.sleep

    async def fake_sleep(delay):
        delays.append(delay)
        await real_sleep(0)

    monkeypatch.setattr(retry.asyncio, "sleep", fake_sleep)
    return delays


def raw_request(body: bytes) -> Any:
    """Stand-in for aiohttp's ClientRequest; only .body is read."""
    return SimpleNamespace(body=body)


def jsonrpc(method: str, **extra) -> Any:
    body = json.dumps({"jsonrpc": "2.0", "method": method, "params": {}, **extra})
    return raw_request(body.encode())


class FakeResponse:
    def __init__(self, status: int, retry_after: str | None = None) -> None:
        self.status = status
        self.headers = {} if retry_after is None else {"Retry-After": retry_after}
        self.released = False

    def release(self) -> None:
        self.released = True


def handler_for(*statuses: int, retry_after: str | None = None):
    responses = [FakeResponse(status, retry_after) for status in statuses]
    sent = []

    async def handler(request):
        sent.append(request)
        return responses[len(sent) - 1]

    return handler, sent, responses


@pytest.mark.parametrize(
    "method",
    ["host.get", "apiinfo.version", "configuration.export", "user.login"],
)
async def test_reads_are_retried_on_5xx(sleeps, method):
    handler, sent, responses = handler_for(502, 503, 200)

    response = await retry_middleware(jsonrpc(method), handler)

    assert response is responses[2]
    assert len(sent) == 3
    assert sleeps == [0.5, 1.0]
    # Retried responses are released so their connections go back to the pool.
    assert responses[0].released
    assert responses[1].released


@pytest.mark.parametrize("method", ["host.create", "script.execute", "user.logout"])
async def test_writes_are_not_retried_on_5xx(sleeps, method):
    """A proxy timeout does not prove the write was not carried out."""
    handler, sent, responses = handler_for(504, 200)

    response = await retry_middleware(jsonrpc(method), handler)

    assert response is responses[0]
    assert len(sent) == 1
    assert sleeps == []


@pytest.mark.usefixtures("sleeps")
async def test_writes_are_retried_on_429():
    handler, sent, responses = handler_for(429, 200)

    assert await retry_middleware(jsonrpc("host.delete"), handler) is responses[1]
    assert len(sent) == 2


async def test_success_and_client_errors_are_returned_at_once(sleeps):
    for status in (200, 400, 401, 404):
        handler, sent, responses = handler_for(status)
        assert await retry_middleware(jsonrpc("host.get"), handler) is responses[0]
        assert len(sent) == 1
    assert sleeps == []


@pytest.mark.usefixtures("sleeps")
async def test_last_attempt_is_returned_when_retries_run_out():
    handler, sent, responses = handler_for(503, 503, 503, 200)

    response = await retry_middleware(jsonrpc("host.get"), handler)

    assert response is responses[2]
    assert not responses[2].released
    assert len(sent) == retry.MAX_ATTEMPTS


@pytest.mark.parametrize(("header", "delay"), [("3", 3.0), (" 1.5 ", 1.5), ("0", 0.0)])
async def test_retry_after_is_honoured(sleeps, header, delay):
    handler, _, _ = handler_for(429, 200, retry_after=header)

    await retry_middleware(jsonrpc("host.get"), handler)

    assert sleeps == [delay]


@pytest.mark.parametrize(
    "header",
    ["", "soon", "Wed, 21 Oct 2026 07:28:00 GMT", "nan", "inf", "-1"],
)
async def test_unusable_retry_after_falls_back_to_backoff(sleeps, header):
    handler, _, _ = handler_for(503, 200, retry_after=header)

    await retry_middleware(jsonrpc("host.get"), handler)

    assert sleeps == [0.5]


async def test_retry_after_beyond_the_cap_is_not_waited_for(sleeps):
    """Retrying sooner than asked would only be refused again."""
    handler, sent, responses = handler_for(429, 200, retry_after="120")

    assert await retry_middleware(jsonrpc("host.get"), handler) is responses[0]
    assert len(sent) == 1
    assert sleeps == []


@pytest.mark.usefixtures("sleeps")
async def test_method_is_found_in_any_key_order():
    body = json.dumps({"id": "1", "method": "item.get", "jsonrpc": "2.0"})
    handler, sent, _ = handler_for(503, 200)

    await retry_middleware(raw_request(body.encode()), handler)

    assert len(sent) == 2


@pytest.mark.parametrize(
    "body",
    [
        b"",
        b"not json",
        b"\xff\xfe",
        json.dumps({"jsonrpc": "2.0", "method": 5}).encode(),
        json.dumps([{"method": "host.get"}]).encode(),
    ],
)
@pytest.mark.usefixtures("sleeps")
async def test_unreadable_body_counts_as_a_write(body):
    handler, sent, _ = handler_for(503, 200)

    await retry_middleware(raw_request(body), handler)

    assert len(sent) == 1


async def test_session_retries_real_zabbix_requests(sleeps):
    """End to end over loopback: the body zabbix_utils builds is readable."""
    hits: list[str] = []

    async def api(request: web.Request) -> web.StreamResponse:
        body = await request.json()
        hits.append(body["method"])
        if len(hits) == 1:
            return web.Response(status=503)
        return web.json_response({"jsonrpc": "2.0", "result": [], "id": body["id"]})

    app = web.Application()
    app.router.add_post("/api_jsonrpc.php", api)
    async with TestServer(app, host="127.0.0.1") as server:
        session = build_session(verify_ssl=True)
        async with session:
            response = await session.post(
                server.make_url("/api_jsonrpc.php"),
                json={"jsonrpc": "2.0", "method": "host.get", "params": {}, "id": "1"},
            )
            assert response.status == 200

    assert hits == ["host.get", "host.get"]
    # aiohttp itself yields with sleep(0); only the backoff waits.
    assert [delay for delay in sleeps if delay] == [0.5]


async def test_build_session_installs_the_retry_middleware():
    session = build_session(verify_ssl=False)
    try:
        assert isinstance(session, aiohttp.ClientSession)
        assert session._middlewares == (retry_middleware,)
        assert isinstance(session.connector, aiohttp.TCPConnector)
        assert session.connector._ssl is False
    finally:
        await session.close()
