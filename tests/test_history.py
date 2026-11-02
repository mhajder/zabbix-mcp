"""History and trend tools: history.get must read the table the items use."""

import pytest
from fastmcp.exceptions import ToolError

pytestmark = pytest.mark.asyncio

VALUES = [{"itemid": "1", "clock": "1700000000", "value": "0.5"}]


async def test_history_type_is_detected_from_the_items(call_tool, zabbix):
    """A wrong guess returns [] instead of an error, which reads as "no data"."""
    zabbix.on("item.get", [{"itemid": "1", "value_type": "3"}])
    zabbix.on("history.get", VALUES)

    result = await call_tool(
        "history_get",
        {"itemids": ["1"], "time_from": 1700000000, "time_till": 1700003600},
    )

    assert result == {"history": VALUES, "count": 1, "limit": 100}
    assert zabbix.calls == [
        (
            "item.get",
            {"itemids": ["1"], "output": ["itemid", "value_type"], "webitems": True},
        ),
        (
            "history.get",
            {
                "itemids": ["1"],
                "history": 3,
                "time_from": 1700000000,
                "time_till": 1700003600,
                "sortfield": "clock",
                "sortorder": "DESC",
                "limit": 100,
            },
        ),
    ]


async def test_explicit_history_type_skips_the_lookup(call_tool, zabbix):
    zabbix.on("history.get", [])

    await call_tool(
        "history_get",
        {"itemids": ["1"], "history": 0, "sortorder": "ASC", "limit": 10},
    )

    assert zabbix.calls == [
        (
            "history.get",
            {
                "itemids": ["1"],
                "history": 0,
                "sortfield": "clock",
                "sortorder": "ASC",
                "limit": 10,
            },
        )
    ]


async def test_history_count_output_never_sorts(call_tool, zabbix):
    zabbix.on("history.get", "250")

    result = await call_tool(
        "history_get", {"itemids": ["1"], "history": 1, "count_output": True}
    )

    assert result == {"total": 250}
    assert zabbix.params("history.get") == [
        {"itemids": ["1"], "history": 1, "countOutput": True}
    ]


async def test_unknown_items_are_an_error_not_empty_history(call_tool, zabbix):
    zabbix.on("item.get", [])

    with pytest.raises(ToolError, match=r"No items found for itemids \['404'\]"):
        await call_tool("history_get", {"itemids": ["404"]})
    assert zabbix.params("history.get") == []


async def test_mixed_value_types_are_refused(call_tool, zabbix):
    zabbix.on(
        "item.get",
        [{"itemid": "1", "value_type": "0"}, {"itemid": "2", "value_type": "4"}],
    )

    with pytest.raises(ToolError, match=r"mix value types \[0, 4\]"):
        await call_tool("history_get", {"itemids": ["1", "2"]})


async def test_item_lookup_failure_is_not_reported_as_missing_items(call_tool, zabbix):
    zabbix.on("item.get", TimeoutError())

    with pytest.raises(ToolError, match=r"^Error retrieving history: TimeoutError$"):
        await call_tool("history_get", {"itemids": ["1"]})


async def test_trend_get(call_tool, zabbix):
    trends = [{"itemid": "1", "clock": "1700000000", "value_avg": "2"}]
    zabbix.on("trend.get", trends)

    result = await call_tool(
        "trend_get", {"itemids": ["1"], "time_from": 1, "time_till": 2, "limit": 5}
    )

    assert result == {"trends": trends, "count": 1, "limit": 5}
    assert zabbix.params("trend.get") == [
        {"itemids": ["1"], "time_from": 1, "time_till": 2, "limit": 5}
    ]


async def test_trend_count_output(call_tool, zabbix):
    zabbix.on("trend.get", "24")

    assert await call_tool("trend_get", {"itemids": ["1"], "count_output": True}) == {
        "total": 24
    }
    assert zabbix.params("trend.get") == [{"itemids": ["1"], "countOutput": True}]


async def test_trend_failure_is_a_tool_error(call_tool, zabbix):
    zabbix.on("trend.get", ConnectionError("down"))

    with pytest.raises(ToolError, match=r"^Error retrieving trends: ConnectionError"):
        await call_tool("trend_get", {"itemids": ["1"]})


async def test_itemids_are_required(call_tool, zabbix):
    with pytest.raises(ToolError, match="itemids"):
        await call_tool("history_get", {"itemids": []})
    assert zabbix.calls == []
