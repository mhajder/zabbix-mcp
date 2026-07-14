"""
Zabbix MCP Server Macros Tools
"""

from typing import Annotated
from typing import Any

from fastmcp import Context
from pydantic import Field

from zabbix_mcp.models import ZabbixConfig
from zabbix_mcp.zabbix_client import ZabbixClient


def register_macros_tools(mcp, config: ZabbixConfig):
    """Register Zabbix macros tools with the MCP server"""

    @mcp.tool(
        tags={"zabbix", "usermacro", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def usermacro_get(
        ctx: Context,
        hostmacroids: Annotated[list[str] | None, Field(default=None)] = None,
        globalmacroids: Annotated[list[str] | None, Field(default=None)] = None,
        hostids: Annotated[list[str] | None, Field(default=None)] = None,
        templateids: Annotated[list[str] | None, Field(default=None)] = None,
        globalmacro: Annotated[
            bool, Field(default=False, description="Return global macros.")
        ] = False,
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
        Get user macros from Zabbix.

        User macros are variables that can be referenced in items, triggers, and scripts.
        They allow parameterization of monitoring configurations with custom values.

        Args:
            hostmacroids: List of host macro IDs to get.
            globalmacroids: List of global macro IDs to get.
            hostids: List of host IDs to get macros from.
            templateids: List of template IDs to get macros from.
            globalmacro: If true, return global macros (available to all hosts).
            search: Dictionary with search criteria like {'macro': '{$THRESHOLD}'}.
            filter_params: Additional filter parameters for advanced filtering.
            limit: Maximum number of results to return (default 100). Set higher for more results.
            offset: Number of results to skip for pagination. Use with sortfield.

        Returns:
            dict: Contains 'macros' list with macro objects, 'count' of returned macros,
                  and pagination metadata ('limit', 'offset').
                  Each macro includes:
                  - hostmacrois/globalmacrois: Macro ID
                  - macro: Macro name/identifier
                  - value: Macro value
                  - description: Optional description

        Note: Use {$MACRO_NAME} syntax in items and triggers to reference macros. Global macros apply to all hosts.
        """
        try:
            await ctx.info("Retrieving user macros...")
            params: dict[str, Any] = {"output": output}
            if sortfield:
                params["sortfield"] = sortfield
            if sortorder:
                params["sortorder"] = sortorder
            if count_output:
                params["countOutput"] = True
            if hostmacroids:
                params["hostmacroids"] = hostmacroids
            if globalmacroids:
                params["globalmacroids"] = globalmacroids
            if hostids:
                params["hostids"] = hostids
            if templateids:
                params["templateids"] = templateids
            if globalmacro:
                params["globalmacro"] = globalmacro
            if search:
                params["search"] = search
            if filter_params:
                params["filter"] = filter_params

            params["limit"] = limit
            if offset > 0:
                params["offset"] = offset

            async with ZabbixClient(config) as api:
                result = await api.usermacro.get(**params)
                return {
                    "macros": result,
                    "count": int(result) if count_output else len(result),
                    "limit": limit,
                    "offset": offset,
                }
        except Exception as e:
            await ctx.error(f"Error retrieving user macros: {e!s}")
            return {"error": str(e)}

    @mcp.tool(
        tags={"zabbix", "usermacro"},
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
        },
    )
    async def usermacro_create(
        ctx: Context,
        hostid: Annotated[str, Field(description="Host ID for the macro.")],
        macro: Annotated[str, Field(description="Macro name (e.g., {$MYMACRO}).")],
        value: Annotated[str, Field(description="Macro value.")],
        type_: Annotated[
            int, Field(default=0, description="0=text, 1=secret, 2=vault.")
        ] = 0,
        description: Annotated[str | None, Field(default=None)] = None,
    ) -> dict:
        """
        Create a new host macro in Zabbix.

        Host macros define custom variables for specific hosts. They can be referenced in items
        and triggers using {$MACRO_NAME} syntax, allowing dynamic configuration without editing items.

        Args:
            hostid: ID of the host to create the macro for. Find with host_get.
            macro: Macro name in format {$NAME}. Must be uppercase alphanumeric with underscores.
                   Example: {$THRESHOLD}, {$API_KEY}.
            value: Macro value - the actual value substituted when referenced.
            type_: Macro type:
                   - 0 = Text (plain value)
                   - 1 = Secret (sensitive value, hidden in UI)
                   - 2 = Vault (secret from external vault system)
                   Default is 0 (text).
            description: Optional description explaining the macro's purpose.

        Returns:
            dict: Contains 'hostmacroids' list with newly created macro ID(s) and 'success' flag.

        Note: Use {$MACRO_NAME} in item keys and trigger expressions. Global macros use different API.
        """
        try:
            await ctx.info(f"Creating macro '{macro}'...")
            params: dict[str, Any] = {
                "hostid": hostid,
                "macro": macro,
                "value": value,
                "type": type_,
            }
            if description:
                params["description"] = description

            async with ZabbixClient(config) as api:
                result = await api.usermacro.create(**params)
                return {"hostmacroids": result.get("hostmacroids", []), "success": True}
        except Exception as e:
            await ctx.error(f"Error creating macro: {e!s}")
            return {"error": str(e)}

    @mcp.tool(
        tags={"zabbix", "usermacro"},
        annotations={
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
        },
    )
    async def usermacro_delete(
        ctx: Context,
        hostmacroids: Annotated[
            list[str], Field(description="Host macro IDs to delete.")
        ],
    ) -> dict:
        """
        Delete host macros from Zabbix.

        Permanently removes host-level macro definitions. Items and triggers using this macro
        will no longer be able to reference it, potentially causing parsing errors.

        Args:
            hostmacroids: List of host macro IDs to delete. Find them with usermacro_get.

        Returns:
            dict: Contains 'hostmacroids' list with deleted macro IDs and 'success' flag.
                  On error, contains 'error' key with the error message.

        Warning: Deleting a macro may break items/triggers that reference it. Verify impact before deletion.
        """
        try:
            await ctx.info(f"Deleting macros: {hostmacroids}...")
            async with ZabbixClient(config) as api:
                result = await api.usermacro.delete(*hostmacroids)
                return {"hostmacroids": result.get("hostmacroids", []), "success": True}
        except Exception as e:
            await ctx.error(f"Error deleting macros: {e!s}")
            return {"error": str(e)}
