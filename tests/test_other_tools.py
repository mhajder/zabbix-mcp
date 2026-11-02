"""The smaller tool modules: actions, media types, graphs, discovery, SLA,
services, scripts and the API version."""

import pytest
from fastmcp.exceptions import ToolError

pytestmark = pytest.mark.asyncio

# tool, JSON-RPC object, result key, id field, extra arguments -> extra filters
GET_TOOLS = [
    (
        "action_get",
        "action",
        "actions",
        "actionid",
        {"actionids": ["1"], "groupids": ["4"], "hostids": ["10"]},
        {"actionids": ["1"], "groupids": ["4"], "hostids": ["10"]},
    ),
    (
        "mediatype_get",
        "mediatype",
        "mediatypes",
        "mediatypeid",
        {"mediatypeids": ["1"]},
        {"mediatypeids": ["1"]},
    ),
    (
        "graph_get",
        "graph",
        "graphs",
        "graphid",
        {"graphids": ["1"], "hostids": ["10"], "templateids": ["100"]},
        {"graphids": ["1"], "hostids": ["10"], "templateids": ["100"]},
    ),
    (
        "discoveryrule_get",
        "discoveryrule",
        "discoveryrules",
        "itemid",
        {"itemids": ["1"], "hostids": ["10"], "templateids": ["100"]},
        {"itemids": ["1"], "hostids": ["10"], "templateids": ["100"]},
    ),
    (
        "drule_get",
        "drule",
        "drules",
        "druleid",
        {"druleids": ["1"]},
        {"druleids": ["1"]},
    ),
    (
        "sla_get",
        "sla",
        "slas",
        "slaid",
        {"slaids": ["1"], "serviceids": ["2"]},
        {"slaids": ["1"], "serviceids": ["2"]},
    ),
    (
        "service_get",
        "service",
        "services",
        "serviceid",
        {"serviceids": ["1"], "parentids": ["2"]},
        {"serviceids": ["1"], "parentids": ["2"]},
    ),
    (
        "script_get",
        "script",
        "scripts",
        "scriptid",
        {"scriptids": ["1"], "hostids": ["10"], "groupids": ["4"]},
        {"scriptids": ["1"], "hostids": ["10"], "groupids": ["4"]},
    ),
]


@pytest.mark.parametrize(
    ("tool", "obj", "key", "id_field", "arguments", "filters"), GET_TOOLS
)
async def test_get_tools_page_with_filters(
    call_tool, zabbix, tool, obj, key, id_field, arguments, filters
):
    rows = [{id_field: "2"}, {id_field: "3"}]
    zabbix.queue(f"{obj}.get", "5", [{id_field: "1"}, *rows], list(reversed(rows)))

    result = await call_tool(
        tool,
        {
            **arguments,
            "search": {"name": "x"},
            "filter_params": {"status": 0},
            "limit": 2,
            "offset": 1,
        },
    )

    assert result == {
        key: rows,
        "count": 2,
        "total": 5,
        "limit": 2,
        "offset": 1,
        "has_more": True,
    }
    filters = {**filters, "search": {"name": "x"}, "filter": {"status": 0}}
    count, cursor, final = zabbix.params(f"{obj}.get")
    assert count == {**filters, "countOutput": True}
    assert cursor == {
        **filters,
        "sortfield": id_field,
        "sortorder": "ASC",
        "output": [id_field],
        "limit": 3,
    }
    assert final == {**filters, f"{id_field}s": ["2", "3"], "output": "extend"}


@pytest.mark.parametrize(
    ("tool", "obj", "key", "id_field", "arguments", "filters"), GET_TOOLS
)
async def test_get_tools_count_output(
    call_tool, zabbix, tool, obj, key, id_field, arguments, filters
):
    del key, id_field, arguments, filters
    zabbix.on(f"{obj}.get", "9")

    assert await call_tool(tool, {"count_output": True}) == {"total": 9}
    assert zabbix.calls == [(f"{obj}.get", {"countOutput": True})]


@pytest.mark.parametrize(
    ("tool", "action"),
    [
        ("action_get", "Error retrieving actions"),
        ("mediatype_get", "Error retrieving media types"),
        ("graph_get", "Error retrieving graphs"),
        ("discoveryrule_get", "Error retrieving discovery rules"),
        ("drule_get", "Error retrieving network discovery rules"),
        ("sla_get", "Error retrieving SLAs"),
        ("service_get", "Error retrieving services"),
        ("script_get", "Error retrieving scripts"),
    ],
)
async def test_get_tool_failures_become_tool_errors(call_tool, zabbix, tool, action):
    obj = tool.removesuffix("_get")
    zabbix.on(f"{obj}.get", TimeoutError())

    with pytest.raises(ToolError, match=f"^{action}: TimeoutError$"):
        await call_tool(tool)


async def test_graph_get_selects(call_tool, zabbix):
    zabbix.queue("graph.get", "1", [{"graphid": "1"}])

    await call_tool(
        "graph_get",
        {"select_items": True, "select_hosts": True, "select_templates": True},
    )

    assert zabbix.params("graph.get")[1] == {
        "sortfield": "graphid",
        "sortorder": "ASC",
        "output": "extend",
        "selectGraphItems": "extend",
        "selectHosts": "extend",
        "selectTemplates": "extend",
        "limit": 100,
    }


async def test_script_execute(call_tool, zabbix):
    zabbix.on("script.execute", {"response": "success", "value": "pong"})

    result = await call_tool("script_execute", {"scriptid": "1", "hostid": "10"})

    assert result == {
        "result": {"response": "success", "value": "pong"},
        "success": True,
    }
    assert zabbix.calls == [("script.execute", {"scriptid": "1", "hostid": "10"})]


async def test_script_execute_failure(call_tool, zabbix):
    zabbix.on("script.execute", TimeoutError())

    with pytest.raises(ToolError, match=r"^Error executing script: TimeoutError$"):
        await call_tool("script_execute", {"scriptid": "1", "hostid": "10"})


async def test_api_version_reports_the_connected_version(call_tool, zabbix):
    assert await call_tool("api_version") == {"version": "7.0.0"}
    # Read from the cached version; no request is sent.
    assert zabbix.calls == []


async def test_api_version_failure(call_tool, monkeypatch):
    from zabbix_mcp.zabbix_client import ZabbixClient

    async def unreachable(_self):
        raise ConnectionRefusedError("Connection refused")

    monkeypatch.setattr(ZabbixClient, "__aenter__", unreachable)

    with pytest.raises(
        ToolError,
        match=r"^Error getting API version: ConnectionRefusedError: Connection refused$",
    ):
        await call_tool("api_version")
