from typing import Any

import pytest
from fastmcp.exceptions import ToolError
from zabbix_utils.exceptions import APIRequestError

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


async def test_problem_get_builds_filters(call_tool, zabbix):
    zabbix.queue("problem.get", "1", [{"eventid": "5", "objectid": "100"}])

    result = await call_tool(
        "problem_get",
        {
            "eventids": ["5"],
            "groupids": ["4"],
            "hostids": ["10"],
            "objectids": ["100"],
            "time_from": 1700000000,
            "time_till": 1700003600,
            "recent": True,
            "severities": [4, "5"],
            "search": {"opdata": "x"},
            "name_contains": "CPU",
            "acknowledged": False,
            "suppressed": True,
        },
    )

    assert result == {
        "problems": [{"eventid": "5", "objectid": "100"}],
        "count": 1,
        "total": 1,
        "limit": 100,
        "offset": 0,
        "has_more": False,
    }
    assert zabbix.params("problem.get")[1] == {
        "eventids": ["5"],
        "groupids": ["4"],
        "hostids": ["10"],
        "objectids": ["100"],
        "time_from": 1700000000,
        "time_till": 1700003600,
        "recent": True,
        # Severities arrive as ints or strings; Zabbix gets ints.
        "severities": [4, 5],
        "search": {"opdata": "x", "name": "CPU"},
        "acknowledged": False,
        "suppressed": True,
        "sortfield": "eventid",
        "sortorder": "ASC",
        "output": "extend",
        "limit": 100,
    }


async def test_problem_get_count_output(call_tool, zabbix):
    zabbix.on("problem.get", "17")

    assert await call_tool("problem_get", {"count_output": True}) == {"total": 17}
    assert zabbix.calls == [("problem.get", {"countOutput": True})]


async def test_problem_get_select_hosts_borrows_objectid(call_tool, zabbix):
    """Hosts are found through the trigger id, which 'output' may leave out."""
    zabbix.queue("problem.get", "1", [{"eventid": "5", "name": "x", "objectid": "100"}])
    zabbix.on("trigger.get", [{"triggerid": "100", "hosts": [WEB01]}])

    result = await call_tool(
        "problem_get", {"output": ["eventid", "name"], "select_hosts": True}
    )

    assert result["problems"] == [{"eventid": "5", "name": "x", "hosts": [WEB01]}]
    assert zabbix.params("problem.get")[1]["output"] == ["eventid", "name", "objectid"]


async def test_problem_get_select_hosts_keeps_requested_objectid(call_tool, zabbix):
    zabbix.queue("problem.get", "1", [{"eventid": "5", "objectid": "100"}])
    zabbix.on("trigger.get", [{"triggerid": "100", "hosts": [DB01]}])

    result = await call_tool("problem_get", {"select_hosts": True})

    assert result["problems"] == [{"eventid": "5", "objectid": "100", "hosts": [DB01]}]


async def test_event_get_builds_filters_and_selects(call_tool, zabbix):
    zabbix.queue("event.get", "2", [{"eventid": "5"}])

    result = await call_tool(
        "event_get",
        {
            "eventids": ["5"],
            "groupids": ["4"],
            "hostids": ["10"],
            "objectids": ["100"],
            "time_from": 1,
            "time_till": 2,
            "acknowledged": True,
            "suppressed": False,
            "select_hosts": True,
            "select_related_object": True,
            "select_tags": True,
            "sortorder": "DESC",
            "limit": 1,
        },
    )

    assert result["events"] == [{"eventid": "5"}]
    assert result["has_more"] is True
    assert zabbix.params("event.get")[1] == {
        "eventids": ["5"],
        "groupids": ["4"],
        "hostids": ["10"],
        "objectids": ["100"],
        "time_from": 1,
        "time_till": 2,
        "acknowledged": True,
        "suppressed": False,
        "sortfield": "eventid",
        "sortorder": "DESC",
        "output": "extend",
        "selectHosts": "extend",
        "selectRelatedObject": "extend",
        "selectTags": "extend",
        "limit": 1,
    }


async def test_event_get_count_output(call_tool, zabbix):
    zabbix.on("event.get", "4")

    assert await call_tool("event_get", {"count_output": True}) == {"total": 4}


async def test_event_acknowledge_defaults_to_acknowledge(call_tool, zabbix):
    zabbix.on("event.acknowledge", {"eventids": ["5"]})

    result = await call_tool("event_acknowledge", {"eventids": ["5"]})

    assert result == {"eventids": ["5"], "success": True}
    assert zabbix.params("event.acknowledge") == [{"eventids": ["5"], "action": 2}]


async def test_event_acknowledge_message_sets_the_add_message_flag(call_tool, zabbix):
    """Zabbix stores a message sent without flag 4 as empty, silently."""
    zabbix.on("event.acknowledge", {"eventids": ["5"]})

    await call_tool(
        "event_acknowledge", {"eventids": ["5"], "action": 1, "message": "fixed"}
    )
    await call_tool(
        "event_acknowledge", {"eventids": ["5"], "action": 6, "message": "again"}
    )

    assert zabbix.params("event.acknowledge") == [
        {"eventids": ["5"], "action": 5, "message": "fixed"},
        {"eventids": ["5"], "action": 6, "message": "again"},
    ]


@pytest.mark.parametrize(
    ("tool", "arguments", "method", "action"),
    [
        ("problem_get", {}, "problem.get", "Error retrieving problems"),
        ("event_get", {}, "event.get", "Error retrieving events"),
        (
            "event_acknowledge",
            {"eventids": ["1"]},
            "event.acknowledge",
            "Error acknowledging events",
        ),
    ],
)
async def test_zabbix_failures_become_tool_errors(
    call_tool, zabbix, tool, arguments, method, action
):
    zabbix.on(method, APIRequestError("No permissions to referred object."))

    with pytest.raises(ToolError, match=f"^{action}: APIRequestError: No permissions"):
        await call_tool(tool, arguments)
