"""
Zabbix MCP Server Triggers Tools
"""

from typing import Annotated
from typing import Any

from fastmcp import Context
from pydantic import Field

from zabbix_mcp.models import ZabbixConfig
from zabbix_mcp.zabbix_client import ZabbixClient


def register_triggers_tools(mcp, config: ZabbixConfig):
    """Register Zabbix triggers tools with the MCP server"""

    @mcp.tool(
        tags={"zabbix", "trigger", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def trigger_get(
        ctx: Context,
        triggerids: Annotated[list[str] | None, Field(default=None)] = None,
        hostids: Annotated[list[str] | None, Field(default=None)] = None,
        groupids: Annotated[list[str] | None, Field(default=None)] = None,
        templateids: Annotated[list[str] | None, Field(default=None)] = None,
        search: Annotated[dict[str, str] | None, Field(default=None)] = None,
        filter_params: Annotated[dict[str, Any] | None, Field(default=None)] = None,
        description_contains: Annotated[
            str | None,
            Field(
                default=None,
                description="Shortcut to search for triggers by description (name) (constructs search={'description': description_contains}).",
            ),
        ] = None,
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
        only_true: Annotated[
            bool,
            Field(default=False, description="Only return triggers in problem state."),
        ] = False,
        min_severity: Annotated[
            int | None, Field(default=None, description="Minimum severity (0-5).")
        ] = None,
        select_hosts: Annotated[
            bool,
            Field(
                default=False,
                description="If true, include the hosts each trigger belongs to in the response (selectHosts=extend).",
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
        Get triggers from Zabbix.

        Triggers are rules that define when a problem occurs based on item values. They evaluate
        expressions against collected metrics and transition between problem and normal states.

        Args:
            triggerids: List of trigger IDs to get. If empty, returns all triggers.
            hostids: List of host IDs to get triggers from.
            groupids: List of group IDs to get triggers from hosts in those groups.
            templateids: List of template IDs to get triggers from those templates.
            search: Dictionary with search criteria like {'description': 'CPU'}.
            filter_params: Additional filter parameters for advanced filtering.
            description_contains: Shortcut to search for triggers by description (name) (adds to 'search').
            limit: Maximum number of results to return (default 100). Set higher for more results.
            offset: Number of results to skip for pagination. Use with sortfield.
            only_true: If true, only return triggers currently in problem state.
            min_severity: Minimum severity level (0=Not classified, 1=Information, 2=Warning,
                         3=Average, 4=High, 5=Disaster). Returns triggers of this severity or higher.
            select_hosts: If true, each trigger includes a 'hosts' list with hostid and host name.
                         Eliminates the need for separate host lookups.

        Returns:
            dict: Contains 'triggers' list with trigger objects, 'count' of results returned,
                  and pagination metadata ('limit', 'offset').
                  Each trigger includes:
                  - triggerid: Unique trigger ID
                  - description: Trigger name/description
                  - expression: Trigger expression/condition
                  - state: 0=normal, 1=problem
                  - value: 0=normal, 1=problem
                  - severity: Severity level (0-5)

        Note: Use trigger_create to define new monitoring rules, trigger_delete to remove them.
        """
        try:
            await ctx.info("Retrieving triggers...")
            params: dict[str, Any] = {"output": output}
            if sortfield:
                params["sortfield"] = sortfield
            if sortorder:
                params["sortorder"] = sortorder
            if count_output:
                params["countOutput"] = True
            if triggerids:
                params["triggerids"] = triggerids
            if hostids:
                params["hostids"] = hostids
            if groupids:
                params["groupids"] = groupids
            if templateids:
                params["templateids"] = templateids
            _search = dict(search) if search is not None else {}
            if description_contains is not None:
                _search["description"] = description_contains
            if _search:
                params["search"] = _search
            if filter_params:
                params["filter"] = filter_params
            params["limit"] = limit
            if offset > 0:
                params["offset"] = offset
            if only_true:
                params["only_true"] = only_true
            if min_severity is not None:
                params["min_severity"] = min_severity
            if select_hosts:
                params["selectHosts"] = "extend"

            async with ZabbixClient(config) as api:
                result = await api.trigger.get(**params)
                return {
                    "triggers": result,
                    "count": int(result) if count_output else len(result),
                    "limit": limit,
                    "offset": offset,
                }
        except Exception as e:
            await ctx.error(f"Error retrieving triggers: {e!s}")
            return {"error": str(e)}

    @mcp.tool(
        tags={"zabbix", "trigger"},
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
        },
    )
    async def trigger_create(
        ctx: Context,
        description: Annotated[str, Field(description="Trigger description/name.")],
        expression: Annotated[str, Field(description="Trigger expression.")],
        priority: Annotated[int, Field(default=0, description="Severity 0-5.")] = 0,
        status: Annotated[
            int, Field(default=0, description="0=enabled, 1=disabled.")
        ] = 0,
        comments: Annotated[str | None, Field(default=None)] = None,
    ) -> dict:
        """
        Create a new trigger in Zabbix.

        Triggers define the conditions under which problems are detected. They use expressions
        to evaluate item values and determine when to transition from normal to problem state.

        Args:
            description: Trigger name displayed in the UI. Example: 'High CPU load', 'Disk space low'.
                        Be descriptive so operators understand what it detects.
            expression: Trigger expression evaluating item values. Example: 'last(/Zabbix server/system.cpu.load[all,avg1])>0)'.
                       Use Zabbix expression syntax with item references and comparison operators.
                       Macro functions like last(), avg(), max() are supported.
            priority: Severity level (0=Not classified, 1=Information, 2=Warning, 3=Average,
                     4=High, 5=Disaster). Default is 0. Higher severity triggers get more visibility.
            status: 0=enabled (active monitoring), 1=disabled (no alerts). Default is 0.
            comments: Optional comment/notes about the trigger explaining its purpose and context.

        Returns:
            dict: Contains 'triggerids' list with newly created trigger ID(s) and 'success' flag.

        Note: Ensure expression references valid items. Use multiple conditions combined with operators
              like 'and', 'or' for complex logic. Test trigger before enabling in production.
        """
        try:
            await ctx.info(f"Creating trigger '{description}'...")
            params: dict[str, Any] = {
                "description": description,
                "expression": expression,
                "priority": priority,
                "status": status,
            }
            if comments:
                params["comments"] = comments

            async with ZabbixClient(config) as api:
                result = await api.trigger.create(**params)
                return {"triggerids": result.get("triggerids", []), "success": True}
        except Exception as e:
            await ctx.error(f"Error creating trigger: {e!s}")
            return {"error": str(e)}

    @mcp.tool(
        tags={"zabbix", "trigger"},
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
        },
    )
    async def trigger_update(
        ctx: Context,
        triggerid: Annotated[str, Field(description="ID of the trigger to update.")],
        description: Annotated[str | None, Field(default=None)] = None,
        expression: Annotated[str | None, Field(default=None)] = None,
        priority: Annotated[int | None, Field(default=None)] = None,
        status: Annotated[
            int | None,
            Field(default=None, description="0=enabled, 1=disabled."),
        ] = None,
        comments: Annotated[str | None, Field(default=None)] = None,
    ) -> dict:
        """
        Update an existing trigger in Zabbix.

        Modifies properties of an existing trigger. You can change the description,
        expression, priority, status, or comments. Only specify fields you want to change.

        Args:
            triggerid: ID of the trigger to update (required). Find it with trigger_get.
            description: New trigger name/description.
            expression: New trigger expression.
            priority: New severity level (0-5).
            status: New status: 0=enabled, 1=disabled.
            comments: New comments/notes.

        Returns:
            dict: Contains 'triggerids' list with updated trigger IDs and 'success' flag.
                  On error, contains 'error' key with the error message.
        """
        try:
            await ctx.info(f"Updating trigger {triggerid}...")
            params: dict[str, Any] = {"triggerid": triggerid}
            if description is not None:
                params["description"] = description
            if expression is not None:
                params["expression"] = expression
            if priority is not None:
                params["priority"] = priority
            if status is not None:
                params["status"] = status
            if comments is not None:
                params["comments"] = comments

            async with ZabbixClient(config) as api:
                result = await api.trigger.update(**params)
                return {"triggerids": result.get("triggerids", []), "success": True}
        except Exception as e:
            await ctx.error(f"Error updating trigger: {e!s}")
            return {"error": str(e)}

    @mcp.tool(
        tags={"zabbix", "trigger"},
        annotations={
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
        },
    )
    async def trigger_delete(
        ctx: Context,
        triggerids: Annotated[list[str], Field(description="Trigger IDs to delete.")],
    ) -> dict:
        """
        Delete triggers from Zabbix.

        Permanently removes one or more triggers. Hosts will no longer generate alerts for these
        conditions. Historical trigger data and associated problems are typically retained.

        Args:
            triggerids: List of trigger IDs to delete. Find them with trigger_get.

        Returns:
            dict: Contains 'triggerids' list with deleted trigger IDs and 'success' flag.
                  On error, contains 'error' key with the error message.

        Warning: Deleting a trigger stops all alerts and problem detection for that condition.
                 Consider disabling instead (set status=1) if you might need to re-enable it later.
        """
        try:
            await ctx.info(f"Deleting triggers: {triggerids}...")
            async with ZabbixClient(config) as api:
                result = await api.trigger.delete(*triggerids)
                return {"triggerids": result.get("triggerids", []), "success": True}
        except Exception as e:
            await ctx.error(f"Error deleting triggers: {e!s}")
            return {"error": str(e)}

    ##########################
    # Problem Tools
    ##########################
