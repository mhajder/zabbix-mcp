"""
Zabbix MCP Server History Tools
"""

from typing import Annotated
from typing import Any

from fastmcp import Context
from pydantic import Field

from zabbix_mcp.models import ZabbixConfig
from zabbix_mcp.tools.errors import fail
from zabbix_mcp.tools.pagination import fetch_total
from zabbix_mcp.zabbix_client import ZabbixClient


async def _detect_value_type(api: Any, itemids: list[str]) -> int:
    """Look up which history table the given items store their values in.

    history.get reads one storage type at a time and returns an empty list -
    not an error - when it does not match the item, which makes a wrong guess
    look like "no data".

    Args:
        api: Authenticated Zabbix API instance.
        itemids: Items the caller wants history for.

    Returns:
        int: The shared value_type of the items.

    Raises:
        ValueError: If the items do not exist, or mix value types, in which case
            no single history table can serve them all.
    """
    items = await api.item.get(itemids=itemids, output=["itemid", "value_type"])
    value_types = {int(item["value_type"]) for item in items}
    if not value_types:
        raise ValueError(f"No items found for itemids {itemids}.")
    if len(value_types) > 1:
        raise ValueError(
            f"Items {itemids} mix value types {sorted(value_types)}; history.get reads "
            "one type at a time. Request them separately, or pass 'history' explicitly."
        )
    return value_types.pop()


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
            int | None,
            Field(
                default=None,
                description="Storage type to read: 0=float, 1=char, 2=log, 3=unsigned, 4=text. Must match the items' value_type or Zabbix returns nothing. Detected from the items when omitted.",
            ),
        ] = None,
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
            history: Which history table to read. Zabbix stores each item's values in the
                    table matching its value_type, and reading the wrong one returns an
                    empty list rather than an error - so this must agree with the items.
                    Leave it unset and the value_type is looked up from the items instead.
                    - 0 = Float numeric values
                    - 1 = Character string values
                    - 2 = Log data
                    - 3 = Unsigned numeric values
                    - 4 = Text data
            time_from: Unix timestamp to get history from this time onwards.
            time_till: Unix timestamp to get history up to this time.
            limit: Maximum number of results to return (default 100). Set higher for more results.
            sortfield: Field to sort by (default 'clock' = timestamp).
            sortorder: Sort direction - 'ASC' (oldest first) or 'DESC' (newest first). Default is DESC.

        Returns:
            dict: Contains 'history' list with value objects, 'count' of returned values,
                  and the applied 'limit'.
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
            # Sorting is kept separate because Zabbix rejects countOutput
            # combined with sortfield.
            filters: dict[str, Any] = {"itemids": itemids, "history": history}
            if time_from:
                filters["time_from"] = time_from
            if time_till:
                filters["time_till"] = time_till

            async with ZabbixClient(config) as api:
                if history is None:
                    filters["history"] = await _detect_value_type(api, itemids)

                if count_output:
                    return {"total": await fetch_total(api.history, filters)}

                values = await api.history.get(
                    **filters,
                    sortfield=sortfield,
                    sortorder=sortorder,
                    limit=limit,
                )
                return {
                    "history": values,
                    "count": len(values),
                    "limit": limit,
                }
        except Exception as e:
            await fail(ctx, "Error retrieving history", e)

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

        Returns:
            dict: Contains 'trends' list with aggregate data, 'count' of returned records,
                  and the applied 'limit'.
                  Each trend record includes:
                  - itemid: Item ID this trend belongs to
                  - clock: Unix timestamp (at hour boundaries)
                  - value_min: Minimum value during the hour
                  - value_max: Maximum value during the hour
                  - value_avg: Average value during the hour
                  - num: Number of values included in calculation

        Note: Trends are hourly aggregates. For finer-grained data, use history_get.
              Trends are kept for longer periods than raw history for space efficiency.
              trend.get accepts no sorting parameters - narrow the range with time_from
              and time_till instead.
        """
        try:
            await ctx.info("Retrieving trends...")
            filters: dict[str, Any] = {"itemids": itemids}
            if time_from:
                filters["time_from"] = time_from
            if time_till:
                filters["time_till"] = time_till

            async with ZabbixClient(config) as api:
                if count_output:
                    return {"total": await fetch_total(api.trend, filters)}

                trends = await api.trend.get(**filters, limit=limit)
                return {
                    "trends": trends,
                    "count": len(trends),
                    "limit": limit,
                }
        except Exception as e:
            await fail(ctx, "Error retrieving trends", e)

    ##########################
    # User Tools
    ##########################
