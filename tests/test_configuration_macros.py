"""Configuration export/import and user macro tools."""

import pytest
from fastmcp.exceptions import ToolError

pytestmark = pytest.mark.asyncio


async def test_export_sends_the_ids_as_options(call_tool, zabbix):
    zabbix.on("configuration.export", '{"zabbix_export": {}}')

    result = await call_tool(
        "configuration_export",
        {
            "format_type": "yaml",
            "prettyprint": True,
            "templateids": ["10001"],
            "hostids": ["10"],
        },
    )

    assert result == {"content": '{"zabbix_export": {}}', "success": True}
    assert zabbix.params("configuration.export") == [
        {
            "format": "yaml",
            "prettyprint": True,
            "options": {"templates": ["10001"], "hosts": ["10"]},
        }
    ]


async def test_export_of_hosts_only(call_tool, zabbix):
    zabbix.on("configuration.export", "{}")

    await call_tool("configuration_export", {"hostids": ["10"]})

    assert zabbix.params("configuration.export") == [
        {"format": "json", "prettyprint": False, "options": {"hosts": ["10"]}}
    ]


@pytest.mark.parametrize("ids", [{}, {"templateids": [], "hostids": []}])
async def test_export_without_ids_is_refused(call_tool, zabbix, ids):
    """Zabbix answers it with an empty document, which looks like success."""
    with pytest.raises(ToolError, match="Give at least one of 'templateids'"):
        await call_tool("configuration_export", ids)
    assert zabbix.calls == []


async def test_import_default_rules_create_and_update_only(call_tool, zabbix):
    zabbix.on("configuration.import", True)

    result = await call_tool("configuration_import", {"content": "{}"})

    assert result == {"result": True, "success": True}
    ((method, params),) = zabbix.calls
    # import_ is how zabbix_utils spells the 'import' keyword.
    assert method == "configuration.import"
    assert params["format"] == "json"
    assert params["source"] == "{}"
    rules = params["rules"]
    assert rules["hosts"] == {"createMissing": True, "updateExisting": True}
    # Zabbix rejects updateExisting for template linkage.
    assert rules["templateLinkage"] == {"createMissing": True}
    assert not any("deleteMissing" in rule for rule in rules.values())


async def test_import_delete_missing_only_where_zabbix_allows_it(call_tool, zabbix):
    zabbix.on("configuration.import", True)

    await call_tool(
        "configuration_import",
        {"content": "<xml/>", "format_type": "xml", "delete_missing": True},
    )

    rules = zabbix.params("configuration.import")[0]["rules"]
    assert rules["items"] == {
        "createMissing": True,
        "updateExisting": True,
        "deleteMissing": True,
    }
    assert rules["templateLinkage"] == {"createMissing": True, "deleteMissing": True}
    # Not supported for these, and Zabbix fails the whole import on it.
    for name in ("hosts", "templates", "host_groups", "mediaTypes"):
        assert "deleteMissing" not in rules[name]


async def test_import_custom_rules_are_sent_as_given(call_tool, zabbix):
    zabbix.on("configuration.import", True)
    rules = {"items": {"createMissing": True}}

    await call_tool(
        "configuration_import",
        {"content": "{}", "rules": rules, "delete_missing": True},
    )

    assert zabbix.params("configuration.import")[0]["rules"] == rules


async def test_usermacro_get_breaks_ties_by_host_macro_id(call_tool, zabbix):
    """usermacro.get sorts by macro name only, so ties are ordered by id."""
    zabbix.queue(
        "usermacro.get",
        "2",
        [
            {"hostmacroid": "9", "macro": "{$A}"},
            {"hostmacroid": "3", "macro": "{$A}"},
        ],
        [{"hostmacroid": "9"}, {"hostmacroid": "3"}],
    )

    result = await call_tool(
        "usermacro_get",
        {
            "hostmacroids": ["3", "9"],
            "hostids": ["10"],
            "templateids": ["100"],
            "search": {"macro": "{$A"},
            "filter_params": {"type": 0},
        },
    )

    assert result["macros"] == [{"hostmacroid": "3"}, {"hostmacroid": "9"}]
    count, cursor, final = zabbix.params("usermacro.get")
    filters = {
        "hostmacroids": ["3", "9"],
        "hostids": ["10"],
        "templateids": ["100"],
        "search": {"macro": "{$A"},
        "filter": {"type": 0},
    }
    assert count == {**filters, "countOutput": True}
    assert cursor == {
        **filters,
        "sortfield": "macro",
        "sortorder": "ASC",
        "output": ["hostmacroid", "macro"],
        "limit": 100,
    }
    assert final == {**filters, "hostmacroids": ["3", "9"], "output": "extend"}


async def test_global_macros_page_by_global_macro_id(call_tool, zabbix):
    zabbix.queue(
        "usermacro.get",
        "1",
        [{"globalmacroid": "2", "macro": "{$SNMP}"}],
        [{"globalmacroid": "2", "macro": "{$SNMP}"}],
    )

    result = await call_tool(
        "usermacro_get", {"globalmacro": True, "globalmacroids": ["2"]}
    )

    assert result["macros"] == [{"globalmacroid": "2", "macro": "{$SNMP}"}]
    assert zabbix.params("usermacro.get")[2] == {
        "globalmacroids": ["2"],
        "globalmacro": True,
        "output": "extend",
    }


async def test_usermacro_get_count_output(call_tool, zabbix):
    zabbix.on("usermacro.get", "40")

    assert await call_tool("usermacro_get", {"count_output": True}) == {"total": 40}


async def test_usermacro_create_and_delete(call_tool, zabbix):
    zabbix.on("usermacro.create", {"hostmacroids": ["11"]})
    zabbix.on("usermacro.delete", {"hostmacroids": ["11"]})

    assert await call_tool(
        "usermacro_create",
        {
            "hostid": "10",
            "macro": "{$PASS}",
            "value": "x",
            "type_": 1,
            "description": "secret",
        },
    ) == {"hostmacroids": ["11"], "success": True}
    await call_tool("usermacro_create", {"hostid": "10", "macro": "{$A}", "value": "1"})
    await call_tool("usermacro_delete", {"hostmacroids": ["11"]})

    assert zabbix.calls == [
        (
            "usermacro.create",
            {
                "hostid": "10",
                "macro": "{$PASS}",
                "value": "x",
                "type": 1,
                "description": "secret",
            },
        ),
        (
            "usermacro.create",
            {"hostid": "10", "macro": "{$A}", "value": "1", "type": 0},
        ),
        ("usermacro.delete", ["11"]),
    ]


@pytest.mark.parametrize(
    ("tool", "arguments", "method", "action"),
    [
        (
            "configuration_export",
            {"hostids": ["1"]},
            "configuration.export",
            "Error exporting configuration",
        ),
        (
            "configuration_import",
            {"content": "{}"},
            "configuration.import",
            "Error importing configuration",
        ),
        ("usermacro_get", {}, "usermacro.get", "Error retrieving user macros"),
        (
            "usermacro_create",
            {"hostid": "1", "macro": "{$A}", "value": "1"},
            "usermacro.create",
            "Error creating macro",
        ),
        (
            "usermacro_delete",
            {"hostmacroids": ["1"]},
            "usermacro.delete",
            "Error deleting macros",
        ),
    ],
)
async def test_zabbix_failures_become_tool_errors(
    call_tool, zabbix, tool, arguments, method, action
):
    zabbix.on(method, ConnectionError("down"))

    with pytest.raises(ToolError, match=f"^{action}: ConnectionError: down$"):
        await call_tool(tool, arguments)
