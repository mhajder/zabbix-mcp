"""
Zabbix MCP Server Mediatypes Tools
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


def register_mediatypes_tools(mcp, config: ZabbixConfig):
    """Register Zabbix mediatypes tools with the MCP server"""

    @mcp.tool(
        tags={"zabbix", "mediatype", "read-only"},
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
        },
    )
    async def mediatype_get(
        ctx: Context,
        mediatypeids: Annotated[list[str] | None, Field(default=None)] = None,
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
                description="Number of matching records to skip. Use with 'limit' to page through results; check 'has_more' and 'total' in the response.",
                ge=0,
            ),
        ] = 0,
        sortfield: Annotated[
            str,
            Field(
                default="mediatypeid",
                description="Field to sort by. A deterministic sort is required for paging to be consistent.",
            ),
        ] = "mediatypeid",
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
        Get media types from Zabbix.

        Media types define communication channels for sending notifications (email, SMS, webhooks, etc.).
        Actions use media types to deliver alerts to users and integrations.

        Args:
            mediatypeids: List of media type IDs to get. If empty, returns all media types.
            search: Dictionary with search criteria like {'name': 'Email'}. Zabbix 5.4
                    renamed the media type 'description' field to 'name'.
            filter_params: Additional filter parameters for advanced filtering.
            limit: Maximum number of results to return (default 100). Set higher for more results.
            offset: Number of matching records to skip, for paging.

        Returns:
            dict: Contains 'mediatypes' list with media type objects, 'count' of returned types,
                  'total' matching records, the applied 'limit' and 'offset', and
                  'has_more' indicating whether further pages exist.
                  Each media type includes:
                  - mediatypeid: Unique media type ID
                  - type: Type code (0=email, 1=Exec script, 2=SMS, 3=Webhook, etc.)
                  - name: Media type name/description

        Note: Use with actions to define alert routing. Configure alert settings in media type configuration.
        """
        try:
            await ctx.info("Retrieving media types...")
            # Sorting is kept out of 'filters' because Zabbix rejects
            # countOutput combined with sortfield.
            sort: dict[str, Any] = {"sortfield": sortfield, "sortorder": sortorder}
            filters: dict[str, Any] = {}
            shape: dict[str, Any] = {"output": output}
            if mediatypeids:
                filters["mediatypeids"] = mediatypeids
            if search:
                filters["search"] = search
            if filter_params:
                filters["filter"] = filter_params

            async with ZabbixClient(config) as api:
                if count_output:
                    return {"total": await fetch_total(api.mediatype, filters)}

                rows, total = await fetch_page(
                    api.mediatype,
                    filters=filters,
                    shape=shape,
                    sort=sort,
                    id_field="mediatypeid",
                    limit=limit,
                    offset=offset,
                )
                return {
                    "mediatypes": rows,
                    "count": len(rows),
                    "total": total,
                    "limit": limit,
                    "offset": offset,
                    "has_more": offset + len(rows) < total,
                }
        except Exception as e:
            await fail(ctx, "Error retrieving media types", e)

    ##########################
    # Graph Tools
    ##########################
