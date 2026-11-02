"""Template and trigger tools."""

import pytest
from fastmcp.exceptions import ToolError

pytestmark = pytest.mark.asyncio


async def test_template_get_builds_filters_and_selects(call_tool, zabbix):
    zabbix.queue("template.get", "1", [{"templateid": "10001"}])

    result = await call_tool(
        "template_get",
        {
            "templateids": ["10001"],
            "groupids": ["1"],
            "hostids": ["10"],
            "search": {"description": "linux"},
            "template_name_contains": "Linux",
            "select_groups": True,
            "select_hosts": True,
            "select_templates": True,
            "select_macros": True,
            "select_tags": True,
        },
    )

    assert result["templates"] == [{"templateid": "10001"}]
    assert zabbix.params("template.get")[1] == {
        "templateids": ["10001"],
        "groupids": ["1"],
        "hostids": ["10"],
        # The technical name is 'host' on templates too.
        "search": {"description": "linux", "host": "Linux"},
        "sortfield": "host",
        "sortorder": "ASC",
        "output": "extend",
        "selectTemplateGroups": "extend",
        "selectHosts": "extend",
        "selectTemplates": "extend",
        "selectMacros": "extend",
        "selectTags": "extend",
        "limit": 100,
    }


async def test_template_get_count_output(call_tool, zabbix):
    zabbix.on("template.get", "300")

    assert await call_tool("template_get", {"count_output": True}) == {"total": 300}


async def test_template_create_update_delete(call_tool, zabbix):
    zabbix.on("template.create", {"templateids": ["20"]})
    zabbix.on("template.update", {"templateids": ["20"]})
    zabbix.on("template.delete", {"templateids": ["20"]})
    groups = [{"groupid": "1"}]

    assert await call_tool(
        "template_create",
        {"host": "tpl", "groups": groups, "name": "Tpl", "description": "d"},
    ) == {"templateids": ["20"], "success": True}
    await call_tool("template_create", {"host": "tpl2", "groups": groups})
    await call_tool(
        "template_update", {"templateid": "20", "name": "T", "description": ""}
    )
    await call_tool("template_update", {"templateid": "20"})
    await call_tool("template_delete", {"templateids": ["20", "21"]})

    assert zabbix.calls == [
        (
            "template.create",
            {"host": "tpl", "groups": groups, "name": "Tpl", "description": "d"},
        ),
        ("template.create", {"host": "tpl2", "groups": groups}),
        ("template.update", {"templateid": "20", "name": "T", "description": ""}),
        ("template.update", {"templateid": "20"}),
        ("template.delete", ["20", "21"]),
    ]


async def test_trigger_get_builds_filters(call_tool, zabbix):
    zabbix.queue("trigger.get", "1", [{"triggerid": "13"}])

    result = await call_tool(
        "trigger_get",
        {
            "triggerids": ["13"],
            "hostids": ["10"],
            "groupids": ["4"],
            "templateids": ["100"],
            "search": {"comments": "x"},
            "description_contains": "CPU",
            "filter_params": {"value": 1},
            "only_true": True,
            "min_severity": 3,
            "select_hosts": True,
        },
    )

    assert result["triggers"] == [{"triggerid": "13"}]
    assert zabbix.params("trigger.get")[1] == {
        "triggerids": ["13"],
        "hostids": ["10"],
        "groupids": ["4"],
        "templateids": ["100"],
        "search": {"comments": "x", "description": "CPU"},
        "filter": {"value": 1},
        "only_true": True,
        "min_severity": 3,
        "sortfield": "triggerid",
        "sortorder": "ASC",
        "output": "extend",
        "selectHosts": "extend",
        "limit": 100,
    }


async def test_trigger_get_min_severity_zero_is_sent(call_tool, zabbix):
    zabbix.on("trigger.get", "0")

    await call_tool("trigger_get", {"min_severity": 0, "count_output": True})

    assert zabbix.calls == [("trigger.get", {"min_severity": 0, "countOutput": True})]


async def test_trigger_create_update_delete(call_tool, zabbix):
    zabbix.on("trigger.create", {"triggerids": ["13"]})
    zabbix.on("trigger.update", {"triggerids": ["13"]})
    zabbix.on("trigger.delete", {"triggerids": ["13"]})
    expression = "last(/web01/system.cpu.load)>5"

    assert await call_tool(
        "trigger_create",
        {"description": "High load", "expression": expression, "comments": "c"},
    ) == {"triggerids": ["13"], "success": True}
    await call_tool(
        "trigger_create",
        {"description": "d", "expression": expression, "priority": 4, "status": 1},
    )
    await call_tool(
        "trigger_update",
        {
            "triggerid": "13",
            "description": "d2",
            "expression": expression,
            "priority": 5,
            "status": 0,
            "comments": "",
        },
    )
    await call_tool("trigger_update", {"triggerid": "13"})
    await call_tool("trigger_delete", {"triggerids": ["13"]})

    assert zabbix.calls == [
        (
            "trigger.create",
            {
                "description": "High load",
                "expression": expression,
                "priority": 0,
                "status": 0,
                "comments": "c",
            },
        ),
        (
            "trigger.create",
            {"description": "d", "expression": expression, "priority": 4, "status": 1},
        ),
        (
            "trigger.update",
            {
                "triggerid": "13",
                "description": "d2",
                "expression": expression,
                "priority": 5,
                "status": 0,
                "comments": "",
            },
        ),
        ("trigger.update", {"triggerid": "13"}),
        ("trigger.delete", ["13"]),
    ]


@pytest.mark.parametrize(
    ("tool", "arguments", "method", "action"),
    [
        ("template_get", {}, "template.get", "Error retrieving templates"),
        (
            "template_create",
            {"host": "t", "groups": [{"groupid": "1"}]},
            "template.create",
            "Error creating template",
        ),
        (
            "template_update",
            {"templateid": "1"},
            "template.update",
            "Error updating template",
        ),
        (
            "template_delete",
            {"templateids": ["1"]},
            "template.delete",
            "Error deleting templates",
        ),
        ("trigger_get", {}, "trigger.get", "Error retrieving triggers"),
        (
            "trigger_create",
            {"description": "d", "expression": "e"},
            "trigger.create",
            "Error creating trigger",
        ),
        (
            "trigger_update",
            {"triggerid": "1"},
            "trigger.update",
            "Error updating trigger",
        ),
        (
            "trigger_delete",
            {"triggerids": ["1"]},
            "trigger.delete",
            "Error deleting triggers",
        ),
    ],
)
async def test_zabbix_failures_become_tool_errors(
    call_tool, zabbix, tool, arguments, method, action
):
    zabbix.on(method, OSError("Connection refused"))

    with pytest.raises(ToolError, match=f"^{action}: OSError: Connection refused$"):
        await call_tool(tool, arguments)
