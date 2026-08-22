"""
Zabbix MCP Server Sla Tools
"""

from typing import Annotated
from typing import Any

from fastmcp import Context
from pydantic import Field

from zabbix_mcp.models import ZabbixConfig
from zabbix_mcp.tools.pagination import fetch_page
from zabbix_mcp.tools.pagination import fetch_total
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
                description="Number of matching records to skip. Use with 'limit' to page through results; check 'has_more' and 'total' in the response.",
                ge=0,
            ),
        ] = 0,
        sortfield: Annotated[
            str,
            Field(
                default="slaid",
                description="Field to sort by. A deterministic sort is required for paging to be consistent.",
            ),
        ] = "slaid",
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
            offset: Number of matching records to skip, for paging.

        Returns:
            dict: Contains 'slas' list with SLA objects, 'count' of returned SLAs,
                  'total' matching records, the applied 'limit' and 'offset', and
                  'has_more' indicating whether further pages exist.
                  Each SLA includes:
                  - slaid: Unique SLA ID
                  - name: SLA name
                  - slo: Service Level Objective percentage target
                  - status: 0=enabled, 1=disabled

        Note: SLAs measure service availability. Track compliance and generate reports.
        """
        try:
            await ctx.info("Retrieving SLAs...")
            # Sorting is kept out of 'filters' because Zabbix rejects
            # countOutput combined with sortfield.
            sort: dict[str, Any] = {"sortfield": sortfield, "sortorder": sortorder}
            filters: dict[str, Any] = {}
            shape: dict[str, Any] = {"output": output}
            if slaids:
                filters["slaids"] = slaids
            if serviceids:
                filters["serviceids"] = serviceids
            if search:
                filters["search"] = search
            if filter_params:
                filters["filter"] = filter_params

            async with ZabbixClient(config) as api:
                if count_output:
                    return {"total": await fetch_total(api.sla, filters)}

                rows, total = await fetch_page(
                    api.sla,
                    filters=filters,
                    shape=shape,
                    sort=sort,
                    id_field="slaid",
                    limit=limit,
                    offset=offset,
                )
                return {
                    "slas": rows,
                    "count": len(rows),
                    "total": total,
                    "limit": limit,
                    "offset": offset,
                    "has_more": offset + len(rows) < total,
                }
        except Exception as e:
            await ctx.error(f"Error retrieving SLAs: {e!s}")
            return {"error": str(e)}
