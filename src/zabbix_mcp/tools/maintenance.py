"""
Zabbix MCP Server Maintenance Tools
"""

from typing import Annotated
from typing import Any

from fastmcp import Context
from pydantic import Field

from zabbix_mcp.models import ZabbixConfig
from zabbix_mcp.tools.errors import fail
from zabbix_mcp.tools.pagination import fetch_page
from zabbix_mcp.tools.pagination import fetch_total
from zabbix_mcp.zabbix_client import ZabbixClient

# Every field a maintenance time period accepts. Dropping any of them silently
# changes the recurrence the caller asked for, so all are passed through.
_TIMEPERIOD_FIELDS = (
    "timeperiod_type",
    "every",
    "month",
    "dayofweek",
    "day",
    "start_time",
    "start_date",
    "period",
)

# Shortest maintenance period Zabbix accepts, in seconds.
_MIN_PERIOD = 300


def _coerce_timeperiods(
    timeperiods: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Coerce caller-supplied time periods to the integers Zabbix expects.

    Args:
        timeperiods: Raw period dicts from the caller, if any.

    Returns:
        list: The non-empty periods, with every known field as an int.

    Raises:
        ValueError: If a period is shorter than Zabbix accepts. Zabbix's own
            error for it does not say which period or what the minimum is.
    """
    normalized = [
        {
            field: int(period[field])
            for field in _TIMEPERIOD_FIELDS
            if period.get(field) is not None
        }
        for period in timeperiods or []
        if isinstance(period, dict)
    ]
    normalized = [period for period in normalized if period]
    for index, period in enumerate(normalized):
        if "period" in period and period["period"] < _MIN_PERIOD:
            raise ValueError(
                f"timeperiods[{index}] has period={period['period']}s; Zabbix "
                f"requires at least {_MIN_PERIOD} seconds (5 minutes)."
            )
    return normalized


def _one_off_period(active_since: int, active_till: int) -> dict[str, Any]:
    """Build a "one time only" period covering exactly the given window."""
    return {
        "timeperiod_type": 0,
        "start_date": int(active_since),
        # Zabbix rejects periods shorter than five minutes.
        "period": max(int(active_till) - int(active_since), _MIN_PERIOD),
    }


def _normalize_timeperiods(
    timeperiods: list[dict[str, Any]] | None,
    active_since: int,
    active_till: int,
) -> list[dict[str, Any]]:
    """Coerce caller-supplied time periods, or build a one-off default.

    Args:
        timeperiods: Raw period dicts from the caller, if any.
        active_since: Maintenance window start, used for the default period.
        active_till: Maintenance window end, used for the default period.

    Returns:
        list: Time periods ready for maintenance.create. Never empty - Zabbix
            requires at least one.
    """
    return _coerce_timeperiods(timeperiods) or [
        _one_off_period(active_since, active_till)
    ]


def _is_one_off_for_window(
    timeperiods: list[dict[str, Any]], active_since: int, active_till: int
) -> bool:
    """Tell whether the periods are just the one-off default for the window.

    That is what maintenance_create sends when no periods are given, so it is
    safe to rebuild when the window moves. Zabbix rounds stored times down to
    the minute, hence the tolerance.

    Args:
        timeperiods: The maintenance's current periods, as maintenance.get
            returns them.
        active_since: The maintenance's current window start.
        active_till: The maintenance's current window end.

    Returns:
        bool: True for a single one-off period matching the window.
    """
    if len(timeperiods) != 1:
        return False
    current = timeperiods[0]
    expected = _one_off_period(active_since, active_till)
    try:
        return int(current.get("timeperiod_type", -1)) == 0 and all(
            abs(int(current.get(field, -1)) - expected[field]) < 60
            for field in ("start_date", "period")
        )
    except (TypeError, ValueError):
        return False


def register_maintenance_tools(mcp, config: ZabbixConfig):
    """Register Zabbix maintenance tools with the MCP server"""

    @mcp.tool(
        tags={"zabbix", "maintenance", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def maintenance_get(
        ctx: Context,
        maintenanceids: Annotated[list[str] | None, Field(default=None)] = None,
        groupids: Annotated[list[str] | None, Field(default=None)] = None,
        hostids: Annotated[list[str] | None, Field(default=None)] = None,
        output: Annotated[str | list[str], Field(default="extend")] = "extend",
        limit: Annotated[
            int,
            Field(
                default=100,
                description="Maximum number of results to return. Default is 100.",
                ge=1,
            ),
        ] = 100,
        offset: Annotated[
            int,
            Field(
                default=0,
                description="Number of matching records to skip. Use with 'limit' to page through results; check 'has_more' and 'total' in the response.",
                ge=0,
            ),
        ] = 0,
        sortfield: Annotated[
            str,
            Field(
                default="maintenanceid",
                description="Field to sort by. A deterministic sort is required for paging to be consistent.",
            ),
        ] = "maintenanceid",
        sortorder: Annotated[
            str,
            Field(default="ASC", description="Sort direction - 'ASC' or 'DESC'."),
        ] = "ASC",
        count_output: Annotated[
            bool,
            Field(
                default=False,
                description="If true, returns only the count of matched objects as an integer.",
            ),
        ] = False,
    ) -> dict:
        """
        Get maintenance periods from Zabbix.

        Maintenance windows define periods when monitoring is paused for planned upgrades,
        maintenance, or testing. Alerts are suppressed during maintenance periods.

        Args:
            maintenanceids: List of maintenance IDs to get. Omit to return all maintenance periods; an empty list matches none.
            groupids: List of host group IDs to get maintenance for. An empty list matches none.
            hostids: List of host IDs to get maintenance for. An empty list matches none.
            limit: Maximum number of results to return (default 100). Set higher for more results.
            offset: Number of matching records to skip, for paging.

        Returns:
            dict: Contains 'maintenance' list with maintenance objects, 'count' of returned records,
                  'total' matching records, the applied 'limit' and 'offset', and
                  'has_more' indicating whether further pages exist.
                  Each maintenance includes:
                  - maintenanceid: Unique maintenance ID
                  - name: Maintenance window name
                  - active_since: Unix timestamp when maintenance becomes active
                  - active_till: Unix timestamp when maintenance ends

        Note: Use maintenance_create to schedule maintenance, maintenance_delete to cancel it.
        """
        try:
            await ctx.info("Retrieving maintenance periods...")
            # Sorting is kept out of 'filters' because Zabbix rejects
            # countOutput combined with sortfield.
            sort: dict[str, Any] = {"sortfield": sortfield, "sortorder": sortorder}
            filters: dict[str, Any] = {}
            shape: dict[str, Any] = {"output": output}
            if maintenanceids is not None:
                filters["maintenanceids"] = maintenanceids
            if groupids is not None:
                filters["groupids"] = groupids
            if hostids is not None:
                filters["hostids"] = hostids

            async with ZabbixClient(config) as api:
                if count_output:
                    return {"total": await fetch_total(api.maintenance, filters)}

                rows, total = await fetch_page(
                    api.maintenance,
                    filters=filters,
                    shape=shape,
                    sort=sort,
                    id_field="maintenanceid",
                    limit=limit,
                    offset=offset,
                )
                return {
                    "maintenance": rows,
                    "count": len(rows),
                    "total": total,
                    "limit": limit,
                    "offset": offset,
                    "has_more": offset + len(rows) < total,
                }
        except Exception as e:
            await fail(ctx, "Error retrieving maintenance", e)

    @mcp.tool(
        tags={"zabbix", "maintenance"},
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
        },
    )
    async def maintenance_create(
        ctx: Context,
        name: Annotated[str, Field(description="Maintenance name.")],
        active_since: Annotated[int, Field(description="Start time (Unix timestamp).")],
        active_till: Annotated[int, Field(description="End time (Unix timestamp).")],
        groupids: Annotated[list[str] | None, Field(default=None)] = None,
        hostids: Annotated[list[str] | None, Field(default=None)] = None,
        timeperiods: Annotated[
            list[dict[str, Any]] | None,
            Field(
                default=None,
                description=(
                    "When maintenance actually runs, e.g. [{'timeperiod_type': 0, "
                    "'start_date': 1735689600, 'period': 3600}]. Required by Zabbix; "
                    "if omitted, a single one-off period covering active_since to "
                    "active_till is sent."
                ),
            ),
        ] = None,
        description: Annotated[str | None, Field(default=None)] = None,
    ) -> dict:
        """
        Create a new maintenance period in Zabbix.

        Schedules a maintenance window when monitoring alerts are suppressed. Useful for planned
        upgrades, patching, or system maintenance without triggering false alarms.

        Args:
            name: Maintenance name displayed in the UI. Example: 'Server upgrade', 'Network maintenance'.
            active_since: Start time as Unix timestamp (when maintenance period begins).
            active_till: End time as Unix timestamp (when maintenance period ends).
            groupids: List of host group IDs to apply maintenance to. At least one of groupids
                     or hostids is required.
            hostids: List of specific host IDs to apply maintenance to.
            timeperiods: When the maintenance actually runs. Zabbix requires this; when it
                     is omitted a single one-off period spanning active_since to
                     active_till is sent, which is what 'maintenance from X to Y' means.
                     Each period accepts timeperiod_type (0=one time, 2=daily, 3=weekly,
                     4=monthly), every, month, dayofweek, day, start_time, start_date
                     and period.
            description: Optional description explaining the maintenance purpose.

        Returns:
            dict: Contains 'maintenanceids' list with newly created maintenance ID(s) and 'success' flag.

        Note: During maintenance windows, no alerts are generated. Monitoring still occurs but alerts
              are suppressed. Use for planned maintenance to avoid alert fatigue.
        """
        try:
            await ctx.info(f"Creating maintenance '{name}'...")
            if not groupids and not hostids:
                raise ValueError(
                    "At least one of 'groupids' or 'hostids' must be given - Zabbix "
                    "requires a maintenance window to cover something."
                )

            params: dict[str, Any] = {
                "name": name,
                "active_since": active_since,
                "active_till": active_till,
                "timeperiods": _normalize_timeperiods(
                    timeperiods, active_since, active_till
                ),
            }

            if groupids:
                params["groups"] = [{"groupid": str(g)} for g in groupids]

            if hostids:
                params["hosts"] = [{"hostid": str(h)} for h in hostids]

            if description:
                params["description"] = description

            async with ZabbixClient(config) as api:
                result = await api.maintenance.create(**params)
                return {
                    "maintenanceids": result.get("maintenanceids", []),
                    "success": True,
                }
        except Exception as e:
            await fail(ctx, "Error creating maintenance", e)

    @mcp.tool(
        tags={"zabbix", "maintenance"},
        annotations={
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
        },
    )
    async def maintenance_update(
        ctx: Context,
        maintenanceid: Annotated[
            str, Field(description="ID of the maintenance to update.")
        ],
        name: Annotated[str | None, Field(default=None)] = None,
        active_since: Annotated[int | None, Field(default=None)] = None,
        active_till: Annotated[int | None, Field(default=None)] = None,
        timeperiods: Annotated[
            list[dict[str, Any]] | None,
            Field(
                default=None,
                description=(
                    "Replaces all of the maintenance's time periods, e.g. "
                    "[{'timeperiod_type': 0, 'start_date': 1735689600, 'period': 3600}]. "
                    "Omit to keep them; a one-off period created for the old window "
                    "is moved along with it."
                ),
            ),
        ] = None,
        description: Annotated[str | None, Field(default=None)] = None,
    ) -> dict:
        """
        Update an existing maintenance period in Zabbix.

        Modifies properties of an existing maintenance window. You can change the name,
        start time, end time, time periods, or description. Only specify the fields you
        want to change.

        Args:
            maintenanceid: ID of the maintenance to update (required). Find it with maintenance_get.
            name: New maintenance name.
            active_since: New start time (Unix timestamp).
            active_till: New end time (Unix timestamp).
            timeperiods: New time periods, replacing all current ones. Same format as
                     maintenance_create. When omitted and the window changes, a single
                     one-off period that covered the old window is rebuilt for the new
                     one; recurring periods are left as they are.
            description: New description.

        Returns:
            dict: Contains 'maintenanceids' list with updated maintenance IDs, 'success' flag,
                  and 'timeperiods_updated' telling whether the time periods were replaced.

        Note: Alerts are suppressed only while a time period is running, not for the whole
              active_since..active_till window. Extending the window of a recurring
              maintenance does not add periods - pass timeperiods to change them.
        """
        try:
            await ctx.info(f"Updating maintenance {maintenanceid}...")
            params: dict[str, Any] = {"maintenanceid": maintenanceid}
            if name is not None:
                params["name"] = name
            if active_since is not None:
                params["active_since"] = active_since
            if active_till is not None:
                params["active_till"] = active_till
            if description is not None:
                params["description"] = description
            if timeperiods is not None:
                params["timeperiods"] = _coerce_timeperiods(timeperiods)
                if not params["timeperiods"]:
                    raise ValueError(
                        "'timeperiods' must contain at least one period - Zabbix "
                        "requires one. Omit it to keep the current periods."
                    )

            async with ZabbixClient(config) as api:
                window_moves = active_since is not None or active_till is not None
                if window_moves and timeperiods is None:
                    # Zabbix keeps the periods as they are, so a one-off period
                    # made for the old window would stop suppressing alerts at
                    # the old end time.
                    current = await api.maintenance.get(
                        maintenanceids=[maintenanceid],
                        output=["active_since", "active_till"],
                        selectTimeperiods="extend",
                    )
                    if current:
                        old_since = int(current[0]["active_since"])
                        old_till = int(current[0]["active_till"])
                        if _is_one_off_for_window(
                            current[0].get("timeperiods") or [], old_since, old_till
                        ):
                            params["timeperiods"] = [
                                _one_off_period(
                                    active_since
                                    if active_since is not None
                                    else old_since,
                                    active_till
                                    if active_till is not None
                                    else old_till,
                                )
                            ]

                result = await api.maintenance.update(**params)
                return {
                    "maintenanceids": result.get("maintenanceids", []),
                    "success": True,
                    "timeperiods_updated": "timeperiods" in params,
                }
        except Exception as e:
            await fail(ctx, "Error updating maintenance", e)

    @mcp.tool(
        tags={"zabbix", "maintenance"},
        annotations={
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
        },
    )
    async def maintenance_delete(
        ctx: Context,
        maintenanceids: Annotated[
            list[str],
            Field(description="Maintenance IDs to delete.", min_length=1),
        ],
    ) -> dict:
        """
        Delete maintenance periods from Zabbix.

        Cancels maintenance windows immediately, resuming alert generation. If the maintenance
        period has already passed, historical event suppression is retained.

        Args:
            maintenanceids: List of maintenance IDs to delete. Find them with maintenance_get.

        Returns:
            dict: Contains 'maintenanceids' list with deleted maintenance IDs and 'success' flag.

        Note: Alerts will resume immediately upon deletion. If maintenance period has passed,
              no impact on historical data. Consider timing of deletion to avoid alert storms.
        """
        try:
            await ctx.info(f"Deleting maintenance: {maintenanceids}...")
            async with ZabbixClient(config) as api:
                result = await api.maintenance.delete(*maintenanceids)
                return {
                    "maintenanceids": result.get("maintenanceids", []),
                    "success": True,
                }
        except Exception as e:
            await fail(ctx, "Error deleting maintenance", e)

    ##########################
    # Action Tools
    ##########################
