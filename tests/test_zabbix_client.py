"""The shared Zabbix connection, against a fake JSON-RPC endpoint on loopback.

The endpoint answers like Zabbix 7.0, so these tests exercise the real
zabbix_utils client: the version probe, login, the auth header, session expiry
and logout.
"""

import asyncio
import os
from collections.abc import AsyncIterator
from collections.abc import Callable
from typing import Any

import pytest
import pytest_asyncio
from aiohttp import web
from aiohttp.test_utils import TestServer
from zabbix_utils.aioapi import AsyncZabbixAPI
from zabbix_utils.exceptions import APIRequestError
from zabbix_utils.exceptions import ProcessingError
from zabbix_utils.types import APIVersion

from zabbix_mcp import zabbix_client
from zabbix_mcp.models import ZabbixConfig
from zabbix_mcp.zabbix_client import ZabbixClient

pytestmark = pytest.mark.asyncio

SESSION_LOST = "Session terminated, re-login, please."


class FakeZabbix:
    """A JSON-RPC endpoint recording every request it gets."""

    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []
        self.version = "7.0.0"
        # method -> list of results/errors to hand out before the default
        self.scripted: dict[str, list[Any]] = {}
        self.logins = 0
        self.url = ""

    def methods(self) -> list[str]:
        return [r["method"] for r in self.requests]

    def script(self, method: str, *answers: Any) -> None:
        self.scripted.setdefault(method, []).extend(answers)

    async def handle(self, request: web.Request) -> web.StreamResponse:
        body = await request.json()
        method = body["method"]
        self.requests.append(
            {
                "method": method,
                "params": body["params"],
                "authorization": request.headers.get("Authorization"),
            }
        )
        answers = self.scripted.get(method)
        answer = answers.pop(0) if answers else self.default(method)
        if isinstance(answer, web.StreamResponse):
            return answer
        if isinstance(answer, dict) and "code" in answer:
            return web.json_response(
                {"jsonrpc": "2.0", "error": answer, "id": body["id"]}
            )
        return web.json_response({"jsonrpc": "2.0", "result": answer, "id": body["id"]})

    def default(self, method: str) -> Any:
        if method == "apiinfo.version":
            return self.version
        if method == "user.login":
            self.logins += 1
            return f"{self.logins:032d}"
        if method == "user.logout":
            return True
        return [{"hostid": "10"}]


def session_error(data: str = SESSION_LOST) -> dict[str, Any]:
    return {"code": -32602, "message": "Invalid params.", "data": data}


@pytest.fixture(autouse=True)
def fresh_client(monkeypatch):
    """Each test starts with no shared connection and no cached API version."""
    monkeypatch.setattr(ZabbixClient, "_instance", None)
    monkeypatch.setattr(AsyncZabbixAPI, zabbix_client._VERSION_CACHE_ATTR, None)
    # zabbix_utils reads credentials from the environment when given None.
    for name in ("ZABBIX_URL", "ZABBIX_TOKEN", "ZABBIX_USER", "ZABBIX_PASSWORD"):
        monkeypatch.delenv(name, raising=False)


@pytest_asyncio.fixture
async def zabbix() -> AsyncIterator[FakeZabbix]:
    fake = FakeZabbix()
    app = web.Application()
    app.router.add_post("/api_jsonrpc.php", fake.handle)
    async with TestServer(app, host="127.0.0.1") as server:
        fake.url = str(server.make_url("/api_jsonrpc.php"))
        yield fake


@pytest.fixture
def make_config(zabbix) -> Callable[..., ZabbixConfig]:
    def make(**overrides: Any) -> ZabbixConfig:
        settings: dict[str, Any] = {"zabbix_url": zabbix.url, "timeout": 5}
        if "token" not in overrides:
            settings.update(user="Admin", password="zabbix")
        return ZabbixConfig(**{**settings, **overrides})

    return make


async def test_user_password_login_is_shared_and_logged_out_on_close(
    zabbix, make_config
):
    client = ZabbixClient(make_config())

    async with ZabbixClient() as api:
        assert await api.host.get(output=["hostid"]) == [{"hostid": "10"}]
    async with ZabbixClient() as api:
        await api.host.get()
    await client.close()

    assert zabbix.methods() == [
        "apiinfo.version",
        "user.login",
        "host.get",
        "host.get",
        "user.logout",
    ]
    version, login, first, *_ = zabbix.requests
    # apiinfo.version is refused when it carries an Authorization header.
    assert version["authorization"] is None
    assert login["params"] == {"username": "Admin", "password": "zabbix"}
    assert first["params"] == {"output": ["hostid"]}
    assert first["authorization"] == f"Bearer {1:032d}"


