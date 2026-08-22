"""
Zabbix MCP Server Graphs Tools
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


def register_graphs_tools(mcp, config: ZabbixConfig):
    """Register Zabbix graphs tools with the MCP server"""

    @mcp.tool(
        tags={"zabbix", "graph", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def graph_get(
        ctx: Context,
        graphids: Annotated[list[str] | None, Field(default=None)] = None,
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
        select_items: Annotated[
            bool,
            Field(
                default=False,
                description="If true, include the items contained in each graph (selectGraphItems=extend).",
            ),
        ] = False,
        select_hosts: Annotated[
            bool,
            Field(
                default=False,
                description="If true, include the hosts that the graphs belong to (selectHosts=extend).",
            ),
        ] = False,
        select_templates: Annotated[
            bool,
            Field(
                default=False,
                description="If true, include the templates that the graphs belong to (selectTemplates=extend).",
            ),
        ] = False,
        sortfield: Annotated[
            str,
            Field(
                default="graphid",
                description="Field to sort by. A deterministic sort is required for paging to be consistent.",
            ),
        ] = "graphid",
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
        Get graphs from Zabbix.

        Graphs visualize item data over time, displaying metric values in line/bar/pie charts.
        Graphs can be included in dashboards, reports, and custom views for data analysis.

        Args:
            graphids: List of graph IDs to get. If empty, returns all graphs.
            hostids: List of host IDs to get graphs from.
            templateids: List of template IDs to get graphs from.
            search: Dictionary with search criteria like {'name': 'CPU'}.
            filter_params: Additional filter parameters for advanced filtering.
            limit: Maximum number of results to return (default 100). Set higher for more results.
            offset: Number of matching records to skip, for paging.
            select_items: If true, each graph includes a 'gitems' list with graph items.
            select_hosts: If true, each graph includes a 'hosts' list.
            select_templates: If true, each graph includes a 'templates' list.

        Returns:
            dict: Contains 'graphs' list with graph objects, 'count' of returned graphs,
                  'total' matching records, the applied 'limit' and 'offset', and
                  'has_more' indicating whether further pages exist.
                  Each graph includes:
                  - graphid: Unique graph ID
                  - name: Graph name
                  - type: Graph type (0=normal line, 1=stacked line, 2=bar, 3=pie)

        Note: Graphs display collected item data. Use for visualization and dashboard creation.
        """
        try:
            await ctx.info("Retrieving graphs...")
            # Sorting is kept out of 'filters' because Zabbix rejects
            # countOutput combined with sortfield.
            sort: dict[str, Any] = {"sortfield": sortfield, "sortorder": sortorder}
            filters: dict[str, Any] = {}
            shape: dict[str, Any] = {"output": output}
            if graphids:
                filters["graphids"] = graphids
            if hostids:
                filters["hostids"] = hostids
            if templateids:
                filters["templateids"] = templateids
            if search:
                filters["search"] = search
            if filter_params:
                filters["filter"] = filter_params
            if select_items:
                shape["selectGraphItems"] = "extend"
            if select_hosts:
                shape["selectHosts"] = "extend"
            if select_templates:
                shape["selectTemplates"] = "extend"

            async with ZabbixClient(config) as api:
                if count_output:
                    return {"total": await fetch_total(api.graph, filters)}

                rows, total = await fetch_page(
                    api.graph,
                    filters=filters,
                    shape=shape,
                    sort=sort,
                    id_field="graphid",
                    limit=limit,
                    offset=offset,
                )
                return {
                    "graphs": rows,
                    "count": len(rows),
                    "total": total,
                    "limit": limit,
                    "offset": offset,
                    "has_more": offset + len(rows) < total,
                }
        except Exception as e:
            await fail(ctx, "Error retrieving graphs", e)

    ##########################
    # Discovery Tools
    ##########################
