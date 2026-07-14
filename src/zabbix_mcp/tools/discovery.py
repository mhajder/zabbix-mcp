"""
Zabbix MCP Server Discovery Tools
"""

from typing import Annotated
from typing import Any

from fastmcp import Context
from pydantic import Field

from zabbix_mcp.models import ZabbixConfig
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
            offset: Number of results to skip for pagination. Use with sortfield.

        Returns:
            dict: Contains 'discoveryrules' list with discovery rule objects, 'count',
                  and pagination metadata ('limit', 'offset').
                  Each rule includes:
                  - itemid: Discovery rule item ID
                  - name: Discovery rule name
                  - key_: Discovery rule key
                  - type: Discovery method (0=Zabbix agent, 2=SNMP, etc.)

        Note: Discovery rules generate items and triggers dynamically. Monitor their status and adjust as needed.
        """
        try:
            await ctx.info("Retrieving discovery rules...")
            params: dict[str, Any] = {"output": output}
            if sortfield:
                params["sortfield"] = sortfield
            if sortorder:
                params["sortorder"] = sortorder
            if count_output:
                params["countOutput"] = True
            if itemids:
                params["itemids"] = itemids
            if hostids:
                params["hostids"] = hostids
            if templateids:
                params["templateids"] = templateids
            if search:
                params["search"] = search
            if filter_params:
                params["filter"] = filter_params

            params["limit"] = limit
            if offset > 0:
                params["offset"] = offset

            async with ZabbixClient(config) as api:
                result = await api.discoveryrule.get(**params)
                return {
                    "discoveryrules": result,
                    "count": int(result) if count_output else len(result),
                    "limit": limit,
                    "offset": offset,
                }
        except Exception as e:
            await ctx.error(f"Error retrieving discovery rules: {e!s}")
            return {"error": str(e)}

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
        Get network discovery rules from Zabbix.

        Network discovery (drule) rules perform network scanning to discover hosts and services.
        They can scan for active devices, open ports, and available services in CIDR ranges.

        Args:
            druleids: List of network discovery rule IDs to get. If empty, returns all rules.
            search: Dictionary with search criteria like {'name': 'LAN'}.
            filter_params: Additional filter parameters for advanced filtering.
            limit: Maximum number of results to return (default 100). Set higher for more results.
            offset: Number of results to skip for pagination. Use with sortfield.

        Returns:
            dict: Contains 'drules' list with network discovery rule objects, 'count',
                  and pagination metadata ('limit', 'offset').
                  Each rule includes:
                  - druleid: Discovery rule ID
                  - name: Rule name
                  - status: 0=enabled, 1=disabled

        Note: Network discovery performs network scans. Use carefully to avoid performance impact.
        """
        try:
            await ctx.info("Retrieving network discovery rules...")
            params: dict[str, Any] = {"output": output}
            if sortfield:
                params["sortfield"] = sortfield
            if sortorder:
                params["sortorder"] = sortorder
            if count_output:
                params["countOutput"] = True
            if druleids:
                params["druleids"] = druleids
            if search:
                params["search"] = search
            if filter_params:
                params["filter"] = filter_params

            params["limit"] = limit
            if offset > 0:
                params["offset"] = offset

            async with ZabbixClient(config) as api:
                result = await api.drule.get(**params)
                return {
                    "drules": result,
                    "count": int(result) if count_output else len(result),
                    "limit": limit,
                    "offset": offset,
                }
        except Exception as e:
            await ctx.error(f"Error retrieving network discovery rules: {e!s}")
            return {"error": str(e)}
