"""
Zabbix MCP Server Mediatypes Tools
"""

from typing import Annotated
from typing import Any

from fastmcp import Context
from pydantic import Field

from zabbix_mcp.models import ZabbixConfig
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
        Get media types from Zabbix.

        Media types define communication channels for sending notifications (email, SMS, webhooks, etc.).
        Actions use media types to deliver alerts to users and integrations.

        Args:
            mediatypeids: List of media type IDs to get. If empty, returns all media types.
            search: Dictionary with search criteria like {'description': 'email'}.
            filter_params: Additional filter parameters for advanced filtering.
            limit: Maximum number of results to return (default 100). Set higher for more results.
            offset: Number of results to skip for pagination. Use with sortfield.

        Returns:
            dict: Contains 'mediatypes' list with media type objects, 'count' of returned types,
                  and pagination metadata ('limit', 'offset').
                  Each media type includes:
                  - mediatypeid: Unique media type ID
                  - type: Type code (0=email, 1=Exec script, 2=SMS, 3=Webhook, etc.)
                  - name: Media type name/description

        Note: Use with actions to define alert routing. Configure alert settings in media type configuration.
        """
        try:
            await ctx.info("Retrieving media types...")
            params: dict[str, Any] = {"output": output}
            if sortfield:
                params["sortfield"] = sortfield
            if sortorder:
                params["sortorder"] = sortorder
            if count_output:
                params["countOutput"] = True
            if mediatypeids:
                params["mediatypeids"] = mediatypeids
            if search:
                params["search"] = search
            if filter_params:
                params["filter"] = filter_params

            params["limit"] = limit
            if offset > 0:
                params["offset"] = offset

            async with ZabbixClient(config) as api:
                result = await api.mediatype.get(**params)
                return {
                    "mediatypes": result,
                    "count": int(result) if count_output else len(result),
                    "limit": limit,
                    "offset": offset,
                }
        except Exception as e:
            await ctx.error(f"Error retrieving media types: {e!s}")
            return {"error": str(e)}

    ##########################
    # Graph Tools
    ##########################
