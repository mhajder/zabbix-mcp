"""
Zabbix MCP Server Discovery Tools
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


def register_discovery_tools(mcp, config: ZabbixConfig):
    """Register Zabbix discovery tools with the MCP server"""

    @mcp.tool(
        tags={"zabbix", "discovery", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def discoveryrule_get(
        ctx: Context,
        itemids: Annotated[list[str] | None, Field(default=None)] = None,
        hostids: Annotated[list[str] | None, Field(default=None)] = None,
        templateids: Annotated[list[str] | None, Field(default=None)] = None,
        search: Annotated[dict[str, str] | None, Field(default=None)] = None,
        filter_params: Annotated[dict[str, Any] | None, Field(default=None)] = None,
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
                default="itemid",
                description="Field to sort by. A deterministic sort is required for paging to be consistent.",
            ),
        ] = "itemid",
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
        Get discovery rules from Zabbix.

        Discovery rules automatically detect items, triggers, and interfaces from network resources.
        They enable dynamic host and item management without manual configuration.

        Args:
            itemids: List of item IDs (discovery rules are items) to get.
            hostids: List of host IDs to get discovery rules from.
            templateids: List of template IDs to get discovery rules from.
            search: Dictionary with search criteria like {'name': 'SNMP'}.
            filter_params: Additional filter parameters for advanced filtering.
            limit: Maximum number of results to return (default 100). Set higher for more results.
            offset: Number of matching records to skip, for paging.

        Returns:
            dict: Contains 'discoveryrules' list with discovery rule objects, 'count',
                  'total' matching records, the applied 'limit' and 'offset', and
                  'has_more' indicating whether further pages exist.
                  Each rule includes:
                  - itemid: Discovery rule item ID
                  - name: Discovery rule name
                  - key_: Discovery rule key
                  - type: Discovery method (0=Zabbix agent, 2=SNMP, etc.)

        Note: Discovery rules generate items and triggers dynamically. Monitor their status and adjust as needed.
        """
        try:
            await ctx.info("Retrieving discovery rules...")
            # Sorting is kept out of 'filters' because Zabbix rejects
            # countOutput combined with sortfield.
            sort: dict[str, Any] = {"sortfield": sortfield, "sortorder": sortorder}
            filters: dict[str, Any] = {}
            shape: dict[str, Any] = {"output": output}
            if itemids:
                filters["itemids"] = itemids
            if hostids:
                filters["hostids"] = hostids
            if templateids:
                filters["templateids"] = templateids
            if search:
                filters["search"] = search
            if filter_params:
                filters["filter"] = filter_params

            async with ZabbixClient(config) as api:
                if count_output:
                    return {"total": await fetch_total(api.discoveryrule, filters)}

                rows, total = await fetch_page(
                    api.discoveryrule,
                    filters=filters,
                    shape=shape,
                    sort=sort,
                    id_field="itemid",
                    limit=limit,
                    offset=offset,
                )
                return {
                    "discoveryrules": rows,
                    "count": len(rows),
                    "total": total,
                    "limit": limit,
                    "offset": offset,
                    "has_more": offset + len(rows) < total,
                }
        except Exception as e:
            await fail(ctx, "Error retrieving discovery rules", e)

    @mcp.tool(
        tags={"zabbix", "drule", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def drule_get(
        ctx: Context,
        druleids: Annotated[list[str] | None, Field(default=None)] = None,
        search: Annotated[dict[str, str] | None, Field(default=None)] = None,
        filter_params: Annotated[dict[str, Any] | None, Field(default=None)] = None,
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
                default="druleid",
                description="Field to sort by. A deterministic sort is required for paging to be consistent.",
            ),
        ] = "druleid",
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
        Get network discovery rules from Zabbix.

        Network discovery (drule) rules perform network scanning to discover hosts and services.
        They can scan for active devices, open ports, and available services in CIDR ranges.

        Args:
            druleids: List of network discovery rule IDs to get. If empty, returns all rules.
            search: Dictionary with search criteria like {'name': 'LAN'}.
            filter_params: Additional filter parameters for advanced filtering.
            limit: Maximum number of results to return (default 100). Set higher for more results.
            offset: Number of matching records to skip, for paging.

        Returns:
            dict: Contains 'drules' list with network discovery rule objects, 'count',
                  'total' matching records, the applied 'limit' and 'offset', and
                  'has_more' indicating whether further pages exist.
                  Each rule includes:
                  - druleid: Discovery rule ID
                  - name: Rule name
                  - status: 0=enabled, 1=disabled

        Note: Network discovery performs network scans. Use carefully to avoid performance impact.
        """
        try:
            await ctx.info("Retrieving network discovery rules...")
            # Sorting is kept out of 'filters' because Zabbix rejects
            # countOutput combined with sortfield.
            sort: dict[str, Any] = {"sortfield": sortfield, "sortorder": sortorder}
            filters: dict[str, Any] = {}
            shape: dict[str, Any] = {"output": output}
            if druleids:
                filters["druleids"] = druleids
            if search:
                filters["search"] = search
            if filter_params:
                filters["filter"] = filter_params

            async with ZabbixClient(config) as api:
                if count_output:
                    return {"total": await fetch_total(api.drule, filters)}

                rows, total = await fetch_page(
                    api.drule,
                    filters=filters,
                    shape=shape,
                    sort=sort,
                    id_field="druleid",
                    limit=limit,
                    offset=offset,
                )
                return {
                    "drules": rows,
                    "count": len(rows),
                    "total": total,
                    "limit": limit,
                    "offset": offset,
                    "has_more": offset + len(rows) < total,
                }
        except Exception as e:
            await fail(ctx, "Error retrieving network discovery rules", e)
