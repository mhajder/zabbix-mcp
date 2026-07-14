"""
Zabbix MCP Server Actions Tools
"""

from typing import Annotated
from typing import Any

from fastmcp import Context
from pydantic import Field

from zabbix_mcp.models import ZabbixConfig
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
            offset: Number of results to skip for pagination. Use with sortfield.

        Returns:
            dict: Contains 'actions' list with action objects, 'count' of returned actions,
                  and pagination metadata ('limit', 'offset').
                  Each action includes:
                  - actionid: Unique action ID
                  - name: Action name/description
                  - status: 0=enabled, 1=disabled
                  - esc_period: Escalation period

        Note: Actions are triggered when problem conditions are met. Use with caution in production.
        """
        try:
            await ctx.info("Retrieving actions...")
            params: dict[str, Any] = {"output": output}
            if sortfield:
                params["sortfield"] = sortfield
            if sortorder:
                params["sortorder"] = sortorder
            if count_output:
                params["countOutput"] = True
            if actionids:
                params["actionids"] = actionids
            if groupids:
                params["groupids"] = groupids
            if hostids:
                params["hostids"] = hostids
            if search:
                params["search"] = search
            if filter_params:
                params["filter"] = filter_params

            params["limit"] = limit
            if offset > 0:
                params["offset"] = offset

            async with ZabbixClient(config) as api:
                result = await api.action.get(**params)
                return {
                    "actions": result,
                    "count": int(result) if count_output else len(result),
                    "limit": limit,
                    "offset": offset,
                }
        except Exception as e:
            await ctx.error(f"Error retrieving actions: {e!s}")
            return {"error": str(e)}

    ##########################
    # Media Type Tools
    ##########################
