"""
Zabbix MCP Server Graphs Tools
"""

from typing import Annotated
from typing import Any

from fastmcp import Context
from pydantic import Field

from zabbix_mcp.models import ZabbixConfig
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
                description="Number of results to skip (for pagination). Requires sortfield to be set.",
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
            offset: Number of results to skip for pagination. Use with sortfield.
            select_items: If true, each graph includes a 'gitems' list with graph items.
            select_hosts: If true, each graph includes a 'hosts' list.
            select_templates: If true, each graph includes a 'templates' list.

        Returns:
            dict: Contains 'graphs' list with graph objects, 'count' of returned graphs,
                  and pagination metadata ('limit', 'offset').
                  Each graph includes:
                  - graphid: Unique graph ID
                  - name: Graph name
                  - type: Graph type (0=normal line, 1=stacked line, 2=bar, 3=pie)

        Note: Graphs display collected item data. Use for visualization and dashboard creation.
        """
        try:
            await ctx.info("Retrieving graphs...")
            params: dict[str, Any] = {"output": output}
            if sortfield:
                params["sortfield"] = sortfield
            if sortorder:
                params["sortorder"] = sortorder
            if count_output:
                params["countOutput"] = True
            if graphids:
                params["graphids"] = graphids
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
            if select_items:
                params["selectGraphItems"] = "extend"
            if select_hosts:
                params["selectHosts"] = "extend"
            if select_templates:
                params["selectTemplates"] = "extend"

            async with ZabbixClient(config) as api:
                result = await api.graph.get(**params)
                return {
                    "graphs": result,
                    "count": int(result) if count_output else len(result),
                    "limit": limit,
                    "offset": offset,
                }
        except Exception as e:
            await ctx.error(f"Error retrieving graphs: {e!s}")
            return {"error": str(e)}

    ##########################
    # Discovery Tools
    ##########################
