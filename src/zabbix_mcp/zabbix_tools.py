"""
Zabbix MCP Server Tools

This module provides tools for interacting with the Zabbix API through the MCP server.
"""

from typing import Annotated
from typing import Any

from fastmcp import Context
from pydantic import Field

from zabbix_mcp.models import ZabbixConfig
from zabbix_mcp.zabbix_client import ZabbixClient


def register_tools(mcp, config: ZabbixConfig):
    """Register Zabbix tools with the MCP server"""

    ##########################
    # API Info Tools
    ##########################

    @mcp.tool(
        tags={"zabbix", "api", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def api_version(ctx: Context = None) -> dict:
        """
        Get Zabbix API version information.

        This tool retrieves the current version of the Zabbix API you are connecting to.
        This is useful for understanding API capabilities and ensuring compatibility
        with specific features that may be version-dependent.

        Returns:
            dict: Contains 'version' key with the API version string (e.g., "6.0.10").
                  On error, contains 'error' key with the error message.

        Example response:
            {"version": "6.0.10"}
        """
        try:
            await ctx.info("Getting Zabbix API version...")
            async with ZabbixClient(config) as api:
                version = str(api.version)
                return {"version": version}
        except Exception as e:
            await ctx.error(f"Error getting API version: {e!s}")
            return {"error": str(e)}

    ##########################
    # Host Tools
    ##########################

    @mcp.tool(
        tags={"zabbix", "host", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def host_get(
        hostids: Annotated[
            list[str] | None,
            Field(default=None, description="List of host IDs to retrieve."),
        ] = None,
        groupids: Annotated[
            list[str] | None,
            Field(default=None, description="List of host group IDs to filter by."),
        ] = None,
        templateids: Annotated[
            list[str] | None,
            Field(default=None, description="List of template IDs to filter by."),
        ] = None,
        proxyids: Annotated[
            list[str] | None,
            Field(default=None, description="List of proxy IDs to filter by."),
        ] = None,
        search: Annotated[
            dict[str, str] | None,
            Field(
                default=None, description="Search criteria (e.g., {'host': 'web*'})."
            ),
        ] = None,
        filter_params: Annotated[
            dict[str, Any] | None,
            Field(default=None, description="Filter criteria (e.g., {'status': 0})."),
        ] = None,
        output: Annotated[
            str,
            Field(
                default="extend",
                description="Output format: 'extend' or specific fields.",
            ),
        ] = "extend",
        limit: Annotated[
            int | None,
            Field(default=None, description="Maximum number of results.", ge=1),
        ] = None,
        ctx: Context = None,
    ) -> dict:
        """
        Get hosts from Zabbix with optional filtering.

        Retrieves a list of monitored hosts from Zabbix. You can filter by host IDs,
        groups, templates, proxies, or use search criteria. This is useful for discovering
        which hosts are available in your monitoring system.

        Args:
            hostids: Specific host IDs to retrieve. If empty, retrieves all hosts.
            groupids: Filter hosts by group membership (host must belong to these groups).
            templateids: Filter hosts that use specific templates.
            proxyids: Filter hosts assigned to specific proxies.
            search: Search pattern for host name. Supports wildcards (e.g., 'web*', '*prod').
            filter_params: Exact match filter (e.g., {'status': '0'} for enabled hosts).
            output: 'extend' returns all fields, or specify specific field names.
            limit: Maximum number of results to return (useful for pagination).

        Returns:
            dict: Contains 'hosts' list with host objects and 'count' of results returned.
                  Each host contains: hostid, host (technical name), name (visible name),
                  status, groups, interfaces, and other host properties.

        Example response:
            {
                "hosts": [
                    {
                        "hostid": "10001",
                        "host": "server1",
                        "name": "Production Server 1",
                        "status": "0"
                    }
                ],
                "count": 1
            }
        """
        try:
            await ctx.info("Retrieving hosts...")
            params: dict[str, Any] = {"output": output}

            if hostids:
                params["hostids"] = hostids
            if groupids:
                params["groupids"] = groupids
            if templateids:
                params["templateids"] = templateids
            if proxyids:
                params["proxyids"] = proxyids
            if search:
                params["search"] = search
            if filter_params:
                params["filter"] = filter_params
            if limit:
                params["limit"] = limit

            async with ZabbixClient(config) as api:
                result = await api.host.get(**params)
                return {"hosts": result, "count": len(result)}

        except Exception as e:
            await ctx.error(f"Error retrieving hosts: {e!s}")
            return {"error": str(e)}

    @mcp.tool(
        tags={"zabbix", "host"},
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
        },
    )
    async def host_create(
        host: Annotated[str, Field(description="Technical name of the host.")],
        groups: Annotated[
            list[dict[str, str]],
            Field(description="Host groups (e.g., [{'groupid': '1'}])."),
        ],
        interfaces: Annotated[
            list[dict[str, Any]] | None,
            Field(default=None, description="Host interfaces."),
        ] = None,
        templates: Annotated[
            list[dict[str, str]] | None,
            Field(default=None, description="Templates to link."),
        ] = None,
        name: Annotated[
            str | None, Field(default=None, description="Visible name.")
        ] = None,
        status: Annotated[
            int, Field(default=0, description="0=enabled, 1=disabled.")
        ] = 0,
        description: Annotated[
            str | None, Field(default=None, description="Description.")
        ] = None,
        ctx: Context = None,
    ) -> dict:
        """
        Create a new host in Zabbix.

        Adds a new monitored host to Zabbix. This is essential for starting to monitor
        a new server or device. You must specify at least a host name and groups.
        You can optionally configure interfaces (for agent/SNMP communication) and link templates.

        Args:
            host: Technical name of the host (e.g., 'server-prod-01'). Must be unique.
            groups: List of group IDs to assign this host to. Format: [{'groupid': '10'}].
                    Every host must belong to at least one group.
            interfaces: List of host interfaces for data collection. Format:
                       [{'type': 1, 'main': 1, 'useip': 1, 'ip': '192.168.1.1', 'port': '10050'}]
                       Types: 1=Agent, 2=SNMP, 3=IPMI, 4=JMX
            templates: List of template IDs to link. Format: [{'templateid': '10001'}].
                      Templates provide monitoring items and triggers.
            name: Visible name for display in the UI (can contain spaces and special chars).
            status: 0=enabled (monitored), 1=disabled (not monitored).
            description: Free-text description of the host (e.g., 'Production web server').

        Returns:
            dict: Contains 'hostids' list with IDs of newly created hosts and 'success' flag.
                  On error, contains 'error' key with the error message.

        Example response:
            {
                "hostids": ["10005"],
                "success": true
            }

        Note: Use hostgroup_get to find group IDs and template_get to find template IDs.
        """
        try:
            await ctx.info(f"Creating host '{host}'...")
            params: dict[str, Any] = {"host": host, "groups": groups, "status": status}
            if interfaces:
                params["interfaces"] = interfaces
            if templates:
                params["templates"] = templates
            if name:
                params["name"] = name
            if description:
                params["description"] = description

            async with ZabbixClient(config) as api:
                result = await api.host.create(**params)
                return {"hostids": result.get("hostids", []), "success": True}
        except Exception as e:
            await ctx.error(f"Error creating host: {e!s}")
            return {"error": str(e)}

    @mcp.tool(
        tags={"zabbix", "host"},
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def host_update(
        hostid: Annotated[str, Field(description="ID of the host to update.")],
        host: Annotated[
            str | None, Field(default=None, description="New technical name.")
        ] = None,
        name: Annotated[
            str | None, Field(default=None, description="New visible name.")
        ] = None,
        status: Annotated[
            int | None, Field(default=None, description="0=enabled, 1=disabled.")
        ] = None,
        description: Annotated[
            str | None, Field(default=None, description="New description.")
        ] = None,
        ctx: Context = None,
    ) -> dict:
        """
        Update an existing host in Zabbix.

        Modifies properties of an existing host. You can change the technical name,
        visible name, status (enable/disable monitoring), or description. Only specify
        the fields you want to change.

        Args:
            hostid: ID of the host to update (required). Find it with host_get.
            host: New technical name for the host.
            name: New visible name for display.
            status: New status: 0=enabled (monitored), 1=disabled (not monitored).
            description: New description text.

        Returns:
            dict: Contains 'hostids' list with updated host IDs and 'success' flag.
                  On error, contains 'error' key with the error message.

        Example response:
            {
                "hostids": ["10001"],
                "success": true
            }
        """
        try:
            await ctx.info(f"Updating host {hostid}...")
            params: dict[str, Any] = {"hostid": hostid}
            if host:
                params["host"] = host
            if name:
                params["name"] = name
            if status is not None:
                params["status"] = status
            if description:
                params["description"] = description

            async with ZabbixClient(config) as api:
                result = await api.host.update(**params)
                return {"hostids": result.get("hostids", []), "success": True}
        except Exception as e:
            await ctx.error(f"Error updating host: {e!s}")
            return {"error": str(e)}

    @mcp.tool(
        tags={"zabbix", "host"},
        annotations={
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
        },
    )
    async def host_delete(
        hostids: Annotated[list[str], Field(description="List of host IDs to delete.")],
        ctx: Context = None,
    ) -> dict:
        """
        Delete hosts from Zabbix.

        Permanently removes one or more hosts from Zabbix. This will delete all associated
        data including history and alerts. Use with caution as this is a destructive operation.

        Args:
            hostids: List of host IDs to delete. Find them with host_get.

        Returns:
            dict: Contains 'hostids' list with deleted host IDs and 'success' flag.
                  On error, contains 'error' key with the error message.

        Example response:
            {
                "hostids": ["10001", "10002"],
                "success": true
            }

        Warning: This is permanent. Consider disabling the host instead (set status=1)
                 if you might need to restore it later.
        """
        try:
            await ctx.info(f"Deleting hosts: {hostids}...")
            async with ZabbixClient(config) as api:
                result = await api.host.delete(*hostids)
                return {"hostids": result.get("hostids", []), "success": True}
        except Exception as e:
            await ctx.error(f"Error deleting hosts: {e!s}")
            return {"error": str(e)}

    ##########################
    # Host Group Tools
    ##########################

    @mcp.tool(
        tags={"zabbix", "hostgroup", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def hostgroup_get(
        groupids: Annotated[
            list[str] | None, Field(default=None, description="Group IDs.")
        ] = None,
        hostids: Annotated[
            list[str] | None, Field(default=None, description="Host IDs.")
        ] = None,
        search: Annotated[
            dict[str, str] | None, Field(default=None, description="Search.")
        ] = None,
        output: Annotated[
            str, Field(default="extend", description="Output format.")
        ] = "extend",
        ctx: Context = None,
    ) -> dict:
        """
        Get host groups from Zabbix.

        Retrieves host groups with optional filtering. Host groups are used to organize
        and manage hosts collectively, applying templates, permissions, and maintenance
        windows to multiple hosts at once.

        Args:
            groupids: List of host group IDs to get. If empty, returns all groups.
                      Find group IDs with a search or from existing hosts.
            search: Substring search in group name. Matches partial names like 'Web' finds 'Web Servers'.
                    Case-sensitive partial match.
            limit: Maximum number of groups to return (default unlimited). Useful for large deployments.

        Returns:
            dict: Contains 'hostgroups' list with group objects (id, name) and 'success' flag.
                  Each group object has:
                  - groupid: Unique group ID
                  - name: Group name (e.g., 'Linux servers', 'Web Servers')

        Example response:
            {
                "hostgroups": [
                    {"groupid": "2", "name": "Linux servers"},
                    {"groupid": "3", "name": "Web Servers"}
                ],
                "success": true
            }

        Note: Use host_get to see which hosts belong to a group, or which groups contain specific hosts.
        """
        try:
            await ctx.info("Retrieving host groups...")
            params: dict[str, Any] = {"output": output}
            if groupids:
                params["groupids"] = groupids
            if hostids:
                params["hostids"] = hostids
            if search:
                params["search"] = search

            async with ZabbixClient(config) as api:
                result = await api.hostgroup.get(**params)
                return {"groups": result, "count": len(result)}
        except Exception as e:
            await ctx.error(f"Error retrieving host groups: {e!s}")
            return {"error": str(e)}

    @mcp.tool(
        tags={"zabbix", "hostgroup"},
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
        },
    )
    async def hostgroup_create(
        name: Annotated[str, Field(description="Name of the host group.")],
        ctx: Context = None,
    ) -> dict:
        """
        Create a new host group in Zabbix.

        Host groups serve as containers for organizing hosts. They're essential for
        applying permissions, templates, and maintenance windows to multiple hosts at once.

        Args:
            name: Name of the host group (required). Example: 'Web Servers', 'Database Servers'.
                  Names should be descriptive for organizational clarity.

        Returns:
            dict: Contains 'groupids' list with the newly created group ID(s) and 'success' flag.
                  The groupid is needed for other operations like adding hosts to the group.

        Example response:
            {
                "groupids": ["5"],
                "success": true
            }

        Note: Group names must be unique. Use hostgroup_get to verify the group name is not already taken.
        """
        try:
            await ctx.info(f"Creating host group '{name}'...")
            async with ZabbixClient(config) as api:
                result = await api.hostgroup.create(name=name)
                return {"groupids": result.get("groupids", []), "success": True}
        except Exception as e:
            await ctx.error(f"Error creating host group: {e!s}")
            return {"error": str(e)}

    @mcp.tool(
        tags={"zabbix", "hostgroup"},
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
        },
    )
    async def hostgroup_update(
        groupid: Annotated[str, Field(description="ID of the group to update.")],
        name: Annotated[str | None, Field(default=None)] = None,
        ctx: Context = None,
    ) -> dict:
        """
        Update an existing host group in Zabbix.

        Modifies properties of an existing host group. You can change the group's name.
        Only specify the fields you want to change.

        Args:
            groupid: ID of the host group to update (required). Find it with hostgroup_get.
            name: New group name.

        Returns:
            dict: Contains 'groupids' list with updated group IDs and 'success' flag.
                  On error, contains 'error' key with the error message.

        Example response:
            {
                "groupids": ["5"],
                "success": true
            }
        """
        try:
            await ctx.info(f"Updating host group {groupid}...")
            params: dict[str, Any] = {"groupid": groupid}
            if name is not None:
                params["name"] = name

            async with ZabbixClient(config) as api:
                result = await api.hostgroup.update(**params)
                return {"groupids": result.get("groupids", []), "success": True}
        except Exception as e:
            await ctx.error(f"Error updating host group: {e!s}")
            return {"error": str(e)}

    @mcp.tool(
        tags={"zabbix", "hostgroup"},
        annotations={
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
        },
    )
    async def hostgroup_delete(
        groupids: Annotated[list[str], Field(description="Group IDs to delete.")],
        ctx: Context = None,
    ) -> dict:
        """
        Delete host groups from Zabbix.

        Permanently removes one or more host groups. Hosts in deleted groups will no longer
        be members of that group (though the hosts themselves remain unless explicitly deleted).

        Args:
            groupids: List of host group IDs to delete. Find them with hostgroup_get.

        Returns:
            dict: Contains 'groupids' list with deleted group IDs and 'success' flag.
                  On error, contains 'error' key with the error message.

        Example response:
            {
                "groupids": ["5"],
                "success": true
            }

        Warning: If hosts belong to the group, they will no longer be members after deletion.
                 Consider reassigning hosts to different groups before deleting.
        """
        try:
            await ctx.info(f"Deleting host groups: {groupids}...")
            async with ZabbixClient(config) as api:
                result = await api.hostgroup.delete(*groupids)
                return {"groupids": result.get("groupids", []), "success": True}
        except Exception as e:
            await ctx.error(f"Error deleting host groups: {e!s}")
            return {"error": str(e)}

    ##########################
    # Template Tools
    ##########################

    @mcp.tool(
        tags={"zabbix", "template", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def template_get(
        templateids: Annotated[list[str] | None, Field(default=None)] = None,
        groupids: Annotated[list[str] | None, Field(default=None)] = None,
        hostids: Annotated[list[str] | None, Field(default=None)] = None,
        search: Annotated[dict[str, str] | None, Field(default=None)] = None,
        output: Annotated[str, Field(default="extend")] = "extend",
        ctx: Context = None,
    ) -> dict:
        """
        Get templates from Zabbix.

        Templates are reusable collections of items, triggers, and graphs that can be applied to hosts.
        They standardize monitoring across multiple servers with the same role.

        Args:
            templateids: List of template IDs to get. If empty, returns all templates.
                         Find template IDs with a search or from host associations.
            search: Substring search in template name. Matches partial names like 'Linux' finds 'Linux Server Template'.
            limit: Maximum number of templates to return (default unlimited).

        Returns:
            dict: Contains 'templates' list with template objects and 'success' flag.
                  Each template object has:
                  - templateid: Unique template ID
                  - name: Template name (e.g., 'Linux Server Template')
                  - description: Optional template description

        Example response:
            {
                "templates": [
                    {"templateid": "10001", "name": "Linux Server Template", "description": ""},
                    {"templateid": "10002", "name": "MySQL Template", "description": "Database monitoring"}
                ],
                "success": true
            }

        Note: Use host_create or host_update with templateids to apply templates to hosts.
        """
        try:
            await ctx.info("Retrieving templates...")
            params: dict[str, Any] = {"output": output}
            if templateids:
                params["templateids"] = templateids
            if groupids:
                params["groupids"] = groupids
            if hostids:
                params["hostids"] = hostids
            if search:
                params["search"] = search

            async with ZabbixClient(config) as api:
                result = await api.template.get(**params)
                return {"templates": result, "count": len(result)}
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
        host: Annotated[str, Field(description="Technical name of the template.")],
        groups: Annotated[list[dict[str, str]], Field(description="Host groups.")],
        name: Annotated[str | None, Field(default=None)] = None,
        description: Annotated[str | None, Field(default=None)] = None,
        ctx: Context = None,
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

        Example response:
            {
                "templateids": ["10003"],
                "success": true
            }

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
        templateid: Annotated[str, Field(description="ID of the template to update.")],
        name: Annotated[str | None, Field(default=None)] = None,
        description: Annotated[str | None, Field(default=None)] = None,
        ctx: Context = None,
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

        Example response:
            {
                "templateids": ["10003"],
                "success": true
            }
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
        templateids: Annotated[list[str], Field(description="Template IDs to delete.")],
        ctx: Context = None,
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

        Example response:
            {
                "templateids": ["10003"],
                "success": true
            }

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

    @mcp.tool(
        tags={"zabbix", "item", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def item_get(
        itemids: Annotated[list[str] | None, Field(default=None)] = None,
        hostids: Annotated[list[str] | None, Field(default=None)] = None,
        groupids: Annotated[list[str] | None, Field(default=None)] = None,
        templateids: Annotated[list[str] | None, Field(default=None)] = None,
        search: Annotated[dict[str, str] | None, Field(default=None)] = None,
        filter_params: Annotated[dict[str, Any] | None, Field(default=None)] = None,
        output: Annotated[str, Field(default="extend")] = "extend",
        limit: Annotated[int | None, Field(default=None, ge=1)] = None,
        ctx: Context = None,
    ) -> dict:
        """
        Get items (metrics) from Zabbix.

        Items are the data sources in Zabbix - they define what metrics are collected and how
        (protocol, interval, etc.). Each item produces a stream of values over time.

        Args:
            itemids: List of item IDs to get. If empty, returns all items.
            hostids: List of host IDs to get items from. Filters items by host.
            groupids: List of group IDs to get items from hosts in those groups.
            templateids: List of template IDs to get items from those templates.
            search: Dictionary with search criteria like {'name': 'CPU'} for substring matching.
            filter_params: Additional filter parameters for advanced filtering.
            limit: Maximum number of items to return (default unlimited).

        Returns:
            dict: Contains 'items' list with item objects and 'success' flag.
                  Each item includes:
                  - itemid: Unique item ID
                  - name: Item name (e.g., 'CPU load average')
                  - key_: Item key (e.g., 'system.cpu.load')
                  - type: Collection method (0=Zabbix agent, 2=SNMP, 3=IPMI, etc.)
                  - value_type: Data type (0=numeric float, 1=character, 3=numeric unsigned, 4=log)
                  - status: 0=enabled, 1=disabled
                  - interval: Collection interval in seconds

        Example response:
            {
                "items": [
                    {
                        "itemid": "23456",
                        "name": "CPU load average",
                        "key_": "system.cpu.load",
                        "type": "0",
                        "value_type": "0",
                        "status": "0",
                        "interval": "60"
                    }
                ],
                "success": true
            }

        Note: Use item_create to add new metrics to monitor, item_delete to remove them.
        """
        try:
            await ctx.info("Retrieving items...")
            params: dict[str, Any] = {"output": output}
            if itemids:
                params["itemids"] = itemids
            if hostids:
                params["hostids"] = hostids
            if groupids:
                params["groupids"] = groupids
            if templateids:
                params["templateids"] = templateids
            if search:
                params["search"] = search
            if filter_params:
                params["filter"] = filter_params
            if limit:
                params["limit"] = limit

            async with ZabbixClient(config) as api:
                result = await api.item.get(**params)
                return {"items": result, "count": len(result)}
        except Exception as e:
            await ctx.error(f"Error retrieving items: {e!s}")
            return {"error": str(e)}

    @mcp.tool(
        tags={"zabbix", "item"},
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
        },
    )
    async def item_create(
        name: Annotated[str, Field(description="Item name.")],
        key_: Annotated[str, Field(description="Item key.")],
        hostid: Annotated[str, Field(description="Host ID.")],
        type_: Annotated[
            int, Field(description="Item type (0=Zabbix agent, 2=trapper, etc.).")
        ],
        value_type: Annotated[
            int, Field(description="Value type (0=float, 1=char, 3=unsigned, 4=text).")
        ],
        delay: Annotated[str, Field(default="1m")] = "1m",
        units: Annotated[str | None, Field(default=None)] = None,
        description: Annotated[str | None, Field(default=None)] = None,
        ctx: Context = None,
    ) -> dict:
        """
        Create a new item in Zabbix.

        Items define what data is collected from a host. Each item specifies the metric name,
        how to collect it (agent, SNMP, etc.), what interval to use, and what data type to store.

        Args:
            name: Item name displayed in Zabbix UI. Example: 'CPU load average', 'Memory usage'.
            key_: Unique item key that identifies the metric. Example: 'system.cpu.load', 'vm.memory.size'.
                  Zabbix agent item keys follow specific naming conventions.
            hostid: ID of the host this item belongs to. Get from host_get.
            type_: Collection method:
                   - 0 = Zabbix agent (most common)
                   - 2 = Zabbix trapper (passive agent)
                   - 3 = SNMP
                   - 5 = Zabbix internal
                   - 7 = SNMP trap
                   - 10 = External check
                   - 11 = Database monitor
                   - 12 = IPMI
                   - 13 = SSH agent
            value_type: Data type of collected values:
                        - 0 = Numeric (float)
                        - 1 = Character string
                        - 3 = Numeric (unsigned)
                        - 4 = Log data
            delay: Collection interval. Default '1m'. Use time suffixes like '30s', '5m', '1h'.
            units: Optional units for the values like 'bytes', 'CPU%', 'rpm'.
            description: Optional item description explaining its purpose.

        Returns:
            dict: Contains 'itemids' list with newly created item ID(s) and 'success' flag.

        Example response:
            {
                "itemids": ["23789"],
                "success": true
            }

        Note: The item key_ must match what the data source (agent, SNMP, etc.) can provide.
              After creation, configure triggers to alert on this item's values.
        """
        try:
            await ctx.info(f"Creating item '{name}'...")
            params: dict[str, Any] = {
                "name": name,
                "key_": key_,
                "hostid": hostid,
                "type": type_,
                "value_type": value_type,
                "delay": delay,
            }
            if units:
                params["units"] = units
            if description:
                params["description"] = description

            async with ZabbixClient(config) as api:
                result = await api.item.create(**params)
                return {"itemids": result.get("itemids", []), "success": True}
        except Exception as e:
            await ctx.error(f"Error creating item: {e!s}")
            return {"error": str(e)}

    @mcp.tool(
        tags={"zabbix", "item"},
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
        },
    )
    async def item_update(
        itemid: Annotated[str, Field(description="ID of the item to update.")],
        name: Annotated[str | None, Field(default=None)] = None,
        delay: Annotated[str | None, Field(default=None)] = None,
        units: Annotated[str | None, Field(default=None)] = None,
        description: Annotated[str | None, Field(default=None)] = None,
        status: Annotated[
            int | None,
            Field(default=None, description="0=enabled, 1=disabled."),
        ] = None,
        ctx: Context = None,
    ) -> dict:
        """
        Update an existing item in Zabbix.

        Modifies properties of an existing monitoring item. You can change the name,
        collection interval, units, or status. Only specify the fields you want to change.

        Args:
            itemid: ID of the item to update (required). Find it with item_get.
            name: New item name.
            delay: New collection interval (e.g., '30s', '5m', '1h').
            units: New units for the values.
            description: New description.
            status: New status: 0=enabled (monitored), 1=disabled (not monitored).

        Returns:
            dict: Contains 'itemids' list with updated item IDs and 'success' flag.
                  On error, contains 'error' key with the error message.

        Example response:
            {
                "itemids": ["23789"],
                "success": true
            }
        """
        try:
            await ctx.info(f"Updating item {itemid}...")
            params: dict[str, Any] = {"itemid": itemid}
            if name is not None:
                params["name"] = name
            if delay is not None:
                params["delay"] = delay
            if units is not None:
                params["units"] = units
            if description is not None:
                params["description"] = description
            if status is not None:
                params["status"] = status

            async with ZabbixClient(config) as api:
                result = await api.item.update(**params)
                return {"itemids": result.get("itemids", []), "success": True}
        except Exception as e:
            await ctx.error(f"Error updating item: {e!s}")
            return {"error": str(e)}

    @mcp.tool(
        tags={"zabbix", "item"},
        annotations={
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
        },
    )
    async def item_delete(
        itemids: Annotated[list[str], Field(description="Item IDs to delete.")],
        ctx: Context = None,
    ) -> dict:
        """
        Delete items from Zabbix.

        Permanently removes one or more items from monitoring. The item's historical data is
        typically removed as part of cleanup, though this depends on Zabbix configuration.

        Args:
            itemids: List of item IDs to delete. Find them with item_get.

        Returns:
            dict: Contains 'itemids' list with deleted item IDs and 'success' flag.
                  On error, contains 'error' key with the error message.

        Example response:
            {
                "itemids": ["23789"],
                "success": true
            }

        Warning: Deleting an item removes all its historical data and associated triggers.
                 Consider disabling the item first to test impact before permanent deletion.
        """
        try:
            await ctx.info(f"Deleting items: {itemids}...")
            async with ZabbixClient(config) as api:
                result = await api.item.delete(*itemids)
                return {"itemids": result.get("itemids", []), "success": True}
        except Exception as e:
            await ctx.error(f"Error deleting items: {e!s}")
            return {"error": str(e)}

    ##########################
    # Trigger Tools
    ##########################

    @mcp.tool(
        tags={"zabbix", "trigger", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def trigger_get(
        triggerids: Annotated[list[str] | None, Field(default=None)] = None,
        hostids: Annotated[list[str] | None, Field(default=None)] = None,
        groupids: Annotated[list[str] | None, Field(default=None)] = None,
        templateids: Annotated[list[str] | None, Field(default=None)] = None,
        search: Annotated[dict[str, str] | None, Field(default=None)] = None,
        filter_params: Annotated[dict[str, Any] | None, Field(default=None)] = None,
        output: Annotated[str, Field(default="extend")] = "extend",
        limit: Annotated[int | None, Field(default=None, ge=1)] = None,
        only_true: Annotated[
            bool,
            Field(default=False, description="Only return triggers in problem state."),
        ] = False,
        min_severity: Annotated[
            int | None, Field(default=None, description="Minimum severity (0-5).")
        ] = None,
        ctx: Context = None,
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
            limit: Maximum number of triggers to return (default unlimited).
            only_true: If true, only return triggers currently in problem state.
            min_severity: Minimum severity level (0=Not classified, 1=Information, 2=Warning,
                         3=Average, 4=High, 5=Disaster). Returns triggers of this severity or higher.

        Returns:
            dict: Contains 'triggers' list with trigger objects and 'success' flag.
                  Each trigger includes:
                  - triggerid: Unique trigger ID
                  - description: Trigger name/description
                  - expression: Trigger expression/condition
                  - state: 0=normal, 1=problem
                  - value: 0=normal, 1=problem
                  - severity: Severity level (0-5)

        Example response:
            {
                "triggers": [
                    {
                        "triggerid": "13567",
                        "description": "High CPU load",
                        "expression": "{10084:system.cpu.load[percpu,avg1]}>5",
                        "state": "0",
                        "value": "0",
                        "severity": "3"
                    }
                ],
                "success": true
            }

        Note: Use trigger_create to define new monitoring rules, trigger_delete to remove them.
        """
        try:
            await ctx.info("Retrieving triggers...")
            params: dict[str, Any] = {"output": output}
            if triggerids:
                params["triggerids"] = triggerids
            if hostids:
                params["hostids"] = hostids
            if groupids:
                params["groupids"] = groupids
            if templateids:
                params["templateids"] = templateids
            if search:
                params["search"] = search
            if filter_params:
                params["filter"] = filter_params
            if limit:
                params["limit"] = limit
            if only_true:
                params["only_true"] = only_true
            if min_severity is not None:
                params["min_severity"] = min_severity

            async with ZabbixClient(config) as api:
                result = await api.trigger.get(**params)
                return {"triggers": result, "count": len(result)}
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
        description: Annotated[str, Field(description="Trigger description/name.")],
        expression: Annotated[str, Field(description="Trigger expression.")],
        priority: Annotated[int, Field(default=0, description="Severity 0-5.")] = 0,
        status: Annotated[
            int, Field(default=0, description="0=enabled, 1=disabled.")
        ] = 0,
        comments: Annotated[str | None, Field(default=None)] = None,
        ctx: Context = None,
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

        Example response:
            {
                "triggerids": ["13789"],
                "success": true
            }

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
        triggerid: Annotated[str, Field(description="ID of the trigger to update.")],
        description: Annotated[str | None, Field(default=None)] = None,
        expression: Annotated[str | None, Field(default=None)] = None,
        priority: Annotated[int | None, Field(default=None)] = None,
        status: Annotated[
            int | None,
            Field(default=None, description="0=enabled, 1=disabled."),
        ] = None,
        comments: Annotated[str | None, Field(default=None)] = None,
        ctx: Context = None,
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

        Example response:
            {
                "triggerids": ["13789"],
                "success": true
            }
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
        triggerids: Annotated[list[str], Field(description="Trigger IDs to delete.")],
        ctx: Context = None,
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

        Example response:
            {
                "triggerids": ["13789"],
                "success": true
            }

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

    @mcp.tool(
        tags={"zabbix", "problem", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def problem_get(
        eventids: Annotated[list[str] | None, Field(default=None)] = None,
        groupids: Annotated[list[str] | None, Field(default=None)] = None,
        hostids: Annotated[list[str] | None, Field(default=None)] = None,
        objectids: Annotated[list[str] | None, Field(default=None)] = None,
        time_from: Annotated[
            int | None, Field(default=None, description="Unix timestamp.")
        ] = None,
        time_till: Annotated[
            int | None, Field(default=None, description="Unix timestamp.")
        ] = None,
        recent: Annotated[bool, Field(default=False)] = False,
        severities: Annotated[
            list[int] | None, Field(default=None, description="Severity levels 0-5.")
        ] = None,
        output: Annotated[str, Field(default="extend")] = "extend",
        limit: Annotated[int | None, Field(default=None, ge=1)] = None,
        ctx: Context = None,
    ) -> dict:
        """
        Get problems from Zabbix.

        Problems are active trigger states that indicate issues with monitored infrastructure.
        Each problem is associated with a trigger and can be acknowledged by operators.

        Args:
            eventids: List of event IDs to get problems for. If empty, returns all problems.
            groupids: List of host group IDs to get problems from.
            hostids: List of host IDs to get problems from.
            objectids: List of trigger IDs to get problems from.
            time_from: Unix timestamp to filter problems from this time onwards.
            time_till: Unix timestamp to filter problems up to this time.
            recent: If true, only return recently recovered problems.
            severities: List of severity levels to filter (0=Not classified, 1=Information, 2=Warning,
                       3=Average, 4=High, 5=Disaster).
            limit: Maximum number of problems to return (default unlimited).

        Returns:
            dict: Contains 'problems' list with problem objects and 'success' flag.
                  Each problem includes:
                  - eventid: Event ID of the problem
                  - objectid: Trigger ID that caused the problem
                  - clock: Unix timestamp when problem occurred
                  - ns: Nanosecond adjustment
                  - acknowledged: 0=unacknowledged, 1=acknowledged

        Example response:
            {
                "problems": [
                    {
                        "eventid": "1234567",
                        "objectid": "13567",
                        "clock": "1699564800",
                        "acknowledged": "0"
                    }
                ],
                "success": true
            }

        Note: Use event_acknowledge to mark problems as seen. Get more details with event_get.
        """
        try:
            await ctx.info("Retrieving problems...")
            params: dict[str, Any] = {"output": output}
            if eventids:
                params["eventids"] = eventids
            if groupids:
                params["groupids"] = groupids
            if hostids:
                params["hostids"] = hostids
            if objectids:
                params["objectids"] = objectids
            if time_from:
                params["time_from"] = time_from
            if time_till:
                params["time_till"] = time_till
            if recent:
                params["recent"] = recent
            if severities:
                params["severities"] = severities
            if limit:
                params["limit"] = limit

            async with ZabbixClient(config) as api:
                result = await api.problem.get(**params)
                return {"problems": result, "count": len(result)}
        except Exception as e:
            await ctx.error(f"Error retrieving problems: {e!s}")
            return {"error": str(e)}

    ###########################
    # Event Tools
    ###########################

    @mcp.tool(
        tags={"zabbix", "event", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def event_get(
        eventids: Annotated[list[str] | None, Field(default=None)] = None,
        groupids: Annotated[list[str] | None, Field(default=None)] = None,
        hostids: Annotated[list[str] | None, Field(default=None)] = None,
        objectids: Annotated[list[str] | None, Field(default=None)] = None,
        time_from: Annotated[int | None, Field(default=None)] = None,
        time_till: Annotated[int | None, Field(default=None)] = None,
        output: Annotated[str, Field(default="extend")] = "extend",
        limit: Annotated[int | None, Field(default=None, ge=1)] = None,
        ctx: Context = None,
    ) -> dict:
        """
        Get events from Zabbix.

        Events represent state changes in the system - when triggers transition from normal to
        problem and back, or recovery events. Each event has a timestamp, trigger, and
        can be acknowledged to show operators have seen the alert.

        Args:
            eventids: List of event IDs to get. If empty, returns all events.
            groupids: List of host group IDs to get events from.
            hostids: List of host IDs to get events from.
            objectids: List of trigger IDs to get events from.
            time_from: Unix timestamp to filter events from this time onwards.
            time_till: Unix timestamp to filter events up to this time.
            limit: Maximum number of events to return (default unlimited).

        Returns:
            dict: Contains 'events' list with event objects and 'count' of returned events.
                  Each event includes:
                  - eventid: Unique event ID
                  - objectid: Trigger ID that generated the event
                  - clock: Unix timestamp when event occurred
                  - value: 0=normal, 1=problem
                  - acknowledged: 0=not acknowledged, 1=acknowledged

        Example response:
            {
                "events": [
                    {
                        "eventid": "1234567",
                        "objectid": "13567",
                        "clock": "1699564800",
                        "value": "1",
                        "acknowledged": "0"
                    }
                ],
                "count": 1,
                "success": true
            }

        Note: Use event_acknowledge to mark events as seen by operations team.
        """
        try:
            await ctx.info("Retrieving events...")
            params: dict[str, Any] = {"output": output}
            if eventids:
                params["eventids"] = eventids
            if groupids:
                params["groupids"] = groupids
            if hostids:
                params["hostids"] = hostids
            if objectids:
                params["objectids"] = objectids
            if time_from:
                params["time_from"] = time_from
            if time_till:
                params["time_till"] = time_till
            if limit:
                params["limit"] = limit

            async with ZabbixClient(config) as api:
                result = await api.event.get(**params)
                return {"events": result, "count": len(result)}
        except Exception as e:
            await ctx.error(f"Error retrieving events: {e!s}")
            return {"error": str(e)}

    @mcp.tool(
        tags={"zabbix", "event"},
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def event_acknowledge(
        eventids: Annotated[list[str], Field(description="Event IDs to acknowledge.")],
        action: Annotated[
            int,
            Field(default=1, description="Action: 1=ack, 2=close, 4=add message, etc."),
        ] = 1,
        message: Annotated[str | None, Field(default=None)] = None,
        ctx: Context = None,
    ) -> dict:
        """
        Acknowledge events in Zabbix.

        Mark events (problems/alerts) as acknowledged to show that operations staff are aware
        of and working on the issue. Acknowledged events can also be closed if resolved.

        Args:
            eventids: List of event IDs to acknowledge. Find them with event_get.
            action: Action to perform on the events:
                   - 1 = Acknowledge the event (most common)
                   - 2 = Close the event (if resolved)
                   - 4 = Add message to event
                   Default is 1 (acknowledge).
            message: Optional message to add when acknowledging (e.g., "Working on this", "Will restart service").

        Returns:
            dict: Contains 'success' flag and may include event IDs that were successfully acknowledged.

        Example response:
            {
                "eventids": ["1234567", "1234568"],
                "success": true
            }

        Note: Acknowledging an event doesn't resolve the underlying problem - it just marks that
              the issue has been noticed. The trigger still needs the underlying condition fixed.
        """
        try:
            await ctx.info(f"Acknowledging events: {eventids}...")
            params: dict[str, Any] = {"eventids": eventids, "action": action}
            if message:
                params["message"] = message

            async with ZabbixClient(config) as api:
                result = await api.event.acknowledge(**params)
                return {"eventids": result.get("eventids", []), "success": True}
        except Exception as e:
            await ctx.error(f"Error acknowledging events: {e!s}")
            return {"error": str(e)}

    ##########################
    # History Tools
    ##########################

    @mcp.tool(
        tags={"zabbix", "history", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def history_get(
        itemids: Annotated[
            list[str], Field(description="Item IDs to get history for.")
        ],
        history: Annotated[
            int,
            Field(
                default=0,
                description="History type: 0=float, 1=char, 2=log, 3=unsigned, 4=text.",
            ),
        ] = 0,
        time_from: Annotated[int | None, Field(default=None)] = None,
        time_till: Annotated[int | None, Field(default=None)] = None,
        limit: Annotated[int | None, Field(default=None, ge=1)] = None,
        sortfield: Annotated[str, Field(default="clock")] = "clock",
        sortorder: Annotated[str, Field(default="DESC")] = "DESC",
        ctx: Context = None,
    ) -> dict:
        """
        Get history data from Zabbix.

        Retrieves the raw metric values collected by items. History contains all individual
        collected data points with timestamps, allowing detailed analysis of system behavior over time.

        Args:
            itemids: List of item IDs to get history for. Required. Find items with item_get.
            history: Data type of history to retrieve:
                    - 0 = Float numeric values (default, for most metrics)
                    - 1 = Character string values
                    - 2 = Log data
                    - 3 = Unsigned numeric values
                    - 4 = Text data
            time_from: Unix timestamp to get history from this time onwards.
            time_till: Unix timestamp to get history up to this time.
            limit: Maximum number of history points to return (default unlimited).
            sortfield: Field to sort by (default 'clock' = timestamp).
            sortorder: Sort direction - 'ASC' (oldest first) or 'DESC' (newest first). Default is DESC.

        Returns:
            dict: Contains 'history' list with value objects and 'count' of returned values.
                  Each value includes:
                  - itemid: Item ID this value belongs to
                  - value: The collected metric value
                  - clock: Unix timestamp when value was collected
                  - ns: Nanosecond adjustment

        Example response:
            {
                "history": [
                    {"itemid": "23456", "value": "65.5", "clock": "1699564800", "ns": "0"},
                    {"itemid": "23456", "value": "62.3", "clock": "1699564860", "ns": "0"}
                ],
                "count": 2,
                "success": true
            }

        Note: History contains detailed point-in-time data. For aggregated analysis, use trend_get.
              For high-volume items, use limit and time filters to avoid excessive data retrieval.
        """
        try:
            await ctx.info("Retrieving history...")
            params: dict[str, Any] = {
                "itemids": itemids,
                "history": history,
                "sortfield": sortfield,
                "sortorder": sortorder,
            }
            if time_from:
                params["time_from"] = time_from
            if time_till:
                params["time_till"] = time_till
            if limit:
                params["limit"] = limit

            async with ZabbixClient(config) as api:
                result = await api.history.get(**params)
                return {"history": result, "count": len(result)}
        except Exception as e:
            await ctx.error(f"Error retrieving history: {e!s}")
            return {"error": str(e)}

    @mcp.tool(
        tags={"zabbix", "trend", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def trend_get(
        itemids: Annotated[list[str], Field(description="Item IDs to get trends for.")],
        time_from: Annotated[int | None, Field(default=None)] = None,
        time_till: Annotated[int | None, Field(default=None)] = None,
        limit: Annotated[int | None, Field(default=None, ge=1)] = None,
        ctx: Context = None,
    ) -> dict:
        """
        Get trend data from Zabbix.

        Trends are aggregated (summarized) historical data providing min/max/average values
        at hour-long intervals. Trends use less storage than raw history while preserving
        statistical information for long-term analysis.

        Args:
            itemids: List of item IDs to get trends for. Required. Find items with item_get.
            time_from: Unix timestamp to get trends from this time onwards.
            time_till: Unix timestamp to get trends up to this time.
            limit: Maximum number of trend records to return (default unlimited).

        Returns:
            dict: Contains 'trends' list with aggregate data and 'count' of returned records.
                  Each trend record includes:
                  - itemid: Item ID this trend belongs to
                  - clock: Unix timestamp (at hour boundaries)
                  - value_min: Minimum value during the hour
                  - value_max: Maximum value during the hour
                  - value_avg: Average value during the hour
                  - num: Number of values included in calculation

        Example response:
            {
                "trends": [
                    {
                        "itemid": "23456",
                        "clock": "1699560000",
                        "value_min": "50.1",
                        "value_max": "70.5",
                        "value_avg": "60.8",
                        "num": "60"
                    }
                ],
                "count": 1,
                "success": true
            }

        Note: Trends are hourly aggregates. For finer-grained data, use history_get.
              Trends are kept for longer periods than raw history for space efficiency.
        """
        try:
            await ctx.info("Retrieving trends...")
            params: dict[str, Any] = {"itemids": itemids}
            if time_from:
                params["time_from"] = time_from
            if time_till:
                params["time_till"] = time_till
            if limit:
                params["limit"] = limit

            async with ZabbixClient(config) as api:
                result = await api.trend.get(**params)
                return {"trends": result, "count": len(result)}
        except Exception as e:
            await ctx.error(f"Error retrieving trends: {e!s}")
            return {"error": str(e)}

    ##########################
    # User Tools
    ##########################

    @mcp.tool(
        tags={"zabbix", "user", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def user_get(
        userids: Annotated[list[str] | None, Field(default=None)] = None,
        search: Annotated[dict[str, str] | None, Field(default=None)] = None,
        filter_params: Annotated[dict[str, Any] | None, Field(default=None)] = None,
        output: Annotated[str, Field(default="extend")] = "extend",
        ctx: Context = None,
    ) -> dict:
        """
        Get users from Zabbix.

        Users represent people with access to the Zabbix system. Each user has authentication
        credentials and permission level determining what they can view and modify.

        Args:
            userids: List of user IDs to get. If empty, returns all users.
            search: Dictionary with search criteria like {'alias': 'admin'} for username matching.
            filter_params: Additional filter parameters for advanced filtering.

        Returns:
            dict: Contains 'users' list with user objects and 'count' of returned users.
                  Each user includes:
                  - userid: Unique user ID
                  - alias: Username login
                  - name: User's full name
                  - surname: User's last name
                  - type: User type (1=Zabbix user, 2=Zabbix admin, 3=Zabbix super admin)

        Example response:
            {
                "users": [
                    {"userid": "1", "alias": "Admin", "name": "Admin", "surname": "", "type": "3"},
                    {"userid": "2", "alias": "guest", "name": "Guest", "surname": "User", "type": "1"}
                ],
                "count": 2,
                "success": true
            }

        Note: Use user_create to add new users, user_delete to remove them.
        """
        try:
            await ctx.info("Retrieving users...")
            params: dict[str, Any] = {"output": output}
            if userids:
                params["userids"] = userids
            if search:
                params["search"] = search
            if filter_params:
                params["filter"] = filter_params

            async with ZabbixClient(config) as api:
                result = await api.user.get(**params)
                return {"users": result, "count": len(result)}
        except Exception as e:
            await ctx.error(f"Error retrieving users: {e!s}")
            return {"error": str(e)}

    @mcp.tool(
        tags={"zabbix", "user"},
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
        },
    )
    async def user_create(
        username: Annotated[str, Field(description="Username.")],
        passwd: Annotated[str, Field(description="Password.")],
        usrgrps: Annotated[
            list[dict[str, str]], Field(description="User groups [{'usrgrpid': '1'}].")
        ],
        name: Annotated[str | None, Field(default=None)] = None,
        surname: Annotated[str | None, Field(default=None)] = None,
        ctx: Context = None,
    ) -> dict:
        """
        Create a new user in Zabbix.

        Creates a new user account with specified credentials and group membership. New users
        inherit permissions from their assigned user groups.

        Args:
            username: Login username. Must be unique and alphanumeric.
            passwd: Password for the user account. Should follow security policy (min length, complexity).
            usrgrps: List of user group assignments in format [{'usrgrpid': 'group_id'}, ...].
                    Users inherit permissions from their groups. At least one group is required.
            name: User's first name (optional).
            surname: User's last name (optional).

        Returns:
            dict: Contains 'userids' list with newly created user ID(s) and 'success' flag.

        Example response:
            {
                "userids": ["4"],
                "success": true
            }

        Note: New users receive default permissions from their assigned groups. Change passwords
              through user_update if needed. Username cannot be changed after creation.
        """
        try:
            await ctx.info(f"Creating user '{username}'...")
            params: dict[str, Any] = {
                "username": username,
                "passwd": passwd,
                "usrgrps": usrgrps,
            }
            if name:
                params["name"] = name
            if surname:
                params["surname"] = surname

            async with ZabbixClient(config) as api:
                result = await api.user.create(**params)
                return {"userids": result.get("userids", []), "success": True}
        except Exception as e:
            await ctx.error(f"Error creating user: {e!s}")
            return {"error": str(e)}

    @mcp.tool(
        tags={"zabbix", "user"},
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
        },
    )
    async def user_update(
        userid: Annotated[str, Field(description="ID of the user to update.")],
        username: Annotated[str | None, Field(default=None)] = None,
        name: Annotated[str | None, Field(default=None)] = None,
        surname: Annotated[str | None, Field(default=None)] = None,
        passwd: Annotated[str | None, Field(default=None)] = None,
        type_: Annotated[
            int | None,
            Field(
                default=None,
                description="User type: 1=Zabbix user, 2=Zabbix admin, 3=Zabbix super admin.",
            ),
        ] = None,
        ctx: Context = None,
    ) -> dict:
        """
        Update an existing user in Zabbix.

        Modifies properties of an existing user account. You can change name, surname,
        password, or user type. Only specify the fields you want to change.

        Args:
            userid: ID of the user to update (required). Find it with user_get.
            username: New username (not recommended - can cause issues).
            name: New first name.
            surname: New last name.
            passwd: New password.
            type_: New user type (1=user, 2=admin, 3=super admin).

        Returns:
            dict: Contains 'userids' list with updated user IDs and 'success' flag.
                  On error, contains 'error' key with the error message.

        Example response:
            {
                "userids": ["4"],
                "success": true
            }
        """
        try:
            await ctx.info(f"Updating user {userid}...")
            params: dict[str, Any] = {"userid": userid}
            if username is not None:
                params["username"] = username
            if name is not None:
                params["name"] = name
            if surname is not None:
                params["surname"] = surname
            if passwd is not None:
                params["passwd"] = passwd
            if type_ is not None:
                params["type"] = type_

            async with ZabbixClient(config) as api:
                result = await api.user.update(**params)
                return {"userids": result.get("userids", []), "success": True}
        except Exception as e:
            await ctx.error(f"Error updating user: {e!s}")
            return {"error": str(e)}

    @mcp.tool(
        tags={"zabbix", "user"},
        annotations={
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
        },
    )
    async def user_delete(
        userids: Annotated[list[str], Field(description="User IDs to delete.")],
        ctx: Context = None,
    ) -> dict:
        """
        Delete users from Zabbix.

        Permanently removes user accounts from the system. The user's access will be immediately revoked.
        Historical data and previous actions by the user are retained for audit purposes.

        Args:
            userids: List of user IDs to delete. Find them with user_get.

        Returns:
            dict: Contains 'userids' list with deleted user IDs and 'success' flag.
                  On error, contains 'error' key with the error message.

        Example response:
            {
                "userids": ["4"],
                "success": true
            }

        Warning: This action is permanent and immediate. Deleted users lose all access to Zabbix.
                 Consider disabling the user instead (modify type) if temporary removal is needed.
        """
        try:
            await ctx.info(f"Deleting users: {userids}...")
            async with ZabbixClient(config) as api:
                result = await api.user.delete(*userids)
                return {"userids": result.get("userids", []), "success": True}
        except Exception as e:
            await ctx.error(f"Error deleting users: {e!s}")
            return {"error": str(e)}

    ##########################
    # Proxy Tools
    ##########################

    @mcp.tool(
        tags={"zabbix", "proxy", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def proxy_get(
        proxyids: Annotated[list[str] | None, Field(default=None)] = None,
        search: Annotated[dict[str, str] | None, Field(default=None)] = None,
        filter_params: Annotated[dict[str, Any] | None, Field(default=None)] = None,
        output: Annotated[str, Field(default="extend")] = "extend",
        limit: Annotated[int | None, Field(default=None, ge=1)] = None,
        ctx: Context = None,
    ) -> dict:
        """
        Get proxies from Zabbix.

        Proxies act as data collection points for Zabbix, allowing monitoring of remote networks
        without direct connectivity. Proxies collect data locally and report to the Zabbix server.

        Args:
            proxyids: List of proxy IDs to get. If empty, returns all proxies.
            search: Dictionary with search criteria like {'host': 'proxy1'} for name matching.
            filter_params: Additional filter parameters for advanced filtering.
            limit: Maximum number of proxies to return (default unlimited).

        Returns:
            dict: Contains 'proxies' list with proxy objects and 'count' of returned proxies.
                  Each proxy includes:
                  - proxyid: Unique proxy ID
                  - host: Proxy hostname/name
                  - status: 5=active proxy, 6=passive proxy

        Example response:
            {
                "proxies": [
                    {"proxyid": "10000", "host": "proxy1", "status": "5"}
                ],
                "count": 1,
                "success": true
            }

        Note: Use proxy_create to add new proxies, proxy_delete to remove them.
              Assign hosts to proxies with host_create or host_update using proxyid field.
        """
        try:
            await ctx.info("Retrieving proxies...")
            params: dict[str, Any] = {"output": output}
            if proxyids:
                params["proxyids"] = proxyids
            if search:
                params["search"] = search
            if filter_params:
                params["filter"] = filter_params
            if limit:
                params["limit"] = limit

            async with ZabbixClient(config) as api:
                result = await api.proxy.get(**params)
                return {"proxies": result, "count": len(result)}
        except Exception as e:
            await ctx.error(f"Error retrieving proxies: {e!s}")
            return {"error": str(e)}

    @mcp.tool(
        tags={"zabbix", "proxy"},
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
        },
    )
    async def proxy_create(
        name: Annotated[str, Field(description="Proxy name.")],
        operating_mode: Annotated[
            int, Field(default=0, description="0=active, 1=passive.")
        ] = 0,
        description: Annotated[str | None, Field(default=None)] = None,
        ctx: Context = None,
    ) -> dict:
        """
        Create a new proxy in Zabbix.

        Proxies allow distributed monitoring by collecting data from remote networks and
        reporting to the central Zabbix server. Useful for firewall-separated networks or
        high-latency connections.

        Args:
            name: Proxy hostname/identifier. Should match the proxy machine hostname.
            operating_mode: 0=Active proxy (pulls config from server), 1=Passive proxy (server pushes config).
                           Default is 0 (active).
            description: Optional description explaining the proxy's purpose or location.

        Returns:
            dict: Contains 'proxyids' list with newly created proxy ID(s) and 'success' flag.

        Example response:
            {
                "proxyids": ["10001"],
                "success": true
            }

        Note: After creating, configure the proxy agent on the remote system and assign hosts
              to it using host_create or host_update with the proxyid.
        """
        try:
            await ctx.info(f"Creating proxy '{name}'...")
            params: dict[str, Any] = {"name": name, "operating_mode": operating_mode}
            if description:
                params["description"] = description

            async with ZabbixClient(config) as api:
                result = await api.proxy.create(**params)
                return {"proxyids": result.get("proxyids", []), "success": True}
        except Exception as e:
            await ctx.error(f"Error creating proxy: {e!s}")
            return {"error": str(e)}

    @mcp.tool(
        tags={"zabbix", "proxy"},
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
        },
    )
    async def proxy_update(
        proxyid: Annotated[str, Field(description="ID of the proxy to update.")],
        name: Annotated[str | None, Field(default=None)] = None,
        operating_mode: Annotated[
            int | None, Field(default=None, description="0=active, 1=passive.")
        ] = None,
        description: Annotated[str | None, Field(default=None)] = None,
        ctx: Context = None,
    ) -> dict:
        """
        Update an existing proxy in Zabbix.

        Modifies properties of an existing proxy. You can change the name,
        operating mode, or description. Only specify the fields you want to change.

        Args:
            proxyid: ID of the proxy to update (required). Find it with proxy_get.
            name: New proxy name/hostname.
            operating_mode: New operating mode (0=active, 1=passive).
            description: New description.

        Returns:
            dict: Contains 'proxyids' list with updated proxy IDs and 'success' flag.
                  On error, contains 'error' key with the error message.

        Example response:
            {
                "proxyids": ["10001"],
                "success": true
            }
        """
        try:
            await ctx.info(f"Updating proxy {proxyid}...")
            params: dict[str, Any] = {"proxyid": proxyid}
            if name is not None:
                params["name"] = name
            if operating_mode is not None:
                params["operating_mode"] = operating_mode
            if description is not None:
                params["description"] = description

            async with ZabbixClient(config) as api:
                result = await api.proxy.update(**params)
                return {"proxyids": result.get("proxyids", []), "success": True}
        except Exception as e:
            await ctx.error(f"Error updating proxy: {e!s}")
            return {"error": str(e)}

    @mcp.tool(
        tags={"zabbix", "proxy"},
        annotations={
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
        },
    )
    async def proxy_delete(
        proxyids: Annotated[list[str], Field(description="Proxy IDs to delete.")],
        ctx: Context = None,
    ) -> dict:
        """
        Delete proxies from Zabbix.

        Permanently removes proxy definitions. Hosts assigned to deleted proxies will need
        to be reassigned to other proxies or the server. Data from deleted proxies is typically retained.

        Args:
            proxyids: List of proxy IDs to delete. Find them with proxy_get.

        Returns:
            dict: Contains 'proxyids' list with deleted proxy IDs and 'success' flag.
                  On error, contains 'error' key with the error message.

        Example response:
            {
                "proxyids": ["10001"],
                "success": true
            }

        Warning: Hosts using this proxy will lose monitoring until reassigned. Plan reassignment
                 before deleting. Consider if data history should be preserved.
        """
        try:
            await ctx.info(f"Deleting proxies: {proxyids}...")
            async with ZabbixClient(config) as api:
                result = await api.proxy.delete(*proxyids)
                return {"proxyids": result.get("proxyids", []), "success": True}
        except Exception as e:
            await ctx.error(f"Error deleting proxies: {e!s}")
            return {"error": str(e)}

    ##########################
    # Proxy Tools
    ##########################

    @mcp.tool(
        tags={"zabbix", "maintenance", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def maintenance_get(
        maintenanceids: Annotated[list[str] | None, Field(default=None)] = None,
        groupids: Annotated[list[str] | None, Field(default=None)] = None,
        hostids: Annotated[list[str] | None, Field(default=None)] = None,
        output: Annotated[str, Field(default="extend")] = "extend",
        ctx: Context = None,
    ) -> dict:
        """
        Get maintenance periods from Zabbix.

        Maintenance windows define periods when monitoring is paused for planned upgrades,
        maintenance, or testing. Alerts are suppressed during maintenance periods.

        Args:
            maintenanceids: List of maintenance IDs to get. If empty, returns all maintenance periods.
            groupids: List of host group IDs to get maintenance for.
            hostids: List of host IDs to get maintenance for.

        Returns:
            dict: Contains 'maintenance' list with maintenance objects and 'count' of returned records.
                  Each maintenance includes:
                  - maintenanceid: Unique maintenance ID
                  - name: Maintenance window name
                  - active_since: Unix timestamp when maintenance becomes active
                  - active_till: Unix timestamp when maintenance ends

        Example response:
            {
                "maintenance": [
                    {
                        "maintenanceid": "3",
                        "name": "Patch Tuesday",
                        "active_since": "1699564800",
                        "active_till": "1699575600"
                    }
                ],
                "count": 1,
                "success": true
            }

        Note: Use maintenance_create to schedule maintenance, maintenance_delete to cancel it.
        """
        try:
            await ctx.info("Retrieving maintenance periods...")
            params: dict[str, Any] = {"output": output}
            if maintenanceids:
                params["maintenanceids"] = maintenanceids
            if groupids:
                params["groupids"] = groupids
            if hostids:
                params["hostids"] = hostids

            async with ZabbixClient(config) as api:
                result = await api.maintenance.get(**params)
                return {"maintenance": result, "count": len(result)}
        except Exception as e:
            await ctx.error(f"Error retrieving maintenance: {e!s}")
            return {"error": str(e)}

    @mcp.tool(
        tags={"zabbix", "maintenance"},
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
        },
    )
    async def maintenance_create(
        name: Annotated[str, Field(description="Maintenance name.")],
        active_since: Annotated[int, Field(description="Start time (Unix timestamp).")],
        active_till: Annotated[int, Field(description="End time (Unix timestamp).")],
        groupids: Annotated[list[str] | None, Field(default=None)] = None,
        hostids: Annotated[list[str] | None, Field(default=None)] = None,
        timeperiods: Annotated[list[dict[str, Any]] | None, Field(default=None)] = None,
        description: Annotated[str | None, Field(default=None)] = None,
        ctx: Context = None,
    ) -> dict:
        """
        Create a new maintenance period in Zabbix.

        Schedules a maintenance window when monitoring alerts are suppressed. Useful for planned
        upgrades, patching, or system maintenance without triggering false alarms.

        Args:
            name: Maintenance name displayed in the UI. Example: 'Server upgrade', 'Network maintenance'.
            active_since: Start time as Unix timestamp (when maintenance period begins).
            active_till: End time as Unix timestamp (when maintenance period ends).
            groupids: List of host group IDs to apply maintenance to. At least one of groupids
                     or hostids is required.
            hostids: List of specific host IDs to apply maintenance to.
            timeperiods: Optional list of time period objects for recurring maintenance.
            description: Optional description explaining the maintenance purpose.

        Returns:
            dict: Contains 'maintenanceids' list with newly created maintenance ID(s) and 'success' flag.

        Example response:
            {
                "maintenanceids": ["5"],
                "success": true
            }

        Note: During maintenance windows, no alerts are generated. Monitoring still occurs but alerts
              are suppressed. Use for planned maintenance to avoid alert fatigue.
        """
        try:
            await ctx.info(f"Creating maintenance '{name}'...")
            params: dict[str, Any] = {
                "name": name,
                "active_since": active_since,
                "active_till": active_till,
            }

            if groupids:
                params["groups"] = [{"groupid": str(g)} for g in groupids]

            if hostids:
                params["hosts"] = [{"hostid": str(h)} for h in hostids]

            if timeperiods:
                normalized: list[dict[str, Any]] = []
                for tp in timeperiods:
                    if not isinstance(tp, dict):
                        continue
                    ntp: dict[str, Any] = {}
                    if "timeperiod_type" in tp:
                        ntp["timeperiod_type"] = int(tp["timeperiod_type"])
                    if "start_date" in tp:
                        ntp["start_date"] = int(tp["start_date"])
                    if "period" in tp:
                        ntp["period"] = int(tp["period"])
                    if "dayofweek" in tp:
                        ntp["dayofweek"] = tp["dayofweek"]
                    if "start_time" in tp:
                        ntp["start_time"] = int(tp["start_time"])
                    if ntp:
                        normalized.append(ntp)
                if normalized:
                    params["timeperiods"] = normalized

            if description:
                params["description"] = description

            async with ZabbixClient(config) as api:
                result = await api.maintenance.create(**params)
                return {
                    "maintenanceids": result.get("maintenanceids", []),
                    "success": True,
                }
        except Exception as e:
            await ctx.error(f"Error creating maintenance: {e!s}")
            return {"error": str(e)}

    @mcp.tool(
        tags={"zabbix", "maintenance"},
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
        },
    )
    async def maintenance_update(
        maintenanceid: Annotated[
            str, Field(description="ID of the maintenance to update.")
        ],
        name: Annotated[str | None, Field(default=None)] = None,
        active_since: Annotated[int | None, Field(default=None)] = None,
        active_till: Annotated[int | None, Field(default=None)] = None,
        description: Annotated[str | None, Field(default=None)] = None,
        ctx: Context = None,
    ) -> dict:
        """
        Update an existing maintenance period in Zabbix.

        Modifies properties of an existing maintenance window. You can change the name,
        start time, end time, or description. Only specify the fields you want to change.

        Args:
            maintenanceid: ID of the maintenance to update (required). Find it with maintenance_get.
            name: New maintenance name.
            active_since: New start time (Unix timestamp).
            active_till: New end time (Unix timestamp).
            description: New description.

        Returns:
            dict: Contains 'maintenanceids' list with updated maintenance IDs and 'success' flag.
                  On error, contains 'error' key with the error message.

        Example response:
            {
                "maintenanceids": ["5"],
                "success": true
            }
        """
        try:
            await ctx.info(f"Updating maintenance {maintenanceid}...")
            params: dict[str, Any] = {"maintenanceid": maintenanceid}
            if name is not None:
                params["name"] = name
            if active_since is not None:
                params["active_since"] = active_since
            if active_till is not None:
                params["active_till"] = active_till
            if description is not None:
                params["description"] = description

            async with ZabbixClient(config) as api:
                result = await api.maintenance.update(**params)
                return {
                    "maintenanceids": result.get("maintenanceids", []),
                    "success": True,
                }
        except Exception as e:
            await ctx.error(f"Error updating maintenance: {e!s}")
            return {"error": str(e)}

    @mcp.tool(
        tags={"zabbix", "maintenance"},
        annotations={
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
        },
    )
    async def maintenance_delete(
        maintenanceids: Annotated[
            list[str], Field(description="Maintenance IDs to delete.")
        ],
        ctx: Context = None,
    ) -> dict:
        """
        Delete maintenance periods from Zabbix.

        Cancels maintenance windows immediately, resuming alert generation. If the maintenance
        period has already passed, historical event suppression is retained.

        Args:
            maintenanceids: List of maintenance IDs to delete. Find them with maintenance_get.

        Returns:
            dict: Contains 'maintenanceids' list with deleted maintenance IDs and 'success' flag.
                  On error, contains 'error' key with the error message.

        Example response:
            {
                "maintenanceids": ["5"],
                "success": true
            }

        Note: Alerts will resume immediately upon deletion. If maintenance period has passed,
              no impact on historical data. Consider timing of deletion to avoid alert storms.
        """
        try:
            await ctx.info(f"Deleting maintenance: {maintenanceids}...")
            async with ZabbixClient(config) as api:
                result = await api.maintenance.delete(*maintenanceids)
                return {
                    "maintenanceids": result.get("maintenanceids", []),
                    "success": True,
                }
        except Exception as e:
            await ctx.error(f"Error deleting maintenance: {e!s}")
            return {"error": str(e)}

    ##########################
    # Action Tools
    ##########################

    @mcp.tool(
        tags={"zabbix", "action", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def action_get(
        actionids: Annotated[list[str] | None, Field(default=None)] = None,
        groupids: Annotated[list[str] | None, Field(default=None)] = None,
        hostids: Annotated[list[str] | None, Field(default=None)] = None,
        search: Annotated[dict[str, str] | None, Field(default=None)] = None,
        filter_params: Annotated[dict[str, Any] | None, Field(default=None)] = None,
        output: Annotated[str, Field(default="extend")] = "extend",
        ctx: Context = None,
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

        Returns:
            dict: Contains 'actions' list with action objects and 'count' of returned actions.
                  Each action includes:
                  - actionid: Unique action ID
                  - name: Action name/description
                  - status: 0=enabled, 1=disabled
                  - esc_period: Escalation period

        Example response:
            {
                "actions": [
                    {"actionid": "1", "name": "Send notifications", "status": "0", "esc_period": "1h"}
                ],
                "count": 1,
                "success": true
            }

        Note: Actions are triggered when problem conditions are met. Use with caution in production.
        """
        try:
            await ctx.info("Retrieving actions...")
            params: dict[str, Any] = {"output": output}
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

            async with ZabbixClient(config) as api:
                result = await api.action.get(**params)
                return {"actions": result, "count": len(result)}
        except Exception as e:
            await ctx.error(f"Error retrieving actions: {e!s}")
            return {"error": str(e)}

    ##########################
    # Media Type Tools
    ##########################

    @mcp.tool(
        tags={"zabbix", "mediatype", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def mediatype_get(
        mediatypeids: Annotated[list[str] | None, Field(default=None)] = None,
        search: Annotated[dict[str, str] | None, Field(default=None)] = None,
        filter_params: Annotated[dict[str, Any] | None, Field(default=None)] = None,
        output: Annotated[str, Field(default="extend")] = "extend",
        ctx: Context = None,
    ) -> dict:
        """
        Get media types from Zabbix.

        Media types define communication channels for sending notifications (email, SMS, webhooks, etc.).
        Actions use media types to deliver alerts to users and integrations.

        Args:
            mediatypeids: List of media type IDs to get. If empty, returns all media types.
            search: Dictionary with search criteria like {'description': 'email'}.
            filter_params: Additional filter parameters for advanced filtering.

        Returns:
            dict: Contains 'mediatypes' list with media type objects and 'count' of returned types.
                  Each media type includes:
                  - mediatypeid: Unique media type ID
                  - type: Type code (0=email, 1=Exec script, 2=SMS, 3=Webhook, etc.)
                  - name: Media type name/description

        Example response:
            {
                "mediatypes": [
                    {"mediatypeid": "1", "type": "0", "name": "Email"}
                ],
                "count": 1,
                "success": true
            }

        Note: Use with actions to define alert routing. Configure alert settings in media type configuration.
        """
        try:
            await ctx.info("Retrieving media types...")
            params: dict[str, Any] = {"output": output}
            if mediatypeids:
                params["mediatypeids"] = mediatypeids
            if search:
                params["search"] = search
            if filter_params:
                params["filter"] = filter_params

            async with ZabbixClient(config) as api:
                result = await api.mediatype.get(**params)
                return {"mediatypes": result, "count": len(result)}
        except Exception as e:
            await ctx.error(f"Error retrieving media types: {e!s}")
            return {"error": str(e)}

    ##########################
    # Graph Tools
    ##########################

    @mcp.tool(
        tags={"zabbix", "graph", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def graph_get(
        graphids: Annotated[list[str] | None, Field(default=None)] = None,
        hostids: Annotated[list[str] | None, Field(default=None)] = None,
        templateids: Annotated[list[str] | None, Field(default=None)] = None,
        search: Annotated[dict[str, str] | None, Field(default=None)] = None,
        filter_params: Annotated[dict[str, Any] | None, Field(default=None)] = None,
        output: Annotated[str, Field(default="extend")] = "extend",
        ctx: Context = None,
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

        Returns:
            dict: Contains 'graphs' list with graph objects and 'count' of returned graphs.
                  Each graph includes:
                  - graphid: Unique graph ID
                  - name: Graph name
                  - type: Graph type (0=normal line, 1=stacked line, 2=bar, 3=pie)

        Example response:
            {
                "graphs": [
                    {"graphid": "562", "name": "CPU load", "type": "0"}
                ],
                "count": 1,
                "success": true
            }

        Note: Graphs display collected item data. Use for visualization and dashboard creation.
        """
        try:
            await ctx.info("Retrieving graphs...")
            params: dict[str, Any] = {"output": output}
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

            async with ZabbixClient(config) as api:
                result = await api.graph.get(**params)
                return {"graphs": result, "count": len(result)}
        except Exception as e:
            await ctx.error(f"Error retrieving graphs: {e!s}")
            return {"error": str(e)}

    ##########################
    # Discovery Tools
    ##########################

    @mcp.tool(
        tags={"zabbix", "discovery", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def discoveryrule_get(
        itemids: Annotated[list[str] | None, Field(default=None)] = None,
        hostids: Annotated[list[str] | None, Field(default=None)] = None,
        templateids: Annotated[list[str] | None, Field(default=None)] = None,
        search: Annotated[dict[str, str] | None, Field(default=None)] = None,
        filter_params: Annotated[dict[str, Any] | None, Field(default=None)] = None,
        output: Annotated[str, Field(default="extend")] = "extend",
        ctx: Context = None,
    ) -> dict:
        """
        Get discovery rules from Zabbix.

        Discovery rules automatically detect items, triggers, and interfaces from network resources.
        They enable dynamic host and item management without manual configuration.

        Args:
            itemids: List of item IDs (discovery rules are items) to get.
            hostids: List of host IDs to get discovery rules from.
            templateids: List of template IDs to get discovery rules from.
            search: Dictionary with search criteria like {'name': 'SNMP'}.
            filter_params: Additional filter parameters for advanced filtering.

        Returns:
            dict: Contains 'discoveryrules' list with discovery rule objects and 'count'.
                  Each rule includes:
                  - itemid: Discovery rule item ID
                  - name: Discovery rule name
                  - key_: Discovery rule key
                  - type: Discovery method (0=Zabbix agent, 2=SNMP, etc.)

        Example response:
            {
                "discoveryrules": [
                    {"itemid": "23789", "name": "Discover network devices", "key_": "discovery.key", "type": "2"}
                ],
                "count": 1,
                "success": true
            }

        Note: Discovery rules generate items and triggers dynamically. Monitor their status and adjust as needed.
        """
        try:
            await ctx.info("Retrieving discovery rules...")
            params: dict[str, Any] = {"output": output}
            if itemids:
                params["itemids"] = itemids
            if hostids:
                params["hostids"] = hostids
            if templateids:
                params["templateids"] = templateids
            if search:
                params["search"] = search
            if filter_params:
                params["filter"] = filter_params

            async with ZabbixClient(config) as api:
                result = await api.discoveryrule.get(**params)
                return {"discoveryrules": result, "count": len(result)}
        except Exception as e:
            await ctx.error(f"Error retrieving discovery rules: {e!s}")
            return {"error": str(e)}

    @mcp.tool(
        tags={"zabbix", "itemprototype", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def itemprototype_get(
        itemids: Annotated[list[str] | None, Field(default=None)] = None,
        hostids: Annotated[list[str] | None, Field(default=None)] = None,
        discoveryids: Annotated[list[str] | None, Field(default=None)] = None,
        search: Annotated[dict[str, str] | None, Field(default=None)] = None,
        filter_params: Annotated[dict[str, Any] | None, Field(default=None)] = None,
        output: Annotated[str, Field(default="extend")] = "extend",
        ctx: Context = None,
    ) -> dict:
        """
        Get item prototypes from Zabbix.

        Item prototypes are template items created by discovery rules that generate actual items
        dynamically based on discovered entities.

        Args:
            itemids: List of item prototype IDs to get.
            hostids: List of host IDs to get item prototypes from.
            discoveryids: List of discovery rule IDs to get prototypes from.
            search: Dictionary with search criteria like {'name': 'CPU'}.
            filter_params: Additional filter parameters for advanced filtering.

        Returns:
            dict: Contains 'itemprototypes' list with item prototype objects and 'count'.
                  Each prototype includes:
                  - itemid: Item prototype ID
                  - name: Item prototype name
                  - key_: Item prototype key
                  - type: Data collection method

        Example response:
            {
                "itemprototypes": [
                    {"itemid": "23790", "name": "CPU load", "key_": "system.cpu.load", "type": "0"}
                ],
                "count": 1,
                "success": true
            }

        Note: Item prototypes create items dynamically. Use discovery rules to manage them.
        """
        try:
            await ctx.info("Retrieving item prototypes...")
            params: dict[str, Any] = {"output": output}
            if itemids:
                params["itemids"] = itemids
            if hostids:
                params["hostids"] = hostids
            if discoveryids:
                params["discoveryids"] = discoveryids
            if search:
                params["search"] = search
            if filter_params:
                params["filter"] = filter_params

            async with ZabbixClient(config) as api:
                result = await api.itemprototype.get(**params)
                return {"itemprototypes": result, "count": len(result)}
        except Exception as e:
            await ctx.error(f"Error retrieving item prototypes: {e!s}")
            return {"error": str(e)}

    @mcp.tool(
        tags={"zabbix", "drule", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def drule_get(
        druleids: Annotated[list[str] | None, Field(default=None)] = None,
        search: Annotated[dict[str, str] | None, Field(default=None)] = None,
        filter_params: Annotated[dict[str, Any] | None, Field(default=None)] = None,
        output: Annotated[str, Field(default="extend")] = "extend",
        ctx: Context = None,
    ) -> dict:
        """
        Get network discovery rules from Zabbix.

        Network discovery (drule) rules perform network scanning to discover hosts and services.
        They can scan for active devices, open ports, and available services in CIDR ranges.

        Args:
            druleids: List of network discovery rule IDs to get. If empty, returns all rules.
            search: Dictionary with search criteria like {'name': 'LAN'}.
            filter_params: Additional filter parameters for advanced filtering.

        Returns:
            dict: Contains 'drules' list with network discovery rule objects and 'count'.
                  Each rule includes:
                  - druleid: Discovery rule ID
                  - name: Rule name
                  - status: 0=enabled, 1=disabled

        Example response:
            {
                "drules": [
                    {"druleid": "4", "name": "Local LAN discovery", "status": "0"}
                ],
                "count": 1,
                "success": true
            }

        Note: Network discovery performs network scans. Use carefully to avoid performance impact.
        """
        try:
            await ctx.info("Retrieving network discovery rules...")
            params: dict[str, Any] = {"output": output}
            if druleids:
                params["druleids"] = druleids
            if search:
                params["search"] = search
            if filter_params:
                params["filter"] = filter_params

            async with ZabbixClient(config) as api:
                result = await api.drule.get(**params)
                return {"drules": result, "count": len(result)}
        except Exception as e:
            await ctx.error(f"Error retrieving network discovery rules: {e!s}")
            return {"error": str(e)}

    @mcp.tool(
        tags={"zabbix", "configuration", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def configuration_export(
        format_type: Annotated[
            str,
            Field(
                default="json",
                description="Export format: 'json' or 'xml'.",
            ),
        ] = "json",
        prettyprint: Annotated[
            int,
            Field(default=0, description="0=normal, 1=pretty-printed."),
        ] = 0,
        hostids: Annotated[list[str] | None, Field(default=None)] = None,
        templateids: Annotated[list[str] | None, Field(default=None)] = None,
        groupids: Annotated[list[str] | None, Field(default=None)] = None,
        ctx: Context = None,
    ) -> dict:
        """
        Export Zabbix configurations.

        Exports monitored hosts, templates, and groups to JSON or XML format.
        Useful for backup, migration, or sharing configurations.

        Args:
            format_type: Export format: 'json' or 'xml'. Default is 'json'.
            prettyprint: 0=normal format, 1=pretty-printed format.
            hostids: List of host IDs to export. If empty, exports all.
            templateids: List of template IDs to export.
            groupids: List of group IDs to export.

        Returns:
            dict: Contains 'content' with the exported configuration data.
                  The format depends on the format_type parameter.

        Example response:
            {
                "content": "{ ... JSON/XML content ... }",
                "success": true
            }

        Note: Large exports may take time. Use specific IDs for targeted exports.
        """
        try:
            await ctx.info("Exporting configuration...")
            params: dict[str, Any] = {"format": format_type, "prettyprint": prettyprint}
            if hostids:
                params["hostids"] = hostids
            if templateids:
                params["templateids"] = templateids
            if groupids:
                params["groupids"] = groupids

            async with ZabbixClient(config) as api:
                result = await api.configuration.export(**params)
                return {"content": result, "success": True}
        except Exception as e:
            await ctx.error(f"Error exporting configuration: {e!s}")
            return {"error": str(e)}

    @mcp.tool(
        tags={"zabbix", "configuration"},
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
        },
    )
    async def configuration_import(
        content: Annotated[str, Field(description="Configuration content to import.")],
        format_type: Annotated[
            str,
            Field(
                default="json",
                description="Import format: 'json' or 'xml'.",
            ),
        ] = "json",
        ctx: Context = None,
    ) -> dict:
        """
        Import configurations into Zabbix.

        Imports hosts, templates, and other configurations from JSON or XML format.
        Useful for migration, cloning, or restoring configurations.

        Args:
            content: Configuration content to import (JSON or XML string).
            format_type: Import format: 'json' or 'xml'. Default is 'json'.

        Returns:
            dict: Contains import result with created/updated object counts.
                  Returns success flag and summary of imported items.

        Example response:
            {
                "result": {"hosts": {"created": 1, "updated": 0}},
                "success": true
            }

        Warning: Importing can create or overwrite existing configurations.
                 Verify content before importing in production environments.
        """
        try:
            await ctx.info("Importing configuration...")
            params: dict[str, Any] = {"format": format_type, "source": content}

            async with ZabbixClient(config) as api:
                result = await api.configuration.import_config(**params)
                return {"result": result, "success": True}
        except Exception as e:
            await ctx.error(f"Error importing configuration: {e!s}")
            return {"error": str(e)}

    ##########################
    # SLA Tools
    ##########################

    @mcp.tool(
        tags={"zabbix", "sla", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def sla_get(
        slaids: Annotated[list[str] | None, Field(default=None)] = None,
        serviceids: Annotated[list[str] | None, Field(default=None)] = None,
        search: Annotated[dict[str, str] | None, Field(default=None)] = None,
        filter_params: Annotated[dict[str, Any] | None, Field(default=None)] = None,
        output: Annotated[str, Field(default="extend")] = "extend",
        ctx: Context = None,
    ) -> dict:
        """
        Get SLAs from Zabbix.

        Service Level Agreements (SLAs) define uptime and availability targets for services.
        They track compliance with service objectives and generate reports on availability.

        Args:
            slaids: List of SLA IDs to get. If empty, returns all SLAs.
            serviceids: List of service IDs to get SLAs for.
            search: Dictionary with search criteria like {'name': 'Website'}.
            filter_params: Additional filter parameters for advanced filtering.

        Returns:
            dict: Contains 'slas' list with SLA objects and 'count' of returned SLAs.
                  Each SLA includes:
                  - slaid: Unique SLA ID
                  - name: SLA name
                  - slo: Service Level Objective percentage target
                  - status: 0=enabled, 1=disabled

        Example response:
            {
                "slas": [
                    {"slaid": "1", "name": "Production SLA", "slo": "99.9", "status": "0"}
                ],
                "count": 1,
                "success": true
            }

        Note: SLAs measure service availability. Track compliance and generate reports.
        """
        try:
            await ctx.info("Retrieving SLAs...")
            params: dict[str, Any] = {"output": output}
            if slaids:
                params["slaids"] = slaids
            if serviceids:
                params["serviceids"] = serviceids
            if search:
                params["search"] = search
            if filter_params:
                params["filter"] = filter_params

            async with ZabbixClient(config) as api:
                result = await api.sla.get(**params)
                return {"slas": result, "count": len(result)}
        except Exception as e:
            await ctx.error(f"Error retrieving SLAs: {e!s}")
            return {"error": str(e)}

    @mcp.tool(
        tags={"zabbix", "service", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def service_get(
        serviceids: Annotated[list[str] | None, Field(default=None)] = None,
        parentids: Annotated[list[str] | None, Field(default=None)] = None,
        search: Annotated[dict[str, str] | None, Field(default=None)] = None,
        filter_params: Annotated[dict[str, Any] | None, Field(default=None)] = None,
        output: Annotated[str, Field(default="extend")] = "extend",
        ctx: Context = None,
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

        Returns:
            dict: Contains 'services' list with service objects and 'count' of returned services.
                  Each service includes:
                  - serviceid: Unique service ID
                  - name: Service name
                  - status: Service status/availability

        Example response:
            {
                "services": [
                    {"serviceid": "1", "name": "Web Application", "status": "0"}
                ],
                "count": 1,
                "success": true
            }

        Note: Services form the basis for SLA tracking. Define service hierarchies for dependency mapping.
        """
        try:
            await ctx.info("Retrieving services...")
            params: dict[str, Any] = {"output": output}
            if serviceids:
                params["serviceids"] = serviceids
            if parentids:
                params["parentids"] = parentids
            if search:
                params["search"] = search
            if filter_params:
                params["filter"] = filter_params

            async with ZabbixClient(config) as api:
                result = await api.service.get(**params)
                return {"services": result, "count": len(result)}
        except Exception as e:
            await ctx.error(f"Error retrieving services: {e!s}")
            return {"error": str(e)}

    ###########################
    # Script Tools
    ###########################

    @mcp.tool(
        tags={"zabbix", "script", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def script_get(
        scriptids: Annotated[list[str] | None, Field(default=None)] = None,
        hostids: Annotated[list[str] | None, Field(default=None)] = None,
        groupids: Annotated[list[str] | None, Field(default=None)] = None,
        search: Annotated[dict[str, str] | None, Field(default=None)] = None,
        filter_params: Annotated[dict[str, Any] | None, Field(default=None)] = None,
        output: Annotated[str, Field(default="extend")] = "extend",
        ctx: Context = None,
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

        Returns:
            dict: Contains 'scripts' list with script objects and 'count' of returned scripts.
                  Each script includes:
                  - scriptid: Unique script ID
                  - name: Script name
                  - command: Script command or code

        Example response:
            {
                "scripts": [
                    {"scriptid": "1", "name": "Restart service", "command": "systemctl restart service"}
                ],
                "count": 1,
                "success": true
            }

        Note: Scripts can be run manually or triggered by actions. Use for automation and remediation.
        """
        try:
            await ctx.info("Retrieving scripts...")
            params: dict[str, Any] = {"output": output}
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

            async with ZabbixClient(config) as api:
                result = await api.script.get(**params)
                return {"scripts": result, "count": len(result)}
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
        scriptid: Annotated[str, Field(description="Script ID to execute.")],
        hostid: Annotated[str, Field(description="Host ID to execute the script on.")],
        ctx: Context = None,
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

        Example response:
            {
                "response": "Service restarted successfully",
                "success": true
            }

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

    @mcp.tool(
        tags={"zabbix", "usermacro", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def usermacro_get(
        hostmacroids: Annotated[list[str] | None, Field(default=None)] = None,
        globalmacroids: Annotated[list[str] | None, Field(default=None)] = None,
        hostids: Annotated[list[str] | None, Field(default=None)] = None,
        templateids: Annotated[list[str] | None, Field(default=None)] = None,
        globalmacro: Annotated[
            bool, Field(default=False, description="Return global macros.")
        ] = False,
        search: Annotated[dict[str, str] | None, Field(default=None)] = None,
        filter_params: Annotated[dict[str, Any] | None, Field(default=None)] = None,
        output: Annotated[str, Field(default="extend")] = "extend",
        ctx: Context = None,
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

        Returns:
            dict: Contains 'macros' list with macro objects and 'count' of returned macros.
                  Each macro includes:
                  - hostmacrois/globalmacrois: Macro ID
                  - macro: Macro name/identifier
                  - value: Macro value
                  - description: Optional description

        Example response:
            {
                "macros": [
                    {"hostmacroids": "10", "macro": "{$THRESHOLD}", "value": "80"}
                ],
                "count": 1,
                "success": true
            }

        Note: Use {$MACRO_NAME} syntax in items and triggers to reference macros. Global macros apply to all hosts.
        """
        try:
            await ctx.info("Retrieving user macros...")
            params: dict[str, Any] = {"output": output}
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

            async with ZabbixClient(config) as api:
                result = await api.usermacro.get(**params)
                return {"macros": result, "count": len(result)}
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
        hostid: Annotated[str, Field(description="Host ID for the macro.")],
        macro: Annotated[str, Field(description="Macro name (e.g., {$MYMACRO}).")],
        value: Annotated[str, Field(description="Macro value.")],
        type_: Annotated[
            int, Field(default=0, description="0=text, 1=secret, 2=vault.")
        ] = 0,
        description: Annotated[str | None, Field(default=None)] = None,
        ctx: Context = None,
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

        Example response:
            {
                "hostmacroids": ["12"],
                "success": true
            }

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
        hostmacroids: Annotated[
            list[str], Field(description="Host macro IDs to delete.")
        ],
        ctx: Context = None,
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

        Example response:
            {
                "hostmacroids": ["12"],
                "success": true
            }

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
