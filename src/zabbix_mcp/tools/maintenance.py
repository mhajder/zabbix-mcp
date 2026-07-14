"""
Zabbix MCP Server Maintenance Tools
"""

from typing import Annotated
from typing import Any

from fastmcp import Context
from pydantic import Field

from zabbix_mcp.models import ZabbixConfig
from zabbix_mcp.zabbix_client import ZabbixClient


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
                description="Number of results to skip (for pagination). Requires sortfield to be set.",
                ge=0,
            ),
        ] = 0,
        sortfield: Annotated[
            str | None,
            Field(default=None, description="Field to sort by."),
        ] = None,
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
            offset: Number of results to skip for pagination. Use with sortfield.

        Returns:
            dict: Contains 'maintenance' list with maintenance objects, 'count' of returned records,
                  and pagination metadata ('limit', 'offset').
                  Each maintenance includes:
                  - maintenanceid: Unique maintenance ID
                  - name: Maintenance window name
                  - active_since: Unix timestamp when maintenance becomes active
                  - active_till: Unix timestamp when maintenance ends

        Note: Use maintenance_create to schedule maintenance, maintenance_delete to cancel it.
        """
        try:
            await ctx.info("Retrieving maintenance periods...")
            params: dict[str, Any] = {"output": output}
            if sortfield:
                params["sortfield"] = sortfield
            if sortorder:
                params["sortorder"] = sortorder
            if count_output:
                params["countOutput"] = True
            if maintenanceids:
                params["maintenanceids"] = maintenanceids
            if groupids:
                params["groupids"] = groupids
            if hostids:
                params["hostids"] = hostids

            params["limit"] = limit
            if offset > 0:
                params["offset"] = offset

            async with ZabbixClient(config) as api:
                result = await api.maintenance.get(**params)
                return {
                    "maintenance": result,
                    "count": int(result) if count_output else len(result),
                    "limit": limit,
                    "offset": offset,
                }
        except Exception as e:
            await ctx.error(f"Error retrieving maintenance: {e!s}")
            return {"error": str(e)}

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
        timeperiods: Annotated[list[dict[str, Any]] | None, Field(default=None)] = None,
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
            timeperiods: Optional list of time period objects for recurring maintenance.
            description: Optional description explaining the maintenance purpose.

        Returns:
            dict: Contains 'maintenanceids' list with newly created maintenance ID(s) and 'success' flag.

        Note: During maintenance windows, no alerts are generated. Monitoring still occurs but alerts
              are suppressed. Use for planned maintenance to avoid alert fatigue.
        """
        try:
            await ctx.info(f"Creating maintenance '{name}'...")
            params: dict[str, Any] = {
                "name": name,
                "active_since": active_since,
                "active_till": active_till,
            }

            if groupids:
                params["groups"] = [{"groupid": str(g)} for g in groupids]

            if hostids:
                params["hosts"] = [{"hostid": str(h)} for h in hostids]

            if timeperiods:
                normalized: list[dict[str, Any]] = []
                for tp in timeperiods:
                    if not isinstance(tp, dict):
                        continue
                    ntp: dict[str, Any] = {}
                    if "timeperiod_type" in tp:
                        ntp["timeperiod_type"] = int(tp["timeperiod_type"])
                    if "start_date" in tp:
                        ntp["start_date"] = int(tp["start_date"])
                    if "period" in tp:
                        ntp["period"] = int(tp["period"])
                    if "dayofweek" in tp:
                        ntp["dayofweek"] = tp["dayofweek"]
                    if "start_time" in tp:
                        ntp["start_time"] = int(tp["start_time"])
                    if ntp:
                        normalized.append(ntp)
                if normalized:
                    params["timeperiods"] = normalized

            if description:
                params["description"] = description

            async with ZabbixClient(config) as api:
                result = await api.maintenance.create(**params)
                return {
                    "maintenanceids": result.get("maintenanceids", []),
                    "success": True,
                }
        except Exception as e:
            await ctx.error(f"Error creating maintenance: {e!s}")
            return {"error": str(e)}

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
                  On error, contains 'error' key with the error message.
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
            await ctx.error(f"Error updating maintenance: {e!s}")
            return {"error": str(e)}

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
                  On error, contains 'error' key with the error message.

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
            await ctx.error(f"Error deleting maintenance: {e!s}")
            return {"error": str(e)}

    ##########################
    # Action Tools
    ##########################
