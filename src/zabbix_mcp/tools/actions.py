"""
Zabbix MCP Server Actions Tools
"""

from typing import Annotated
from typing import Any

from fastmcp import Context
from pydantic import Field

from zabbix_mcp.models import ZabbixConfig
from zabbix_mcp.tools.pagination import fetch_page
from zabbix_mcp.tools.pagination import fetch_total
from zabbix_mcp.zabbix_client import ZabbixClient


def register_actions_tools(mcp, config: ZabbixConfig):
    """Register Zabbix actions tools with the MCP server"""

    @mcp.tool(
        tags={"zabbix", "action", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def action_get(
        ctx: Context,
        actionids: Annotated[list[str] | None, Field(default=None)] = None,
        groupids: Annotated[list[str] | None, Field(default=None)] = None,
        hostids: Annotated[list[str] | None, Field(default=None)] = None,
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
                default="actionid",
                description="Field to sort by. A deterministic sort is required for paging to be consistent.",
            ),
        ] = "actionid",
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
        Get actions from Zabbix.

        Actions define automated responses to problems/triggers. They specify what happens when
        problems occur - sending notifications, executing remote commands, etc.

        Args:
            actionids: List of action IDs to get. If empty, returns all actions.
            groupids: List of host group IDs to get actions for.
            hostids: List of host IDs to get actions for.
            search: Dictionary with search criteria like {'name': 'notify'}.
            filter_params: Additional filter parameters for advanced filtering.
            limit: Maximum number of results to return (default 100). Set higher for more results.
            offset: Number of matching records to skip, for paging.

        Returns:
            dict: Contains 'actions' list with action objects, 'count' of returned actions,
                  'total' matching records, the applied 'limit' and 'offset', and
                  'has_more' indicating whether further pages exist.
                  Each action includes:
                  - actionid: Unique action ID
                  - name: Action name/description
                  - status: 0=enabled, 1=disabled
                  - esc_period: Escalation period

        Note: Actions are triggered when problem conditions are met. Use with caution in production.
        """
        try:
            await ctx.info("Retrieving actions...")
            # Sorting is kept out of 'filters' because Zabbix rejects
            # countOutput combined with sortfield.
            sort: dict[str, Any] = {"sortfield": sortfield, "sortorder": sortorder}
            filters: dict[str, Any] = {}
            shape: dict[str, Any] = {"output": output}
            if actionids:
                filters["actionids"] = actionids
            if groupids:
                filters["groupids"] = groupids
            if hostids:
                filters["hostids"] = hostids
            if search:
                filters["search"] = search
            if filter_params:
                filters["filter"] = filter_params

            async with ZabbixClient(config) as api:
                if count_output:
                    return {"total": await fetch_total(api.action, filters)}

                rows, total = await fetch_page(
                    api.action,
                    filters=filters,
                    shape=shape,
                    sort=sort,
                    id_field="actionid",
                    limit=limit,
                    offset=offset,
                )
                return {
                    "actions": rows,
                    "count": len(rows),
                    "total": total,
                    "limit": limit,
                    "offset": offset,
                    "has_more": offset + len(rows) < total,
                }
        except Exception as e:
            await ctx.error(f"Error retrieving actions: {e!s}")
            return {"error": str(e)}

    ##########################
    # Media Type Tools
    ##########################
