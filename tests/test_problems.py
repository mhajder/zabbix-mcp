from typing import Any

import pytest

from zabbix_mcp.tools.problems import attach_problem_hosts


class _FakeTrigger:
    def __init__(self, triggers: list[dict[str, Any]]) -> None:
        self.triggers = triggers
        self.calls: list[dict[str, Any]] = []

    async def get(self, **params: Any) -> list[dict[str, Any]]:
        self.calls.append(params)
        return self.triggers


class _FakeApi:
    def __init__(self, triggers: list[dict[str, Any]]) -> None:
        self.trigger = _FakeTrigger(triggers)


WEB01 = {"hostid": "10", "host": "web01", "name": "Web 01"}
DB01 = {"hostid": "20", "host": "db01", "name": "DB 01"}

pytestmark = pytest.mark.asyncio


async def test_attaches_hosts_by_trigger_with_one_lookup():
    api = _FakeApi(
        [
            {"triggerid": "100", "hosts": [WEB01]},
            {"triggerid": "200", "hosts": [DB01]},
        ]
    )
    problems = [
        {"eventid": "1", "objectid": "100"},
        {"eventid": "2", "objectid": "200"},
        {"eventid": "3", "objectid": "100"},
    ]

    await attach_problem_hosts(api, problems)

    assert [p["hosts"] for p in problems] == [[WEB01], [DB01], [WEB01]]
    assert len(api.trigger.calls) == 1
    call = api.trigger.calls[0]
    assert call["triggerids"] == ["100", "200"]
    assert call["selectHosts"] == ["hostid", "host", "name"]


async def test_unknown_trigger_gets_empty_hosts():
    """A trigger deleted or hidden by permissions must not drop the problem."""
    api = _FakeApi([])
    problems = [{"eventid": "1", "objectid": "999"}]

    await attach_problem_hosts(api, problems)

    assert problems == [{"eventid": "1", "objectid": "999", "hosts": []}]


async def test_empty_page_skips_lookup():
    api = _FakeApi([])

    await attach_problem_hosts(api, [])

    assert api.trigger.calls == []
