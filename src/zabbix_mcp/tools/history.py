"""
Zabbix MCP Server History Tools
"""

from typing import Annotated
from typing import Any

from fastmcp import Context
from pydantic import Field

from zabbix_mcp.models import ZabbixConfig
from zabbix_mcp.zabbix_client import ZabbixClient


def register_history_tools(mcp, config: ZabbixConfig):
    """Register Zabbix history tools with the MCP server"""

    @mcp.tool(
        tags={"zabbix", "history", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def history_get(
        ctx: Context,
        itemids: Annotated[
            list[str], Field(description="Item IDs to get history for.")
        ],
        history: Annotated[
            int,
            Field(
                default=0,
                description="History type: 0=float, 1=char, 2=log, 3=unsigned, 4=text.",
            ),
        ] = 0,
        time_from: Annotated[int | None, Field(default=None)] = None,
        time_till: Annotated[int | None, Field(default=None)] = None,
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
        sortfield: Annotated[str, Field(default="clock")] = "clock",
        sortorder: Annotated[str, Field(default="DESC")] = "DESC",
        count_output: Annotated[
            bool,
            Field(
                default=False,
                description="If true, returns only the count of matched objects as an integer.",
            ),
        ] = False,
    ) -> dict:
        """
        Get history data from Zabbix.

        Retrieves the raw metric values collected by items. History contains all individual
        collected data points with timestamps, allowing detailed analysis of system behavior over time.

        Args:
            itemids: List of item IDs to get history for. Required. Find items with item_get.
            history: Data type of history to retrieve:
                    - 0 = Float numeric values (default, for most metrics)
                    - 1 = Character string values
                    - 2 = Log data
                    - 3 = Unsigned numeric values
                    - 4 = Text data
            time_from: Unix timestamp to get history from this time onwards.
            time_till: Unix timestamp to get history up to this time.
            limit: Maximum number of results to return (default 100). Set higher for more results.
            offset: Number of results to skip for pagination. Use with sortfield.
            sortfield: Field to sort by (default 'clock' = timestamp).
            sortorder: Sort direction - 'ASC' (oldest first) or 'DESC' (newest first). Default is DESC.

        Returns:
            dict: Contains 'history' list with value objects, 'count' of returned values,
                  and pagination metadata ('limit', 'offset').
                  Each value includes:
                  - itemid: Item ID this value belongs to
                  - value: The collected metric value
                  - clock: Unix timestamp when value was collected
                  - ns: Nanosecond adjustment

        Note: History contains detailed point-in-time data. For aggregated analysis, use trend_get.
              For high-volume items, use limit and time filters to avoid excessive data retrieval.
        """
        try:
            await ctx.info("Retrieving history...")
            params: dict[str, Any] = {
                "itemids": itemids,
                "history": history,
                "sortfield": sortfield,
                "sortorder": sortorder,
            }
            if time_from:
                params["time_from"] = time_from
            if time_till:
                params["time_till"] = time_till
            params["limit"] = limit
            if offset > 0:
                params["offset"] = offset

            if count_output:
                params["countOutput"] = True

            async with ZabbixClient(config) as api:
                result = await api.history.get(**params)
                return {
                    "history": result,
                    "count": int(result) if count_output else len(result),
                    "limit": limit,
                    "offset": offset,
                }
        except Exception as e:
            await ctx.error(f"Error retrieving history: {e!s}")
            return {"error": str(e)}

    @mcp.tool(
        tags={"zabbix", "trend", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def trend_get(
        ctx: Context,
        itemids: Annotated[list[str], Field(description="Item IDs to get trends for.")],
        time_from: Annotated[int | None, Field(default=None)] = None,
        time_till: Annotated[int | None, Field(default=None)] = None,
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
        Get trend data from Zabbix.

        Trends are aggregated (summarized) historical data providing min/max/average values
        at hour-long intervals. Trends use less storage than raw history while preserving
        statistical information for long-term analysis.

        Args:
            itemids: List of item IDs to get trends for. Required. Find items with item_get.
            time_from: Unix timestamp to get trends from this time onwards.
            time_till: Unix timestamp to get trends up to this time.
            limit: Maximum number of results to return (default 100). Set higher for more results.
            offset: Number of results to skip for pagination. Use with sortfield.

        Returns:
            dict: Contains 'trends' list with aggregate data, 'count' of returned records,
                  and pagination metadata ('limit', 'offset').
                  Each trend record includes:
                  - itemid: Item ID this trend belongs to
                  - clock: Unix timestamp (at hour boundaries)
                  - value_min: Minimum value during the hour
                  - value_max: Maximum value during the hour
                  - value_avg: Average value during the hour
                  - num: Number of values included in calculation

        Note: Trends are hourly aggregates. For finer-grained data, use history_get.
              Trends are kept for longer periods than raw history for space efficiency.
        """
        try:
            await ctx.info("Retrieving trends...")
            params: dict[str, Any] = {"itemids": itemids}
            if time_from:
                params["time_from"] = time_from
            if time_till:
                params["time_till"] = time_till
            params["limit"] = limit
            if offset > 0:
                params["offset"] = offset

            if sortfield:
                params["sortfield"] = sortfield
            if sortorder:
                params["sortorder"] = sortorder
            if count_output:
                params["countOutput"] = True

            async with ZabbixClient(config) as api:
                result = await api.trend.get(**params)
                return {
                    "trends": result,
                    "count": int(result) if count_output else len(result),
                    "limit": limit,
                    "offset": offset,
                }
        except Exception as e:
            await ctx.error(f"Error retrieving trends: {e!s}")
            return {"error": str(e)}

    ##########################
    # User Tools
    ##########################