async def test_token_auth_sends_the_token_without_logging_in(zabbix, make_config):
    client = ZabbixClient(make_config(token="api-token"))

    async with client as api:
        await api.host.get()
    await client.close()

    assert zabbix.methods() == ["apiinfo.version", "host.get"]
    assert zabbix.requests[1]["authorization"] == "Bearer api-token"


async def test_version_is_probed_once_per_process(zabbix, make_config):
    client = ZabbixClient(make_config())
    async with client:
        pass
    await client.close()
    async with client:
        pass

    assert zabbix.methods().count("apiinfo.version") == 1
    cached = getattr(AsyncZabbixAPI, zabbix_client._VERSION_CACHE_ATTR)
    assert str(cached) == "7.0.0"
    await client.close()


async def test_version_probe_error_is_raised(zabbix, make_config):
    zabbix.script("apiinfo.version", {"code": -32600, "message": "Invalid request."})
    client = ZabbixClient(make_config())

    with pytest.raises(RuntimeError, match="Could not read Zabbix API version"):
        async with client:
            pass
    assert zabbix.methods() == ["apiinfo.version"]


async def test_version_probe_http_error_is_raised(zabbix, make_config):
    zabbix.script("apiinfo.version", web.Response(status=502))
    client = ZabbixClient(make_config())

    with pytest.raises(Exception, match="502"):
        async with client:
            pass


async def test_library_without_a_version_cache_is_left_alone(
    monkeypatch, make_config, caplog
):
    """If zabbix_utils renames its cache, the seed must not invent one."""
    monkeypatch.delattr(AsyncZabbixAPI, zabbix_client._VERSION_CACHE_ATTR)
    caplog.set_level("DEBUG", logger="zabbix_mcp.zabbix_client")

    await ZabbixClient(make_config())._seed_api_version()

    assert "no longer caches the API version" in caplog.text
    assert not hasattr(AsyncZabbixAPI, zabbix_client._VERSION_CACHE_ATTR)


async def test_failed_login_closes_the_session(zabbix, make_config, monkeypatch):
    sessions = []
    real_build = zabbix_client.build_session

    def tracking_build(verify_ssl):
        session = real_build(verify_ssl)
        sessions.append(session)
        return session

    monkeypatch.setattr(zabbix_client, "build_session", tracking_build)
    zabbix.script(
        "user.login", {"code": -32500, "message": "Login failed.", "data": ""}
    )

    with pytest.raises(APIRequestError, match="Login failed"):
        async with ZabbixClient(make_config()):
            pass
    assert sessions
    assert sessions[0].closed
    # Nothing half-made is kept for the next call.
    assert ZabbixClient()._api is None


async def test_expired_session_logs_in_again_and_resends(zabbix, make_config):
    zabbix.script("host.get", session_error())
    client = ZabbixClient(make_config())

    async with client as api:
        assert await api.host.get() == [{"hostid": "10"}]
    await client.close()

    assert zabbix.methods() == [
        "apiinfo.version",
        "user.login",
        "host.get",
        "user.login",
        "host.get",
        "user.logout",
    ]
    assert zabbix.requests[4]["authorization"] == f"Bearer {2:032d}"


@pytest.mark.parametrize(
    "data",
    [" Not authorised. ", "Not authorized.", "SESSION TERMINATED, RE-LOGIN, PLEASE."],
)
async def test_every_session_lost_message_is_recognised(zabbix, make_config, data):
    zabbix.script("host.get", session_error(data))

    async with ZabbixClient(make_config()) as api:
        await api.host.get()

    assert zabbix.logins == 2


@pytest.mark.parametrize(
    "error",
    [
        # Other errors echo caller input; a host named "re-login" is not a lost session.
        session_error('Host "re-login" not found.'),
        {"code": -32602, "message": "Invalid params.", "data": "Bad sortfield."},
    ],
)
async def test_other_errors_are_not_retried(zabbix, make_config, error):
    zabbix.script("host.get", error)

    with pytest.raises(APIRequestError):
        async with ZabbixClient(make_config()) as api:
            await api.host.get()
    assert zabbix.logins == 1


async def test_token_session_errors_are_not_retried(zabbix, make_config):
    """A token does not expire like a login session; logging in cannot help."""
    zabbix.script("host.get", session_error())

    with pytest.raises(APIRequestError, match="Session terminated"):
        async with ZabbixClient(make_config(token="api-token")) as api:
            await api.host.get()
    assert "user.login" not in zabbix.methods()


