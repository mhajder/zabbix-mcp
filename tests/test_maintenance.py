"""Maintenance tools: time periods Zabbix accepts, kept in step with the window."""

import pytest
from fastmcp.exceptions import ToolError

pytestmark = pytest.mark.asyncio

SINCE = 1_700_000_000
TILL = SINCE + 7200


async def test_maintenance_get(call_tool, zabbix):
    zabbix.queue("maintenance.get", "1", [{"maintenanceid": "3"}])

    result = await call_tool(
        "maintenance_get",
        {"maintenanceids": ["3"], "groupids": ["4"], "hostids": ["10"]},
    )

    assert result == {
        "maintenance": [{"maintenanceid": "3"}],
        "count": 1,
        "total": 1,
        "limit": 100,
        "offset": 0,
        "has_more": False,
    }
    assert zabbix.params("maintenance.get")[1] == {
        "maintenanceids": ["3"],
        "groupids": ["4"],
        "hostids": ["10"],
        "sortfield": "maintenanceid",
        "sortorder": "ASC",
        "output": "extend",
        "limit": 100,
    }


async def test_maintenance_get_count_output(call_tool, zabbix):
    zabbix.on("maintenance.get", "6")

    assert await call_tool("maintenance_get", {"count_output": True}) == {"total": 6}


async def test_create_without_periods_covers_the_window_once(call_tool, zabbix):
    zabbix.on("maintenance.create", {"maintenanceids": ["3"]})

    result = await call_tool(
        "maintenance_create",
        {
            "name": "patching",
            "active_since": SINCE,
            "active_till": TILL,
            "groupids": ["4"],
            "hostids": ["10"],
            "description": "monthly",
        },
    )

    assert result == {"maintenanceids": ["3"], "success": True}
    assert zabbix.params("maintenance.create") == [
        {
            "name": "patching",
            "active_since": SINCE,
            "active_till": TILL,
            "timeperiods": [
                {"timeperiod_type": 0, "start_date": SINCE, "period": 7200}
            ],
            "groups": [{"groupid": "4"}],
            "hosts": [{"hostid": "10"}],
            "description": "monthly",
        }
    ]


async def test_short_window_gets_the_minimum_period(call_tool, zabbix):
    zabbix.on("maintenance.create", {"maintenanceids": ["3"]})

    await call_tool(
        "maintenance_create",
        {
            "name": "m",
            "active_since": SINCE,
            "active_till": SINCE + 60,
            "hostids": ["1"],
        },
    )

    assert zabbix.params("maintenance.create")[0]["timeperiods"] == [
        {"timeperiod_type": 0, "start_date": SINCE, "period": 300}
    ]


async def test_given_periods_are_coerced_and_keep_every_field(call_tool, zabbix):
    """Dropping a field such as 'month' silently changes the recurrence."""
    zabbix.on("maintenance.create", {"maintenanceids": ["3"]})
    periods = [
        {
            "timeperiod_type": "4",
            "every": "1",
            "month": "4095",
            "dayofweek": "64",
            "day": None,
            "start_time": "3600",
            "period": "7200",
            "unknown": "x",
        },
        # An all-null period carries nothing and is left out.
        {"day": None},
    ]

    await call_tool(
        "maintenance_create",
        {
            "name": "m",
            "active_since": SINCE,
            "active_till": TILL,
            "hostids": ["1"],
            "timeperiods": periods,
        },
    )

    assert zabbix.params("maintenance.create")[0]["timeperiods"] == [
        {
            "timeperiod_type": 4,
            "every": 1,
            "month": 4095,
            "dayofweek": 64,
            "start_time": 3600,
            "period": 7200,
        }
    ]


async def test_period_shorter_than_zabbix_accepts_is_refused(call_tool, zabbix):
    with pytest.raises(ToolError, match=r"timeperiods\[0\] has period=60s"):
        await call_tool(
            "maintenance_create",
            {
                "name": "m",
                "active_since": SINCE,
                "active_till": TILL,
                "hostids": ["1"],
                "timeperiods": [{"timeperiod_type": 0, "period": 60}],
            },
        )
    assert zabbix.calls == []


@pytest.mark.parametrize("targets", [{}, {"groupids": [], "hostids": []}])
async def test_create_needs_hosts_or_groups(call_tool, zabbix, targets):
    with pytest.raises(ToolError, match="At least one of 'groupids' or 'hostids'"):
        await call_tool(
            "maintenance_create",
            {"name": "m", "active_since": SINCE, "active_till": TILL, **targets},
        )
    assert zabbix.calls == []


async def test_update_fields_without_moving_the_window(call_tool, zabbix):
    zabbix.on("maintenance.update", {"maintenanceids": ["3"]})

    result = await call_tool(
        "maintenance_update",
        {"maintenanceid": "3", "name": "n", "description": ""},
    )

    assert result == {
        "maintenanceids": ["3"],
        "success": True,
        "timeperiods_updated": False,
    }
    assert zabbix.calls == [
        ("maintenance.update", {"maintenanceid": "3", "name": "n", "description": ""})
    ]


def current(since, till, periods):
    return [
        {"active_since": str(since), "active_till": str(till), "timeperiods": periods}
    ]


