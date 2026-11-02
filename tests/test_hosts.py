"""Host and host group tools: the JSON-RPC each call sends and what it returns."""

import pytest
from fastmcp.exceptions import ToolError
from zabbix_utils.types import APIVersion

pytestmark = pytest.mark.asyncio


async def test_host_get_builds_filters_search_and_selects(call_tool, zabbix):
    rows = [{"hostid": "10", "host": "web01"}]
    zabbix.queue("host.get", "1", rows)

    result = await call_tool(
        "host_get",
        {
            "hostids": ["10"],
            "groupids": ["4"],
            "templateids": ["100"],
            "proxyids": ["7"],
            "search": {"name": "Web"},
            "hostname_contains": "web",
            "filter_params": {"available": 1},
            "status": 0,
            "output": ["host"],
            "select_groups": True,
            "select_templates": True,
            "select_interfaces": True,
            "select_tags": True,
            "sortfield": "name",
            "sortorder": "DESC",
            "limit": 5,
        },
    )

    assert result == {
        "hosts": rows,
        "count": 1,
        "total": 1,
        "limit": 5,
        "offset": 0,
        "has_more": False,
    }
    filters = {
        "hostids": ["10"],
        "groupids": ["4"],
        "templateids": ["100"],
        "proxyids": ["7"],
        "search": {"name": "Web", "host": "web"},
        "filter": {"available": 1, "status": 0},
    }
    count, page = zabbix.params("host.get")
    assert count == {**filters, "countOutput": True}
    assert page == {
        **filters,
        "sortfield": "name",
        "sortorder": "DESC",
        "output": ["host"],
        "selectHostGroups": "extend",
        "selectParentTemplates": "extend",
        "selectInterfaces": "extend",
        "selectTags": "extend",
        "limit": 5,
    }


async def test_host_get_defaults_send_no_filters(call_tool, zabbix):
    zabbix.queue("host.get", "250", [{"hostid": str(i)} for i in range(100)])

    result = await call_tool("host_get")

    assert result["count"] == 100
    assert result["has_more"] is True
    assert zabbix.params("host.get")[0] == {"countOutput": True}


async def test_host_get_count_output_returns_only_the_total(call_tool, zabbix):
    zabbix.on("host.get", "42")

    assert await call_tool("host_get", {"groupids": [], "count_output": True}) == {
        "total": 42
    }
    # An empty list is passed on: Zabbix matches nothing, not everything.
    assert zabbix.calls == [("host.get", {"groupids": [], "countOutput": True})]


async def test_host_create_from_arguments(call_tool, zabbix):
    zabbix.on("host.create", {"hostids": ["10501"]})
    interfaces = [{"type": 1, "main": 1, "useip": 1, "ip": "192.0.2.1"}]

    result = await call_tool(
        "host_create",
        {
            "host": "web01",
            "groups": [{"groupid": "4"}],
            "interfaces": interfaces,
            "templates": [{"templateid": "10001"}],
            "name": "Web 01",
            "status": 1,
            "description": "front end",
        },
    )

    assert result == {"hostids": ["10501"], "success": True}
    assert zabbix.params("host.create") == [
        {
            "host": "web01",
            "groups": [{"groupid": "4"}],
            "status": 1,
            "interfaces": interfaces,
            "templates": [{"templateid": "10001"}],
            "name": "Web 01",
            "description": "front end",
        }
    ]


async def test_host_create_leaves_out_unset_optionals(call_tool, zabbix):
    zabbix.on("host.create", {"hostids": ["1"]})

    await call_tool("host_create", {"host": "db01", "groups": [{"groupid": "2"}]})

    assert zabbix.params("host.create") == [
        {"host": "db01", "groups": [{"groupid": "2"}], "status": 0}
    ]


async def test_host_create_raw_params_are_sent_as_given(call_tool, zabbix):
    zabbix.on("host.create", {})
    params = {"host": "x", "groups": [{"groupid": "1"}], "inventory_mode": 1}

    result = await call_tool("host_create", {"params": params, "host": "ignored"})

    assert result == {"hostids": [], "success": True}
    assert zabbix.params("host.create") == [params]


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ({"groups": [{"groupid": "4"}]}, "'host' is required"),
        ({"host": "", "groups": [{"groupid": "4"}]}, "'host' is required"),
        ({"host": "web01"}, "'groups' is required"),
        ({"host": "web01", "groups": []}, "'groups' is required"),
    ],
)
async def test_host_create_requires_host_and_groups(
    call_tool, zabbix, arguments, message
):
    with pytest.raises(ToolError, match=f"Error creating host: ValueError: {message}"):
        await call_tool("host_create", arguments)
    assert zabbix.calls == []


async def test_host_update_sends_only_given_fields(call_tool, zabbix):
    zabbix.on("host.update", {"hostids": ["10"]})

    result = await call_tool(
        "host_update",
        {
            "hostid": "10",
            "host": "web01",
            "name": "",
            "status": 1,
            "description": "d",
            "templates": [{"templateid": "1"}],
            "templates_clear": [{"templateid": "2"}],
        },
    )

    assert result == {"hostids": ["10"], "success": True}
    assert zabbix.params("host.update") == [
        {
            "hostid": "10",
            "host": "web01",
            "name": "",
            "status": 1,
            "description": "d",
            "templates": [{"templateid": "1"}],
            "templates_clear": [{"templateid": "2"}],
        }
    ]


