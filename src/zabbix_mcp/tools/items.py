"""
Zabbix MCP Server Items Tools
"""

from typing import Annotated
from typing import Any

from fastmcp import Context
from pydantic import Field

from zabbix_mcp.models import ZabbixConfig
from zabbix_mcp.zabbix_client import ZabbixClient


def register_items_tools(mcp, config: ZabbixConfig):
    """Register Zabbix items tools with the MCP server"""

    @mcp.tool(
        tags={"zabbix", "item", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def item_get(
        ctx: Context,
        itemids: Annotated[list[str] | None, Field(default=None)] = None,
        hostids: Annotated[list[str] | None, Field(default=None)] = None,
        groupids: Annotated[list[str] | None, Field(default=None)] = None,
        templateids: Annotated[list[str] | None, Field(default=None)] = None,
        search: Annotated[dict[str, str] | None, Field(default=None)] = None,
        filter_params: Annotated[dict[str, Any] | None, Field(default=None)] = None,
        item_name_contains: Annotated[
            str | None,
            Field(
                default=None,
                description="Shortcut to search for items by name (constructs search={'name': item_name_contains}).",
            ),
        ] = None,
        item_key_contains: Annotated[
            str | None,
            Field(
                default=None,
                description="Shortcut to search for items by key (constructs search={'key_': item_key_contains}).",
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
        select_hosts: Annotated[
            bool,
            Field(
                default=False,
                description="If true, include the hosts each item belongs to in the response (selectHosts=extend).",
            ),
        ] = False,
        select_tags: Annotated[
            bool,
            Field(
                default=False,
                description="If true, include the tags for each item in the response (selectTags=extend).",
            ),
        ] = False,
        select_triggers: Annotated[
            bool,
            Field(
                default=False,
                description="If true, include the triggers for each item in the response (selectTriggers=extend).",
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
            item_name_contains: Shortcut to search for items by name (adds to 'search').
            item_key_contains: Shortcut to search for items by key (adds to 'search').
            limit: Maximum number of results to return (default 100). Set higher for more results.
            offset: Number of results to skip for pagination. Use with sortfield.
            select_hosts: If true, include the hosts each item belongs to.
            select_tags: If true, include the tags for each item.
            select_triggers: If true, include the triggers associated with each item.

        Returns:
            dict: Contains 'items' list with item objects, 'count' of results returned,
                  and pagination metadata ('limit', 'offset').
                  Each item includes:
                  - itemid: Unique item ID
                  - name: Item name (e.g., 'CPU load average')
                  - key_: Item key (e.g., 'system.cpu.load')
                  - type: Collection method (0=Zabbix agent, 2=SNMP, 3=IPMI, etc.)
                  - value_type: Data type (0=numeric float, 1=character, 3=numeric unsigned, 4=log)
                  - status: 0=enabled, 1=disabled
                  - interval: Collection interval in seconds

        Note: Use item_create to add new metrics to monitor, item_delete to remove them.
        """
        try:
            await ctx.info("Retrieving items...")
            params: dict[str, Any] = {"output": output}
            if sortfield:
                params["sortfield"] = sortfield
            if sortorder:
                params["sortorder"] = sortorder
            if count_output:
                params["countOutput"] = True
            if itemids:
                params["itemids"] = itemids
            if hostids:
                params["hostids"] = hostids
            if groupids:
                params["groupids"] = groupids
            if templateids:
                params["templateids"] = templateids
            _search = dict(search) if search is not None else {}
            if item_name_contains is not None:
                _search["name"] = item_name_contains
            if item_key_contains is not None:
                _search["key_"] = item_key_contains
            if _search:
                params["search"] = _search
            if filter_params:
                params["filter"] = dict(filter_params)
            params["limit"] = limit
            if offset > 0:
                params["offset"] = offset
            if select_hosts:
                params["selectHosts"] = "extend"
            if select_tags:
                params["selectTags"] = "extend"
            if select_triggers:
                params["selectTriggers"] = "extend"

            async with ZabbixClient(config) as api:
                result = await api.item.get(**params)
                return {
                    "items": result,
                    "count": int(result) if count_output else len(result),
                    "limit": limit,
                    "offset": offset,
                }
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
        ctx: Context,
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
        ctx: Context,
        itemid: Annotated[str, Field(description="ID of the item to update.")],
        name: Annotated[str | None, Field(default=None)] = None,
        delay: Annotated[str | None, Field(default=None)] = None,
        units: Annotated[str | None, Field(default=None)] = None,
        description: Annotated[str | None, Field(default=None)] = None,
        status: Annotated[
            int | None,
            Field(default=None, description="0=enabled, 1=disabled."),
        ] = None,
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
        ctx: Context,
        itemids: Annotated[list[str], Field(description="Item IDs to delete.")],
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
        tags={"zabbix", "itemprototype", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def itemprototype_get(
        ctx: Context,
        itemids: Annotated[list[str] | None, Field(default=None)] = None,
        hostids: Annotated[list[str] | None, Field(default=None)] = None,
        discoveryids: Annotated[list[str] | None, Field(default=None)] = None,
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
        Get item prototypes from Zabbix.

        Item prototypes are template items created by discovery rules that generate actual items
        dynamically based on discovered entities.

        Args:
            itemids: List of item prototype IDs to get.
            hostids: List of host IDs to get item prototypes from.
            discoveryids: List of discovery rule IDs to get prototypes from.
            search: Dictionary with search criteria like {'name': 'CPU'}.
            filter_params: Additional filter parameters for advanced filtering.
            limit: Maximum number of results to return (default 100). Set higher for more results.
            offset: Number of results to skip for pagination. Use with sortfield.

        Returns:
            dict: Contains 'itemprototypes' list with item prototype objects, 'count',
                  and pagination metadata ('limit', 'offset').
                  Each prototype includes:
                  - itemid: Item prototype ID
                  - name: Item prototype name
                  - key_: Item prototype key
                  - type: Data collection method

        Note: Item prototypes create items dynamically. Use discovery rules to manage them.
        """
        try:
            await ctx.info("Retrieving item prototypes...")
            params: dict[str, Any] = {"output": output}
            if sortfield:
                params["sortfield"] = sortfield
            if sortorder:
                params["sortorder"] = sortorder
            if count_output:
                params["countOutput"] = True
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

            params["limit"] = limit
            if offset > 0:
                params["offset"] = offset

            async with ZabbixClient(config) as api:
                result = await api.itemprototype.get(**params)
                return {
                    "itemprototypes": result,
                    "count": int(result) if count_output else len(result),
                    "limit": limit,
                    "offset": offset,
                }
        except Exception as e:
            await ctx.error(f"Error retrieving item prototypes: {e!s}")
            return {"error": str(e)}
