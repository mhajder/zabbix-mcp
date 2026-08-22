"""
Zabbix MCP Server Templates Tools
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
                description="Number of matching records to skip. Use with 'limit' to page through results; check 'has_more' and 'total' in the response.",
                ge=0,
            ),
        ] = 0,
        select_groups: Annotated[
            bool,
            Field(
                default=False,
                description="If true, include the template groups the templates belong to (selectTemplateGroups=extend).",
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
            str,
            Field(
                default="host",
                description="Field to sort by. A deterministic sort is required for paging to be consistent.",
            ),
        ] = "host",
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
            offset: Number of matching records to skip, for paging.
            select_groups: If true, each template includes a 'templategroups' list with its template groups.
            select_hosts: If true, each template includes a 'hosts' list with linked hosts.
            select_templates: If true, each template includes a 'templates' list with linked templates.
            select_macros: If true, each template includes a 'macros' list.
            select_tags: If true, each template includes a 'tags' list.

        Returns:
            dict: Contains 'templates' list with template objects, 'count' of results returned,
                  'total' matching records, the applied 'limit' and 'offset', and
                  'has_more' indicating whether further pages exist.
                  Each template object has:
                  - templateid: Unique template ID
                  - name: Template name (e.g., 'Linux Server Template')
                  - description: Optional template description

        Note: Use host_create or host_update with templateids to apply templates to hosts.
        """
        try:
            await ctx.info("Retrieving templates...")
            # Sorting is kept out of 'filters' because Zabbix rejects
            # countOutput combined with sortfield.
            sort: dict[str, Any] = {"sortfield": sortfield, "sortorder": sortorder}
            filters: dict[str, Any] = {}
            shape: dict[str, Any] = {"output": output}
            if templateids:
                filters["templateids"] = templateids
            if groupids:
                filters["groupids"] = groupids
            if hostids:
                filters["hostids"] = hostids
            _search = dict(search) if search is not None else {}
            if template_name_contains is not None:
                _search["host"] = template_name_contains
            if _search:
                filters["search"] = _search
            if select_groups:
                shape["selectTemplateGroups"] = "extend"
            if select_hosts:
                shape["selectHosts"] = "extend"
            if select_templates:
                shape["selectTemplates"] = "extend"
            if select_macros:
                shape["selectMacros"] = "extend"
            if select_tags:
                shape["selectTags"] = "extend"

            async with ZabbixClient(config) as api:
                if count_output:
                    return {"total": await fetch_total(api.template, filters)}

                rows, total = await fetch_page(
                    api.template,
                    filters=filters,
                    shape=shape,
                    sort=sort,
                    id_field="templateid",
                    limit=limit,
                    offset=offset,
                )
                return {
                    "templates": rows,
                    "count": len(rows),
                    "total": total,
                    "limit": limit,
                    "offset": offset,
                    "has_more": offset + len(rows) < total,
                }
        except Exception as e:
            await fail(ctx, "Error retrieving templates", e)

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
        groups: Annotated[
            list[dict[str, str]],
            Field(
                description="Template groups the template belongs to, e.g. [{'groupid': '10'}]. Since Zabbix 6.2 these are template groups, not host groups."
            ),
        ],
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
            groups: Template group IDs this template belongs to. Required. Zabbix 6.2 split
                    template groups out from host groups, so a host group id is rejected
                    here - find ids with templategroup.get or the Templates group in the UI.

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
            await fail(ctx, "Error creating template", e)

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
            await fail(ctx, "Error updating template", e)

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
        templateids: Annotated[
            list[str],
            Field(description="Template IDs to delete.", min_length=1),
        ],
    ) -> dict:
        """
        Delete templates from Zabbix.

        Permanently removes one or more templates. Hosts that have the deleted templates applied
        will lose those template's items, triggers, and graphs. The hosts themselves remain unchanged.

        Args:
            templateids: List of template IDs to delete. Find them with template_get.

        Returns:
            dict: Contains 'templateids' list with deleted template IDs and 'success' flag.

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
            await fail(ctx, "Error deleting templates", e)

    ##########################
    # Item Tools
    ##########################
