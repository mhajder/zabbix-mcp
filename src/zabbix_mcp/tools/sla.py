"""
Zabbix MCP Server Sla Tools
"""

from typing import Annotated
from typing import Any

from fastmcp import Context
from pydantic import Field

from zabbix_mcp.models import ZabbixConfig
from zabbix_mcp.zabbix_client import ZabbixClient


def register_sla_tools(mcp, config: ZabbixConfig):
    """Register Zabbix sla tools with the MCP server"""

    @mcp.tool(
        tags={"zabbix", "sla", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def sla_get(
        ctx: Context,
        slaids: Annotated[list[str] | None, Field(default=None)] = None,
        serviceids: Annotated[list[str] | None, Field(default=None)] = None,
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
        Get SLAs from Zabbix.

        Service Level Agreements (SLAs) define uptime and availability targets for services.
        They track compliance with service objectives and generate reports on availability.

        Args:
            slaids: List of SLA IDs to get. If empty, returns all SLAs.
            serviceids: List of service IDs to get SLAs for.
            search: Dictionary with search criteria like {'name': 'Website'}.
            filter_params: Additional filter parameters for advanced filtering.
            limit: Maximum number of results to return (default 100). Set higher for more results.
            offset: Number of results to skip for pagination. Use with sortfield.

        Returns:
            dict: Contains 'slas' list with SLA objects, 'count' of returned SLAs,
                  and pagination metadata ('limit', 'offset').
                  Each SLA includes:
                  - slaid: Unique SLA ID
                  - name: SLA name
                  - slo: Service Level Objective percentage target
                  - status: 0=enabled, 1=disabled

        Note: SLAs measure service availability. Track compliance and generate reports.
        """
        try:
            await ctx.info("Retrieving SLAs...")
            params: dict[str, Any] = {"output": output}
            if sortfield:
                params["sortfield"] = sortfield
            if sortorder:
                params["sortorder"] = sortorder
            if count_output:
                params["countOutput"] = True
            if slaids:
                params["slaids"] = slaids
            if serviceids:
                params["serviceids"] = serviceids
            if search:
                params["search"] = search
            if filter_params:
                params["filter"] = filter_params

            params["limit"] = limit
            if offset > 0:
                params["offset"] = offset

            async with ZabbixClient(config) as api:
                result = await api.sla.get(**params)
                return {
                    "slas": result,
                    "count": int(result) if count_output else len(result),
                    "limit": limit,
                    "offset": offset,
                }
        except Exception as e:
            await ctx.error(f"Error retrieving SLAs: {e!s}")
            return {"error": str(e)}
