"""
Zabbix MCP Server Hosts Tools
"""

from typing import Annotated
from typing import Any

from fastmcp import Context
from pydantic import Field

from zabbix_mcp.models import ZabbixConfig
from zabbix_mcp.zabbix_client import ZabbixClient


def register_hosts_tools(mcp, config: ZabbixConfig):
    """Register Zabbix hosts tools with the MCP server"""

    @mcp.tool(
        tags={"zabbix", "host", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def host_get(
        ctx: Context,
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
                default=None,
                description="Search criteria (e.g., {'host': 'web'} to perform a 'LIKE' search).",
            ),
        ] = None,
        filter_params: Annotated[
            dict[str, Any] | None,
            Field(default=None, description="Filter criteria (e.g., {'status': 0})."),
        ] = None,
        hostname_contains: Annotated[
            str | None,
            Field(
                default=None,
                description="Shortcut to search for hosts by name (constructs search={'host': hostname_contains}).",
            ),
        ] = None,
        status: Annotated[
            int | str | None,
            Field(
                default=None,
                description="Shortcut to filter by status (0=enabled, 1=disabled) (constructs filter={'status': status}).",
            ),
        ] = None,
        output: Annotated[
            str | list[str],
            Field(
                default="extend",
                description="Output format: 'extend' or specific fields.",
            ),
        ] = "extend",
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
                description="If true, include the host groups each host belongs to in the response (selectGroups=extend).",
            ),
        ] = False,
        select_templates: Annotated[
            bool,
            Field(
                default=False,
                description="If true, include the templates linked to each host in the response (selectTemplates=extend).",
            ),
        ] = False,
        select_interfaces: Annotated[
            bool,
            Field(
                default=False,
                description="If true, include the interfaces for each host in the response (selectInterfaces=extend).",
            ),
        ] = False,
        select_tags: Annotated[
            bool,
            Field(
                default=False,
                description="If true, include the tags for each host in the response (selectTags=extend).",
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
        Get hosts from Zabbix with optional filtering.

        Retrieves a list of monitored hosts from Zabbix. You can filter by host IDs,
        groups, templates, proxies, or use search criteria. This is useful for discovering
        which hosts are available in your monitoring system.

        Args:
            hostids: Specific host IDs to retrieve. If empty, retrieves all hosts.
            groupids: Filter hosts by group membership (host must belong to these groups).
            templateids: Filter hosts that use specific templates.
            proxyids: Filter hosts assigned to specific proxies.
            search: Search pattern for host name. If no additional options are given, this will perform a 'LIKE "%...%"' search.
            filter_params: Exact match filter (e.g., {'status': '0'} for enabled hosts).
            hostname_contains: Shortcut to search for hosts by name (adds to 'search').
            status: Shortcut to filter by status (0=enabled, 1=disabled) (adds to 'filter_params').
            output: 'extend' returns all fields, or specify specific field names.
            limit: Maximum number of results to return (default 100). Set higher for more results.
            offset: Number of results to skip for pagination. Use with sortfield.
            select_groups: If true, each host includes a 'groups' list with its host groups.
            select_templates: If true, each host includes a 'parentTemplates' list with linked templates.
            select_interfaces: If true, each host includes an 'interfaces' list.
            select_tags: If true, each host includes a 'tags' list.

        Returns:
            dict: Contains 'hosts' list with host objects, 'count' of results returned,
                  and pagination metadata ('limit', 'offset').
                  Each host contains: hostid, host (technical name), name (visible name),
                  status, groups, interfaces, and other host properties.
        """
        try:
            await ctx.info("Retrieving hosts...")
            params: dict[str, Any] = {"output": output}
            if sortfield:
                params["sortfield"] = sortfield
            if sortorder:
                params["sortorder"] = sortorder
            if count_output:
                params["countOutput"] = True

            if hostids:
                params["hostids"] = hostids
            if groupids:
                params["groupids"] = groupids
            if templateids:
                params["templateids"] = templateids
            if proxyids:
                params["proxyids"] = proxyids
            _search = dict(search) if search is not None else {}
            if hostname_contains is not None:
                _search["host"] = hostname_contains
            if _search:
                params["search"] = _search
            _filter = dict(filter_params) if filter_params is not None else {}
            if status is not None:
                _filter["status"] = status
            if _filter:
                params["filter"] = _filter
            params["limit"] = limit
            if offset > 0:
                params["offset"] = offset
            if select_groups:
                params["selectGroups"] = "extend"
            if select_templates:
                params["selectParentTemplates"] = "extend"
            if select_interfaces:
                params["selectInterfaces"] = "extend"
            if select_tags:
                params["selectTags"] = "extend"

            async with ZabbixClient(config) as api:
                result = await api.host.get(**params)
                return {
                    "hosts": result,
                    "count": int(result) if count_output else len(result),
                    "limit": limit,
                    "offset": offset,
                }

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
        ctx: Context,
        params: Annotated[
            dict[str, Any] | None,
            Field(
                default=None,
                description="Raw params dict for bulk operations. If provided, individual parameters are ignored.",
            ),
        ] = None,
        host: Annotated[
            str | None, Field(default=None, description="Technical name of the host.")
        ] = None,
        groups: Annotated[
            list[dict[str, str]] | None,
            Field(default=None, description="Host groups (e.g., [{'groupid': '1'}])."),
        ] = None,
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

        Note: Use hostgroup_get to find group IDs and template_get to find template IDs.
        """
        try:
            # Use custom params dict if provided, otherwise build from individual parameters
            if params is None:
                await ctx.info(f"Creating host '{host}'...")
                params = {"host": host, "groups": groups, "status": status}
                if interfaces:
                    params["interfaces"] = interfaces
                if templates:
                    params["templates"] = templates
                if name:
                    params["name"] = name
                if description:
                    params["description"] = description
            else:
                await ctx.info("Creating host(s) using custom params dict...")

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
        ctx: Context,
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
        ctx: Context,
        hostids: Annotated[list[str], Field(description="List of host IDs to delete.")],
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
        ctx: Context,
        groupids: Annotated[
            list[str] | None, Field(default=None, description="Group IDs.")
        ] = None,
        hostids: Annotated[
            list[str] | None, Field(default=None, description="Host IDs.")
        ] = None,
        search: Annotated[
            dict[str, str] | None, Field(default=None, description="Search.")
        ] = None,
        group_name_contains: Annotated[
            str | None,
            Field(
                default=None,
                description="Shortcut to search for groups by name (constructs search={'name': group_name_contains}).",
            ),
        ] = None,
        output: Annotated[
            str | list[str], Field(default="extend", description="Output format.")
        ] = "extend",
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
        select_hosts: Annotated[
            bool,
            Field(
                default=False,
                description="If true, include the hosts in each group in the response (selectHosts=extend).",
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
        Get host groups from Zabbix.

        Retrieves host groups with optional filtering. Host groups are used to organize
        and manage hosts collectively, applying templates, permissions, and maintenance
        windows to multiple hosts at once.

        Args:
            groupids: List of host group IDs to get. If empty, returns all groups.
                      Find group IDs with a search or from existing hosts.
            search: Substring search in group name. Matches partial names like 'Web' finds 'Web Servers'.
                    Case-sensitive partial match.
            group_name_contains: Shortcut to search for groups by name (adds to 'search').
            limit: Maximum number of results to return (default 100). Set higher for more results.
            offset: Number of results to skip for pagination. Use with sortfield.
            select_hosts: If true, include the hosts in each group.

        Returns:
            dict: Contains 'groups' list with group objects (id, name), 'count' of results returned,
                  and pagination metadata ('limit', 'offset').
                  Each group object has:
                  - groupid: Unique group ID
                  - name: Group name (e.g., 'Linux servers', 'Web Servers')

        Note: Use host_get to see which hosts belong to a group, or which groups contain specific hosts.
        """
        try:
            await ctx.info("Retrieving host groups...")
            params: dict[str, Any] = {"output": output}
            if sortfield:
                params["sortfield"] = sortfield
            if sortorder:
                params["sortorder"] = sortorder
            if count_output:
                params["countOutput"] = True
            if groupids:
                params["groupids"] = groupids
            if hostids:
                params["hostids"] = hostids
            _search = dict(search) if search is not None else {}
            if group_name_contains is not None:
                _search["name"] = group_name_contains
            if _search:
                params["search"] = _search
            params["limit"] = limit
            if offset > 0:
                params["offset"] = offset
            if select_hosts:
                params["selectHosts"] = "extend"

            async with ZabbixClient(config) as api:
                result = await api.hostgroup.get(**params)
                return {
                    "groups": result,
                    "count": int(result) if count_output else len(result),
                    "limit": limit,
                    "offset": offset,
                }
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
        ctx: Context,
        name: Annotated[str, Field(description="Name of the host group.")],
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
        ctx: Context,
        groupid: Annotated[str, Field(description="ID of the group to update.")],
        name: Annotated[str | None, Field(default=None)] = None,
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
        ctx: Context,
        groupids: Annotated[list[str], Field(description="Group IDs to delete.")],
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
