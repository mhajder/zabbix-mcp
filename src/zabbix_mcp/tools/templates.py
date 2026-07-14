"""
Zabbix MCP Server Templates Tools
"""

from typing import Annotated
from typing import Any

from fastmcp import Context
from pydantic import Field

from zabbix_mcp.models import ZabbixConfig
from zabbix_mcp.zabbix_client import ZabbixClient


def register_templates_tools(mcp, config: ZabbixConfig):
    """Register Zabbix templates tools with the MCP server"""

    @mcp.tool(
        tags={"zabbix", "template", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def template_get(
        ctx: Context,
        templateids: Annotated[list[str] | None, Field(default=None)] = None,
        groupids: Annotated[list[str] | None, Field(default=None)] = None,
        hostids: Annotated[list[str] | None, Field(default=None)] = None,
        search: Annotated[dict[str, str] | None, Field(default=None)] = None,
        template_name_contains: Annotated[
            str | None,
            Field(
                default=None,
                description="Shortcut to search for templates by name (constructs search={'host': template_name_contains}).",
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
        select_groups: Annotated[
            bool,
            Field(
                default=False,
                description="If true, include the template groups the templates belong to (selectGroups=extend).",
            ),
        ] = False,
        select_hosts: Annotated[
            bool,
            Field(
                default=False,
                description="If true, include the hosts that are linked to the templates (selectHosts=extend).",
            ),
        ] = False,
        select_templates: Annotated[
            bool,
            Field(
                default=False,
                description="If true, include the templates that are linked to these templates directly (selectTemplates=extend).",
            ),
        ] = False,
        select_macros: Annotated[
            bool,
            Field(
                default=False,
                description="If true, include the macros for the templates (selectMacros=extend).",
            ),
        ] = False,
        select_tags: Annotated[
            bool,
            Field(
                default=False,
                description="If true, include the tags for the templates (selectTags=extend).",
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
        Get templates from Zabbix.

        Templates are reusable collections of items, triggers, and graphs that can be applied to hosts.
        They standardize monitoring across multiple servers with the same role.

        Args:
            templateids: List of template IDs to get. If empty, returns all templates.
                         Find template IDs with a search or from host associations.
            search: Substring search in template name. Matches partial names like 'Linux' finds 'Linux Server Template'.
            template_name_contains: Shortcut to search for templates by name (adds to 'search').
            limit: Maximum number of results to return (default 100). Set higher for more results.
            offset: Number of results to skip for pagination. Use with sortfield.
            select_groups: If true, each template includes a 'groups' list with its template groups.
            select_hosts: If true, each template includes a 'hosts' list with linked hosts.
            select_templates: If true, each template includes a 'templates' list with linked templates.
            select_macros: If true, each template includes a 'macros' list.
            select_tags: If true, each template includes a 'tags' list.

        Returns:
            dict: Contains 'templates' list with template objects, 'count' of results returned,
                  and pagination metadata ('limit', 'offset').
                  Each template object has:
                  - templateid: Unique template ID
                  - name: Template name (e.g., 'Linux Server Template')
                  - description: Optional template description

        Note: Use host_create or host_update with templateids to apply templates to hosts.
        """
        try:
            await ctx.info("Retrieving templates...")
            params: dict[str, Any] = {"output": output}
            if sortfield:
                params["sortfield"] = sortfield
            if sortorder:
                params["sortorder"] = sortorder
            if count_output:
                params["countOutput"] = True
            if templateids:
                params["templateids"] = templateids
            if groupids:
                params["groupids"] = groupids
            if hostids:
                params["hostids"] = hostids
            _search = dict(search) if search is not None else {}
            if template_name_contains is not None:
                _search["host"] = template_name_contains
            if _search:
                params["search"] = _search
            params["limit"] = limit
            if offset > 0:
                params["offset"] = offset
            if select_groups:
                params["selectGroups"] = "extend"
            if select_hosts:
                params["selectHosts"] = "extend"
            if select_templates:
                params["selectTemplates"] = "extend"
            if select_macros:
                params["selectMacros"] = "extend"
            if select_tags:
                params["selectTags"] = "extend"

            async with ZabbixClient(config) as api:
                result = await api.template.get(**params)
                return {
                    "templates": result,
                    "count": int(result) if count_output else len(result),
                    "limit": limit,
                    "offset": offset,
                }
        except Exception as e:
            await ctx.error(f"Error retrieving templates: {e!s}")
            return {"error": str(e)}

    @mcp.tool(
        tags={"zabbix", "template"},
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
        },
    )
    async def template_create(
        ctx: Context,
        host: Annotated[str, Field(description="Technical name of the template.")],
        groups: Annotated[list[dict[str, str]], Field(description="Host groups.")],
        name: Annotated[str | None, Field(default=None)] = None,
        description: Annotated[str | None, Field(default=None)] = None,
    ) -> dict:
        """
        Create a new template in Zabbix.

        Templates define the monitoring configuration (items, triggers, graphs) that can be
        reused across multiple hosts. Creating custom templates enables standardized monitoring
        for specific applications or server types.

        Args:
            name: Template name (required). Example: 'Apache Web Server', 'PostgreSQL Database'.
                  Should describe what the template monitors.
            description: Optional template description explaining its purpose and use.
            groups: List of group IDs where this template will be visible. Required, typically
                    set to group ID 1 (Templates) for built-in templates.

        Returns:
            dict: Contains 'templateids' list with newly created template ID(s) and 'success' flag.

        Note: After creating a template, add items, triggers, and graphs to it using respective APIs.
              Then apply to hosts with host_update using the templateid.
        """
        try:
            await ctx.info(f"Creating template '{host}'...")
            params: dict[str, Any] = {"host": host, "groups": groups}
            if name:
                params["name"] = name
            if description:
                params["description"] = description

            async with ZabbixClient(config) as api:
                result = await api.template.create(**params)
                return {"templateids": result.get("templateids", []), "success": True}
        except Exception as e:
            await ctx.error(f"Error creating template: {e!s}")
            return {"error": str(e)}

    @mcp.tool(
        tags={"zabbix", "template"},
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
        },
    )
    async def template_update(
        ctx: Context,
        templateid: Annotated[str, Field(description="ID of the template to update.")],
        name: Annotated[str | None, Field(default=None)] = None,
        description: Annotated[str | None, Field(default=None)] = None,
    ) -> dict:
        """
        Update an existing template in Zabbix.

        Modifies properties of an existing template. You can change the name or description.
        Only specify the fields you want to change.

        Args:
            templateid: ID of the template to update (required). Find it with template_get.
            name: New template name.
            description: New template description.

        Returns:
            dict: Contains 'templateids' list with updated template IDs and 'success' flag.
                  On error, contains 'error' key with the error message.
        """
        try:
            await ctx.info(f"Updating template {templateid}...")
            params: dict[str, Any] = {"templateid": templateid}
            if name is not None:
                params["name"] = name
            if description is not None:
                params["description"] = description

            async with ZabbixClient(config) as api:
                result = await api.template.update(**params)
                return {"templateids": result.get("templateids", []), "success": True}
        except Exception as e:
            await ctx.error(f"Error updating template: {e!s}")
            return {"error": str(e)}

    @mcp.tool(
        tags={"zabbix", "template"},
        annotations={
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
        },
    )
    async def template_delete(
        ctx: Context,
        templateids: Annotated[list[str], Field(description="Template IDs to delete.")],
    ) -> dict:
        """
        Delete templates from Zabbix.

        Permanently removes one or more templates. Hosts that have the deleted templates applied
        will lose those template's items, triggers, and graphs. The hosts themselves remain unchanged.

        Args:
            templateids: List of template IDs to delete. Find them with template_get.

        Returns:
            dict: Contains 'templateids' list with deleted template IDs and 'success' flag.
                  On error, contains 'error' key with the error message.

        Warning: Deleting a template removes all associated items, triggers, and graphs from
                 hosts using that template. Consider unlinked the template first if you want
                 to keep the configurations on the hosts.
        """
        try:
            await ctx.info(f"Deleting templates: {templateids}...")
            async with ZabbixClient(config) as api:
                result = await api.template.delete(*templateids)
                return {"templateids": result.get("templateids", []), "success": True}
        except Exception as e:
            await ctx.error(f"Error deleting templates: {e!s}")
            return {"error": str(e)}

    ##########################
    # Item Tools
    ##########################
