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
    if normalized:
        return normalized

    # "One time only", covering exactly the requested window.
    return [
        {
            "timeperiod_type": 0,
            "start_date": int(active_since),
            "period": max(int(active_till) - int(active_since), 60),
        }
    ]


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
            maintenanceids: List of maintenance IDs to get. If empty, returns all maintenance periods.
            groupids: List of host group IDs to get maintenance for.
            hostids: List of host IDs to get maintenance for.
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
            if maintenanceids:
                filters["maintenanceids"] = maintenanceids
            if groupids:
                filters["groupids"] = groupids
            if hostids:
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
            "destructiveHint": False,
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
        description: Annotated[str | None, Field(default=None)] = None,
    ) -> dict:
        """
        Update an existing maintenance period in Zabbix.

        Modifies properties of an existing maintenance window. You can change the name,
        start time, end time, or description. Only specify the fields you want to change.

        Args:
            maintenanceid: ID of the maintenance to update (required). Find it with maintenance_get.
            name: New maintenance name.
            active_since: New start time (Unix timestamp).
            active_till: New end time (Unix timestamp).
            description: New description.

        Returns:
            dict: Contains 'maintenanceids' list with updated maintenance IDs and 'success' flag.
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

            async with ZabbixClient(config) as api:
                result = await api.maintenance.update(**params)
                return {
                    "maintenanceids": result.get("maintenanceids", []),
                    "success": True,
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
            list[str], Field(description="Maintenance IDs to delete.")
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
