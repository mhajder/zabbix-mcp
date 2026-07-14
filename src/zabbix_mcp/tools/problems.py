"""
Zabbix MCP Server Problems Tools
"""

from typing import Annotated
from typing import Any

from fastmcp import Context
from pydantic import Field

from zabbix_mcp.models import ZabbixConfig
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
                description="Number of results to skip (for pagination). Requires sortfield to be set.",
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
            offset: Number of results to skip for pagination. Use with sortfield.
            acknowledged: False = unacknowledged only, True = acknowledged only, None = all.
            suppressed: False = unsuppressed only, True = suppressed only, None = all.

        Returns:
            dict: Contains 'problems' list with problem objects, 'count' of results returned,
                  and pagination metadata ('limit', 'offset').
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
            params: dict[str, Any] = {"output": output}
            if sortfield:
                params["sortfield"] = sortfield
            if sortorder:
                params["sortorder"] = sortorder
            if count_output:
                params["countOutput"] = True
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
                params["severities"] = [int(s) for s in severities]
            _search = dict(search) if search is not None else {}
            if name_contains is not None:
                _search["name"] = name_contains
            if _search:
                params["search"] = _search
            params["limit"] = limit
            if offset > 0:
                params["offset"] = offset
            if acknowledged is not None:
                params["acknowledged"] = acknowledged
            if suppressed is not None:
                params["suppressed"] = suppressed

            async with ZabbixClient(config) as api:
                result = await api.problem.get(**params)
                return {
                    "problems": result,
                    "count": int(result) if count_output else len(result),
                    "limit": limit,
                    "offset": offset,
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
                description="Number of results to skip (for pagination). Requires sortfield to be set.",
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
            offset: Number of results to skip for pagination. Use with sortfield.
            acknowledged: False = unacknowledged only, True = acknowledged only, None = all.
            suppressed: False = unsuppressed only, True = suppressed only, None = all.
            select_hosts: If true, include the hosts each event belongs to.
            select_related_object: If true, include the related object (like trigger) that generated the event.
            select_tags: If true, include the tags for each event.

        Returns:
            dict: Contains 'events' list with event objects, 'count' of returned events,
                  and pagination metadata ('limit', 'offset').
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
            params: dict[str, Any] = {"output": output}
            if sortfield:
                params["sortfield"] = sortfield
            if sortorder:
                params["sortorder"] = sortorder
            if count_output:
                params["countOutput"] = True
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
            params["limit"] = limit
            if offset > 0:
                params["offset"] = offset
            if acknowledged is not None:
                params["acknowledged"] = acknowledged
            if suppressed is not None:
                params["suppressed"] = suppressed
            if select_hosts:
                params["selectHosts"] = "extend"
            if select_related_object:
                params["selectRelatedObject"] = "extend"
            if select_tags:
                params["selectTags"] = "extend"

            async with ZabbixClient(config) as api:
                result = await api.event.get(**params)
                return {
                    "events": result,
                    "count": int(result) if count_output else len(result),
                    "limit": limit,
                    "offset": offset,
                }
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
        ctx: Context,
        eventids: Annotated[list[str], Field(description="Event IDs to acknowledge.")],
        action: Annotated[
            int,
            Field(default=1, description="Action: 1=ack, 2=close, 4=add message, etc."),
        ] = 1,
        message: Annotated[str | None, Field(default=None)] = None,
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