async def test_logout_is_not_retried(zabbix, make_config):
    zabbix.script("user.logout", session_error())
    client = ZabbixClient(make_config())
    async with client:
        pass

    # close() swallows the logout failure but still closes the session.
    session = client._session
    await client.close()

    assert zabbix.methods().count("user.login") == 1
    assert session is not None
    assert session.closed


async def test_concurrent_calls_on_an_expired_session_log_in_once(zabbix, make_config):
    client = ZabbixClient(make_config())
    async with client as api:
        zabbix.script("host.get", session_error(), session_error())
        results = await asyncio.gather(api.host.get(), api.host.get())

    assert results == [[{"hostid": "10"}], [{"hostid": "10"}]]
    assert zabbix.logins == 2
    await client.close()


async def test_failed_relogin_is_not_repeated_during_the_cooldown(
    zabbix, make_config, monkeypatch, caplog
):
    """Zabbix blocks an account after a few failed logins in a row."""
    clock = [1000.0]
    monkeypatch.setattr(zabbix_client.time, "monotonic", lambda: clock[0])
    client = ZabbixClient(make_config())
    async with client as api:
        zabbix.script("host.get", session_error(), session_error())
        zabbix.script(
            "user.login",
            {
                "code": -32500,
                "message": "Application error.",
                "data": "Login name or password is incorrect.",
            },
        )

        with pytest.raises(APIRequestError, match="incorrect"):
            await api.host.get()
        assert "not retrying for 300s" in caplog.text

        clock[0] += 10
        with pytest.raises(APIRequestError, match="Session terminated"):
            await api.host.get()
        assert zabbix.methods().count("user.login") == 2

        # After the cooldown it tries again, and a success clears the failure.
        clock[0] += zabbix_client.RELOGIN_COOLDOWN
        zabbix.script("host.get", session_error())
        assert await api.host.get() == [{"hostid": "10"}]
        assert api._login_failed_at is None
    assert zabbix.methods().count("user.login") == 3


async def test_whitespace_credentials_in_the_environment_are_dropped(
    make_config, monkeypatch
):
    """login() falls back to the raw variables when the config says None."""
    monkeypatch.setenv("ZABBIX_USER", "  ")
    monkeypatch.setenv("ZABBIX_PASSWORD", "")
    monkeypatch.setenv("ZABBIX_TOKEN", "env-token")

    async with ZabbixClient(make_config(token="api-token")) as api:
        await api.host.get()

    assert "ZABBIX_USER" not in os.environ
    assert "ZABBIX_PASSWORD" not in os.environ
    assert os.environ["ZABBIX_TOKEN"] == "env-token"  # noqa: S105


async def test_a_new_event_loop_gets_a_new_connection(make_config):
    """A session belongs to the loop that made it (a restarted server, a test)."""
    client = ZabbixClient(make_config(token="api-token"))
    async with client as first:
        pass

    client._loop = None  # as if made on a loop that has since closed
    async with client as second:
        pass

    assert second is not first
    await client.close()
    await first.client_session.close()


async def test_singleton_needs_a_config_first():
    with pytest.raises(ValueError, match="Config must be provided"):
        ZabbixClient()


async def test_singleton_keeps_its_first_config(make_config):
    first = ZabbixClient(make_config(token="a"))
    second = ZabbixClient(make_config(token="b"))

    assert second is first
    assert second.config.token == "a"  # noqa: S105


async def test_close_without_a_connection_does_nothing(make_config):
    client = ZabbixClient(make_config())

    await client.close()

    assert client._api is None


async def test_context_exit_keeps_the_connection(make_config):
    client = ZabbixClient(make_config(token="t"))
    async with client as api:
        pass

    assert client._api is api
    assert await client.__aexit__(None, None, None) is False
    await client.close()


async def test_not_logged_in_error_is_raised_by_the_library(zabbix, monkeypatch):
    """Guards the assumption that need_auth calls fail before login."""
    # Seeded, or the constructor would block the loop on a synchronous probe.
    monkeypatch.setattr(
        AsyncZabbixAPI, zabbix_client._VERSION_CACHE_ATTR, APIVersion("7.0.0")
    )
    api = zabbix_client._ReloggingZabbixAPI(
        url=zabbix.url, skip_version_check=True, relogin=True, timeout=5
    )
    try:
        with pytest.raises(ProcessingError, match="not logged in"):
            await api.send_async_request("host.get", {})
    finally:
        await api.client_session.close()