@pytest.mark.parametrize("blank", ["", "   "])
async def test_host_update_ignores_blank_host_and_proxy(call_tool, zabbix, blank):
    """Clients filling unused fields with "" must not rename or re-home a host."""
    zabbix.on("host.update", {"hostids": ["10"]})

    await call_tool(
        "host_update", {"hostid": "10", "host": blank, "proxyid": blank, "status": 0}
    )

    assert zabbix.params("host.update") == [{"hostid": "10", "status": 0}]


@pytest.mark.parametrize(
    ("proxyid", "expected"),
    [
        ("7", {"monitored_by": 1, "proxyid": "7"}),
        (" 7 ", {"monitored_by": 1, "proxyid": "7"}),
        ("0", {"monitored_by": 0, "proxyid": "0"}),
    ],
)
async def test_host_update_proxy_on_zabbix_7(call_tool, zabbix, proxyid, expected):
    zabbix.on("host.update", {"hostids": ["10"]})

    await call_tool("host_update", {"hostid": "10", "proxyid": proxyid})

    assert zabbix.params("host.update") == [{"hostid": "10", **expected}]


async def test_host_update_proxy_before_zabbix_7(call_tool, zabbix):
    """6.x has proxy_hostid and rejects monitored_by."""
    zabbix.version = APIVersion("6.4.0")
    zabbix.on("host.update", {"hostids": ["10"]})

    await call_tool("host_update", {"hostid": "10", "proxyid": "7"})

    assert zabbix.params("host.update") == [{"hostid": "10", "proxy_hostid": "7"}]


async def test_host_delete_sends_the_ids_as_a_list(call_tool, zabbix):
    zabbix.on("host.delete", {"hostids": ["1", "2"]})

    result = await call_tool("host_delete", {"hostids": ["1", "2"]})

    assert result == {"hostids": ["1", "2"], "success": True}
    assert zabbix.params("host.delete") == [["1", "2"]]


async def test_host_delete_rejects_an_empty_list(call_tool, zabbix):
    with pytest.raises(ToolError, match="hostids"):
        await call_tool("host_delete", {"hostids": []})
    assert zabbix.calls == []


async def test_hostgroup_get_builds_filters(call_tool, zabbix):
    zabbix.queue("hostgroup.get", "3", [{"groupid": "4", "name": "Linux"}])

    result = await call_tool(
        "hostgroup_get",
        {
            "groupids": ["4"],
            "hostids": ["10"],
            "search": {"name": "Lin"},
            "group_name_contains": "Linux",
            "select_hosts": True,
        },
    )

    assert result["groups"] == [{"groupid": "4", "name": "Linux"}]
    assert result["has_more"] is True
    assert zabbix.params("hostgroup.get")[1] == {
        "groupids": ["4"],
        "hostids": ["10"],
        "search": {"name": "Linux"},
        "sortfield": "groupid",
        "sortorder": "ASC",
        "output": "extend",
        "selectHosts": "extend",
        "limit": 100,
    }


async def test_hostgroup_get_count_output(call_tool, zabbix):
    zabbix.on("hostgroup.get", "12")

    assert await call_tool("hostgroup_get", {"count_output": True}) == {"total": 12}


async def test_hostgroup_create_update_delete(call_tool, zabbix):
    zabbix.on("hostgroup.create", {"groupids": ["30"]})
    zabbix.on("hostgroup.update", {"groupids": ["30"]})
    zabbix.on("hostgroup.delete", {"groupids": ["30"]})

    assert await call_tool("hostgroup_create", {"name": "Web"}) == {
        "groupids": ["30"],
        "success": True,
    }
    await call_tool("hostgroup_update", {"groupid": "30", "name": "Web servers"})
    await call_tool("hostgroup_update", {"groupid": "30"})
    await call_tool("hostgroup_delete", {"groupids": ["30"]})

    assert zabbix.calls == [
        ("hostgroup.create", {"name": "Web"}),
        ("hostgroup.update", {"groupid": "30", "name": "Web servers"}),
        ("hostgroup.update", {"groupid": "30"}),
        ("hostgroup.delete", ["30"]),
    ]


@pytest.mark.parametrize(
    ("tool", "arguments", "method", "action"),
    [
        ("host_get", {}, "host.get", "Error retrieving hosts"),
        (
            "host_create",
            {"params": {"host": "x"}},
            "host.create",
            "Error creating host",
        ),
        ("host_update", {"hostid": "1"}, "host.update", "Error updating host"),
        ("host_delete", {"hostids": ["1"]}, "host.delete", "Error deleting hosts"),
        ("hostgroup_get", {}, "hostgroup.get", "Error retrieving host groups"),
        (
            "hostgroup_create",
            {"name": "x"},
            "hostgroup.create",
            "Error creating host group",
        ),
        (
            "hostgroup_update",
            {"groupid": "1"},
            "hostgroup.update",
            "Error updating host group",
        ),
        (
            "hostgroup_delete",
            {"groupids": ["1"]},
            "hostgroup.delete",
            "Error deleting host groups",
        ),
    ],
)
async def test_zabbix_failures_become_tool_errors(
    call_tool, zabbix, tool, arguments, method, action
):
    zabbix.on(method, ConnectionResetError("reset by peer"))

    with pytest.raises(ToolError, match=f"^{action}: ConnectionResetError: reset"):
        await call_tool(tool, arguments)
