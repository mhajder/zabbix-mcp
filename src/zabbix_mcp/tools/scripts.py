"""
Zabbix MCP Server Scripts Tools
"""

from typing import Annotated
from typing import Any

from fastmcp import Context
from pydantic import Field

from zabbix_mcp.models import ZabbixConfig
from zabbix_mcp.zabbix_client import ZabbixClient


def register_scripts_tools(mcp, config: ZabbixConfig):
    """Register Zabbix scripts tools with the MCP server"""

    @mcp.tool(
        tags={"zabbix", "script", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def script_get(
        ctx: Context,
        scriptids: Annotated[list[str] | None, Field(default=None)] = None,
        hostids: Annotated[list[str] | None, Field(default=None)] = None,
        groupids: Annotated[list[str] | None, Field(default=None)] = None,
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
        Get scripts from Zabbix.

        Scripts are custom automation routines that can be executed on monitored hosts or the server.
        They can be triggered manually or by actions to automate remediation or configuration tasks.

        Args:
            scriptids: List of script IDs to get. If empty, returns all scripts.
            hostids: List of host IDs to get scripts for.
            groupids: List of group IDs to get scripts for hosts in those groups.
            search: Dictionary with search criteria like {'name': 'restart'}.
            filter_params: Additional filter parameters for advanced filtering.
            limit: Maximum number of results to return (default 100). Set higher for more results.
            offset: Number of results to skip for pagination. Use with sortfield.

        Returns:
            dict: Contains 'scripts' list with script objects, 'count' of returned scripts,
                  and pagination metadata ('limit', 'offset').
                  Each script includes:
                  - scriptid: Unique script ID
                  - name: Script name
                  - command: Script command or code

        Note: Scripts can be run manually or triggered by actions. Use for automation and remediation.
        """
        try:
            await ctx.info("Retrieving scripts...")
            params: dict[str, Any] = {"output": output}
            if sortfield:
                params["sortfield"] = sortfield
            if sortorder:
                params["sortorder"] = sortorder
            if count_output:
                params["countOutput"] = True
            if scriptids:
                params["scriptids"] = scriptids
            if hostids:
                params["hostids"] = hostids
            if groupids:
                params["groupids"] = groupids
            if search:
                params["search"] = search
            if filter_params:
                params["filter"] = filter_params

            params["limit"] = limit
            if offset > 0:
                params["offset"] = offset

            async with ZabbixClient(config) as api:
                result = await api.script.get(**params)
                return {
                    "scripts": result,
                    "count": int(result) if count_output else len(result),
                    "limit": limit,
                    "offset": offset,
                }
        except Exception as e:
            await ctx.error(f"Error retrieving scripts: {e!s}")
            return {"error": str(e)}

    @mcp.tool(
        tags={"zabbix", "script"},
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
        },
    )
    async def script_execute(
        ctx: Context,
        scriptid: Annotated[str, Field(description="Script ID to execute.")],
        hostid: Annotated[str, Field(description="Host ID to execute the script on.")],
    ) -> dict:
        """
        Execute a script on a host in Zabbix.

        Runs a custom script on a specified host. Used for executing remediation tasks,
        configuration changes, or diagnostic commands remotely.

        Args:
            scriptid: ID of the script to execute. Find with script_get.
            hostid: ID of the host to run the script on.

        Returns:
            dict: Contains execution result with status and any output from the script.
                  Returns success flag and response data from the executed script.

        Warning: Script execution happens remotely on the host. Ensure the script is safe
                 and the host has proper agent/connectivity to execute it.
        """
        try:
            await ctx.info(f"Executing script {scriptid} on host {hostid}...")
            async with ZabbixClient(config) as api:
                result = await api.script.execute(scriptid=scriptid, hostid=hostid)
                return {"result": result, "success": True}
        except Exception as e:
            await ctx.error(f"Error executing script: {e!s}")
            return {"error": str(e)}

    ##########################
    # User Macro Tools
    ##########################
