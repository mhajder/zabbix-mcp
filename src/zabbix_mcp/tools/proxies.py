"""
Zabbix MCP Server Proxies Tools
"""

from typing import Annotated
from typing import Any

from fastmcp import Context
from pydantic import Field

from zabbix_mcp.models import ZabbixConfig
from zabbix_mcp.zabbix_client import ZabbixClient


def register_proxies_tools(mcp, config: ZabbixConfig):
    """Register Zabbix proxies tools with the MCP server"""

    @mcp.tool(
        tags={"zabbix", "proxy", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def proxy_get(
        ctx: Context,
        proxyids: Annotated[list[str] | None, Field(default=None)] = None,
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
        Get proxies from Zabbix.

        Proxies act as data collection points for Zabbix, allowing monitoring of remote networks
        without direct connectivity. Proxies collect data locally and report to the Zabbix server.

        Args:
            proxyids: List of proxy IDs to get. If empty, returns all proxies.
            search: Dictionary with search criteria like {'host': 'proxy1'} for name matching.
            filter_params: Additional filter parameters for advanced filtering.
            limit: Maximum number of results to return (default 100). Set higher for more results.
            offset: Number of results to skip for pagination. Use with sortfield.

        Returns:
            dict: Contains 'proxies' list with proxy objects, 'count' of returned proxies,
                  and pagination metadata ('limit', 'offset').
                  Each proxy includes:
                  - proxyid: Unique proxy ID
                  - host: Proxy hostname/name
                  - status: 5=active proxy, 6=passive proxy

        Note: Use proxy_create to add new proxies, proxy_delete to remove them.
              Assign hosts to proxies with host_create or host_update using proxyid field.
        """
        try:
            await ctx.info("Retrieving proxies...")
            params: dict[str, Any] = {"output": output}
            if sortfield:
                params["sortfield"] = sortfield
            if sortorder:
                params["sortorder"] = sortorder
            if count_output:
                params["countOutput"] = True
            if proxyids:
                params["proxyids"] = proxyids
            if search:
                params["search"] = search
            if filter_params:
                params["filter"] = filter_params
            params["limit"] = limit
            if offset > 0:
                params["offset"] = offset

            async with ZabbixClient(config) as api:
                result = await api.proxy.get(**params)
                return {
                    "proxies": result,
                    "count": int(result) if count_output else len(result),
                    "limit": limit,
                    "offset": offset,
                }
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
        ctx: Context,
        name: Annotated[str, Field(description="Proxy name.")],
        operating_mode: Annotated[
            int, Field(default=0, description="0=active, 1=passive.")
        ] = 0,
        description: Annotated[str | None, Field(default=None)] = None,
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
        ctx: Context,
        proxyid: Annotated[str, Field(description="ID of the proxy to update.")],
        name: Annotated[str | None, Field(default=None)] = None,
        operating_mode: Annotated[
            int | None, Field(default=None, description="0=active, 1=passive.")
        ] = None,
        description: Annotated[str | None, Field(default=None)] = None,
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
        ctx: Context,
        proxyids: Annotated[list[str], Field(description="Proxy IDs to delete.")],
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
