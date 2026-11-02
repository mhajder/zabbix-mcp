"""Item and item prototype tools."""

import pytest
from fastmcp.exceptions import ToolError

pytestmark = pytest.mark.asyncio


async def test_item_get_builds_filters_search_and_selects(call_tool, zabbix):
    rows = [{"itemid": "1", "key_": "system.cpu.load"}]
    zabbix.queue("item.get", "1", rows)

    result = await call_tool(
        "item_get",
        {
            "itemids": ["1"],
            "hostids": ["10"],
            "groupids": ["4"],
            "templateids": ["100"],
            "search": {"description": "load"},
            "filter_params": {"value_type": 0},
            "item_name_contains": "CPU",
            "item_key_contains": "system.cpu",
            "webitems": True,
            "select_hosts": True,
            "select_tags": True,
            "select_triggers": True,
        },
    )

    assert result["items"] == rows
    assert result["total"] == 1
    assert zabbix.params("item.get")[1] == {
        "itemids": ["1"],
        "hostids": ["10"],
        "groupids": ["4"],
        "templateids": ["100"],
        "webitems": True,
        "search": {"description": "load", "name": "CPU", "key_": "system.cpu"},
        "filter": {"value_type": 0},
        "sortfield": "itemid",
        "sortorder": "ASC",
        "output": "extend",
        "selectHosts": "extend",
        "selectTags": "extend",
        "selectTriggers": "extend",
        "limit": 100,
    }


async def test_item_get_count_output(call_tool, zabbix):
    zabbix.on("item.get", "8")

    assert await call_tool("item_get", {"count_output": True}) == {"total": 8}
    assert zabbix.calls == [("item.get", {"countOutput": True})]


async def test_item_create_sends_api_field_names(call_tool, zabbix):
    """type_ and key_ are Python-safe names; Zabbix wants 'type' and 'key_'."""
    zabbix.on("item.create", {"itemids": ["23000"]})

    result = await call_tool(
        "item_create",
        {
            "name": "CPU load",
            "key_": "system.cpu.load",
            "hostid": "10",
            "type_": 0,
            "value_type": 0,
            "interfaceid": "5",
            "units": "%",
            "description": "load average",
        },
    )

    assert result == {"itemids": ["23000"], "success": True}
    assert zabbix.params("item.create") == [
        {
            "name": "CPU load",
            "key_": "system.cpu.load",
            "hostid": "10",
            "type": 0,
            "value_type": 0,
            "delay": "1m",
            "interfaceid": "5",
            "units": "%",
            "description": "load average",
        }
    ]


async def test_item_create_leaves_out_unset_optionals(call_tool, zabbix):
    zabbix.on("item.create", {"itemids": ["1"]})

    await call_tool(
        "item_create",
        {"name": "t", "key_": "trap", "hostid": "10", "type_": 2, "value_type": 4},
    )

    assert zabbix.params("item.create")[0] == {
        "name": "t",
        "key_": "trap",
        "hostid": "10",
        "type": 2,
        "value_type": 4,
        "delay": "1m",
    }


async def test_item_update_and_delete(call_tool, zabbix):
    zabbix.on("item.update", {"itemids": ["1"]})
    zabbix.on("item.delete", {"itemids": ["1"]})

    await call_tool(
        "item_update",
        {
            "itemid": "1",
            "name": "n",
            "delay": "5m",
            "units": "B",
            "description": "",
            "status": 1,
        },
    )
    await call_tool("item_update", {"itemid": "1"})
    assert await call_tool("item_delete", {"itemids": ["1"]}) == {
        "itemids": ["1"],
        "success": True,
    }

    assert zabbix.calls == [
        (
            "item.update",
            {
                "itemid": "1",
                "name": "n",
                "delay": "5m",
                "units": "B",
                "description": "",
                "status": 1,
            },
        ),
        ("item.update", {"itemid": "1"}),
        ("item.delete", ["1"]),
    ]


async def test_itemprototype_get(call_tool, zabbix):
    zabbix.queue("itemprototype.get", "1", [{"itemid": "9"}])

    result = await call_tool(
        "itemprototype_get",
        {
            "itemids": ["9"],
            "hostids": ["10"],
            "discoveryids": ["50"],
            "search": {"name": "disk"},
            "filter_params": {"status": 0},
        },
    )

    assert result == {
        "itemprototypes": [{"itemid": "9"}],
        "count": 1,
        "total": 1,
        "limit": 100,
        "offset": 0,
        "has_more": False,
    }
    assert zabbix.params("itemprototype.get")[0] == {
        "itemids": ["9"],
        "hostids": ["10"],
        "discoveryids": ["50"],
        "search": {"name": "disk"},
        "filter": {"status": 0},
        "countOutput": True,
    }


async def test_itemprototype_get_count_output(call_tool, zabbix):
    zabbix.on("itemprototype.get", "3")

    assert await call_tool("itemprototype_get", {"count_output": True}) == {"total": 3}


@pytest.mark.parametrize(
    ("tool", "arguments", "method", "action"),
    [
        ("item_get", {}, "item.get", "Error retrieving items"),
        (
            "item_create",
            {"name": "n", "key_": "k", "hostid": "1", "type_": 2, "value_type": 0},
            "item.create",
            "Error creating item",
        ),
        ("item_update", {"itemid": "1"}, "item.update", "Error updating item"),
        ("item_delete", {"itemids": ["1"]}, "item.delete", "Error deleting items"),
        (
            "itemprototype_get",
            {},
            "itemprototype.get",
            "Error retrieving item prototypes",
        ),
    ],
)
async def test_zabbix_failures_become_tool_errors(
    call_tool, zabbix, tool, arguments, method, action
):
    zabbix.on(method, TimeoutError())

    with pytest.raises(ToolError, match=f"^{action}: TimeoutError$"):
        await call_tool(tool, arguments)
