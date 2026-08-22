"""
Zabbix MCP Server Services Tools
"""

from typing import Annotated
from typing import Any

from fastmcp import Context
from pydantic import Field

from zabbix_mcp.models import ZabbixConfig
from zabbix_mcp.tools.pagination import fetch_page
from zabbix_mcp.tools.pagination import fetch_total
from zabbix_mcp.zabbix_client import ZabbixClient


def register_services_tools(mcp, config: ZabbixConfig):
    """Register Zabbix services tools with the MCP server"""

    @mcp.tool(
        tags={"zabbix", "service", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def service_get(
        ctx: Context,
        serviceids: Annotated[list[str] | None, Field(default=None)] = None,
        parentids: Annotated[list[str] | None, Field(default=None)] = None,
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
                default="serviceid",
                description="Field to sort by. A deterministic sort is required for paging to be consistent.",
            ),
        ] = "serviceid",
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
        Get services from Zabbix.

        Services represent business capabilities or applications (e.g., 'Web Application', 'Database').
        Services can depend on other services, creating hierarchies for tracking dependencies.

        Args:
            serviceids: List of service IDs to get. If empty, returns all services.
            parentids: List of parent service IDs to get child services from.
            search: Dictionary with search criteria like {'name': 'API'}.
            filter_params: Additional filter parameters for advanced filtering.
            limit: Maximum number of results to return (default 100). Set higher for more results.
            offset: Number of matching records to skip, for paging.

        Returns:
            dict: Contains 'services' list with service objects, 'count' of returned services,
                  'total' matching records, the applied 'limit' and 'offset', and
                  'has_more' indicating whether further pages exist.
                  Each service includes:
                  - serviceid: Unique service ID
                  - name: Service name
                  - status: Service status/availability

        Note: Services form the basis for SLA tracking. Define service hierarchies for dependency mapping.
        """
        try:
            await ctx.info("Retrieving services...")
            # Sorting is kept out of 'filters' because Zabbix rejects
            # countOutput combined with sortfield.
            sort: dict[str, Any] = {"sortfield": sortfield, "sortorder": sortorder}
            filters: dict[str, Any] = {}
            shape: dict[str, Any] = {"output": output}
            if serviceids:
                filters["serviceids"] = serviceids
            if parentids:
                filters["parentids"] = parentids
            if search:
                filters["search"] = search
            if filter_params:
                filters["filter"] = filter_params

            async with ZabbixClient(config) as api:
                if count_output:
                    return {"total": await fetch_total(api.service, filters)}

                rows, total = await fetch_page(
                    api.service,
                    filters=filters,
                    shape=shape,
                    sort=sort,
                    id_field="serviceid",
                    limit=limit,
                    offset=offset,
                )
                return {
                    "services": rows,
                    "count": len(rows),
                    "total": total,
                    "limit": limit,
                    "offset": offset,
                    "has_more": offset + len(rows) < total,
                }
        except Exception as e:
            await ctx.error(f"Error retrieving services: {e!s}")
            return {"error": str(e)}

    ###########################
    # Script Tools
    ###########################
