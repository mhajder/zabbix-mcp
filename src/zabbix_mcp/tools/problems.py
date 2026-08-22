"""
Zabbix MCP Server Problems Tools
"""

from typing import Annotated
from typing import Any

from fastmcp import Context
from pydantic import Field

from zabbix_mcp.models import ZabbixConfig
from zabbix_mcp.tools.pagination import fetch_page
from zabbix_mcp.tools.pagination import fetch_total
from zabbix_mcp.zabbix_client import ZabbixClient


def register_problems_tools(mcp, config: ZabbixConfig):
    """Register Zabbix problems tools with the MCP server"""

    @mcp.tool(
        tags={"zabbix", "problem", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def problem_get(
        ctx: Context,
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
            list[int | str] | None,
            Field(default=None, description="Severity levels 0-5."),
        ] = None,
        search: Annotated[dict[str, str] | None, Field(default=None)] = None,
        name_contains: Annotated[
            str | None,
            Field(
                default=None,
                description="Shortcut to search for problems by name (constructs search={'name': name_contains}).",
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
        acknowledged: Annotated[
            bool | None,
            Field(
                default=None,
                description="If false, return only unacknowledged problems. If true, return only acknowledged problems.",
            ),
        ] = None,
        suppressed: Annotated[
            bool | None,
            Field(
                default=None,
                description="If false, return only unsuppressed problems. If true, return only suppressed problems.",
            ),
        ] = None,
        sortfield: Annotated[
            str,
            Field(
                default="eventid",
                description="Field to sort by. A deterministic sort is required for paging to be consistent.",
            ),
        ] = "eventid",
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
            search: Dictionary with search criteria like {'name': 'CPU'}.
            name_contains: Shortcut to search for problems by name (adds to 'search').
            limit: Maximum number of results to return (default 100). Set higher for more results.
            offset: Number of matching records to skip, for paging.
            acknowledged: False = unacknowledged only, True = acknowledged only, None = all.
            suppressed: False = unsuppressed only, True = suppressed only, None = all.

        Returns:
            dict: Contains 'problems' list with problem objects, 'count' of results returned,
                  'total' matching records, the applied 'limit' and 'offset', and
                  'has_more' indicating whether further pages exist.
                  Each problem includes:
                  - eventid: Event ID of the problem
                  - objectid: Trigger ID that caused the problem
                  - clock: Unix timestamp when problem occurred
                  - ns: Nanosecond adjustment
                  - acknowledged: 0=unacknowledged, 1=acknowledged

        Note: Use event_acknowledge to mark problems as seen. Get more details with event_get.
        """
        try:
            await ctx.info("Retrieving problems...")
            # Sorting is kept out of 'filters' because Zabbix rejects
            # countOutput combined with sortfield.
            sort: dict[str, Any] = {"sortfield": sortfield, "sortorder": sortorder}
            filters: dict[str, Any] = {}
            shape: dict[str, Any] = {"output": output}
            if eventids:
                filters["eventids"] = eventids
            if groupids:
                filters["groupids"] = groupids
            if hostids:
                filters["hostids"] = hostids
            if objectids:
                filters["objectids"] = objectids
            if time_from:
                filters["time_from"] = time_from
            if time_till:
                filters["time_till"] = time_till
            if recent:
                filters["recent"] = recent
            if severities:
                filters["severities"] = [int(s) for s in severities]
            _search = dict(search) if search is not None else {}
            if name_contains is not None:
                _search["name"] = name_contains
            if _search:
                filters["search"] = _search
            if acknowledged is not None:
                filters["acknowledged"] = acknowledged
            if suppressed is not None:
                filters["suppressed"] = suppressed

            async with ZabbixClient(config) as api:
                if count_output:
                    return {"total": await fetch_total(api.problem, filters)}

                rows, total = await fetch_page(
                    api.problem,
                    filters=filters,
                    shape=shape,
                    sort=sort,
                    id_field="eventid",
                    limit=limit,
                    offset=offset,
                )
                return {
                    "problems": rows,
                    "count": len(rows),
                    "total": total,
                    "limit": limit,
                    "offset": offset,
                    "has_more": offset + len(rows) < total,
                }
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
        ctx: Context,
        eventids: Annotated[list[str] | None, Field(default=None)] = None,
        groupids: Annotated[list[str] | None, Field(default=None)] = None,
        hostids: Annotated[list[str] | None, Field(default=None)] = None,
        objectids: Annotated[list[str] | None, Field(default=None)] = None,
        time_from: Annotated[int | None, Field(default=None)] = None,
        time_till: Annotated[int | None, Field(default=None)] = None,
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
        acknowledged: Annotated[
            bool | None,
            Field(
                default=None,
                description="If false, return only unacknowledged events. If true, return only acknowledged events.",
            ),
        ] = None,
        suppressed: Annotated[
            bool | None,
            Field(
                default=None,
                description="If false, return only unsuppressed events. If true, return only suppressed events.",
            ),
        ] = None,
        select_hosts: Annotated[
            bool,
            Field(
                default=False,
                description="If true, include the hosts each event belongs to in the response (selectHosts=extend).",
            ),
        ] = False,
        select_related_object: Annotated[
            bool,
            Field(
                default=False,
                description="If true, include the related object (e.g., trigger) in the response (selectRelatedObject=extend).",
            ),
        ] = False,
        select_tags: Annotated[
            bool,
            Field(
                default=False,
                description="If true, include the tags for each event in the response (selectTags=extend).",
            ),
        ] = False,
        sortfield: Annotated[
            str,
            Field(
                default="eventid",
                description="Field to sort by. A deterministic sort is required for paging to be consistent.",
            ),
        ] = "eventid",
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
            limit: Maximum number of results to return (default 100). Set higher for more results.
            offset: Number of matching records to skip, for paging.
            acknowledged: False = unacknowledged only, True = acknowledged only, None = all.
            suppressed: False = unsuppressed only, True = suppressed only, None = all.
            select_hosts: If true, include the hosts each event belongs to.
            select_related_object: If true, include the related object (like trigger) that generated the event.
            select_tags: If true, include the tags for each event.

        Returns:
            dict: Contains 'events' list with event objects, 'count' of returned events,
                  'total' matching records, the applied 'limit' and 'offset', and
                  'has_more' indicating whether further pages exist.
                  Each event includes:
                  - eventid: Unique event ID
                  - objectid: Trigger ID that generated the event
                  - clock: Unix timestamp when event occurred
                  - value: 0=normal, 1=problem
                  - acknowledged: 0=not acknowledged, 1=acknowledged

        Note: Use event_acknowledge to mark events as seen by operations team.
        """
        try:
            await ctx.info("Retrieving events...")
            # Sorting is kept out of 'filters' because Zabbix rejects
            # countOutput combined with sortfield.
            sort: dict[str, Any] = {"sortfield": sortfield, "sortorder": sortorder}
            filters: dict[str, Any] = {}
            shape: dict[str, Any] = {"output": output}
            if eventids:
                filters["eventids"] = eventids
            if groupids:
                filters["groupids"] = groupids
            if hostids:
                filters["hostids"] = hostids
            if objectids:
                filters["objectids"] = objectids
            if time_from:
                filters["time_from"] = time_from
            if time_till:
                filters["time_till"] = time_till
            if acknowledged is not None:
                filters["acknowledged"] = acknowledged
            if suppressed is not None:
                filters["suppressed"] = suppressed
            if select_hosts:
                shape["selectHosts"] = "extend"
            if select_related_object:
                shape["selectRelatedObject"] = "extend"
            if select_tags:
                shape["selectTags"] = "extend"

            async with ZabbixClient(config) as api:
                if count_output:
                    return {"total": await fetch_total(api.event, filters)}

                rows, total = await fetch_page(
                    api.event,
                    filters=filters,
                    shape=shape,
                    sort=sort,
                    id_field="eventid",
                    limit=limit,
                    offset=offset,
                )
                return {
                    "events": rows,
                    "count": len(rows),
                    "total": total,
                    "limit": limit,
                    "offset": offset,
                    "has_more": offset + len(rows) < total,
                }
        except Exception as e:
            await ctx.error(f"Error retrieving events: {e!s}")
            return {"error": str(e)}

    @mcp.tool(
        tags={"zabbix", "event"},
        annotations={
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
        },
    )
    async def event_acknowledge(
        ctx: Context,
        eventids: Annotated[list[str], Field(description="Event IDs to acknowledge.")],
        action: Annotated[
            int,
            Field(
                default=2,
                description="Bitmask: 1=close problem, 2=acknowledge, 4=add message, 8=change severity, 16=unacknowledge, 32=suppress, 64=unsuppress.",
            ),
        ] = 2,
        message: Annotated[str | None, Field(default=None)] = None,
    ) -> dict:
        """
        Acknowledge events in Zabbix.

        Mark events (problems/alerts) as acknowledged to show that operations staff are aware
        of and working on the issue. Acknowledged events can also be closed if resolved.

        Args:
            eventids: List of event IDs to acknowledge. Find them with event_get.
            action: Bitmask of operations to apply. Sum the flags to combine them:
                   - 1 = Close the problem (only if the trigger allows manual close)
                   - 2 = Acknowledge the event (default, most common)
                   - 4 = Add message to event
                   - 8 = Change severity
                   - 16 = Unacknowledge the event
                   - 32 = Suppress the event
                   - 64 = Unsuppress the event
                   Default is 2 (acknowledge). Example: 6 acknowledges and adds a message.
            message: Message to add to the event. Zabbix requires the 'add message' flag (4)
                     to be included in 'action' for the message to be accepted.

        Returns:
            dict: Contains 'success' flag and may include event IDs that were successfully acknowledged.

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