async def test_moving_the_window_rebuilds_the_default_one_off_period(call_tool, zabbix):
    """Left alone, the old one-off period falls outside the new window."""
    # Zabbix rounds stored times down to the minute.
    stored = [{"timeperiod_type": "0", "start_date": str(SINCE - 20), "period": "7200"}]
    zabbix.on("maintenance.get", current(SINCE, TILL, stored))
    zabbix.on("maintenance.update", {"maintenanceids": ["3"]})

    result = await call_tool(
        "maintenance_update", {"maintenanceid": "3", "active_till": TILL + 3600}
    )

    assert result["timeperiods_updated"] is True
    assert zabbix.calls == [
        (
            "maintenance.get",
            {
                "maintenanceids": ["3"],
                "output": ["active_since", "active_till"],
                "selectTimeperiods": "extend",
            },
        ),
        (
            "maintenance.update",
            {
                "maintenanceid": "3",
                "active_till": TILL + 3600,
                "timeperiods": [
                    {"timeperiod_type": 0, "start_date": SINCE, "period": 10800}
                ],
            },
        ),
    ]


async def test_moving_the_start_keeps_the_stored_end(call_tool, zabbix):
    stored = [{"timeperiod_type": "0", "start_date": str(SINCE), "period": "7200"}]
    zabbix.on("maintenance.get", current(SINCE, TILL, stored))
    zabbix.on("maintenance.update", {"maintenanceids": ["3"]})

    await call_tool(
        "maintenance_update", {"maintenanceid": "3", "active_since": SINCE + 3600}
    )

    assert zabbix.params("maintenance.update")[0]["timeperiods"] == [
        {"timeperiod_type": 0, "start_date": SINCE + 3600, "period": 3600}
    ]


@pytest.mark.parametrize(
    "stored",
    [
        # A recurring schedule is the caller's own; it must not be replaced.
        [{"timeperiod_type": "3", "every": "1", "dayofweek": "64", "period": "3600"}],
        [{"timeperiod_type": "0", "start_date": str(SINCE + 600), "period": "7200"}],
        [
            {"timeperiod_type": "0", "start_date": str(SINCE), "period": "7200"},
            {"timeperiod_type": "0", "start_date": str(SINCE), "period": "600"},
        ],
        [{"timeperiod_type": "0", "start_date": "soon", "period": "7200"}],
        [],
    ],
)
async def test_moving_the_window_keeps_custom_periods(call_tool, zabbix, stored):
    zabbix.on("maintenance.get", current(SINCE, TILL, stored))
    zabbix.on("maintenance.update", {"maintenanceids": ["3"]})

    result = await call_tool(
        "maintenance_update", {"maintenanceid": "3", "active_till": TILL + 60}
    )

    assert result["timeperiods_updated"] is False
    assert zabbix.params("maintenance.update") == [
        {"maintenanceid": "3", "active_till": TILL + 60}
    ]


async def test_moving_the_window_of_an_unknown_maintenance(call_tool, zabbix):
    """Nothing to rebuild; Zabbix reports the missing id on update."""
    zabbix.on("maintenance.get", [])
    zabbix.on("maintenance.update", {"maintenanceids": ["3"]})

    await call_tool("maintenance_update", {"maintenanceid": "3", "active_since": SINCE})

    assert zabbix.params("maintenance.update") == [
        {"maintenanceid": "3", "active_since": SINCE}
    ]


async def test_update_with_explicit_periods_skips_the_lookup(call_tool, zabbix):
    zabbix.on("maintenance.update", {"maintenanceids": ["3"]})

    result = await call_tool(
        "maintenance_update",
        {
            "maintenanceid": "3",
            "active_since": SINCE,
            "active_till": TILL,
            "timeperiods": [{"timeperiod_type": "0", "period": "900"}],
        },
    )

    assert result["timeperiods_updated"] is True
    assert zabbix.calls == [
        (
            "maintenance.update",
            {
                "maintenanceid": "3",
                "active_since": SINCE,
                "active_till": TILL,
                "timeperiods": [{"timeperiod_type": 0, "period": 900}],
            },
        )
    ]


async def test_update_with_no_usable_periods_is_refused(call_tool, zabbix):
    """An empty list would wipe the periods, which Zabbix does not allow."""
    with pytest.raises(ToolError, match="'timeperiods' must contain at least one"):
        await call_tool("maintenance_update", {"maintenanceid": "3", "timeperiods": []})
    assert zabbix.calls == []


async def test_maintenance_delete(call_tool, zabbix):
    zabbix.on("maintenance.delete", {"maintenanceids": ["3"]})

    assert await call_tool("maintenance_delete", {"maintenanceids": ["3"]}) == {
        "maintenanceids": ["3"],
        "success": True,
    }
    assert zabbix.params("maintenance.delete") == [["3"]]


@pytest.mark.parametrize(
    ("tool", "arguments", "method", "action"),
    [
        ("maintenance_get", {}, "maintenance.get", "Error retrieving maintenance"),
        (
            "maintenance_create",
            {"name": "m", "active_since": SINCE, "active_till": TILL, "hostids": ["1"]},
            "maintenance.create",
            "Error creating maintenance",
        ),
        (
            "maintenance_update",
            {"maintenanceid": "3", "active_since": SINCE},
            "maintenance.get",
            "Error updating maintenance",
        ),
        (
            "maintenance_update",
            {"maintenanceid": "3"},
            "maintenance.update",
            "Error updating maintenance",
        ),
        (
            "maintenance_delete",
            {"maintenanceids": ["3"]},
            "maintenance.delete",
            "Error deleting maintenance",
        ),
    ],
)
async def test_zabbix_failures_become_tool_errors(
    call_tool, zabbix, tool, arguments, method, action
):
    zabbix.on(method, ConnectionError("down"))

    with pytest.raises(ToolError, match=f"^{action}: ConnectionError: down$"):
        await call_tool(tool, arguments)
